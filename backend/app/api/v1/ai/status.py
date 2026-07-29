"""Lightweight, non-admin-safe "is AI configured" signal (D-23 gap closure).

`GET /api/v1/ai/status` is `require_viewer`-gated -- EVERY authenticated
tenant role (Viewer, Analyst, Admin, Owner) can call it to learn whether the
tenant has turned AI on, derived from the SAME source of truth the engine
itself uses (never the admin-only connectors listing), and returns ONLY a
boolean. It never returns the underlying connector row, ciphertext, decrypted
value, or any other credential-shaped material -- see
`test_status_response_never_leaks_key_material` for the proof.

This closes 24-VERIFICATION.md's truth #2 gap: the frontend previously had
no non-admin-safe way to learn "is AI configured", so Analyst/Viewer's
`keyConfigured` derivation fell back to an optimistic guess off an admin-
gated endpoint's error state.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.tenant_keys import get_tenant_anthropic_key
from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

router = APIRouter()


@router.get("/status")
async def get_ai_status(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> dict[str, bool]:
    configured = await get_tenant_anthropic_key(db, user.tenant_id) is not None
    return {"configured": configured}
