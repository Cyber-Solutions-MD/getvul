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

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
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
