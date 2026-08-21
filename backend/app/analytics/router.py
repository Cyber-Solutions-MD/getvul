"""Analytics API routes (Phase 42 Plan 01 -- TREND-01/03 tracer slice; Plan
03 adds group scope + custom date range -- see below):

GET /overview (require_viewer) -- the tenant- OR group-scoped risk-exposure
trend series + detected version boundaries + aging/burndown for the
selected window, computed live on every read (D-13, no new table/migration).
Mirrors `app/coverage/router.py`'s thin-handler + RBAC shape exactly -- D-01,
this is also a brand-new top-level module.

Plan 03 additions:
  - `scope`/`group_id` (D-02): re-scopes every chart to an AssetGroup's
    CURRENT members. `group_id` resolution (T-42-08 IDOR) happens inside
    `service.get_analytics_overview` via `list_members`'s tenant-scoped
    None-on-miss lookup -- this route converts that `None` return into a
    404, mirroring `coverage/router.py::_get_asset_or_404`'s "never a
    fetch-then-403" shape.
  - `from`/`to` (D-03 custom range, aliased because `from` is a Python
    keyword): validated as ISO dates (FastAPI/Pydantic `date` query-param
    parsing, Pitfall 3 -- never string-interpolated), `to >= from`
    required, and the span is capped at `MAX_ANALYTICS_WINDOW_DAYS`
    (T-42-09 DoS guard) -- all enforced HERE, before the service layer is
    ever called, mirroring the existing `/trends` `le=365` idiom.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics.schemas import AnalyticsOverviewResponse
from app.analytics.service import MAX_ANALYTICS_WINDOW_DAYS
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
    scope: str = Query("all", pattern="^(all|group)$"),
    group_id: uuid.UUID | None = Query(None),
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None, alias="to"),
) -> dict[str, Any]:
    """TREND-01/02/03: tenant- OR group-scoped risk-exposure trend +
    version-boundary list + aging/burndown for the selected window. D-14 --
    viewer+ (any authenticated tenant user), matching the existing
    `GET /trends` RBAC precedent -- no mutating endpoint exists in this
    module. T-42-01 (tenant isolation) and T-42-09 (DoS via an unbounded
    window) are mitigated in `service.py`'s tenant-scoped query and this
    route's `days`/span bounds respectively; T-42-08 (IDOR on `group_id`)
    is mitigated by the None->404 conversion below.

    `days` (a preset window, 7-365) and `from`/`to` (an explicit custom
    range) are mutually available -- when both `from` and `to` are
    supplied they take precedence over `days` (validated as a pair: either
    both present or neither; `to` must not precede `from`; the span is
    capped at `MAX_ANALYTICS_WINDOW_DAYS`).

    Returns the plain dict `get_analytics_overview` builds; `response_model=`
    above is what actually validates/serializes it against
    `AnalyticsOverviewResponse` at the FastAPI boundary."""
    if scope == "group" and group_id is None:
        raise HTTPException(status_code=422, detail="group_id is required when scope=group")

    start_param: date | None = None
    end_param: date | None = None
    if from_ is not None or to is not None:
        if from_ is None or to is None:
            raise HTTPException(status_code=422, detail="Both 'from' and 'to' are required for a custom range")
        if to < from_:
            raise HTTPException(status_code=422, detail="'to' must not be before 'from'")
        if (to - from_).days > MAX_ANALYTICS_WINDOW_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"Custom range cannot exceed {MAX_ANALYTICS_WINDOW_DAYS} days",
            )
        start_param, end_param = from_, to

    overview = await _get_analytics_overview(
        db,
        user.tenant_id,
        days=days,
        start=start_param,
        end=end_param,
        scope=scope,
        group_id=group_id,
    )
    if overview is None:
        # T-42-08: `group_id` didn't resolve via `list_members` (nonexistent
        # OR cross-tenant) -- 404, never a fetch-then-403.
        raise HTTPException(status_code=404, detail="Asset group not found")
    return overview
