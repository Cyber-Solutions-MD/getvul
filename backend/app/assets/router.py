"""Asset API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_admin, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from app.assets.schemas import AssetFilter, AssetResponse, AssetSummary
from app.assets.service import get_asset, get_asset_stats, list_assets

router = APIRouter()


@router.get("/stats")
async def asset_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get asset dashboard statistics."""
    return await get_asset_stats(db, user.tenant_id)


@router.get("", response_model=PaginatedResponse[AssetSummary])
async def list_all_assets(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    hostname: str | None = Query(None),
    os_name: str | None = Query(None),
    asset_type: str | None = Query(None),
    cloud_provider: str | None = Query(None),
    source: str | None = Query(None),
    risk_score_min: int | None = Query(None, ge=0, le=100),
    search: str | None = Query(None),
):
    filters = AssetFilter(
        hostname=hostname, os_name=os_name, asset_type=asset_type,
        cloud_provider=cloud_provider, source=source,
        risk_score_min=risk_score_min, search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_assets(db, user.tenant_id, filters, pagination)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_single_asset(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    asset = await get_asset(db, user.tenant_id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/vulnerabilities")
async def get_asset_vulns(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
):
    from app.vulnerabilities.schemas import VulnerabilityFilter
    from app.vulnerabilities.service import list_vulnerabilities
    filters = VulnerabilityFilter(asset_id=asset_id, severity=severity, status=status)
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_vulnerabilities(db, user.tenant_id, filters, pagination)


@router.post("/recompute-risk-scores")
async def recompute_risk(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Recompute risk scores for all assets. Requires Admin."""
    from app.assets.risk import recompute_all_risk_scores
    count = await recompute_all_risk_scores(db, user.tenant_id)
    return {"message": f"Recomputed risk scores for {count} assets", "count": count}
