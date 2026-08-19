"""Vulnerability business logic and database queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import Select, asc, case, desc, func, nulls_last, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.audit import AuditLog
from app.exceptions.service import active_exception_subquery, lapsed_exception_seconds
from app.pagination import PaginatedResponse, PaginationParams
from app.tenants.models import Tenant
from app.vulnerabilities.models import RemediationEvent, Vulnerability, VulnerabilityCorrelation
from app.vulnerabilities.schemas import (
    BulkStatusUpdate,
    DashboardStats,
    FacetsResponse,
    SeverityCount,
    SourceCount,
    VulnerabilityByHost,
    VulnerabilityFilter,
    VulnerabilityResponse,
    VulnerabilitySummary,
)
from app.vulnerabilities.sla_tier_service import (
    get_tier_policy,
    resolve_state_for_vuln,
    severity_to_tier,
    tier_for_score,
)

# Phase 11 / T-11-03: only these facet groups are allowed via ?facets=
# CSV. Anything outside this set surfaces as HTTP 400 (not 500) so the
# frontend can show a structured error and not leak an internal stack.
_ALLOWED_FACET_GROUPS: frozenset[str] = frozenset({"severity", "source", "status"})


def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: VulnerabilityFilter) -> Select:
    """Apply filter conditions to a vulnerability query."""
    query = query.where(Vulnerability.tenant_id == tenant_id)
    # Phase 39 / EXC-02 / D-01 / D-15: exclude findings covered by an active
    # (non-expired, non-revoked) exception. This is the single choke point
    # for list_vulnerabilities, list_vulnerabilities_by_host, and
    # get_facets (39-RESEARCH.md Pattern 1) — additive to the legacy
    # SUPPRESSED/FALSE_POSITIVE status filter (D-02), never a replacement.
    query = query.where(~active_exception_subquery(tenant_id, datetime.now(UTC)))

    if filters.severity:
        query = query.where(Vulnerability.severity.in_(filters.severity))
    if filters.source:
        # Phase 35 / SRC-03/SRC-04: filter on the Phase-30 correlation ARRAY
        # (VulnerabilityCorrelation.sources), NOT the per-row
        # Vulnerability.source column — the correlation array is the only
        # place true multi-scanner corroboration can be expressed.
        #
        # AND with <2 selected sources is a documented no-op (Pitfall 1):
        # OR and AND are mathematically identical for a single-element set,
        # so it falls into the OR branch below rather than the exclusive
        # AND branch.
        corr_subq = select(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.sources.contains(filters.source)
            if filters.source_mode == "and" and len(filters.source) >= 2
            else VulnerabilityCorrelation.sources.overlap(filters.source),
        )
        if filters.source_mode == "and" and len(filters.source) >= 2:
            # AND: only rows with a qualifying correlation match — a
            # single-source finding (no correlation row) structurally
            # cannot corroborate, and must be excluded.
            query = query.where(tuple_(Vulnerability.cve_id, Vulnerability.asset_id).in_(corr_subq))
        else:
            # OR (default) / AND-with-<2 no-op: correlation overlap OR
            # direct per-row source match — the direct-source fallback is
            # what lets single-source findings (which have NO correlation
            # row at all) still match the OR filter.
            query = query.where(
                or_(
                    tuple_(Vulnerability.cve_id, Vulnerability.asset_id).in_(corr_subq),
                    Vulnerability.source.in_(filters.source),
                )
            )
    if filters.status:
        query = query.where(Vulnerability.status.in_(filters.status))
    if filters.cve_id:
        query = query.where(Vulnerability.cve_id.ilike(f"%{filters.cve_id}%"))
    if filters.exploit_available is not None:
        query = query.where(Vulnerability.exploit_available == filters.exploit_available)
    if filters.cisa_kev is not None:
        query = query.where(Vulnerability.cisa_kev == filters.cisa_kev)
    if filters.asset_id:
        query = query.where(Vulnerability.asset_id == filters.asset_id)
    if filters.search:
        query = query.where(
            or_(
                Vulnerability.cve_id.ilike(f"%{filters.search}%"),
                Vulnerability.affected_product.ilike(f"%{filters.search}%"),
                Vulnerability.vulnerability_name.ilike(f"%{filters.search}%"),
            )
        )
    if filters.age_days_min is not None:
        cutoff = datetime.now(UTC) - timedelta(days=filters.age_days_min)
        query = query.where(Vulnerability.first_detected_at <= cutoff)
    if filters.age_days_max is not None:
        cutoff = datetime.now(UTC) - timedelta(days=filters.age_days_max)
        query = query.where(Vulnerability.first_detected_at >= cutoff)

    return query


async def list_vulnerabilities(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
    pagination: PaginationParams,
) -> PaginatedResponse[VulnerabilitySummary]:
    """List vulnerabilities with filters and pagination."""

    # Count query
    count_q = _apply_filters(
        select(func.count(Vulnerability.id)),
        tenant_id,
        filters,
    )
    total = (await db.execute(count_q)).scalar_one()

    # Data query with optional asset join
    data_q = (
        _apply_filters(select(Vulnerability), tenant_id, filters)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .add_columns(Asset.hostname.label("asset_hostname"))
    )

    # Phase 34 / RISK-08: scalar Tenant fetch (mirrors sla_service.py:43),
    # tenant_id-scoped, once per call — read ONLY to branch the "triage" sort
    # below on cutover_risk_exposure_scoring. Default OFF; the flag is never
    # flipped in this environment (34-CONTEXT locked).
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    cutover_enabled = tenant.cutover_risk_exposure_scoring if tenant is not None else False

    # Phase 36 / SLA-01/SLA-02: resolve the tenant's tier policy ONCE per
    # request, then attach a freshly read-time-computed sla_state/sla_due_at
    # to every row below (D-01/D-02 — server-authoritative "live" state;
    # Pitfall 3 — the schema fields only populate if something sets them).
    sla_policy = get_tier_policy(tenant)
    sla_now = datetime.now(UTC)

    # D-T-01: 'triage' sort = KEV desc → CVSS desc → SLA-due asc.
    # nulls_last() so missing CVSS / SLA dates don't bubble to the top.
    # Phase 34 / RISK-08: with the cutover flag ON, the new per-finding
    # risk_exposure_score leads as the PRIMARY key (a superset of the old
    # intent -- it already folds in CVSS/KEV) while keeping the existing 3
    # as tiebreakers; with the flag OFF (default), this branch is
    # byte-identical to pre-Phase-34 behavior.
    if filters.sort == "triage":
        if cutover_enabled:
            data_q = data_q.order_by(
                nulls_last(desc(Vulnerability.risk_exposure_score)),
                desc(Vulnerability.cisa_kev),
                nulls_last(desc(Vulnerability.cvss_v3_score)),
                nulls_last(asc(Vulnerability.sla_due_at)),
            )
        else:
            data_q = data_q.order_by(
                desc(Vulnerability.cisa_kev),
                nulls_last(desc(Vulnerability.cvss_v3_score)),
                nulls_last(asc(Vulnerability.sla_due_at)),
            )
    elif filters.sort == "cve_id":
        # Phase 11 / D-T-01: lexicographic. cve_id is `String(20) NOT NULL`
        # in practice (NULL only on legacy rows that never had a CVE
        # assigned); nulls_last keeps those off the top regardless of order.
        col = Vulnerability.cve_id
        data_q = data_q.order_by(nulls_last(asc(col)) if filters.order == "asc" else nulls_last(desc(col)))
    elif filters.sort == "cvss_v3_score":
        # Phase 11 / D-T-01: numeric. NULL scores must sort last in both
        # directions — a null score is "unknown", not "lowest".
        col = Vulnerability.cvss_v3_score
        data_q = data_q.order_by(nulls_last(asc(col)) if filters.order == "asc" else nulls_last(desc(col)))
    elif filters.sort == "sla_due_at":
        # Phase 11 / D-T-01: datetime. NULL means "no SLA tracked" — same
        # nulls-last rule as CVSS.
        col = Vulnerability.sla_due_at
        data_q = data_q.order_by(nulls_last(asc(col)) if filters.order == "asc" else nulls_last(desc(col)))
    elif filters.sort == "severity":
        # Phase 11 / D-T-01: explicit severity-rank branch lets ?order= flip
        # the direction. Rank ascends with severity (CRITICAL=4 → LOW=1) so
        # ?order=desc puts CRITICAL first — matches the user's mental model
        # of "descending severity = worst first" (T-D-01 sketch language).
        # Rows with an unknown severity get rank 0 so they always trail
        # known severities under desc and lead under asc.
        sev_rank = case(
            (Vulnerability.severity == "CRITICAL", 4),
            (Vulnerability.severity == "HIGH", 3),
            (Vulnerability.severity == "MEDIUM", 2),
            (Vulnerability.severity == "LOW", 1),
            else_=0,
        )
        data_q = data_q.order_by(asc(sev_rank) if filters.order == "asc" else desc(sev_rank))
    else:
        # Existing severity-case ordering — unchanged. Reached when
        # filters.sort is None (default path for legacy callers).
        data_q = data_q.order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 1),
                (Vulnerability.severity == "HIGH", 2),
                (Vulnerability.severity == "MEDIUM", 3),
                (Vulnerability.severity == "LOW", 4),
                else_=5,
            ),
            Vulnerability.last_seen_at.desc(),
        )

    data_q = data_q.offset(pagination.offset).limit(pagination.page_size)
    results = (await db.execute(data_q)).all()

    page_rows = [row[0] if hasattr(row, "__getitem__") else row.Vulnerability for row in results]

    # Phase 35 / SRC-01 / SRC-08: page-scoped batched provenance fetch.
    # Extends risk_exposure_service.py:320-345's bulk-dict-lookup precedent,
    # but PAGE-scoped (not tenant-wide) and carrying the sources ARRAY (not
    # just the count) — exactly ONE extra query per page load, independent
    # of page size, never a per-row correlation lookup (the literal SRC-08
    # anti-pattern).
    page_keys = {(v.cve_id, v.asset_id) for v in page_rows if v.cve_id and v.asset_id}
    corr_by_key: dict[tuple[str, uuid.UUID], VulnerabilityCorrelation] = {}
    if page_keys:
        corr_rows = (
            (
                await db.execute(
                    select(VulnerabilityCorrelation).where(
                        # T-35-01: scope the SECOND (batched) query to the
                        # tenant explicitly too, not just the primary query.
                        VulnerabilityCorrelation.tenant_id == tenant_id,
                        tuple_(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id).in_(page_keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        corr_by_key = {(c.cve_id, c.asset_id): c for c in corr_rows}

    # Phase 39 / D-16: page-scoped batched lapsed-exception lookup (mirrors
    # corr_by_key immediately above) — reuses the SAME page_keys set so the
    # live sla_state/sla_due_at of a recently-resurfaced finding reflects
    # how long it spent under a now-lapsed exception, instead of instantly
    # showing breached.
    lapsed_by_key: dict[tuple[str, uuid.UUID], int] = {}
    if page_keys:
        lapsed_by_key = await lapsed_exception_seconds(db, tenant_id, page_keys, sla_now)

    items = []
    for row in results:
        vuln = row[0] if hasattr(row, "__getitem__") else row.Vulnerability
        hostname = row.asset_hostname if hasattr(row, "asset_hostname") else None
        corr = corr_by_key.get((vuln.cve_id, vuln.asset_id))
        # No correlation row = single source, never unknown (mirrors
        # risk_exposure_service.py:352's corr_by_key.get((...), 1) convention).
        sources = corr.sources if corr and corr.sources else [vuln.source]
        sources_count = corr.sources_count if corr else 1
        excepted_seconds = lapsed_by_key.get((vuln.cve_id, vuln.asset_id), 0)
        sla_due_at, sla_state = resolve_state_for_vuln(vuln, sla_policy, sla_now, excepted_seconds=excepted_seconds)
        items.append(
            VulnerabilitySummary(
                id=vuln.id,
                cve_id=vuln.cve_id,
                severity=vuln.severity,
                source=vuln.source,
                status=vuln.status,
                exploit_available=vuln.exploit_available,
                cisa_kev=vuln.cisa_kev,
                affected_product=vuln.affected_product,
                asset_id=vuln.asset_id,
                asset_hostname=hostname,
                first_detected_at=vuln.first_detected_at,
                last_seen_at=vuln.last_seen_at,
                sources=sources,
                sources_count=sources_count,
                sla_state=sla_state,
                sla_due_at=sla_due_at,
            )
        )

    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_vulnerability(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    vuln_id: uuid.UUID,
) -> VulnerabilityResponse | None:
    """Get a single vulnerability by ID with asset hostname."""
    query = (
        select(Vulnerability)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .add_columns(Asset.hostname.label("asset_hostname"))
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
    )
    result = (await db.execute(query)).first()
    if result is None:
        return None

    vuln = result[0]
    hostname = result.asset_hostname

    # Get correlation count
    corr_count = None
    if vuln.cve_id and vuln.asset_id:
        corr_q = select(VulnerabilityCorrelation.sources_count).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.cve_id == vuln.cve_id,
            VulnerabilityCorrelation.asset_id == vuln.asset_id,
        )
        corr_result = (await db.execute(corr_q)).scalar_one_or_none()
        corr_count = corr_result

    # Phase 36 / SLA-01/SLA-02: same read-time resolution as list_vulnerabilities
    # above — detail view must ALSO carry sla_state/sla_due_at (must_haves).
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_policy = get_tier_policy(tenant)
    sla_now = datetime.now(UTC)
    # Phase 39 / D-16: single-row batched lookup (same lapsed_exception_seconds
    # helper as list_vulnerabilities, called with a 1-key set) — the detail
    # view inherits the identical subtraction so it never disagrees with the
    # list it was drilled into from.
    excepted_seconds = 0
    if vuln.cve_id and vuln.asset_id:
        lapsed_map = await lapsed_exception_seconds(db, tenant_id, {(vuln.cve_id, vuln.asset_id)}, sla_now)
        excepted_seconds = lapsed_map.get((vuln.cve_id, vuln.asset_id), 0)
    sla_due_at, sla_state = resolve_state_for_vuln(vuln, sla_policy, sla_now, excepted_seconds=excepted_seconds)

    return VulnerabilityResponse(
        id=vuln.id,
        tenant_id=vuln.tenant_id,
        cve_id=vuln.cve_id,
        vulnerability_name=vuln.vulnerability_name,
        cvss_v3_score=vuln.cvss_v3_score,
        cvss_v3_vector=vuln.cvss_v3_vector,
        severity=vuln.severity,
        epss_score=vuln.epss_score,
        exploit_available=vuln.exploit_available,
        cisa_kev=vuln.cisa_kev,
        asset_id=vuln.asset_id,
        source=vuln.source,
        source_vuln_id=vuln.source_vuln_id,
        affected_product=vuln.affected_product,
        affected_version=vuln.affected_version,
        fixed_version=vuln.fixed_version,
        remediation_info=vuln.remediation_info,
        status=vuln.status,
        first_detected_at=vuln.first_detected_at,
        last_seen_at=vuln.last_seen_at,
        remediated_at=vuln.remediated_at,
        created_at=vuln.created_at,
        updated_at=vuln.updated_at,
        asset_hostname=hostname,
        correlation_sources_count=corr_count,
        # RISK-05 precursor (Phase 33): read directly off the already-fetched
        # `vuln` ORM object -- NO new query, NO live score_finding call
        # (Pitfall 4). Always reflects exactly what was shadow-computed at
        # the last sync's compute_finding_risk_scores pass.
        risk_exposure_score=vuln.risk_exposure_score,
        risk_exposure_breakdown=vuln.risk_exposure_breakdown,
        risk_model_version=vuln.risk_model_version,
        sla_state=sla_state,
        sla_due_at=sla_due_at,
    )


# ── Phase 36 Plan 04 / SLA-04 / D-09 / Pitfall 6 ─────────────────────────────
#
# mark_vulnerability_remediated is the SINGLE helper every REMEDIATED write
# site (vulnerabilities/service.py x2 below, ticketing/service.py x2,
# ticketing/daily_sync.py x3) must route through. Missing it at any one
# site silently drops that path's MTTR data -- see 36-RESEARCH.md Pitfall 6.

logger = structlog.get_logger()


def _freeze_tier_at_remediation(vuln: Vulnerability) -> str:
    """D-09/D-12/Pitfall 13: freeze the FINAL risk tier at the moment of
    remediation -- never tier-at-detection. Mirrors `resolve_state_for_vuln`'s
    scored/NULL-fallback branch, but returns the literal "not_tracked"
    string (rather than a `None` tier) for a scored-but-below-floor finding
    so its remediation event is still written, just bucketed distinctly
    instead of dropped (specless SLA-04 probe)."""
    score = vuln.risk_exposure_score
    if score is None:
        return severity_to_tier(vuln.severity)
    tier = tier_for_score(score)
    return tier if tier is not None else "not_tracked"


async def mark_vulnerability_remediated(
    db: AsyncSession, vuln: Vulnerability, *, verified_by: str | None = None
) -> RemediationEvent:
    """The single REMEDIATED-transition helper (D-09/Pitfall 6).

    Sets `status="REMEDIATED"` + `remediated_at=now` (matching the
    pre-existing canonical write every call site already performed) AND
    inserts a durable `RemediationEvent` row freezing `tier_at_remediation`
    + `duration_seconds` (first_detected_at -> remediated_at). Callers pass
    an already-loaded, already-tenant-scoped ORM `Vulnerability` (every one
    of the six/seven pre-existing call sites already fetches the row before
    this point) -- this function trusts `vuln.tenant_id`/`vuln.id`, it does
    not re-derive or re-check tenant scope itself.

    `verified_by` (Phase 37 Plan 01, SYNC-02) is an optional caller-supplied
    provenance tag (e.g. "rescan") surfaced only via a structured log line
    for the caller's own audit trail -- it does NOT change `remediated_at`
    (resolved-open-question Q1: rescan is truth per D-03, so the honest MTTR
    clock is the 2nd-clean-scan moment, not a separate fix moment) and does
    NOT branch closure behavior. Omitting it (the default) reproduces the
    exact pre-existing behavior for every regression caller.

    Always resets `vuln.clean_scan_streak` to 0 -- a REMEDIATED row must
    never carry a stale streak forward (e.g. into a later reopen-on-
    recurrence cycle, SYNC-03).

    Does not flush/commit -- matches every pre-existing call site's own
    transaction-boundary convention (none of them commit inline either);
    the caller's existing `await db.commit()` covers this too.
    """
    now = datetime.now(UTC)
    vuln.status = "REMEDIATED"
    vuln.remediated_at = now
    vuln.clean_scan_streak = 0

    tier = _freeze_tier_at_remediation(vuln)
    duration_seconds = int((now - vuln.first_detected_at).total_seconds())

    event = RemediationEvent(
        tenant_id=vuln.tenant_id,
        vulnerability_id=vuln.id,
        tier_at_remediation=tier,
        duration_seconds=duration_seconds,
        first_detected_at=vuln.first_detected_at,
        remediated_at=now,
    )
    db.add(event)

    if verified_by is not None:
        logger.info("vuln_remediated", vuln_id=str(vuln.id), verified_by=verified_by)

    return event


# ── Phase 37 Plan 02 / SYNC-03 / D-04 ────────────────────────────────────────
#
# reopen_vulnerability is the sibling resurrection helper to
# mark_vulnerability_remediated: it undoes a soft REMEDIATED close when a
# later scan re-detects the SAME finding row (routed here from
# connectors/sync.py::_upsert_vulnerability's existing-row branch, which
# already resolves recurrence to the same row via `uq_vuln_dedup`). It never
# deletes the historical RemediationEvent row(s) -- MTTR lineage across a
# close -> recur -> reopen -> re-close cycle stays fully reconstructable.


async def reopen_vulnerability(db: AsyncSession, vuln: Vulnerability) -> bool:
    """Resurrect a REMEDIATED row on recurrence (SYNC-03/D-04).

    Sets `status="OPEN"`, clears `remediated_at`, resets
    `clean_scan_streak=0`, and PRESERVES `first_detected_at` (MTTR lineage).
    Writes a tenant-scoped system-actor `AuditLog`
    (`user_email="system:rescan-reopen"`, `action="vuln.reopen_recurrence"`).
    Any existing `RemediationEvent` row(s) for this vuln are left untouched --
    they are historical and must never be deleted.

    No-op (returns False) when called on a non-REMEDIATED row -- idempotent
    guard so a caller can call this unconditionally on every existing-row
    upsert branch without checking status itself first.

    Does not flush/commit -- matches `mark_vulnerability_remediated`'s own
    transaction-boundary convention; the caller's existing commit covers this.
    """
    if vuln.status != "REMEDIATED":
        return False

    vuln.status = "OPEN"
    vuln.remediated_at = None
    vuln.clean_scan_streak = 0
    # first_detected_at is intentionally left untouched.

    db.add(
        AuditLog(
            tenant_id=vuln.tenant_id,
            user_id=None,
            user_email="system:rescan-reopen",
            action="vuln.reopen_recurrence",
            resource_type="vulnerability",
            resource_id=str(vuln.id),
            details={"source": vuln.source},
            ip_address=None,
            created_at=datetime.now(UTC),
        )
    )

    return True


async def get_mttr_by_tier(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    """SLA-04: tier-grouped MTTR aggregate over the durable `RemediationEvent`
    table -- mirrors `trends.py`'s `get_mttr_trend` shape (group by tier
    instead of week). Does NOT touch the pre-existing flat MTTR queries in
    this file's `get_dashboard_stats`, `dashboard.py`, or `trends.py`
    (Pitfall 11 -- those stay untouched, this is purely additive)."""
    mttr_q = (
        select(
            RemediationEvent.tier_at_remediation,
            func.avg(RemediationEvent.duration_seconds).label("avg_seconds"),
            func.count().label("count"),
        )
        .where(RemediationEvent.tenant_id == tenant_id)
        .group_by(RemediationEvent.tier_at_remediation)
    )
    rows = (await db.execute(mttr_q)).all()
    return [
        {
            "tier_at_remediation": r.tier_at_remediation,
            "avg_seconds": float(r.avg_seconds) if r.avg_seconds is not None else None,
            "count": r.count,
        }
        for r in rows
    ]


async def update_vulnerability_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    vuln_id: uuid.UUID,
    new_status: str,
) -> bool:
    """Update status of a single vulnerability.

    D-09/Pitfall 6: a REMEDIATED transition fetches the row and routes it
    through `mark_vulnerability_remediated` (so the durable MTTR
    remediation-event row is never missed); every other status transition
    keeps the original single-statement bulk `update()`.
    """
    now = datetime.now(UTC)

    if new_status == "REMEDIATED":
        vuln = (
            await db.execute(
                select(Vulnerability).where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if vuln is None:
            return False
        await mark_vulnerability_remediated(db, vuln)
        return True

    result = await db.execute(
        update(Vulnerability)
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
        .values(status=new_status, updated_at=now)
    )
    return result.rowcount > 0


async def bulk_update_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    body: BulkStatusUpdate,
) -> int:
    """Bulk update status for multiple vulnerabilities.

    D-09/Pitfall 6: REMEDIATED fetches every matching row and routes each
    one through `mark_vulnerability_remediated` (fetch-then-mutate per row)
    instead of the single-statement bulk `update()`, so every remediated
    row in the batch gets its own remediation-event row with its own
    frozen tier (which can differ per row).
    """
    now = datetime.now(UTC)

    if body.status == "REMEDIATED":
        vulns = (
            (
                await db.execute(
                    select(Vulnerability).where(
                        Vulnerability.id.in_(body.vulnerability_ids),
                        Vulnerability.tenant_id == tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for vuln in vulns:
            await mark_vulnerability_remediated(db, vuln)
        return len(vulns)

    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.id.in_(body.vulnerability_ids),
            Vulnerability.tenant_id == tenant_id,
        )
        .values(status=body.status, updated_at=now)
    )
    return result.rowcount


# ── Phase 11 / D-F-02: contextual facet counts ──


async def get_facets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
    groups: list[str],
) -> FacetsResponse:
    """Per-group facets contextual to all OTHER applied filters (Pitfall 1).

    For each group in ``groups``: run a query that re-applies every filter
    EXCEPT that group's filter (so the chip-bar can show alternative values
    a user could switch to), then ``GROUP BY`` that column. One query per
    group → at most 3 round trips. Each query is a single ``count(*) GROUP
    BY <indexed column>`` so the planner picks an index scan and the latency
    floor is <50ms / facet on typical tenants.

    Args:
        db: open async session — caller's tenant_id is enforced via the
            ``_apply_filters`` ``tenant_id == :t`` clause; this function
            does NOT re-derive it and trusts the parameter.
        tenant_id: the row's owning tenant (T-11-04 IDOR boundary).
        filters: every filter applied to the list query, including any
            group-specific filters that will be temporarily masked.
        groups: subset of ``{"severity", "source", "status"}``. Anything
            outside this set surfaces as HTTP 400 — the router validates
            again, but we double-check here so callers that bypass the
            router (e.g. internal jobs) also get a clean error.
    """
    bad = [g for g in groups if g not in _ALLOWED_FACET_GROUPS]
    if bad:
        # T-11-03: 400, not 500. Detail names the bad facet so the
        # frontend can surface a useful error.
        raise HTTPException(400, f"Unknown facet group(s): {','.join(bad)}")

    out = FacetsResponse()

    if "severity" in groups:
        # Pitfall 1: drop the severity filter when computing severity facets
        # so the chip-bar can show "CRITICAL (5) HIGH (12)" even when the
        # user has CRITICAL selected.
        f_no_sev = filters.model_copy(update={"severity": None})
        sev_q = _apply_filters(
            select(Vulnerability.severity, func.count(Vulnerability.id)),
            tenant_id,
            f_no_sev,
        ).group_by(Vulnerability.severity)
        sev_rows = (await db.execute(sev_q)).all()
        out.severity = {s: c for s, c in sev_rows}

    if "source" in groups:
        f_no_src = filters.model_copy(update={"source": None})
        src_q = _apply_filters(
            select(Vulnerability.source, func.count(Vulnerability.id)),
            tenant_id,
            f_no_src,
        ).group_by(Vulnerability.source)
        src_rows = (await db.execute(src_q)).all()
        out.source = {s: c for s, c in src_rows}

    if "status" in groups:
        f_no_status = filters.model_copy(update={"status": None})
        status_q = _apply_filters(
            select(Vulnerability.status, func.count(Vulnerability.id)),
            tenant_id,
            f_no_status,
        ).group_by(Vulnerability.status)
        status_rows = (await db.execute(status_q)).all()
        out.status = {s: c for s, c in status_rows}

    return out


# ── Phase 11 / D-V-01: by-host grouped list view ──


async def list_vulnerabilities_by_host(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
    pagination: PaginationParams,
) -> PaginatedResponse[VulnerabilityByHost]:
    """Group vulns by host with denormalized severity counts (D-V-01).

    The list page's "by-host" toggle shows one row per asset, with the
    severity-breakdown chips inline. Pagination is on HOST rows, not vuln
    rows, so a tenant with 10k vulns on 500 hosts paginates 500 rows (not
    10k). Critical for the page's responsiveness — a chip-filter that
    narrows from 10k → 8k vulns must NOT change the host-row count in a
    way that doesn't reflect actual host coverage.

    Tenant scope (T-11-04 / IDOR): ``_apply_filters`` adds the
    ``Vulnerability.tenant_id == :t`` predicate to the subquery, so the
    outer ``GROUP BY Asset.hostname, Asset.id`` only sees rows from this
    tenant. Hosts in other tenants are invisible.
    """
    # Build the filtered, tenant-scoped row source. We label the Asset
    # columns with names that do NOT collide with Vulnerability columns
    # (`asset_id` is already a Vulnerability column; we rename Asset.id to
    # `host_asset_id` and Asset.hostname to `host_hostname` to keep the
    # subquery's column names unambiguous — SQLAlchemy refuses to auto-
    # disambiguate labels in subqueries used by GROUP BY downstream).
    filtered = (
        _apply_filters(select(Vulnerability), tenant_id, filters)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .add_columns(
            Asset.id.label("host_asset_id"),
            Asset.hostname.label("host_hostname"),
        )
        .subquery()
    )

    grouped_q = (
        select(
            filtered.c.host_asset_id.label("asset_id"),
            filtered.c.host_hostname.label("host"),
            func.count(filtered.c.id).label("vuln_count"),
            func.count(case((filtered.c.severity == "CRITICAL", 1))).label("critical_count"),
            func.count(case((filtered.c.severity == "HIGH", 1))).label("high_count"),
            func.count(case((filtered.c.severity == "MEDIUM", 1))).label("medium_count"),
            func.count(case((filtered.c.severity == "LOW", 1))).label("low_count"),
            func.max(filtered.c.cvss_v3_score).label("top_cvss"),
        )
        .group_by(filtered.c.host_asset_id, filtered.c.host_hostname)
        # Ordering: CRITICAL count desc so the most-at-risk hosts surface
        # first; ties broken by total vuln_count desc.
        .order_by(
            func.count(case((filtered.c.severity == "CRITICAL", 1))).desc(),
            func.count(filtered.c.id).desc(),
        )
    )

    # Count distinct hosts for pagination total (NOT vuln rows).
    count_q = select(func.count()).select_from(grouped_q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    paged_q = grouped_q.offset(pagination.offset).limit(pagination.page_size)
    rows = (await db.execute(paged_q)).all()

    items = [
        VulnerabilityByHost(
            asset_id=row.asset_id,
            host=row.host,
            vuln_count=row.vuln_count,
            critical_count=row.critical_count,
            high_count=row.high_count,
            medium_count=row.medium_count,
            low_count=row.low_count,
            top_cvss=row.top_cvss,
        )
        for row in rows
    ]
    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_dashboard_stats(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> DashboardStats:
    """Compute dashboard statistics."""

    # Total and open counts
    total_q = select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == tenant_id)
    total = (await db.execute(total_q)).scalar_one()

    open_q = total_q.where(Vulnerability.status == "OPEN")
    open_count = (await db.execute(open_q)).scalar_one()

    # By severity
    sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id)
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()
    by_severity = [SeverityCount(severity=r[0], count=r[1]) for r in sev_rows]

    # By source
    src_q = (
        select(Vulnerability.source, func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id)
        .group_by(Vulnerability.source)
    )
    src_rows = (await db.execute(src_q)).all()
    by_source = [SourceCount(source=r[0], count=r[1]) for r in src_rows]

    # Exploitable
    exploit_q = select(func.count(Vulnerability.id)).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.exploit_available.is_(True),
    )
    exploitable = (await db.execute(exploit_q)).scalar_one()

    # CISA KEV
    kev_q = select(func.count(Vulnerability.id)).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.cisa_kev.is_(True),
    )
    kev_count = (await db.execute(kev_q)).scalar_one()

    # Correlated CVEs (confirmed by 2+ sources)
    corr_q = select(func.count(VulnerabilityCorrelation.id)).where(
        VulnerabilityCorrelation.tenant_id == tenant_id,
        VulnerabilityCorrelation.sources_count >= 2,
    )
    correlated = (await db.execute(corr_q)).scalar_one()

    # MTTR (mean time to remediate) — for vulns remediated in last 90 days
    mttr_q = select(
        func.avg(func.extract("epoch", Vulnerability.remediated_at - Vulnerability.first_detected_at) / 86400)
    ).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status == "REMEDIATED",
        Vulnerability.remediated_at >= datetime.now(UTC) - timedelta(days=90),
    )
    mttr = (await db.execute(mttr_q)).scalar_one()

    # ── Phase 10 / Plan 01 additive fields ──
    # Computed in dashboard.py for isolation; every helper is tenant-scoped.
    from app.vulnerabilities.dashboard import (
        compute_dashboard_tiles_v10,
        compute_nav_counts_v10,
        compute_top_vuln_v10,
        detect_onboarding_state,
    )

    dashboard_tiles = await compute_dashboard_tiles_v10(db, tenant_id)
    top_vuln = await compute_top_vuln_v10(db, tenant_id)
    nav_counts = await compute_nav_counts_v10(db, tenant_id)
    onboarding_state = await detect_onboarding_state(db, tenant_id)

    return DashboardStats(
        total_vulnerabilities=total,
        open_vulnerabilities=open_count,
        by_severity=by_severity,
        by_source=by_source,
        exploitable_count=exploitable,
        cisa_kev_count=kev_count,
        correlated_cves=correlated,
        # WR-03: 0.0-day MTTR is a valid value (detected + remediated same day);
        # `if mttr:` is falsy for 0.0 and would suppress legitimate data. Only
        # None (no remediated-vuln rows) should map to None on the wire.
        mttr_days=round(float(mttr), 1) if mttr is not None else None,
        dashboard_tiles=dashboard_tiles,
        top_vuln=top_vuln,
        vuln_open_count=nav_counts["vuln_open_count"],
        asset_total_count=nav_counts["asset_total_count"],
        ticket_open_count=nav_counts["ticket_open_count"],
        onboarding_state=onboarding_state,
    )


# ── Phase 26 Plan 07 / D-01: AI batch-scope top-N selector ──────────────────


async def get_top_findings_for_ai_batch(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int,
) -> list[uuid.UUID]:
    """D-01 batch-scope query (AIP-02): the tenant's top-N findings for the
    nightly Message Batch pre-warm (`app.ai.batch.run_batch_prewarm`).

    Ranked by the ASSET-02 per-asset `Asset.risk_score` (PRIMARY sort key when
    the Phase 34 / RISK-08 cutover flag is OFF — the default, and
    byte-identical to pre-Phase-34 behavior): "the existing deterministic
    ASSET-02 score" is a per-asset aggregate computed by `assets/risk_score.py`.
    With `Tenant.cutover_risk_exposure_scoring` ON, the PRIMARY key instead
    becomes the per-finding `Vulnerability.risk_exposure_score` (Phase 33,
    RISK-01/02/06) — a genuine improvement (per-finding vs. asset-level
    ranking) plus a cutover. Either way, a KEV desc -> CVSS desc -> SLA-due
    asc per-finding tiebreak (mirrors this file's own `sort="triage"` idiom
    above) keeps two findings on the SAME asset ordered sensibly. An
    asset-less finding (`asset_id IS NULL`) sorts LAST via `nulls_last` on
    whichever primary key is active, never crowding out a scored finding.

    'OPEN' is interpreted as status IN ('OPEN', 'IN_PROGRESS') — matching
    `risk_score.py::compute_risk_scores()`'s own scoring input (D-01,
    threat T-26-03): a finding an analyst has already started triaging is
    still counted in the asset's `risk_score` sum, so it must not be
    silently excluded from its own priority batch. REMEDIATED / SUPPRESSED
    / FALSE_POSITIVE are excluded.

    No per-asset cap in this cut (RESEARCH Open Question #2, resolved:
    deferred — revisit only if Phase 28 observability shows crowding from
    one asset materializes in practice).
    """
    # Phase 34 / RISK-08: scalar Tenant fetch (mirrors sla_service.py:43 /
    # list_vulnerabilities above), tenant_id-scoped, once per call.
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    cutover_enabled = tenant.cutover_risk_exposure_scoring if tenant is not None else False

    # Asset outerjoin is kept on BOTH paths (simplest; the OFF path needs it
    # for Asset.risk_score and dropping it on the ON path is an optional
    # simplification not taken here, to keep the OFF path's query shape
    # untouched).
    primary_key = (
        nulls_last(desc(Vulnerability.risk_exposure_score)) if cutover_enabled else nulls_last(desc(Asset.risk_score))
    )

    result = await db.execute(
        select(Vulnerability.id)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .order_by(
            primary_key,
            desc(Vulnerability.cisa_kev),
            nulls_last(desc(Vulnerability.cvss_v3_score)),
            nulls_last(asc(Vulnerability.sla_due_at)),
        )
        .limit(limit)
    )
    return [row[0] for row in result.all()]
