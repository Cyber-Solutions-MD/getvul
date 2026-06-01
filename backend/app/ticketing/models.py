"""Ticketing, connector config, and sync log models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import text

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TicketProvider(str, enum.Enum):
    JIRA = "JIRA"
    GITHUB = "GITHUB"
    ASANA = "ASANA"


class ConnectorType(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"


class SyncStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ConnectorConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "connector_type", name="uq_connector_tenant_type"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    connector_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    credentials_secret_arn: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(20))
    last_sync_record_count: Mapped[int | None] = mapped_column(Integer)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)

    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="connector", cascade="all, delete-orphan")


class SyncLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sync_logs"

    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connector_configs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    connector: Mapped["ConnectorConfig"] = relationship(back_populates="sync_logs")


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("tenant_id", "external_ticket_id", "provider", name="uq_ticket_external"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_ticket_id: Mapped[str] = mapped_column(String(200), nullable=False)
    external_ticket_url: Mapped[str] = mapped_column(String(500), nullable=False)
    external_status: Mapped[str | None] = mapped_column(String(50))
    project_key: Mapped[str | None] = mapped_column(String(50))
    assignee: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_rule: Mapped[str | None] = mapped_column(String(200))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ticket_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 13 additions (D-P-02 blocked, D-SLA-01 sla_due_at)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ticket_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action: Mapped[dict] = mapped_column(JSONB, nullable=False)
    saved_filter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    schedule_minutes: Mapped[int] = mapped_column(Integer, default=1440)  # default daily
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[str | None] = mapped_column(String(20))
    last_run_tickets_created: Mapped[int | None] = mapped_column(Integer)


class TicketComment(Base, UUIDPrimaryKeyMixin):
    """Local audit note on a ticket (D-C-02). Never writes back to Jira/Asana/GitHub."""

    __tablename__ = "ticket_comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TicketWatcher(Base):
    """Local GetVul subscription watcher for a ticket (D-W-02).

    Composite PK (ticket_id, user_id) enforces idempotency at the DB layer (T-13-03).
    Both FKs CASCADE so rows are cleaned up when the ticket or user is deleted.
    """

    __tablename__ = "ticket_watchers"
    __table_args__ = (PrimaryKeyConstraint("ticket_id", "user_id"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
