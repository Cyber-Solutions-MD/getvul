"""Campaign SQLAlchemy model (Phase 38 -- CAMP-01/CAMP-04)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Phase 38 (CAMP-01..04) -- a thin, persisted identity+lifecycle wrapper
    around an existing `Vulnerability.remediation_id` group.

    D-01/D-02: a campaign is 1:1 with an existing remediation group -- it
    does NOT introduce a new grouping engine. D-07: this table stores
    IDENTITY + LIFECYCLE ONLY -- deliberately NO denormalized label snapshot
    (`remediation_action`/`affected_product`) and NO progress/percentage/
    MTTR/member-count column. Every display value (label, counts, %,
    status) is always live-joined off `vulnerabilities`/`remediation_events`
    at read time, exactly like `get_remediations_grouped()` already does for
    the identical grouping key (38-RESEARCH.md Pattern 2). D-03: membership
    is a live `WHERE remediation_id = :x` query, never a frozen snapshot --
    this table intentionally has no `campaign_members` join table.

    `closed_at` is the ONLY lifecycle marker, serving two purposes:
      1. D-11's partial-unique-index predicate below -- exactly one row per
         (tenant_id, remediation_id) WHERE closed_at IS NULL, so launching a
         campaign on a remediation_id with an existing ACTIVE campaign opens
         that campaign instead of creating a duplicate (get_or_create,
         service.py). A CLOSED campaign's remediation_id can always accept a
         fresh active campaign (D-13 auto-complete / D-17 manual-close is
         sticky both require this to stay re-launchable).
      2. The D-13/D-19 audit-once gate for the derived complete/active
         display status (lazy-on-read, service.py) -- NOT itself the
         display status; a campaign's Active/Complete pill is always
         recomputed from live member percentages at read time, never stored.

    D-11 (one-way schema commitment, confirmed via Task 1's reversibility
    checkpoint): Postgres has no partial `UNIQUE CONSTRAINT` syntax, only a
    partial `UNIQUE INDEX` -- hence `Index(..., unique=True,
    postgresql_where=...)` below, never `UniqueConstraint`
    (38-RESEARCH.md Pitfall 3; precedent: `020_add_sla_tracking.py:27-32`).
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        Index(
            "uq_campaign_active_remediation",
            "tenant_id",
            "remediation_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # "manual" (analyst-initiated early close) | "auto_complete" (lazy-on-read
    # 100%-derived completion, D-13/D-19) -- distinguishes reactivation
    # eligibility (D-14 applies only to auto_complete, D-17 manual is sticky).
    close_trigger: Mapped[str | None] = mapped_column(String(20))
