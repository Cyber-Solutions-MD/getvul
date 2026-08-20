"""Coverage API routes (Phase 41 Plan 01 -- COV-01 tracer slice; Plan 03
adds POST /assets/{asset_id}/route-to-owner for COV-03):

GET /blind-spots (require_viewer) -- the authoritative-inventory devices
that no scanner has ever touched (D-01/D-02), computed live on every read
(D-10, no new table/migration).

`_get_asset_or_404` is defined here now, ahead of its first caller, so
Plan 03's route-to-owner endpoint can import it directly rather than
duplicating the tenant-scoped-404 shape -- mirrors
`exceptions/router.py::_get_exception_or_404` (T-39-01 IDOR precedent):
tenant scoping belongs IN the WHERE clause, a cross-tenant asset_id must
404, never a fetch-then-403 (T-41-02).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.assets.models import Asset
from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.coverage.schemas import BlindSpotAssetListResponse
from app.coverage.service import DEFAULT_PAGE_SIZE
from app.coverage.service import list_blind_spot_assets as _list_blind_spot_assets
from app.dependencies import DBSession

router = APIRouter()


async def _get_asset_or_404(db: DBSession, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    """T-41-02 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant asset_id must 404, never a
    fetch-then-403 (mirrors exceptions/router.py::_get_exception_or_404).
    Unused by this plan's single GET; exists now so Plan 03's
    route-to-owner endpoint can import it directly."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/blind-spots", response_model=BlindSpotAssetListResponse)
async def list_blind_spot_assets_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> BlindSpotAssetListResponse:
    """COV-01: authoritative (MDM/HR) inventory minus anything a scanner
    has ever touched, computed live from `Asset.seen_by_sources`
    (D-01/D-02/D-10). `has_authoritative_inventory` lets the frontend
    distinguish "no inventory source connected" (D-11) from "fully
    covered, zero blind spots." Tenant-scoped throughout (T-41-01)."""
    return await _list_blind_spot_assets(db, user.tenant_id, page, page_size)
