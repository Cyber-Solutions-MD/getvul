"""AI feedback capture endpoint (D-21/D-22, T-24-28..31).

POST /api/v1/ai/feedback/{resource_type}/{resource_id} -- thumbs (up/down)
+ an optional <=500-char correction note on one AI explanation. Idempotent
per-user UPSERT (D-22): a second submission for the same
(resource_type, resource_id, user) UPDATES the existing row's verdict/note
rather than inserting a duplicate -- so an analyst can change their own
verdict. Capture-only this phase (D-21) -- nothing here reads feedback
back; Phase 28 owns the flywheel/dashboard surfacing.

Gated require_analyst -- mirrors the ticketing watch/unwatch analog
(app/ticketing/router.py::watch_ticket) for consistency with D-17's actor
model, even though feedback capture itself is free/non-billed (RESEARCH
Assumption A4).

resource_type/resource_id are generic path strings (not a Python enum) --
D-15 widens this same endpoint to host/remediation views without a
contract change, mirroring how app/ai/cache.py's build_cache_key() already
treats resource_type as a free string.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.ai.models import AiFeedback
from app.audit import audit
from app.auth.rbac import require_analyst
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Feedback submission body. A thumb alone is a valid submission --
    `note` is optional and never blocks (UI-SPEC "partial" coverage row).
    `extra=forbid` matches the project's mass-assignment-defense
    convention (app/ticketing/schemas.py's BlockedUpdate/CommentCreate)."""

    model_config = {"extra": "forbid"}

    verdict: Literal["up", "down"]
    note: str | None = Field(None, max_length=500)

    @field_validator("note")
    @classmethod
    def _no_ws_only(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


@router.post("/feedback/{resource_type}/{resource_id}")
async def submit_feedback(
    resource_type: str,
    resource_id: str,
    body: FeedbackRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> dict[str, str]:
    now = datetime.now(UTC)

    # Idempotent per-user UPSERT (D-22) -- the composite UNIQUE constraint
    # (resource_type, resource_id, user_id) is the conflict target. A
    # second submission for the SAME (resource, user) updates verdict/note
    # in place; user_id already disambiguates cross-tenant collisions since
    # every user belongs to exactly one tenant (T-24-28).
    stmt = (
        pg_insert(AiFeedback)
        .values(
            tenant_id=user.tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user.id,
            verdict=body.verdict,
            note=body.note,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["resource_type", "resource_id", "user_id"],
            set_={"verdict": body.verdict, "note": body.note, "updated_at": now},
        )
    )
    await db.execute(stmt)

    # T-24-30: a real interactive user action with a real tenant -- the
    # standard audit() helper is acceptable here, distinct from the
    # dedicated audit_log_ai_call() path reserved for actual model-dispatch
    # calls (app/ai/audit.py).
    await audit(db, user, "ai.feedback", resource_type, resource_id, {"verdict": body.verdict})
    await db.commit()

    return {"verdict": body.verdict}
