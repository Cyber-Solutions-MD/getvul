"""Compliance API routes (Phase 43 Plan 01 -- RPT-03 tracer slice):

GET /overview -- the per-framework control-status rollup (D-08/D-09/D-13),
computed fresh on every read (no new table/cache), tenant-scoped,
require_viewer-gated. Mirrors `coverage/router.py`'s thin-handler shape
exactly (43-RESEARCH.md's cross-cutting "tenant-scoped require_viewer read
endpoint" pattern).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.compliance.schemas import ComplianceOverviewResponse
from app.compliance.service import get_compliance_overview as _get_compliance_overview
from app.dependencies import DBSession

router = APIRouter()


@router.get("/overview", response_model=ComplianceOverviewResponse)
async def get_compliance_overview_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> ComplianceOverviewResponse:
    """RPT-03: per-framework control-status rows evidenced by posture
    metrics (D-08). Tenant-scoped throughout (T-43-01) -- `user.tenant_id`
    is passed inline into every downstream service call, never a
    fetch-then-filter."""
    return await _get_compliance_overview(db, user.tenant_id)
