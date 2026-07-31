"""AiFeedback -- analyst thumbs + optional correction note on an AI
explanation (D-21/D-22, T-24-28..31).

Capture-only this phase (D-21) -- no route reads this back; the flywheel/
dashboard surfacing is Phase 28. One row per (resource_type, resource_id,
user_id), editable via UPSERT (`on_conflict_do_update` in
app/api/v1/ai/feedback.py) so an analyst can change their own verdict
without ever accumulating a duplicate row (D-22). `tenant_id` is an
explicit column (not resolved via a join to the resource) so every query
is directly tenant-scoped (T-24-28) -- mirrors CONTEXT.md D-21's "new
dedicated ai_feedback table" call and `ConnectorConfig`'s own explicit
`tenant_id` + `UniqueConstraint` shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AiFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-user, per-tenant verdict (thumbs up/down) + optional note on one
    AI explanation.

    The composite UNIQUE constraint below is the D-22 upsert target: a
    second POST for the same (resource_type, resource_id, user_id) updates
    this row via `ON CONFLICT (...) DO UPDATE` rather than inserting a
    duplicate.
    """

    __tablename__ = "ai_feedback"
    __table_args__ = (UniqueConstraint("resource_type", "resource_id", "user_id", name="uq_ai_feedback_resource_user"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AiBatchJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """D-05/D-06 (RESEARCH #2/Pattern 4, T-26-08): the durable Postgres
    registry for a submitted Anthropic Message Batch.

    An in-memory dict -- the shape `scheduler.py`'s own `_running_syncs`
    already uses for connector syncs -- is NOT sufficient here. A connector
    sync finishes within one process's lifetime; a Message Batch can
    legitimately still be `in_progress` up to 24 hours later, spanning a
    backend restart or deploy. Losing this row would orphan real spend with
    no way to ever retrieve results.

    `model`/`prompt_version` are frozen at submission time (never
    recomputed at poll time): if a tenant changes their configured model
    between submission and completion, the poller must still build the
    cache key the SUBMITTED requests actually used, or a completed
    narrative would be written under a cache key the drill panel's GET
    route (which resolves the tenant's CURRENT model) would never look up.

    `custom_id_hash_map` maps each submitted finding_id (the Message Batch
    `custom_id`) to its factor-hash -- this lets the poller rebuild the
    exact cache key `build_cache_key()` would compute, and lets the GET
    route's `queued` signal answer "is this finding in an already-submitted
    in_progress batch" via a JSONB containment query, without a second,
    single-purpose child table.
    """

    __tablename__ = "ai_batch_jobs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anthropic_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")  # in_progress|completed
    model: Mapped[str] = mapped_column(String(50), nullable=False)  # resolved at submit time -- frozen
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)  # ditto
    custom_id_hash_map: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
