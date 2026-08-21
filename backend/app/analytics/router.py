"""Analytics API routes (Phase 42 Plan 01 -- TREND-01/03 tracer slice):

GET /overview (require_viewer) -- the tenant-scoped risk-exposure trend
series + detected version boundaries for the selected window, computed live
on every read (D-13, no new table/migration). Mirrors
`app/coverage/router.py`'s thin-handler + RBAC shape exactly -- D-01, this
is also a brand-new top-level module.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.analytics.schemas import AnalyticsOverviewResponse
from app.analytics.service import get_analytics_overview as _get_analytics_overview
from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    days: int = Query(30, ge=7, le=365),
) -> dict[str, Any]:
    """TREND-01/03: tenant-scoped risk-exposure trend + version-boundary
    list for the selected window. D-14 -- viewer+ (any authenticated tenant
    user), matching the existing `GET /trends` RBAC precedent -- no
    mutating endpoint exists in this module. T-42-01 (tenant isolation) and
    T-42-03 (DoS via unbounded window) are mitigated in `service.py`'s
    tenant-scoped query and this route's `days` bound respectively.

    Returns the plain dict `get_analytics_overview` builds; `response_model=`
    above is what actually validates/serializes it against
    `AnalyticsOverviewResponse` at the FastAPI boundary."""
    return await _get_analytics_overview(db, user.tenant_id, days=days)
