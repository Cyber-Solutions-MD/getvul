"""Vulnerability API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from sqlalchemy import select, func, case
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
    return {"message": "Status updated", "status": body.status}


@router.post("/bulk-status")
async def bulk_status(
    body: BulkStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Bulk update status for multiple vulnerabilities. Requires Analyst role."""
    count = await bulk_update_status(db, user.tenant_id, body)
    return {"message": f"Updated {count} vulnerabilities", "count": count}


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
):
    """List remediations grouped — each row is a unique remediation with affected host count."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped
    return await get_remediations_grouped(
        db, user.tenant_id, severity=severity, exploit_only=exploit_only,
        kev_only=kev_only, search=search, page=page, page_size=page_size,
    )


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
