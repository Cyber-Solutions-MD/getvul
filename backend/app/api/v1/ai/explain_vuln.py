"""Per-vuln 'Explain this vuln' endpoint (AI-03/AI-04, T-24-16..21).

POST streams a validated, cited explanation via the shared
buffer-then-validate-then-replay engine (`app.ai.explain._run_explain_stream`)
-- gated `require_analyst` (D-17: only Analyst+ may trigger a paid call).
GET is a cheap cache-check with NO model call (D-09) -- gated
`require_viewer` (Viewers may read a cached result, never trigger a new one).

Both routes resolve the grounding record via the EXISTING tenant-scoped
`get_vulnerability(db, tenant_id, vuln_id)` (T-24-18: a foreign-tenant
`finding_id` is not resolvable -- 404, never cross-tenant data).
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
from app.ai.prompt_builder import VULN_ALLOWLIST, build_explain_vuln_prompt, prompt_version
from app.ai.schemas import ExplainVulnResponse
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.redis_client import get_redis
from app.vulnerabilities.service import get_vulnerability

router = APIRouter()


def _allowlisted_hash_fields(record: Any) -> dict[str, Any]:
    """The SAME allowlisted grounding view `build_explain_vuln_prompt()`
    sends to the model -- read back out of the prompt it builds so the
    cache-check GET hashes EXACTLY what the POST path would (D-18),
    without a second, independently-maintained allowlist and without
    triggering a model call. Mirrors `app.ai.explain._extract_scanner_data`.
    """
    _system_prompt, user_blocks = build_explain_vuln_prompt(record)
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    result: dict[str, Any] = json.loads(text[start:end])
    return result


@router.post("/explain-vuln/{finding_id}")
async def explain_vuln(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    record = await get_vulnerability(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    return StreamingResponse(
        _run_explain_stream(
            db,
            tenant_id=user.tenant_id,
            user_email=user.email,
            resource_type="vuln",
            resource_id=str(finding_id),
            record=record,
            build_prompt=build_explain_vuln_prompt,
            response_model=ExplainVulnResponse,
            redis_client=redis_client,
            allowed_source_fields=VULN_ALLOWLIST,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/explain-vuln/{finding_id}")
async def get_explain_vuln_cache(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> dict[str, Any]:
    record = await get_vulnerability(db, user.tenant_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    # Same resolution `_run_explain_stream` uses internally -- a GET must
    # hash/key against the tenant's CURRENTLY-configured model, never a
    # hardcoded default, so it never serves a stale-model cache entry the
    # POST path would not have produced (D-09 cheap lookup, no dispatch).
    model, _monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
    allowlisted_fields = _allowlisted_hash_fields(record)
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(user.tenant_id, "vuln", str(finding_id), the_hash, model, prompt_version())

    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        return {"cached": False}
    return {"cached": True, **cached}
