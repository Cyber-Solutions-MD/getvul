"""Vulnerability API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, distinct, func, select
from sqlalchemy import update as sql_update

from app.assets.models import Asset
from app.auth.rbac import require_admin, require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.exceptions.service import active_exception_subquery
from app.pagination import PaginationParams
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.schemas import (
    BulkStatusUpdate,
    DashboardStats,
    FacetsResponse,
    VulnerabilityFilter,
    VulnerabilityListResponse,
    VulnerabilityResponse,
    VulnerabilityStatusUpdate,
)
from app.vulnerabilities.service import (
    bulk_update_status,
    get_dashboard_stats,
    get_facets,
    get_vulnerability,
    list_vulnerabilities,
    list_vulnerabilities_by_host,
    update_vulnerability_status,
)

router = APIRouter()


@router.get("", response_model=VulnerabilityListResponse)
async def list_vulns(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    limit: int | None = Query(
        None,
        ge=1,
        le=200,
        description="Alias for page_size — Phase 10 frontend Top-5 card uses ?limit=5",
    ),
    severity: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    cve_id: str | None = Query(None),
    exploit_available: bool | None = Query(None),
    cisa_kev: bool | None = Query(None),
    asset_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    age_days_min: int | None = Query(None, ge=0),
    age_days_max: int | None = Query(None, ge=0),
    # T-11-01: pydantic-validated Literal. Unknown sort fields surface as
    # 422 (not 500) before the handler runs.
    sort: Literal[
        "triage",
        "severity",
        "cve_id",
        "cvss_v3_score",
        "sla_due_at",
    ]
    | None = Query(
        None,
        description="Sort field: triage | severity | cve_id | cvss_v3_score | sla_due_at",
    ),
    # T-11-01: explicit direction. Default 'desc' preserves existing severity
    # / triage ordering for callers that pass neither sort= nor order=.
    order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    # Phase 35 / SRC-02/03/04: OR-default vs AND-toggle for the `source`
    # filter, via the correlation ARRAY `&&`/`@>` operators. Literal → 422 on
    # anything else. Must be bound here (not just added to the schema) — this
    # router builds VulnerabilityFilter from explicit Query(...) params, so a
    # field with no matching Query param is silently dropped and never
    # reaches the service.
    source_mode: Literal["or", "and"] = Query(
        "or", description="OR (any selected scanner) vs AND (corroborated by all selected scanners)"
    ),
    # T-11-02 / D-V-01: grouping mode. Unknown values 422 via Literal.
    group: Literal["cve", "host"] = Query(
        "cve",
        description="Group rows by CVE (default) or by host",
    ),
    # T-11-03 / D-F-02: comma-separated facet groups. CSV parsed below;
    # unknown entries surface as HTTP 400 with the bad name in `detail`.
    facets: str | None = Query(
        None,
        description="Comma-separated facet groups: severity,source,status",
        max_length=50,
    ),
):
    """List vulnerabilities with filtering, sorting, grouping, and optional facets.

    Phase 11 / D-F-02 / D-V-01 / D-T-01: a single round-trip returns paged
    rows + optional contextual facet counts + optional by-host grouping. The
    frontend Wave 1+ list page consumes this contract directly (no client-
    side faceting).
    """
    # Parse + validate ?facets= CSV. Unknown entries surface as HTTP 400
    # with the bad name in `detail` — caught here so the frontend chip-bar
    # can show a structured error rather than a generic 500.
    requested_facets: list[str] = []
    if facets:
        requested_facets = [f.strip() for f in facets.split(",") if f.strip()]
        _ALLOWED = {"severity", "source", "status"}  # noqa: N806 — intentional constant-style local
        bad = [f for f in requested_facets if f not in _ALLOWED]
        if bad:
            raise HTTPException(400, f"Unknown facet group(s): {','.join(bad)}")

    filters = VulnerabilityFilter(
        severity=severity,
        source=source,
        status=status,
        cve_id=cve_id,
        exploit_available=exploit_available,
        cisa_kev=cisa_kev,
        asset_id=asset_id,
        search=search,
        age_days_min=age_days_min,
        age_days_max=age_days_max,
        sort=sort,
        order=order,
        group=group,
        source_mode=source_mode,
    )

    # `limit` is the Phase-10-friendly alias; page_size remains the canonical name.
    effective_page_size = limit if limit is not None else page_size
    pagination = PaginationParams(page=page, page_size=effective_page_size)

    # D-V-01: ?group=host returns one row per asset with denormalized
    # severity counts. The page payload type changes — the response_model
    # union accepts either shape.
    if group == "host":
        page_payload = await list_vulnerabilities_by_host(db, user.tenant_id, filters, pagination)
    else:
        page_payload = await list_vulnerabilities(db, user.tenant_id, filters, pagination)

    facet_payload: FacetsResponse | None = None
    if requested_facets:
        facet_payload = await get_facets(db, user.tenant_id, filters, requested_facets)

    return VulnerabilityListResponse(
        items=page_payload.items,
        total=page_payload.total,
        page=page_payload.page,
        page_size=page_payload.page_size,
        total_pages=page_payload.total_pages,
        facets=facet_payload,
    )


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get dashboard statistics for the tenant."""
    return await get_dashboard_stats(db, user.tenant_id)


