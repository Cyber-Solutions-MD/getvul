"""Vulnerability API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from sqlalchemy import distinct, select, func, case
from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.schemas import (
    BulkStatusUpdate,
    DashboardStats,
    VulnerabilityFilter,
    VulnerabilityResponse,
    VulnerabilitySummary,
    VulnerabilityStatusUpdate,
)
from app.vulnerabilities.service import (
    bulk_update_status,
    get_dashboard_stats,
    get_vulnerability,
    list_vulnerabilities,
    update_vulnerability_status,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[VulnerabilitySummary])
async def list_vulns(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
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
):
    """List vulnerabilities with filtering and pagination."""
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
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_vulnerabilities(db, user.tenant_id, filters, pagination)


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
        db, user.tenant_id, filter_id,
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
    from app.vulnerabilities.saved_filters import SavedFilter
    from app.ticketing.models import TicketRule
    from sqlalchemy import select as sel

    sf = (await db.execute(sel(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.tenant_id == user.tenant_id))).scalar_one_or_none()
    if not sf:
        raise HTTPException(404, "Filter not found")

    from app.vulnerabilities.saved_filters import map_filter_to_conditions
    conditions = map_filter_to_conditions(sf.filters)

    rule_name = body.get("name", f"Rule from: {sf.name}")
    action = body.get("action", {"provider": "ASANA", "auto_assign": True, "ticket_mode": "per_host", "max_tickets": 10})
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
):
    """List remediations grouped — each row is a unique remediation with affected host count."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped
    return await get_remediations_grouped(
        db, user.tenant_id, severity=severity, exploit_only=exploit_only,
        kev_only=kev_only, search=search, show_suppressed=show_suppressed,
        page=page, page_size=page_size,
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
    from sqlalchemy import update
    from datetime import datetime, timezone
    from app.assets.risk_score import compute_risk_scores

    # Find affected asset IDs before suppressing
    affected_assets_q = (
        select(func.distinct(Vulnerability.asset_id))
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.asset_id.isnot(None),
        )
    )
    affected_asset_ids = [r[0] for r in (await db.execute(affected_assets_q)).all()]

    # Suppress all vulns with this remediation_id
    now = datetime.now(timezone.utc)
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
    await _audit(db, user, "vuln.suppress", "remediation", remediation_id, {"suppressed": suppressed_count, "assets": len(affected_asset_ids)})

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
    from sqlalchemy import update
    from datetime import datetime, timezone
    from app.assets.risk_score import compute_risk_scores

    now = datetime.now(timezone.utc)
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
        db, user.tenant_id, remediation_id,
        severity=severity, exploit_only=exploit_only, kev_only=kev_only,
    )


@router.get("/hosts/{asset_id}/remediations")
async def remediations_for_host(
    asset_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get remediations for a specific host, grouped by remediation action."""
    # Verify asset belongs to tenant
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
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
        .where(Vulnerability.asset_id == asset_id)
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
