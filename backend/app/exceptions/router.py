"""Exception API routes (Phase 39 Plan 01 -- EXC-01/EXC-02/EXC-03/EXC-04
tracer slice): POST / (grant), GET / (list, runs the Pattern 4 expiry-audit
sweep first), POST /{id}/revoke.

Mirrors `campaigns/router.py`'s shape throughout: `_get_exception_or_404`
tenant-scoped lookup (T-39-01 IDOR -- cross-tenant 404s, never
fetch-then-403), `require_analyst` on writes / `require_viewer` on list
(T-39-02, D-09), and audit-then-commit ordering exactly as `ignore_cve`
(T-39-04 -- any audit failure aborts the whole write since `db.commit()`
never runs).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.assets.risk_score import compute_risk_scores
from app.audit import audit
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.exceptions.models import ExceptionRecord
from app.exceptions.schemas import ExceptionCreate, ExceptionResponse
from app.exceptions.service import grant_exception, list_exceptions, revoke_exception, sweep_expired_audits
from app.tenants.models import User

router = APIRouter()


async def _get_exception_or_404(db: DBSession, tenant_id: uuid.UUID, exception_id: uuid.UUID) -> ExceptionRecord:
    """T-39-01 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant exception_id must 404, never a
    fetch-then-403 (mirrors campaigns/router.py::_get_campaign_or_404)."""
    result = await db.execute(
        select(ExceptionRecord).where(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    return record


async def _to_responses(db: DBSession, records: list[ExceptionRecord]) -> list[ExceptionResponse]:
    """Batches the `approver_display_name` lookup (mirrors the
    `corr_by_key` batched-lookup precedent, `vulnerabilities/service.py:
    217-240`) instead of one query per row."""
    approver_ids = {r.approver_user_id for r in records if r.approver_user_id is not None}
    names: dict[uuid.UUID, str] = {}
    if approver_ids:
        rows = await db.execute(select(User.id, User.display_name, User.email).where(User.id.in_(approver_ids)))
        for user_id, display_name, email in rows.all():
            names[user_id] = display_name or email
    responses = []
    for record in records:
        response = ExceptionResponse.model_validate(record)
        response.approver_display_name = names.get(record.approver_user_id) if record.approver_user_id else None
        responses.append(response)
    return responses


@router.post("", response_model=ExceptionResponse)
async def grant_exception_endpoint(
    body: ExceptionCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> ExceptionResponse:
    """EXC-01: grant a governed exception in one action (D-07 -- recorded
    attribution, no pending->approved state machine). Pitfall 7:
    `compute_risk_scores` only (never `compute_finding_risk_scores`) --
    matches every existing ignore/suppress endpoint's precedent exactly.
    Audit-then-commit, never reversed (T-39-04)."""
    now = datetime.now(UTC)
    record = await grant_exception(db, user.tenant_id, user.id, body, now)

    await compute_risk_scores(db, user.tenant_id)
    await audit(
        db,
        user,
        "exception.grant",
        "exception",
        str(record.id),
        {
            "type": record.type,
            "scope_type": record.scope_type,
            "cve_id": record.cve_id,
            "approver_user_id": str(record.approver_user_id),
            "justification": record.justification,
            "expires_at": record.expires_at.isoformat(),
        },
    )
    await db.commit()
    return (await _to_responses(db, [record]))[0]


@router.get("", response_model=list[ExceptionResponse])
async def list_exceptions_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> list[ExceptionResponse]:
    """EXC-01/EXC-04: runs the Pattern 4 lazy-on-read expiry-audit sweep
    FIRST (idempotent -- a second call writes nothing new for an
    already-swept row), then returns every exception for the caller's
    tenant."""
    now = datetime.now(UTC)
    await sweep_expired_audits(db, user.tenant_id, now)
    records = await list_exceptions(db, user.tenant_id)
    return await _to_responses(db, records)


@router.post("/{exception_id}/revoke", response_model=ExceptionResponse)
async def revoke_exception_endpoint(
    exception_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> ExceptionResponse:
    """D-17: early revocation immediately resurfaces the finding --
    compute-on-read means the join simply stops matching once
    `revoked_at` is set, no separate "unexcept" write needed anywhere
    else. Audited with who/when (EXC-03). WR: idempotent guard -- 409 on
    an already-revoked exception rather than silently overwriting
    `revoked_at`/`revoked_by_user_id` and writing a duplicate audit row
    (mirrors campaigns' `close_campaign` 409-on-already-closed shape)."""
    record = await _get_exception_or_404(db, user.tenant_id, exception_id)
    if record.revoked_at is not None:
        raise HTTPException(409, "Exception is already revoked.")
    now = datetime.now(UTC)
    revoke_exception(record, user.id, now)

    await compute_risk_scores(db, user.tenant_id)
    await audit(db, user, "exception.revoke", "exception", str(record.id), {"revoked_by_user_id": str(user.id)})
    await db.commit()
    return (await _to_responses(db, [record]))[0]
