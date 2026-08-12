"""Phase 34 Plan 03 (RISK-09) — admin router for the threshold diff report,
the per-tenant re-tuning ack, and the gated cutover flag flip.

All three endpoints require `require_role("admin")` (T-34-08). The two
mutating endpoints (`/threshold-ack`, `/enable`) are audited by the service
layer BEFORE `db.commit()` (T-34-09, fail-closed AUDIT-01). `/enable` lets
the service's `HTTPException(409, ...)` propagate on a gate failure — never
a silent reinterpretation (T-34-10). Mirrors
`app/assets/router.py:655-665`'s `require_role("admin")` + local
service-import + thin handler shape.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.schemas import CurrentUser
from app.db.session import get_db

router = APIRouter()


@router.get("/threshold-diff")
async def threshold_diff(
    user: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """RISK-09 pre/post threshold diff report for this tenant's automation
    rules + saved filters. Returns 200 with `{"ready": false, "reason":
    "backfill_incomplete"}` when the historical backfill isn't done yet
    (Pitfall 3) — this is a normal, expected response, not an error."""
    from app.vulnerabilities.risk_cutover_service import compute_threshold_diff

    return await compute_threshold_diff(db, user.tenant_id)


@router.post("/threshold-ack")
async def threshold_ack(
    user: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record an explicit, audited re-tuning acknowledgment for the current
    threshold diff. Raises 409 if the backfill isn't complete (nothing to
    ack yet)."""
    from app.vulnerabilities.risk_cutover_service import record_threshold_ack

    return await record_threshold_ack(db, user)


@router.post("/enable")
async def enable(
    user: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Flip `Tenant.cutover_risk_exposure_scoring` to True. Structurally
    impossible without BOTH gates: backfill complete AND a fresh
    (hash-matching) ack. Raises 409 with a gate-specific detail string on
    failure. NOTE: this endpoint exists and is fixture-tested but is never
    actually called against live data in this environment (34-CONTEXT.md,
    locked)."""
    from app.vulnerabilities.risk_cutover_service import enable_cutover

    return await enable_cutover(db, user)
