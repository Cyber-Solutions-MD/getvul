"""Notification model — in-app + email alerts for security events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )  # null = broadcast to all

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info"
    )  # critical, high, medium, low, info
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # new_critical_vuln, sla_breach, sync_failure, ticket_update, risk_change

    # Link to related resource
    resource_type: Mapped[str | None] = mapped_column(String(50))  # vulnerability, asset, ticket, connector
    resource_id: Mapped[str | None] = mapped_column(String(200))

    # State
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Delivery tracking
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Extra data
    details: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class AlertingGuard(Base, UUIDPrimaryKeyMixin):
    """Phase 40 Plan 01 (D-05/D-06, Task 1 checkpoint option-a) -- the
    durable once-only "already-alerted" guard for ALERT-01 KEV/EPSS
    transition detection, AND the cold-start seeding record.

    Each scheduler tick, `_check_new_kev_epss` (Plan 02) computes the
    tenant's current KEV/EPSS-qualifying `(cve_id, asset_id)` pairs,
    subtracts rows already present here (identity = the UniqueConstraint
    below), fires ALERT-01 on the remainder, then inserts a guard row for
    everything just fired. On a tenant's first-ever pass there is nothing
    to subtract yet, so every currently-qualifying pair is inserted
    *without* firing (D-06 cold-start seeding) -- this prevents a
    launch-day alert storm across the whole existing backlog. A seeded-not-
    fired row therefore has `fired_at IS NULL`; a genuinely fired row has
    `fired_at` set (observability -- Task 1 checkpoint rejected bare
    existence rows for this reason).

    This is a NEW dedicated table, not a reuse of `SlaEscalationEvent`
    (below is the wrong shape too -- that table keys on `vulnerability_id`,
    but ALERT-01's identity is `(cve_id, asset_id, trigger_type)`; see
    40-01-PLAN.md interfaces / Open Question 1).

    `asset_id` is nullable -- an unresolved-asset qualifier (e.g. a KEV/EPSS
    match with no asset linkage yet) still needs its own guard row so it
    isn't treated as "new" once the asset resolves.

    No TimestampMixin: `fired_at` is this row's own semantically-meaningful
    timestamp (nullable to distinguish "seeded" from "fired") --
    created_at/updated_at would be redundant/confusing alongside it.
    """

    __tablename__ = "alerting_guard"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cve_id", "asset_id", "trigger_type", name="uq_alerting_guard_once"),
        Index("ix_alerting_guard_slice", "tenant_id", "trigger_type"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "kev" | "epss"
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
