"""AI router package — /api/v1/ai/*.

`ai_router` is the single mount point Plans 02-09 attach their sub-routers
(explain-vuln/host/remediation, feedback, etc.) to. Registered once in
`app/main.py` via `app.include_router(ai_router)`.
"""

from __future__ import annotations

from fastapi import APIRouter

ai_router = APIRouter(prefix="/api/v1/ai", tags=["AI"])

# spike: Wave-0 throwaway incremental-SSE spike (T-24-03: gated behind
#   require_analyst, never anonymous). Remove or leave inert before phase
#   seal — see 24-01-SUMMARY.md.
# explain_vuln: Plan 04's real per-vuln "Explain this vuln" endpoint (POST
#   SSE stream + GET cache-check) — the tracer's first real sub-router on
#   this mount point.
# explain_host / explain_remediation: Plan 08's D-15 widening — posture-
#   summary (host) and cross-asset-CVE-grouping (remediation, D-16 Option A)
#   views, both thin wrappers reusing _run_explain_stream() unchanged.
# feedback: Plan 07's capture-only thumbs+note upsert endpoint (D-21/D-22).
from app.api.v1.ai import (
    explain_host,  # noqa: E402
    explain_remediation,  # noqa: E402
    explain_vuln,  # noqa: E402
    feedback,  # noqa: E402
    spike,  # noqa: F401
)

ai_router.include_router(explain_vuln.router)
ai_router.include_router(explain_host.router)
ai_router.include_router(explain_remediation.router)
ai_router.include_router(feedback.router)
