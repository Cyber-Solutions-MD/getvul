"""THROWAWAY spike — proves true incremental SSE reaches the browser through
the full nginx -> Docker path before the real "explain this vuln" streaming
engine (Plan 04) is built on top (RESEARCH.md Pitfall 2).

Every existing `StreamingResponse` in this backend (app/main.py::export_resource)
wraps a pre-built, one-shot `iter([bytes])` body — never a generator that yields
multiple chunks over real wall-clock time. This route is the first one that does,
and its only purpose is to verify the browser/curl sees the first frame arrive
well before the last one (not all four dumped at once after nginx buffers them).

Gated behind `require_analyst` (T-24-03) — never anonymous, even though it
carries no tenant data. Remove or leave inert before phase seal; see
24-01-SUMMARY.md for the disposition decision.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.responses import StreamingResponse

from app.auth.rbac import require_analyst
from app.auth.schemas import CurrentUser

from . import ai_router


async def _spike_generator() -> AsyncIterator[bytes]:
    for i in range(4):
        await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'frame': i})}\n\n".encode()


@ai_router.get("/_spike")
async def ai_spike(user: Annotated[CurrentUser, Depends(require_analyst)]) -> StreamingResponse:
    """Throwaway incremental-SSE proof. Yields 4 frames, ~0.5s apart."""
    return StreamingResponse(
        _spike_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
