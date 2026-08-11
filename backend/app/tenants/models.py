"""Tenant and User SQLAlchemy models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdPProvider(str, enum.Enum):
    GOOGLE = "GOOGLE"
    AZURE_ENTRA_ID = "AZURE_ENTRA_ID"


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    idp_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    idp_tenant_id: Mapped[str | None] = mapped_column(String(255))
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sso_enforced: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", server_default="UTC")
    password_policy: Mapped[dict | None] = mapped_column(JSONB)
    syslog_config: Mapped[dict | None] = mapped_column(JSONB)
    smtp_config: Mapped[dict | None] = mapped_column(JSONB)
    sla_config: Mapped[dict | None] = mapped_column(JSONB)
    branding: Mapped[dict | None] = mapped_column(
        JSONB
    )  # logo_path, company_name, tagline, primary_color, accent_color

    # Phase 32 (EXPO-06) — per-tenant calibration config for
    # check_criticality_calibration (app/assets/exposure.py). cap = the
    # AUTO-CRITICAL proportion above which the report flags `over_cap`.
    # hard_cap_enabled is a documented, deliberately unwired flag — default
    # OFF (flag+report only per 32-CONTEXT.md).
    exposure_criticality_cap: Mapped[float] = mapped_column(Float, default=0.15, server_default="0.15")
    exposure_hard_cap_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Phase 34 (RISK-07..10) — historical-recompute + consumer-cutover config. UNLIKE
    # exposure_hard_cap_enabled above, cutover_risk_exposure_scoring is a REAL behavioral
    # branch in every consumer (34-CONTEXT locked). Default OFF; a human flips it on a
    # validated live stack via POST /risk-cutover/enable (Plan 03), never in this env.
    cutover_risk_exposure_scoring: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    risk_cutover_threshold_ack_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # RISK-09 ack gate (Plan 03)
    risk_cutover_threshold_ack_diff_hash: Mapped[str | None] = mapped_column(
        String(64)
    )  # RISK-09 staleness detection (Plan 03)

    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="VIEWER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    idp_subject: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    allow_password_login: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    groups: Mapped[dict | None] = mapped_column(JSONB, default=list)
    password_history: Mapped[dict | None] = mapped_column(JSONB, default=list)  # List of previous hashes
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    department: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    idp_source: Mapped[str | None] = mapped_column(String(30))  # google, azure, humaans, local
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
