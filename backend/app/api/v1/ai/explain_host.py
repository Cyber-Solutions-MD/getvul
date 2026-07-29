"""Per-host 'Explain this asset' endpoint (D-15/D-16 posture-summary view).

POST streams a validated, cited posture explanation via the shared
buffer-then-validate-then-replay engine (`app.ai.explain._run_explain_stream`,
reused UNCHANGED from Plan 04) -- gated `require_analyst`. GET is a cheap
cache-check with NO model call (D-09) -- gated `require_viewer`.

The grounding record is resolved via the NEW tenant-scoped
`get_asset_posture(db, tenant_id, asset_id)` (app.ai.grounding, Plan 08) -- a
foreign-tenant `asset_id` is not resolvable (404, never cross-tenant data),
mirroring `explain_vuln.py`'s own `get_vulnerability` tenant-scoping exactly.
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
from app.ai.grounding import get_asset_posture
from app.ai.prompt_builder import HOST_ALLOWLIST, build_explain_host_prompt, host_prompt_version
from app.ai.schemas import ExplainHostResponse
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.redis_client import get_redis

router = APIRouter()


def _allowlisted_hash_fields(record: Any) -> dict[str, Any]:
    """The SAME allowlisted grounding view `build_explain_host_prompt()`
    sends to the model -- read back out of the prompt it builds so the
    cache-check GET hashes EXACTLY what the POST path would (D-18), without
    a second, independently-maintained allowlist and without triggering a
    model call. Mirrors `explain_vuln.py::_allowlisted_hash_fields`."""
    _system_prompt, user_blocks = build_explain_host_prompt(record)
    text = user_blocks[0]["text"]
    start = text.index(">") + 1
    end = text.rindex("</scanner_data>")
    result: dict[str, Any] = json.loads(text[start:end])
    return result


@router.post("/explain-host/{asset_id}")
async def explain_host(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    record = await get_asset_posture(db, user.tenant_id, asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    return StreamingResponse(
        _run_explain_stream(
            db,
            tenant_id=user.tenant_id,
            user_email=user.email,
            resource_type="host",
            resource_id=str(asset_id),
            record=record,
            build_prompt=build_explain_host_prompt,
            response_model=ExplainHostResponse,
            redis_client=redis_client,
            allowed_source_fields=HOST_ALLOWLIST,
            get_prompt_version=host_prompt_version,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/explain-host/{asset_id}")
async def get_explain_host_cache(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> dict[str, Any]:
    record = await get_asset_posture(db, user.tenant_id, asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Same resolution `_run_explain_stream` uses internally -- a GET must
    # hash/key against the tenant's CURRENTLY-configured model, never a
    # hardcoded default (mirrors explain_vuln.py's GET route exactly).
    model, _monthly_cap_usd = await get_model_and_budget(db, user.tenant_id)
    allowlisted_fields = _allowlisted_hash_fields(record)
    the_hash = record_hash(allowlisted_fields)
    cache_key = build_cache_key(user.tenant_id, "host", str(asset_id), the_hash, model, host_prompt_version())

    cached = await get_cached(redis_client, cache_key)
    if cached is None:
        return {"cached": False}
    return {"cached": True, **cached}
