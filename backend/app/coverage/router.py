"""Coverage API routes (Phase 41 Plan 01 -- COV-01 tracer slice; Plan 04
adds POST /assets/{asset_id}/route-to-owner for COV-03):

GET /blind-spots (require_viewer) -- the authoritative-inventory devices
that no scanner has ever touched (D-01/D-02), computed live on every read
(D-10, no new table/migration).

`_get_asset_or_404` is defined here now, ahead of its first caller, so
Plan 04's route-to-owner endpoint can import it directly rather than
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
from app.audit import audit
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.coverage.schemas import BlindSpotAssetListResponse, CoverageSummaryResponse, RouteToOwnerResponse
from app.coverage.service import DEFAULT_PAGE_SIZE
from app.coverage.service import get_coverage_summary as _get_coverage_summary
from app.coverage.service import list_blind_spot_assets as _list_blind_spot_assets
from app.coverage.service import route_to_owner as _route_to_owner
from app.dependencies import DBSession
from app.tenants.models import Tenant

router = APIRouter()


async def _get_asset_or_404(db: DBSession, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    """T-41-02 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant asset_id must 404, never a
    fetch-then-403 (mirrors exceptions/router.py::_get_exception_or_404).
    Defined ahead of its first caller in Plan 01; used by Plan 04's
    route-to-owner endpoint below."""
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


@router.get("/summary", response_model=CoverageSummaryResponse)
async def get_coverage_summary_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CoverageSummaryResponse:
    """COV-02: per-connector coverage % (D-05), staleness (D-06, strict
    >7d), and wire-normalized sync status (Pitfall 3) for every enabled
    scanner connector -- the strip rendered above the blind-spot list.
    Tenant-scoped throughout (T-41-07)."""
    return await _get_coverage_summary(db, user.tenant_id)


@router.post("/assets/{asset_id}/route-to-owner", response_model=RouteToOwnerResponse)
async def route_to_owner_endpoint(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> RouteToOwnerResponse:
    """COV-03: resolve a never-scanned asset's owner and notify them to
    onboard it (D-07, notify-only), falling back to admins + the tenant
    alert channel when no owner resolves (D-09). Analyst-gated (T-41-10,
    asymmetric with the require_viewer GETs above per D-08); the asset
    lookup is tenant-scoped via `_get_asset_or_404` (T-41-11 IDOR -- a
    cross-tenant asset_id 404s, never 403/500). Repeatable by design (no
    state transition, no idempotency guard) -- audit-then-commit so any
    audit failure aborts the write (T-41-12)."""
    asset = await _get_asset_or_404(db, user.tenant_id, asset_id)
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    result = await _route_to_owner(db, tenant, user, asset)
    await audit(db, user, "coverage.route_to_owner", "asset", str(asset.id), dict(result))
    await db.commit()
    return RouteToOwnerResponse(**result)
