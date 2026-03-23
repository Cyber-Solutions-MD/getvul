"""Asset SQLAlchemy model."""

import enum
import uuid

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceCategory(str, enum.Enum):
    WORKSTATION = "WORKSTATION"
    SERVER = "SERVER"
    NETWORK = "NETWORK"
    MOBILE = "MOBILE"
    OTHER = "OTHER"


class Asset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("tenant_id", "hostname", name="uq_asset_tenant_hostname"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), index=True)
    ip_addresses: Mapped[dict | None] = mapped_column(JSONB, default=list)
    mac_addresses: Mapped[dict | None] = mapped_column(JSONB, default=list)
    os_name: Mapped[str | None] = mapped_column(String(100))
    os_version: Mapped[str | None] = mapped_column(String(50))
    asset_type: Mapped[str | None] = mapped_column(String(30))
    cloud_provider: Mapped[str | None] = mapped_column(String(20))
    cloud_resource_id: Mapped[str | None] = mapped_column(String(300))
    seen_by_sources: Mapped[dict | None] = mapped_column(JSONB, default=list)
    crowdstrike_aid: Mapped[str | None] = mapped_column(String(100))
    defender_device_id: Mapped[str | None] = mapped_column(String(100))
    wiz_asset_id: Mapped[str | None] = mapped_column(String(100))
    nessus_host_id: Mapped[str | None] = mapped_column(String(100))
    risk_score: Mapped[int | None] = mapped_column(Integer)

    # Ignore status
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ignored_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    ignored_reason: Mapped[str | None] = mapped_column(String(500))

    # Device classification
    device_category: Mapped[str | None] = mapped_column(String(30), index=True)

    # CrowdStrike / source device enrichment
    last_login_user: Mapped[str | None] = mapped_column(String(300))
    last_login_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    host_status: Mapped[str | None] = mapped_column(String(30))
    system_manufacturer: Mapped[str | None] = mapped_column(String(200))
    external_ip: Mapped[str | None] = mapped_column(String(50))

    # JAMF / MDM enrichment
    jamf_id: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    building: Mapped[str | None] = mapped_column(String(200))
    assigned_user: Mapped[str | None] = mapped_column(String(300))
    managed_by: Mapped[str | None] = mapped_column(String(30))
    last_checkin_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    mdm_details: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="asset")
    correlations: Mapped[list["VulnerabilityCorrelation"]] = relationship("VulnerabilityCorrelation", back_populates="asset")
