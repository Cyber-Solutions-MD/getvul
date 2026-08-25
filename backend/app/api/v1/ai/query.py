"""The Natural-Language Query 'Ask' endpoint (NLQ-01/NLQ-02/NLQ-03,
T-44-01..06, Phase 44 Plan 01).

POST streams a translated-filter -> deterministic-execute -> grounded-
narrate answer via the two-call orchestrator
(`app.ai.query_assistant._run_query_stream`) -- gated `require_analyst`
(D-18: only Analyst+ may trigger a paid call, mirrors `explain_vuln.py`'s
POST gate exactly).

Unlike `explain_vuln.py`, there is no path-param resource to resolve up
front -- the "record" here IS the analyst's own free-text question,
validated at the request-body boundary (V5: `Field(..., max_length=500)`,
enforced by FastAPI/Pydantic BEFORE any model call, so it is never
silently stripped by Anthropic's structured-output schema translator the
way a `Field(max_length=...)` on a RESPONSE schema would be -- this
constraint lives on the REQUEST body, not the model's own output schema).
"""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.query_assistant import _run_query_stream
from app.auth.rbac import require_analyst
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.redis_client import get_redis

router = APIRouter()


class QueryRequest(BaseModel):
    """V5 input validation: `min_length=1` prevents a wasted, billable
    model call on an accidentally-empty submission; `max_length=500`
    bounds the untrusted question's own size (independent of, and in
    addition to, `MAX_TOKENS` bounding the model call itself)."""

    question: str = Field(..., min_length=1, max_length=500)


@router.post("/query")
async def query(
    body: QueryRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
) -> StreamingResponse:
    return StreamingResponse(
        _run_query_stream(
            db,
            tenant_id=user.tenant_id,
            user_email=user.email,
            question=body.question,
            redis_client=redis_client,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
