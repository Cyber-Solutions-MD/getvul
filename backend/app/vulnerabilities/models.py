"""Vulnerability and Correlation SQLAlchemy models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class VulnStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class VulnSource(str, enum.Enum):
    CROWDSTRIKE = "CROWDSTRIKE"
    NESSUS = "NESSUS"
    DEFENDER = "DEFENDER"
    WIZ = "WIZ"


class Confidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Vulnerability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "vulnerabilities"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", "source", name="uq_vuln_dedup"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str | None] = mapped_column(String(20), index=True)
    vulnerability_name: Mapped[str | None] = mapped_column(String(500))
    cvss_v3_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    cvss_v3_vector: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    epss_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    exploit_available: Mapped[bool] = mapped_column(Boolean, default=False)
    cisa_kev: Mapped[bool] = mapped_column(Boolean, default=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_vuln_id: Mapped[str | None] = mapped_column(String(200))
    source_scan_id: Mapped[str | None] = mapped_column(String(200))
    affected_product: Mapped[str | None] = mapped_column(String(300))
    affected_version: Mapped[str | None] = mapped_column(String(100))
    fixed_version: Mapped[str | None] = mapped_column(String(100))
    remediation_info: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=VulnStatus.OPEN.value, index=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    remediated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped["Asset"] = relationship("Asset", back_populates="vulnerabilities")


class VulnerabilityCorrelation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vulnerability_correlations"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    crowdstrike_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL"))
    nessus_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL"))
    defender_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL"))
    wiz_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL"))
    sources_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(10), default=Confidence.LOW.value)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="correlations")
