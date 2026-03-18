"""Cloud Security Posture Management (CSPM) models — misconfigurations, policy violations."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MisconfigSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class MisconfigStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class MisconfigCategory(str, enum.Enum):
    IAM = "IAM"
    NETWORK = "NETWORK"
    ENCRYPTION = "ENCRYPTION"
    LOGGING = "LOGGING"
    STORAGE = "STORAGE"
    COMPUTE = "COMPUTE"
    DATABASE = "DATABASE"
    CONTAINER = "CONTAINER"
    SECRETS = "SECRETS"
    COMPLIANCE = "COMPLIANCE"
    OTHER = "OTHER"


class Misconfiguration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A misconfiguration / policy violation finding from CSPM tools."""

    __tablename__ = "misconfigurations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rule_id", "resource_id", "source", name="uq_misconfig_dedup"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # ── Finding identity ──
    rule_id: Mapped[str] = mapped_column(
        String(300), nullable=False, index=True,
        comment="Policy/rule ID from the source (e.g. CIS 1.2.3, CS-12345)",
    )
    rule_name: Mapped[str] = mapped_column(String(500), nullable=False)
    rule_description: Mapped[str | None] = mapped_column(Text)

    # ── Category & severity ──
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # ── Compliance frameworks ──
    frameworks: Mapped[dict | None] = mapped_column(
        JSONB, default=list,
        comment='e.g. ["CIS AWS 1.5", "SOC2", "PCI-DSS 3.2.1"]',
    )

    # ── Affected resource ──
    resource_id: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True,
        comment="Cloud resource ID (ARN, Azure resource ID, GCP resource name)",
    )
    resource_name: Mapped[str | None] = mapped_column(String(300))
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        comment="e.g. aws_s3_bucket, azure_vm, gcp_project",
    )
    resource_region: Mapped[str | None] = mapped_column(String(50))
    cloud_provider: Mapped[str | None] = mapped_column(String(20))
    cloud_account_id: Mapped[str | None] = mapped_column(String(100))
    cloud_account_name: Mapped[str | None] = mapped_column(String(200))

    # ── Source tracking ──
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_finding_id: Mapped[str | None] = mapped_column(String(300))

    # ── Remediation ──
    remediation_info: Mapped[str | None] = mapped_column(Text)
    remediation_url: Mapped[str | None] = mapped_column(String(500))

    # ── Status ──
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)

    # ── Timestamps ──
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    remediated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Extra data ──
    details: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Source-specific extra data",
    )
