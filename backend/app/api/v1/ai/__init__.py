"""AI router package — /api/v1/ai/*.

`ai_router` is the single mount point Plans 02-09 attach their sub-routers
(explain-vuln/host/remediation, feedback, etc.) to. Registered once in
`app/main.py` via `app.include_router(ai_router)`.
"""

from __future__ import annotations

from fastapi import APIRouter

ai_router = APIRouter(prefix="/api/v1/ai", tags=["AI"])

# Wave-0 throwaway incremental-SSE spike (T-24-03: gated behind require_analyst,
# never anonymous). Remove or leave inert before phase seal — see 24-01-SUMMARY.md.
from app.api.v1.ai import spike  # noqa: F401
