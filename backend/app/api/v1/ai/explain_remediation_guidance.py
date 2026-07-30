"""Per-finding 'Remediation guidance' endpoint (AIR-01, D-01/D-06/D-10).

POST streams a validated, cited, asset-aware remediation explanation via the
shared buffer-then-validate-then-replay engine
(`app.ai.explain._run_explain_stream`, reused UNCHANGED except for the
Plan 03 Task 1 `dangerous_pattern_check` kwarg) -- gated `require_analyst`
(D-17: only Analyst+ may trigger a paid call). GET is a cheap cache-check
with NO model call (D-09) -- gated `require_viewer`.

The grounding record is resolved via the NEW tenant-scoped
`get_remediation_guidance_context(db, tenant_id, finding_id)` (app.ai.grounding,
Plan 01) -- a foreign-tenant `finding_id` is not resolvable (404, never
cross-tenant data), mirroring `explain_host.py`'s own tenant-scoping exactly
(UUID-keyed single-record shape, NOT `explain_remediation.py`'s CVE-string-
keyed cross-asset shape).

Two things this route does that no existing `explain_*` route does
(25-RESEARCH.md Pattern 4 / 25-PATTERNS.md):

1. **The D-01 pre-generation gate.** Before `_run_explain_stream()` is ever
   invoked, `has_actionable_remediation_text()` is checked against the
   grounding record's own `remediation_action`/`remediation_info`. On a
   miss, a synthetic one-frame `{"type":"error","kind":"grounded_false"}`
   SSE response is returned directly -- audited `status="ungroundable"`,
   zero model calls, zero tokens spent. This is the SAME `kind` the model's
   own `grounded=false` path emits (D-02), so the analyst never learns
   which layer refused.
2. **The GET cache-check's additive `groundable` field.** Every existing
   GET route returns exactly `{"cached": False}` on a miss. This route's
   GET additionally runs the same cheap, zero-dispatch
   `has_actionable_remediation_text()` check and returns
   `{"cached": False, "groundable": <bool>}`, so the frontend can render
   the insufficient-evidence card BEFORE any click (25-UI-SPEC.md state 3).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Annotated, Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.ai.audit import audit_log_ai_call
from app.ai.cache import build_cache_key, get_cached, record_hash
from app.ai.explain import _run_explain_stream, _sse_event, get_model_and_budget
from app.ai.grounding import get_remediation_guidance_context, has_actionable_remediation_text
from app.ai.prompt_builder import (
    REMEDIATION_GUIDANCE_ALLOWLIST,
    build_explain_remediation_guidance_prompt,
    remediation_guidance_prompt_version,
)
from app.ai.safety import contains_dangerous_pattern
from app.ai.schemas import ExplainRemediationGuidanceResponse
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.redis_client import get_redis

router = APIRouter()

# D-01 route-level refusal: zero tokens spent, so the usage shape is a
# literal zero -- mirrors app.ai.explain's own `_ZERO_USAGE` (private to
# that module; constructed locally here rather than importing a second
# private symbol across the module boundary).
_ZERO_USAGE = SimpleNamespace(input_tokens=0, output_tokens=0)


def _allowlisted_hash_fields(record: Any) -> dict[str, Any]:
    """The SAME allowlisted grounding view
    `build_explain_remediation_guidance_prompt()` sends to the model -- read
    back out of the prompt it builds so the cache-check GET hashes EXACTLY
    what the POST path would (D-18). Mirrors `explain_host.py`'s own
    `_allowlisted_hash_fields`."""
    _system_prompt, user_blocks = build_explain_remediation_guidance_prompt(record)
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    result: dict[str, Any] = json.loads(text[start:end])
    return result


async def _refuse_ungroundable(
    db: DBSession,
    *,
    tenant_id: uuid.UUID,
    user_email: str,
    finding_id: uuid.UUID,
    model: str,
) -> AsyncIterator[bytes]:
    """D-01: the deterministic pre-generation refuse path -- no model call,
    audited under its own `status="ungroundable"`, and emits the SAME
    `grounded_false` kind the engine's own model-judgment refusal emits
    (D-02) so the analyst never learns which layer fired."""
    await audit_log_ai_call(
        db,
        tenant_id=tenant_id,
        user_email=user_email,
        model=model,
        usage=_ZERO_USAGE,
        resource_type="remediation-guidance",
        resource_id=str(finding_id),
        status="ungroundable",
        cost_estimate_usd=0.0,
    )
    await db.commit()
    yield _sse_event({"type": "error", "kind": "grounded_false"})


@router.post("/explain-remediation-guidance/{finding_id}")
async def explain_remediation_guidance(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    record = await get_remediation_guidance_context(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    if not has_actionable_remediation_text(record["remediation_action"], record["remediation_info"]):
        model, _monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
        return StreamingResponse(
            _refuse_ungroundable(
                db, tenant_id=user.tenant_id, user_email=user.email, finding_id=finding_id, model=model
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        _run_explain_stream(
            db,
            tenant_id=user.tenant_id,
            user_email=user.email,
            resource_type="remediation-guidance",
            resource_id=str(finding_id),
            record=record,
            build_prompt=build_explain_remediation_guidance_prompt,
            response_model=ExplainRemediationGuidanceResponse,
            redis_client=redis_client,
            allowed_source_fields=REMEDIATION_GUIDANCE_ALLOWLIST,
            get_prompt_version=remediation_guidance_prompt_version,
            dangerous_pattern_check=contains_dangerous_pattern,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/explain-remediation-guidance/{finding_id}")
async def get_explain_remediation_guidance_cache(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> dict[str, Any]:
    record = await get_remediation_guidance_context(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Same resolution `_run_explain_stream` uses internally -- a GET must
    # hash/key against the tenant's CURRENTLY-configured model, never a
    # hardcoded default (mirrors explain_host.py's GET route exactly).
    model, _monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
    allowlisted_fields = _allowlisted_hash_fields(record)
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(
        user.tenant_id, "remediation-guidance", str(finding_id), the_hash, model, remediation_guidance_prompt_version()
    )

    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        # The ONE divergence from every existing GET route (25-UI-SPEC.md
        # state 3): a cheap, zero-dispatch groundable signal lets the
        # frontend render the insufficient-evidence card BEFORE any click.
        groundable = has_actionable_remediation_text(record["remediation_action"], record["remediation_info"])
        return {"cached": False, "groundable": groundable}
    return {"cached": True, **cached}
