"""Asset SQLAlchemy model."""

import enum
import uuid

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssetType(str, enum.Enum):
    ENDPOINT = "ENDPOINT"
    SERVER = "SERVER"
    VM = "VM"
    CONTAINER = "CONTAINER"
    CLOUD_RESOURCE = "CLOUD_RESOURCE"


class CloudProvider(str, enum.Enum):
    AWS = "AWS"
    AZURE = "AZURE"
    GCP = "GCP"


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

    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="asset")
    correlations: Mapped[list["VulnerabilityCorrelation"]] = relationship("VulnerabilityCorrelation", back_populates="asset")
