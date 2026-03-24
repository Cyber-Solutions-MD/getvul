"""CSPM API routes — misconfigurations."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.cspm.schemas import (
    BulkMisconfigStatusUpdate,
    CSPMDashboardStats,
    MisconfigFilter,
    MisconfigResponse,
    MisconfigStatusUpdate,
    MisconfigSummary,
)
from app.cspm.service import (
    bulk_update_misconfig_status,
    get_cloud_resources,
    get_compliance_dashboard,
    get_cspm_stats,
    get_cspm_trends,
    get_misconfiguration,
    list_misconfigurations,
    update_misconfig_status,
)
from app.dependencies import DBSession
from app.pagination import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get("", response_model=PaginatedResponse[MisconfigSummary])
async def list_findings(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    category: list[str] | None = Query(None),
    cloud_provider: str | None = Query(None),
    resource_type: str | None = Query(None),
    search: str | None = Query(None),
):
    filters = MisconfigFilter(
        severity=severity,
        source=source,
        status=status,
        category=category,
        cloud_provider=cloud_provider,
        resource_type=resource_type,
        search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_misconfigurations(db, user.tenant_id, filters, pagination)


@router.get("/stats", response_model=CSPMDashboardStats)
async def cspm_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    return await get_cspm_stats(db, user.tenant_id)


@router.get("/compliance")
async def compliance_dashboard(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    return await get_compliance_dashboard(db, user.tenant_id)


@router.get("/resources")
async def cloud_resources(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    cloud_provider: str | None = Query(None),
    resource_type: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    return await get_cloud_resources(
        db,
        user.tenant_id,
        cloud_provider=cloud_provider,
        resource_type=resource_type,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/trends")
async def cspm_trends(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    days: int = Query(30, ge=7, le=365),
):
    return await get_cspm_trends(db, user.tenant_id, days=days)


@router.get("/{finding_id}", response_model=MisconfigResponse)
async def get_finding(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    result = await get_misconfiguration(db, user.tenant_id, finding_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return result


@router.patch("/{finding_id}/status")
async def update_status(
    finding_id: uuid.UUID,
    body: MisconfigStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    updated = await update_misconfig_status(db, user.tenant_id, finding_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {"message": "Status updated"}


@router.post("/bulk-status")
async def bulk_status(
    body: BulkMisconfigStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    count = await bulk_update_misconfig_status(db, user.tenant_id, body)
    return {"message": f"Updated {count} findings", "count": count}
