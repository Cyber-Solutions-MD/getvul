"""Asset SQLAlchemy model."""

import enum
import uuid

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceCategory(str, enum.Enum):
    WORKSTATION = "WORKSTATION"
    SERVER = "SERVER"
    NETWORK = "NETWORK"
    MOBILE = "MOBILE"
    OTHER = "OTHER"


# Phase 32 — Asset Exposure Context (EXPO-01). Python `str, enum.Enum` +
# `String(20)` columns, NOT a native Postgres ENUM — mirrors DeviceCategory
# above (confirmed zero native-enum usage anywhere in this codebase).
class BusinessCriticality(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataSensitivity(str, enum.Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class ExposureFieldSource(str, enum.Enum):
    AUTO = "AUTO"
    ASSET_OVERRIDE = "ASSET_OVERRIDE"
    GROUP_OVERRIDE = "GROUP_OVERRIDE"  # reserved for Plan 03's AssetGroup entity


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
    containment_status: Mapped[str | None] = mapped_column(String(30))
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

    # Operational labels (e.g. "pci", "dmz", "tier-1") rendered as chips next to hostname.
    # Phase 12 / UX-04-02. Empty list by default. GIN-indexed (alembic 025_add_asset_tags).
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Exposure context (Phase 32 — EXPO-01/02/03). Materialized columns +
    # per-field *_source discriminator, mirroring the risk_score/
    # device_category precedent above. AUTO = auto-inferred by
    # app/assets/exposure.py at upsert/enrichment/recompute; ASSET_OVERRIDE =
    # an admin manually set the value via PATCH /assets/{id}/exposure-context,
    # which permanently wins over any future auto re-run (EXPO-03) since
    # apply_inference_to_asset only ever writes a field whose source is still
    # AUTO. GROUP_OVERRIDE is reserved for Plan 03's AssetGroup entity.
    business_criticality: Mapped[str] = mapped_column(String(20), default="MEDIUM", server_default="MEDIUM")
    business_criticality_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
    data_sensitivity: Mapped[str] = mapped_column(String(20), default="INTERNAL", server_default="INTERNAL")
    data_sensitivity_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
    internet_facing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    internet_facing_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="asset")
    correlations: Mapped[list["VulnerabilityCorrelation"]] = relationship(
        "VulnerabilityCorrelation", back_populates="asset"
    )