@router.get("/overview")
async def overview_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get enhanced dashboard overview — top hosts, tickets, connectors."""
    from app.vulnerabilities.dashboard import get_overview_stats

    return await get_overview_stats(db, user.tenant_id)


# ── Trend Analytics ──


@router.get("/trends")
async def trend_analytics(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    days: int = Query(30, ge=7, le=365),
):
    """Get trend data — vuln timeline, MTTR trend, risk score history."""
    from app.vulnerabilities.trends import get_all_trends

    return await get_all_trends(db, user.tenant_id, days)


# ── SLA Tracking ──


@router.get("/sla/metrics")
async def sla_metrics(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get SLA compliance metrics."""
    from app.vulnerabilities.sla_service import get_sla_metrics

    return await get_sla_metrics(db, user.tenant_id)


@router.post("/sla/backfill")
async def sla_backfill(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Backfill SLA due dates for vulns that don't have one."""
    from app.vulnerabilities.sla_service import backfill_sla_due_dates, check_sla_breaches

    result = await backfill_sla_due_dates(db, user.tenant_id)
    breaches = await check_sla_breaches(db, user.tenant_id)
    await db.commit()
    return {**result, **breaches}


@router.post("/sla/recalculate")
async def sla_recalculate(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Recalculate all SLA due dates based on current config."""
    from app.vulnerabilities.sla_service import check_sla_breaches, recalculate_sla_due_dates

    result = await recalculate_sla_due_dates(db, user.tenant_id)
    breaches = await check_sla_breaches(db, user.tenant_id)

    # WR-02: ticket SLA is materialized on the ticket rows (group MIN of the
    # linked vuln sla_due_at), so changing vulnerability.sla_due_at leaves the
    # ticket SLA stale until the next ticket create/sync. Recompute every
    # affected ticket group now so the SLA pill reflects the new due dates
    # immediately. recompute_ticket_sla does NOT commit — we commit below.
    from sqlalchemy import distinct
    from sqlalchemy import select as _select

    from app.ticketing.models import Ticket
    from app.ticketing.service import recompute_ticket_sla

    # Flush so the recomputed vuln sla_due_at values are visible to the
    # MIN aggregate inside recompute_ticket_sla.
    await db.flush()
    ticket_urls = (
        (await db.execute(_select(distinct(Ticket.external_ticket_url)).where(Ticket.tenant_id == user.tenant_id)))
        .scalars()
        .all()
    )
    for ticket_url in ticket_urls:
        await recompute_ticket_sla(db, ticket_url, user.tenant_id)

    from app.audit import audit

    await audit(db, user, "sla.recalculate", "vulnerability", None, {**result, **breaches})
    await db.commit()
    return {**result, **breaches}


# ── MTTR by tier (Phase 36 Plan 04 / SLA-04, D-09) ──


@router.get("/mttr/by-tier")
async def mttr_by_tier(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Tier-grouped MTTR aggregate (avg duration_seconds + count per
    tier_at_remediation), read from the durable `remediation_events` table.

    Admin-gated + tenant-scoped (T-36-mttr-rbac / T-36-mttr-tenant) — feeds
    Phase 42/43 reporting. Does not touch the pre-existing flat MTTR tiles
    on `/stats`/`/trends` (Pitfall 11).
    """
    from app.vulnerabilities.service import get_mttr_by_tier

    return await get_mttr_by_tier(db, user.tenant_id)


# ── Saved Filters (must be before /{vuln_id} to avoid route conflicts) ──


@router.get("/saved-filters")
async def get_saved_filters(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    filter_type: str | None = Query(None),
):
    from app.vulnerabilities.saved_filters import list_saved_filters

    return await list_saved_filters(db, user.tenant_id, filter_type)


@router.post("/saved-filters")
async def create_filter(
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    from app.vulnerabilities.saved_filters import create_saved_filter

    name = body.get("name", "").strip()
    filter_type = body.get("filter_type", "vulnerability")
    filters = body.get("filters", {})
    if not name:
        raise HTTPException(400, "Name is required")
    result = await create_saved_filter(db, user.tenant_id, name, filter_type, filters)
    await db.commit()
    return result


@router.patch("/saved-filters/{filter_id}")
async def update_filter(
    filter_id: uuid.UUID,
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    from app.vulnerabilities.saved_filters import update_saved_filter

    result = await update_saved_filter(
        db,
        user.tenant_id,
        filter_id,
        name=body.get("name"),
        filters=body.get("filters"),
    )
    if result is None:
        raise HTTPException(404, "Filter not found")
    await db.commit()
    return result


@router.delete("/saved-filters/{filter_id}")
async def remove_filter(
    filter_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    from app.vulnerabilities.saved_filters import delete_saved_filter

    deleted = await delete_saved_filter(db, user.tenant_id, filter_id)
    if not deleted:
        raise HTTPException(404, "Filter not found")
    await db.commit()
    return {"message": "Deleted"}


@router.post("/saved-filters/{filter_id}/create-rule")
async def create_rule_from_filter(
    filter_id: uuid.UUID,
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Create a ticket automation rule from a saved filter."""
    from sqlalchemy import select as sel

    from app.ticketing.models import TicketRule
    from app.vulnerabilities.saved_filters import SavedFilter

    sf = (
        await db.execute(sel(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not sf:
        raise HTTPException(404, "Filter not found")

    from app.vulnerabilities.saved_filters import map_filter_to_conditions

    conditions = map_filter_to_conditions(sf.filters)

    rule_name = body.get("name", f"Rule from: {sf.name}")
    action = body.get(
        "action", {"provider": "ASANA", "auto_assign": True, "ticket_mode": "per_host", "max_tickets": 10}
    )
    schedule = body.get("schedule_minutes", 1440)

    rule = TicketRule(
        tenant_id=user.tenant_id,
        name=rule_name,
        is_enabled=True,
        conditions=conditions,
        action=action,
        saved_filter_id=sf.id,
        schedule_minutes=schedule,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    await db.commit()

    return {"message": "Rule created", "rule_id": str(rule.id), "rule_name": rule.name, "conditions": conditions}


@router.get("/{vuln_id}", response_model=VulnerabilityResponse)
async def get_vuln(
    vuln_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get a single vulnerability with full details."""
    vuln = await get_vulnerability(db, user.tenant_id, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return vuln


@router.patch("/{vuln_id}/status")
async def update_status(
    vuln_id: uuid.UUID,
    body: VulnerabilityStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Update the status of a vulnerability. Requires Analyst role."""
    updated = await update_vulnerability_status(db, user.tenant_id, vuln_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    from app.audit import audit

    await audit(db, user, "vuln.status_update", "vulnerability", str(vuln_id), {"status": body.status})
    return {"message": "Status updated", "status": body.status}


# ── Phase 10 / Plan 01: snooze + unsnooze (D-B-04 / D-H-07 / D-H-08) ────────


class SnoozeBody(BaseModel):
    """POST /{vuln_id}/snooze body.

    `until` defaults to now+1h server-side, bounded to <=30 days per V11
    (T-10-02). The frontend Hero CTA `Snooze 1h` POSTs `{}` and lets the
    server fill in the timestamp.
    """

    until: datetime | None = Field(
        default=None,
        description="ISO timestamp; default = now + 1h. Bounded to <=30 days per V11.",
    )


@router.post("/{vuln_id}/snooze")
async def snooze_vuln(
    vuln_id: uuid.UUID,
    body: SnoozeBody,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Snooze a vulnerability — sets status='SUPPRESSED'.

    Default `until` is now+1h. Maximum is now+30 days (V11 bound, T-10-02).
    `WHERE id = vuln_id AND tenant_id = user.tenant_id` is the IDOR
    mitigation (T-10-01, ASVS V4/V8): cross-tenant requests receive 404,
    NOT 403 — rows you can't see don't exist.
    """
    now = datetime.now(UTC)
    until = body.until or (now + timedelta(hours=1))
    # Normalise naive datetimes that the client may have sent without a tz
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)

    if until <= now:
        raise HTTPException(400, "snooze 'until' must be in the future")
    if until > now + timedelta(days=30):
        raise HTTPException(400, "snooze 'until' may not exceed 30 days")

    result = await db.execute(
        sql_update(Vulnerability)
        .where(
            Vulnerability.id == vuln_id,
            Vulnerability.tenant_id == user.tenant_id,  # IDOR filter — ASVS V4/V8
        )
        .values(status="SUPPRESSED", updated_at=now)
    )
    if result.rowcount == 0:
        # IDOR pattern: foreign rows are indistinguishable from missing rows.
        raise HTTPException(404, "Vulnerability not found")

    from app.audit import audit

    await audit(db, user, "vuln.snooze", "vulnerability", str(vuln_id), {"until": until.isoformat()})
    await db.commit()
    return {"message": "Snoozed", "until": until.isoformat()}


@router.post("/{vuln_id}/unsnooze")
async def unsnooze_vuln(
    vuln_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Reverse a snooze — resets status='OPEN'.

    Backs the D-H-08 Undo toast. Idempotent: re-firing on an already-OPEN
    vuln returns 200 because the 8s toast window can dispatch twice if the
    user double-clicks. Separate route from /snooze (rather than re-using
    /snooze with `until=null`) so the `vuln.unsnooze` audit event is
    distinguishable from `vuln.snooze` in auditor reconstructions
    (T-10-04a). Same tenant_id IDOR filter (T-10-04b).
    """
    now = datetime.now(UTC)
    result = await db.execute(
        sql_update(Vulnerability)
        .where(
            Vulnerability.id == vuln_id,
            Vulnerability.tenant_id == user.tenant_id,  # IDOR filter — ASVS V4/V8
        )
        .values(status="OPEN", updated_at=now)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Vulnerability not found")

    from app.audit import audit

    await audit(db, user, "vuln.unsnooze", "vulnerability", str(vuln_id), {})
    await db.commit()
    return {"message": "Unsnoozed"}


@router.post("/cve/{cve_id}/ignore")
async def ignore_cve(
    cve_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    body: dict = None,
):
    """Ignore a CVE — suppress all vulnerability instances of this CVE across all assets."""
    from datetime import datetime

    from sqlalchemy import update as sql_update

    from app.assets.risk_score import compute_risk_scores

    if body is None:
        body = {}
    now = datetime.now(UTC)
    result = await db.execute(
        sql_update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.cve_id == cve_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(status="SUPPRESSED", updated_at=now)
    )
    count = result.rowcount
    await compute_risk_scores(db, user.tenant_id)
    from app.audit import audit

    await audit(
        db, user, "vuln.ignore_cve", "vulnerability", cve_id, {"suppressed": count, "reason": body.get("reason", "")}
    )
    await db.commit()
    return {"message": f"Ignored CVE {cve_id}", "suppressed": count, "cve_id": cve_id}


@router.post("/cve/{cve_id}/unignore")
async def unignore_cve(
    cve_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Unignore a CVE — reopen all suppressed instances of this CVE."""
    from datetime import datetime

    from sqlalchemy import update as sql_update

    from app.assets.risk_score import compute_risk_scores

    now = datetime.now(UTC)
    result = await db.execute(
        sql_update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.cve_id == cve_id,
            Vulnerability.status == "SUPPRESSED",
        )
        .values(status="OPEN", updated_at=now)
    )
    count = result.rowcount
    await compute_risk_scores(db, user.tenant_id)
    from app.audit import audit

    await audit(db, user, "vuln.unignore_cve", "vulnerability", cve_id, {"reopened": count})
    await db.commit()
    return {"message": f"Restored CVE {cve_id}", "reopened": count, "cve_id": cve_id}


@router.post("/bulk-ignore-cve")
async def bulk_ignore_cve(
    body: dict,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Bulk ignore/unignore CVEs."""
    from datetime import datetime

    from sqlalchemy import update as sql_update

    from app.assets.risk_score import compute_risk_scores

    raw_cve_ids = body.get("cve_ids", [])
    action = body.get("action", "ignore")  # "ignore" or "unignore"
    if not raw_cve_ids:
        raise HTTPException(400, "No CVE IDs provided")
    # Validate: only allow string CVE IDs, max 50 chars each, strip whitespace
    cve_ids = [str(c).strip()[:50] for c in raw_cve_ids if isinstance(c, str) and c.strip()]
    if not cve_ids:
        raise HTTPException(400, "No valid CVE IDs provided")

    now = datetime.now(UTC)
    if action == "ignore":
        result = await db.execute(
            sql_update(Vulnerability)
            .where(
                Vulnerability.tenant_id == user.tenant_id,
                Vulnerability.cve_id.in_(cve_ids),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
            .values(status="SUPPRESSED", updated_at=now)
        )
    else:
        result = await db.execute(
            sql_update(Vulnerability)
            .where(
                Vulnerability.tenant_id == user.tenant_id,
                Vulnerability.cve_id.in_(cve_ids),
                Vulnerability.status == "SUPPRESSED",
            )
            .values(status="OPEN", updated_at=now)
        )
    count = result.rowcount
    await compute_risk_scores(db, user.tenant_id)
    from app.audit import audit

    await audit(db, user, f"vuln.bulk_{action}_cve", "vulnerability", None, {"cve_ids": cve_ids, "count": count})
    await db.commit()
    return {"message": f"{count} vulnerabilities {action}d across {len(cve_ids)} CVEs", "count": count}


@router.post("/bulk-status")
async def bulk_status(
    body: BulkStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Bulk update status for multiple vulnerabilities. Requires Analyst role."""
    count = await bulk_update_status(db, user.tenant_id, body)
    if body.status in ("SUPPRESSED", "OPEN"):
        from app.assets.risk_score import compute_risk_scores

        await compute_risk_scores(db, user.tenant_id)
    from app.audit import audit

    await audit(db, user, "vuln.bulk_status", "vulnerability", None, {"status": body.status, "count": count})
    return {"message": f"Updated {count} vulnerabilities", "count": count}


# ── Correlation views ──


@router.get("/correlations/stats")
async def correlation_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get summary of cross-source correlations for the tenant."""
    from app.vulnerabilities.models import VulnerabilityCorrelation

    # Total correlated CVE+asset pairs
    total_q = select(func.count(VulnerabilityCorrelation.id)).where(
        VulnerabilityCorrelation.tenant_id == user.tenant_id,
    )
    total = (await db.execute(total_q)).scalar_one()

    # By confidence level
    conf_q = (
        select(VulnerabilityCorrelation.confidence, func.count(VulnerabilityCorrelation.id))
        .where(VulnerabilityCorrelation.tenant_id == user.tenant_id)
        .group_by(VulnerabilityCorrelation.confidence)
    )
    conf_rows = (await db.execute(conf_q)).all()
    by_confidence = {r[0]: r[1] for r in conf_rows}

    # Unique CVEs correlated
    unique_cves_q = select(func.count(distinct(VulnerabilityCorrelation.cve_id))).where(
        VulnerabilityCorrelation.tenant_id == user.tenant_id,
    )
    unique_cves = (await db.execute(unique_cves_q)).scalar_one()

    return {
        "total_correlations": total,
        "unique_cves": unique_cves,
        "by_confidence": by_confidence,
    }


@router.get("/{vuln_id}/correlation")
async def get_vuln_correlation(
    vuln_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get cross-source correlation info for a specific vulnerability."""
    from app.vulnerabilities.correlation_service import get_correlation_for_vuln

    vuln = await get_vulnerability(db, user.tenant_id, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    if not vuln.cve_id or not vuln.asset_id:
        return {"correlated": False, "reason": "No CVE ID or asset linked"}

    corr = await get_correlation_for_vuln(db, user.tenant_id, vuln.cve_id, vuln.asset_id)
    if corr is None:
        return {"correlated": False, "reason": "Not detected by multiple sources"}

    return {"correlated": True, **corr}


# ── Escalation history (Phase 36 Plan 03 / SLA-03, D-07) ──


@router.get("/{vuln_id}/escalations")
async def get_vuln_escalations(
    vuln_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get the escalation-fire history for a vulnerability (D-07
    user-visible history), tenant-scoped, ordered by fired_at ascending.

    `get_vulnerability` performs the tenant-scope + existence check (IDOR
    pattern: a cross-tenant vuln_id is indistinguishable from a missing
    one, 404 not 403 — matches `get_vuln_correlation` above).
    """
    from app.vulnerabilities.models import SlaEscalationEvent

    vuln = await get_vulnerability(db, user.tenant_id, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    rows = (
        (
            await db.execute(
                select(SlaEscalationEvent)
                .where(
                    SlaEscalationEvent.tenant_id == user.tenant_id,
                    SlaEscalationEvent.vulnerability_id == vuln_id,
                )
                .order_by(SlaEscalationEvent.fired_at)
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": str(row.id),
            "from_state": row.from_state,
            "to_state": row.to_state,
            "channel": row.channel,
            "fired_at": row.fired_at.isoformat(),
            "delivery_status": row.delivery_status,
            "error_message": row.error_message,
        }
        for row in rows
    ]


# ── Remediation views ──


@router.get("/remediations/grouped")
async def remediations_grouped(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    severity: list[str] | None = Query(None),
    exploit_only: bool = Query(False),
    kev_only: bool = Query(False),
    search: str | None = Query(None),
    show_suppressed: str = Query("active", description="active, ignored, or all"),
    device_type: str | None = Query(None, description="Filter by asset type: SERVER, WORKSTATION, OTHER"),
):
    """List remediations grouped — each row is a unique remediation with affected host count."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped

    return await get_remediations_grouped(
        db,
        user.tenant_id,
        severity=severity,
        exploit_only=exploit_only,
        kev_only=kev_only,
        search=search,
        show_suppressed=show_suppressed,
        page=page,
        page_size=page_size,
        device_category=device_type,
    )


@router.post("/remediations/{remediation_id}/suppress")
async def suppress_remediation(
    remediation_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Suppress all vulnerabilities linked to a remediation.

    Marks all OPEN/IN_PROGRESS vulns with this remediation_id as SUPPRESSED,
    then recomputes risk scores for affected assets.
    """
    from datetime import datetime

    from sqlalchemy import update

    from app.assets.risk_score import compute_risk_scores

    # Find affected asset IDs before suppressing
    affected_assets_q = select(func.distinct(Vulnerability.asset_id)).where(
        Vulnerability.tenant_id == user.tenant_id,
        Vulnerability.remediation_id == remediation_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        Vulnerability.asset_id.isnot(None),
    )
    affected_asset_ids = [r[0] for r in (await db.execute(affected_assets_q)).all()]

    # Suppress all vulns with this remediation_id
    now = datetime.now(UTC)
    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(status="SUPPRESSED", updated_at=now)
    )
    suppressed_count = result.rowcount

    # Recompute risk scores for affected assets
    risk_stats = await compute_risk_scores(db, user.tenant_id)

    from app.audit import audit as _audit

    await _audit(
        db,
        user,
        "vuln.suppress",
        "remediation",
        remediation_id,
        {"suppressed": suppressed_count, "assets": len(affected_asset_ids)},
    )

    await db.commit()

    return {
        "message": f"Suppressed {suppressed_count} vulnerabilities for remediation {remediation_id}",
        "suppressed": suppressed_count,
        "affected_assets": len(affected_asset_ids),
        "risk_scores_updated": risk_stats.get("assets_updated", 0),
    }


@router.post("/remediations/{remediation_id}/unsuppress")
async def unsuppress_remediation(
    remediation_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Unsuppress all vulnerabilities linked to a remediation (reopen them)."""
    from datetime import datetime

    from sqlalchemy import update

    from app.assets.risk_score import compute_risk_scores

    now = datetime.now(UTC)
    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status == "SUPPRESSED",
        )
        .values(status="OPEN", updated_at=now)
    )
    reopened_count = result.rowcount

    risk_stats = await compute_risk_scores(db, user.tenant_id)

    from app.audit import audit as _audit

    await _audit(db, user, "vuln.unsuppress", "remediation", remediation_id, {"reopened": reopened_count})

    await db.commit()

    return {
        "message": f"Reopened {reopened_count} vulnerabilities",
        "reopened": reopened_count,
        "risk_scores_updated": risk_stats.get("assets_updated", 0),
    }


@router.get("/remediations/{remediation_id}/hosts")
async def hosts_for_remediation(
    remediation_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    severity: list[str] | None = Query(None),
    exploit_only: bool = Query(False),
    kev_only: bool = Query(False),
):
    """Get all hosts affected by a specific remediation, with filters."""
    from app.vulnerabilities.remediation_service import get_hosts_for_remediation

    return await get_hosts_for_remediation(
        db,
        user.tenant_id,
        remediation_id,
        severity=severity,
        exploit_only=exploit_only,
        kev_only=kev_only,
    )


@router.get("/hosts/{asset_id}/remediations")
async def remediations_for_host(
    asset_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get remediations for a specific host, grouped by remediation action."""
    # Verify asset belongs to tenant
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    # Group vulns by remediation_action + product
    query = (
        select(
            Vulnerability.remediation_action,
            Vulnerability.affected_product,
            func.count().label("vuln_count"),
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    (Vulnerability.severity == "LOW", 1),
                    else_=0,
                )
            ).label("max_sev_rank"),
        )
        .where(
            Vulnerability.asset_id == asset_id,
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            # EXC-02/D-15 (Phase 39 Consumer 11 / Pitfall 5): this endpoint
            # is a hand-rolled ad hoc query that bypasses _base_open_vulns
            # entirely -- it needs its own exclusion predicate.
            ~active_exception_subquery(user.tenant_id, datetime.now(UTC)),
        )
        .group_by(Vulnerability.remediation_action, Vulnerability.affected_product)
        .order_by(
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    (Vulnerability.severity == "LOW", 1),
                    else_=0,
                )
            ).desc(),
            func.count().desc(),
        )
    )

    result = await db.execute(query)
    rows = result.fetchall()

    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "UNKNOWN"}

    return [
        {
            "remediation_action": row.remediation_action or "No remediation available",
            "product": row.affected_product or "Unknown",
            "max_severity": sev_map.get(row.max_sev_rank, "UNKNOWN"),
            "vuln_count": row.vuln_count,
        }
        for row in rows
    ]
