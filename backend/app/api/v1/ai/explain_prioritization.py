"""Per-finding 'Prioritization narrative' endpoint (AIP-01, D-02/D-08/D-09).

POST streams a validated, cited narrative explaining the deterministic
ASSET-02 score's drivers via the shared buffer-then-validate-then-replay
engine (`app.ai.explain._run_explain_stream`, reused UNCHANGED from Plan 04/
08) -- gated `require_analyst` (D-17: only Analyst+ may trigger a paid
call). GET is a cheap cache-check with NO model call (D-09) -- gated
`require_viewer`.

The grounding record is resolved via the NEW tenant-scoped
`get_prioritization_context(db, tenant_id, finding_id)` (app.ai.grounding,
Plan 01) -- a foreign-tenant `finding_id` is not resolvable (404, never
cross-tenant data), mirroring `explain_host.py`'s own tenant-scoping exactly
(UUID-keyed single-record shape).

This route mirrors `explain_host.py`, NOT `explain_remediation_guidance.py`:
a prioritization narrative explains the deterministic score's drivers, it
never recommends an action to execute, so there is no destructive-command
risk class here (26-PATTERNS.md "No Analog Found"). Consequently:

1. NO safety-pattern denylist kwarg is passed to `_run_explain_stream()` --
   that optional parameter stays at its None default, exactly as
   `explain_host.py` leaves it.
2. NO pre-generation deterministic refuse predicate exists here (unlike the
   asset-aware remediation-guidance view's own actionable-text check) --
   D-04's factor fields are structured scanner/scoring columns, not free
   text with a generic-placeholder failure mode. The model's own
   `grounded=false` judgment is the sole backstop.

The `queued` GET-response field (D-02's async-batch cache-miss UX seam) is
deliberately NOT added here -- it arrives in Plan 06 once the `AiBatchJob`
registry exists to answer "is this finding queued for tonight's batch".
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.ai.cache import build_cache_key, get_cached, record_hash
from app.ai.explain import _run_explain_stream, get_model_and_budget
from app.ai.grounding import get_prioritization_context
from app.ai.prompt_builder import (
    PRIORITIZATION_ALLOWLIST,
    build_explain_prioritization_prompt,
    prioritization_prompt_version,
)
from app.ai.schemas import ExplainPrioritizationResponse
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.redis_client import get_redis

router = APIRouter()


def _allowlisted_hash_fields(record: Any) -> dict[str, Any]:
    """The SAME allowlisted grounding view
    `build_explain_prioritization_prompt()` sends to the model -- read back
    out of the prompt it builds so the cache-check GET hashes EXACTLY what
    the POST path would (D-18), without a second, independently-maintained
    allowlist and without triggering a model call. Mirrors
    `explain_host.py::_allowlisted_hash_fields`."""
    _system_prompt, user_blocks = build_explain_prioritization_prompt(record)
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    result: dict[str, Any] = json.loads(text[start:end])
    return result


@router.post("/explain-prioritization/{finding_id}")
async def explain_prioritization(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    record = await get_prioritization_context(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    return StreamingResponse(
        _run_explain_stream(
            db,
            tenant_id=user.tenant_id,
            user_email=user.email,
            resource_type="prioritization",
            resource_id=str(finding_id),
            record=record,
            build_prompt=build_explain_prioritization_prompt,
            response_model=ExplainPrioritizationResponse,
            redis_client=redis_client,
            allowed_source_fields=PRIORITIZATION_ALLOWLIST,
            get_prompt_version=prioritization_prompt_version,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/explain-prioritization/{finding_id}")
async def get_explain_prioritization_cache(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> dict[str, Any]:
    record = await get_prioritization_context(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Same resolution `_run_explain_stream` uses internally -- a GET must
    # hash/key against the tenant's CURRENTLY-configured model, never a
    # hardcoded default (mirrors explain_host.py's GET route exactly).
    model, _monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
    allowlisted_fields = _allowlisted_hash_fields(record)
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(
        user.tenant_id, "prioritization", str(finding_id), the_hash, model, prioritization_prompt_version()
    )

    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        # NO `queued` field this plan (Plan 06 adds it once AiBatchJob
        # exists) -- every existing GET route's miss shape is the baseline
        # `{"cached": False}`, exactly as `explain_host.py`'s GET returns.
        return {"cached": False}
    return {"cached": True, **cached}
