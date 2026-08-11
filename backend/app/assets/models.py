"""Asset SQLAlchemy model."""

import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String, UniqueConstraint
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
    GROUP_OVERRIDE = "GROUP_OVERRIDE"  # Plan 03 — set by a real AssetGroup's exposure-context override


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

    # RISK-02 (Phase 33): shadow rollup, NOT the live risk_score above.
    # MAX(risk_exposure_score) across the asset's OPEN/IN_PROGRESS
    # findings -- a separate, additive column so risk_score.py's live curve
    # is untouched. Populated by compute_finding_risk_scores (Plan 33-03);
    # NULL when the asset has no open findings. Phase 34 owns any cutover
    # of automated consumers to this value (shadow-only through Phase 33).
    risk_exposure_score: Mapped[int | None] = mapped_column(Integer)
    risk_model_version: Mapped[str | None] = mapped_column(String(20))

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
    # AUTO. GROUP_OVERRIDE (Plan 03) is set by a real AssetGroup's
    # exposure-context override via apply_precedence_to_asset.
    business_criticality: Mapped[str] = mapped_column(String(20), default="MEDIUM", server_default="MEDIUM")
    business_criticality_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
    data_sensitivity: Mapped[str] = mapped_column(String(20), default="INTERNAL", server_default="INTERNAL")
    data_sensitivity_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")
    internet_facing: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    internet_facing_source: Mapped[str] = mapped_column(String(20), default="AUTO", server_default="AUTO")

    # Phase 32 Plan 04 (EXPO-02) — durable raw vendor provenance for a REAL
    # per-connector internet-facing/public-exposure signal, mirroring
    # `external_ip` above (nullable, no server_default — None until a
    # connector genuinely supplies one). `infer_exposure_context` prefers
    # this over the external_ip/tag proxy when it is not None. See
    # app/assets/exposure.py's module docstring for the honest per-connector
    # coverage table (which connectors set this vs. remain FALLBACK).
    internet_facing_detected: Mapped[bool | None] = mapped_column(Boolean)

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="asset")
    correlations: Mapped[list["VulnerabilityCorrelation"]] = relationship(
        "VulnerabilityCorrelation", back_populates="asset"
    )


# Phase 32 Plan 03 — a real, tenant-scoped AssetGroup entity (EXPO-04).
# CONTEXT.md's [USER] decision overrides RESEARCH.md's tag-scoped-query
# shortcut: group-scope exposure overrides target a real group + explicit
# membership, not a tag-containment query. Mirrors ConnectorConfig's
# tenant-scoped-entity shape (ticketing/models.py:39-57).
class AssetGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_asset_group_tenant_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))


# Composite-PK membership join table — mirrors TicketWatcher
# (ticketing/models.py:139-156). Both FKs CASCADE so rows are cleaned up
# when the group or asset is deleted.
class AssetGroupMember(Base):
    __tablename__ = "asset_group_members"
    __table_args__ = (PrimaryKeyConstraint("group_id", "asset_id"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )


# One row per (group_id, field). `updated_at` (TimestampMixin) is the
# tiebreak key for multi-group conflicts on the same asset+field —
# most-recently-updated group override wins (32-CONTEXT.md, unit-tested in
# test_asset_exposure.py::test_conflicting_group_overrides_tiebreak).
class AssetGroupExposureOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_group_exposure_overrides"
    __table_args__ = (UniqueConstraint("group_id", "field", name="uq_group_override_field"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # business_criticality|data_sensitivity|internet_facing
    value: Mapped[str] = mapped_column(String(20), nullable=False)  # stored as string; cast per field on apply
