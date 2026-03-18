#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "☁️ Building CSPM + CrowdStrike connector..."

git checkout main
git pull
git checkout -b feat/cspm-crowdstrike

# ══════════════════════════════════════════════
#  DATABASE: Misconfigurations model
# ══════════════════════════════════════════════

mkdir -p backend/app/cspm

cat > backend/app/cspm/__init__.py << 'FILEEOF'
FILEEOF

cat > backend/app/cspm/models.py << 'FILEEOF'
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
FILEEOF

# ══════════════════════════════════════════════
#  DATABASE: Migration for misconfigurations
# ══════════════════════════════════════════════

cat > backend/alembic/versions/002_add_misconfigurations.py << 'FILEEOF'
"""002 - Add misconfigurations table for CSPM.

Revision ID: 002_add_misconfigurations
Revises: 001_initial_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_add_misconfigurations"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "misconfigurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rule_id", sa.String(300), nullable=False, index=True),
        sa.Column("rule_name", sa.String(500), nullable=False),
        sa.Column("rule_description", sa.Text),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("severity", sa.String(10), nullable=False, index=True),
        sa.Column("frameworks", postgresql.JSONB, server_default="[]"),
        sa.Column("resource_id", sa.String(500), nullable=False, index=True),
        sa.Column("resource_name", sa.String(300)),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_region", sa.String(50)),
        sa.Column("cloud_provider", sa.String(20)),
        sa.Column("cloud_account_id", sa.String(100)),
        sa.Column("cloud_account_name", sa.String(200)),
        sa.Column("source", sa.String(30), nullable=False, index=True),
        sa.Column("source_finding_id", sa.String(300)),
        sa.Column("remediation_info", sa.Text),
        sa.Column("remediation_url", sa.String(500)),
        sa.Column("status", sa.String(20), server_default="OPEN", index=True),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("remediated_at", sa.DateTime(timezone=True)),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "rule_id", "resource_id", "source", name="uq_misconfig_dedup"),
    )
    op.create_index("idx_misconfig_tenant_severity", "misconfigurations", ["tenant_id", "severity"])
    op.create_index("idx_misconfig_tenant_category", "misconfigurations", ["tenant_id", "category"])
    op.create_index("idx_misconfig_tenant_source", "misconfigurations", ["tenant_id", "source"])


def downgrade() -> None:
    op.drop_index("idx_misconfig_tenant_source", table_name="misconfigurations")
    op.drop_index("idx_misconfig_tenant_category", table_name="misconfigurations")
    op.drop_index("idx_misconfig_tenant_severity", table_name="misconfigurations")
    op.drop_table("misconfigurations")
FILEEOF

# Register model in alembic env
sed -i '' '/from app.ticketing.models import/a\
from app.cspm.models import Misconfiguration  # noqa: F401' backend/alembic/env.py

# ══════════════════════════════════════════════
#  BACKEND: CSPM schemas
# ══════════════════════════════════════════════

cat > backend/app/cspm/schemas.py << 'FILEEOF'
"""Pydantic schemas for CSPM endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MisconfigSummary(BaseModel):
    id: uuid.UUID
    rule_id: str
    rule_name: str
    category: str
    severity: str
    source: str
    status: str
    resource_id: str
    resource_name: str | None
    resource_type: str | None
    cloud_provider: str | None
    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class MisconfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rule_id: str
    rule_name: str
    rule_description: str | None
    category: str
    severity: str
    frameworks: list | None
    resource_id: str
    resource_name: str | None
    resource_type: str | None
    resource_region: str | None
    cloud_provider: str | None
    cloud_account_id: str | None
    cloud_account_name: str | None
    source: str
    source_finding_id: str | None
    remediation_info: str | None
    remediation_url: str | None
    status: str
    first_detected_at: datetime
    last_seen_at: datetime
    remediated_at: datetime | None
    details: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MisconfigFilter(BaseModel):
    severity: list[str] | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    category: list[str] | None = None
    cloud_provider: str | None = None
    resource_type: str | None = None
    search: str | None = None


class MisconfigStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class BulkMisconfigStatusUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class CategoryCount(BaseModel):
    category: str
    count: int


class SeverityCount(BaseModel):
    severity: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class CSPMDashboardStats(BaseModel):
    total_findings: int
    open_findings: int
    by_severity: list[SeverityCount]
    by_category: list[CategoryCount]
    by_source: list[SourceCount]
    by_cloud_provider: list[dict]
    compliance_pass_rate: float | None = None
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: CSPM service
# ══════════════════════════════════════════════

cat > backend/app/cspm/service.py << 'FILEEOF'
"""CSPM business logic and database queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cspm.models import Misconfiguration
from app.cspm.schemas import (
    BulkMisconfigStatusUpdate,
    CSPMDashboardStats,
    CategoryCount,
    MisconfigFilter,
    MisconfigResponse,
    MisconfigSummary,
    SeverityCount,
    SourceCount,
)
from app.pagination import PaginatedResponse, PaginationParams


def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: MisconfigFilter) -> Select:
    query = query.where(Misconfiguration.tenant_id == tenant_id)
    if filters.severity:
        query = query.where(Misconfiguration.severity.in_(filters.severity))
    if filters.source:
        query = query.where(Misconfiguration.source.in_(filters.source))
    if filters.status:
        query = query.where(Misconfiguration.status.in_(filters.status))
    if filters.category:
        query = query.where(Misconfiguration.category.in_(filters.category))
    if filters.cloud_provider:
        query = query.where(Misconfiguration.cloud_provider == filters.cloud_provider)
    if filters.resource_type:
        query = query.where(Misconfiguration.resource_type.ilike(f"%{filters.resource_type}%"))
    if filters.search:
        query = query.where(
            or_(
                Misconfiguration.rule_name.ilike(f"%{filters.search}%"),
                Misconfiguration.rule_id.ilike(f"%{filters.search}%"),
                Misconfiguration.resource_name.ilike(f"%{filters.search}%"),
                Misconfiguration.resource_id.ilike(f"%{filters.search}%"),
            )
        )
    return query


async def list_misconfigurations(
    db: AsyncSession, tenant_id: uuid.UUID, filters: MisconfigFilter, pagination: PaginationParams,
) -> PaginatedResponse[MisconfigSummary]:
    count_q = _apply_filters(select(func.count(Misconfiguration.id)), tenant_id, filters)
    total = (await db.execute(count_q)).scalar_one()

    data_q = (
        _apply_filters(select(Misconfiguration), tenant_id, filters)
        .order_by(
            case(
                (Misconfiguration.severity == "CRITICAL", 1),
                (Misconfiguration.severity == "HIGH", 2),
                (Misconfiguration.severity == "MEDIUM", 3),
                (Misconfiguration.severity == "LOW", 4),
                else_=5,
            ),
            Misconfiguration.last_seen_at.desc(),
        )
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    results = (await db.execute(data_q)).scalars().all()

    items = [MisconfigSummary.model_validate(m) for m in results]
    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_misconfiguration(
    db: AsyncSession, tenant_id: uuid.UUID, misconfig_id: uuid.UUID,
) -> MisconfigResponse | None:
    result = await db.execute(
        select(Misconfiguration).where(
            Misconfiguration.id == misconfig_id, Misconfiguration.tenant_id == tenant_id,
        )
    )
    m = result.scalar_one_or_none()
    if m is None:
        return None
    return MisconfigResponse.model_validate(m)


async def update_misconfig_status(
    db: AsyncSession, tenant_id: uuid.UUID, misconfig_id: uuid.UUID, new_status: str,
) -> bool:
    now = datetime.now(timezone.utc)
    values: dict = {"status": new_status, "updated_at": now}
    if new_status == "REMEDIATED":
        values["remediated_at"] = now
    result = await db.execute(
        update(Misconfiguration)
        .where(Misconfiguration.id == misconfig_id, Misconfiguration.tenant_id == tenant_id)
        .values(**values)
    )
    return result.rowcount > 0


async def bulk_update_misconfig_status(
    db: AsyncSession, tenant_id: uuid.UUID, body: BulkMisconfigStatusUpdate,
) -> int:
    now = datetime.now(timezone.utc)
    values: dict = {"status": body.status, "updated_at": now}
    if body.status == "REMEDIATED":
        values["remediated_at"] = now
    result = await db.execute(
        update(Misconfiguration)
        .where(Misconfiguration.id.in_(body.ids), Misconfiguration.tenant_id == tenant_id)
        .values(**values)
    )
    return result.rowcount


async def get_cspm_stats(db: AsyncSession, tenant_id: uuid.UUID) -> CSPMDashboardStats:
    base = Misconfiguration.tenant_id == tenant_id

    total = (await db.execute(select(func.count(Misconfiguration.id)).where(base))).scalar_one()
    open_count = (await db.execute(
        select(func.count(Misconfiguration.id)).where(base, Misconfiguration.status == "OPEN")
    )).scalar_one()

    sev_rows = (await db.execute(
        select(Misconfiguration.severity, func.count(Misconfiguration.id)).where(base).group_by(Misconfiguration.severity)
    )).all()

    cat_rows = (await db.execute(
        select(Misconfiguration.category, func.count(Misconfiguration.id)).where(base).group_by(Misconfiguration.category)
    )).all()

    src_rows = (await db.execute(
        select(Misconfiguration.source, func.count(Misconfiguration.id)).where(base).group_by(Misconfiguration.source)
    )).all()

    cloud_rows = (await db.execute(
        select(Misconfiguration.cloud_provider, func.count(Misconfiguration.id))
        .where(base, Misconfiguration.cloud_provider.isnot(None))
        .group_by(Misconfiguration.cloud_provider)
    )).all()

    remediated = (await db.execute(
        select(func.count(Misconfiguration.id)).where(base, Misconfiguration.status == "REMEDIATED")
    )).scalar_one()
    pass_rate = round((remediated / total) * 100, 1) if total > 0 else None

    return CSPMDashboardStats(
        total_findings=total,
        open_findings=open_count,
        by_severity=[SeverityCount(severity=r[0], count=r[1]) for r in sev_rows],
        by_category=[CategoryCount(category=r[0], count=r[1]) for r in cat_rows],
        by_source=[SourceCount(source=r[0], count=r[1]) for r in src_rows],
        by_cloud_provider=[{"provider": r[0], "count": r[1]} for r in cloud_rows],
        compliance_pass_rate=pass_rate,
    )
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: CSPM router
# ══════════════════════════════════════════════

cat > backend/app/cspm/router.py << 'FILEEOF'
"""CSPM API routes — misconfigurations."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.cspm.schemas import (
    BulkMisconfigStatusUpdate,
    CSPMDashboardStats,
    MisconfigFilter,
    MisconfigResponse,
    MisconfigStatusUpdate,
    MisconfigSummary,
)
from app.cspm.service import (
    bulk_update_misconfig_status,
    get_cspm_stats,
    get_misconfiguration,
    list_misconfigurations,
    update_misconfig_status,
)
from app.dependencies import DBSession
from app.pagination import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get("", response_model=PaginatedResponse[MisconfigSummary])
async def list_findings(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    category: list[str] | None = Query(None),
    cloud_provider: str | None = Query(None),
    resource_type: str | None = Query(None),
    search: str | None = Query(None),
):
    filters = MisconfigFilter(
        severity=severity, source=source, status=status, category=category,
        cloud_provider=cloud_provider, resource_type=resource_type, search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_misconfigurations(db, user.tenant_id, filters, pagination)


@router.get("/stats", response_model=CSPMDashboardStats)
async def cspm_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    return await get_cspm_stats(db, user.tenant_id)


@router.get("/{finding_id}", response_model=MisconfigResponse)
async def get_finding(
    finding_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    result = await get_misconfiguration(db, user.tenant_id, finding_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return result


@router.patch("/{finding_id}/status")
async def update_status(
    finding_id: uuid.UUID,
    body: MisconfigStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    updated = await update_misconfig_status(db, user.tenant_id, finding_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {"message": "Status updated"}


@router.post("/bulk-status")
async def bulk_status(
    body: BulkMisconfigStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    count = await bulk_update_misconfig_status(db, user.tenant_id, body)
    return {"message": f"Updated {count} findings", "count": count}
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: CrowdStrike connector
# ══════════════════════════════════════════════

cat > backend/app/connectors/base.py << 'FILEEOF'
"""Abstract base class for all vulnerability/CSPM connectors."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NormalizedVulnerability:
    """Normalized vulnerability finding from any source."""
    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: float | None
    severity: str
    exploit_available: bool = False
    cisa_kev: bool = False
    source_vuln_id: str | None = None
    affected_product: str | None = None
    affected_version: str | None = None
    fixed_version: str | None = None
    remediation_info: str | None = None
    hostname: str | None = None
    ip_addresses: list[str] = field(default_factory=list)
    os_name: str | None = None
    os_version: str | None = None
    asset_type: str = "ENDPOINT"


@dataclass
class NormalizedMisconfiguration:
    """Normalized CSPM misconfiguration from any source."""
    rule_id: str
    rule_name: str
    rule_description: str | None = None
    category: str = "OTHER"
    severity: str = "MEDIUM"
    frameworks: list[str] = field(default_factory=list)
    resource_id: str = ""
    resource_name: str | None = None
    resource_type: str | None = None
    resource_region: str | None = None
    cloud_provider: str | None = None
    cloud_account_id: str | None = None
    cloud_account_name: str | None = None
    source_finding_id: str | None = None
    remediation_info: str | None = None
    remediation_url: str | None = None
    details: dict | None = None


class BaseConnector(abc.ABC):
    """Abstract connector that all integrations must implement."""

    source_name: str

    @abc.abstractmethod
    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Authenticate with the vendor API. Returns True on success."""
        ...

    @abc.abstractmethod
    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch and normalize vulnerability findings."""
        ...

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch and normalize CSPM findings. Override if supported."""
        return []
FILEEOF

cat > backend/app/connectors/crowdstrike.py << 'FILEEOF'
"""CrowdStrike Falcon Spotlight + CSPM connector."""

from __future__ import annotations

import httpx
import structlog

from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability

logger = structlog.get_logger()

# Severity mapping
CS_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "informational": "INFO",
    "none": "INFO",
}

# CSPM category mapping from CrowdStrike policy types
CS_CSPM_CATEGORY_MAP = {
    "IAM": "IAM",
    "Network": "NETWORK",
    "Encryption": "ENCRYPTION",
    "Logging": "LOGGING",
    "Storage": "STORAGE",
    "Compute": "COMPUTE",
    "Database": "DATABASE",
    "Container": "CONTAINER",
    "Secrets": "SECRETS",
}


class CrowdStrikeConnector(BaseConnector):
    source_name = "CROWDSTRIKE"

    def __init__(self):
        self.base_url: str = "https://api.crowdstrike.com"
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Get OAuth2 token from CrowdStrike."""
        self.base_url = config.get("base_url", credentials.get("base_url", self.base_url))
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

        try:
            resp = await self.client.post(
                "/oauth2/token",
                data={
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
            if resp.status_code == 201:
                self.access_token = resp.json().get("access_token")
                logger.info("crowdstrike_auth_success")
                return True
            else:
                logger.error("crowdstrike_auth_failed", status=resp.status_code)
                return False
        except Exception as e:
            logger.error("crowdstrike_auth_error", error=str(e))
            return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def fetch_vulnerabilities(self) -> list[NormalizedVulnerability]:
        """Fetch vulnerabilities from CrowdStrike Spotlight."""
        if not self.client or not self.access_token:
            return []

        all_vulns: list[NormalizedVulnerability] = []
        after = None
        page = 0

        while True:
            params = {
                "filter": "status:'open'",
                "limit": 400,
                "facets": "cve",
            }
            if after:
                params["after"] = after

            try:
                resp = await self.client.get(
                    "/spotlight/combined/vulnerabilities/v1",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("crowdstrike_vuln_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                cve = item.get("cve", {})
                host = item.get("host_info", {})
                app_info = item.get("app", {})
                remediation = item.get("remediation", {})

                severity_raw = cve.get("base_score_severity", "").lower()
                severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

                vuln = NormalizedVulnerability(
                    cve_id=item.get("cve", {}).get("id"),
                    vulnerability_name=cve.get("description", "")[:500] if cve.get("description") else None,
                    cvss_v3_score=cve.get("base_score"),
                    severity=severity,
                    exploit_available=bool(cve.get("exploit_status")),
                    source_vuln_id=item.get("id"),
                    affected_product=app_info.get("product_name_version"),
                    hostname=host.get("hostname"),
                    ip_addresses=[host.get("local_ip")] if host.get("local_ip") else [],
                    os_name=host.get("os_version"),
                    remediation_info=remediation.get("action"),
                )
                all_vulns.append(vuln)

            # Pagination
            meta = data.get("meta", {}).get("pagination", {})
            after = meta.get("after")
            if not after or len(resources) < 400:
                break
            page += 1

        logger.info("crowdstrike_vulns_fetched", count=len(all_vulns))
        return all_vulns

    async def fetch_misconfigurations(self) -> list[NormalizedMisconfiguration]:
        """Fetch CSPM policy violations from CrowdStrike Horizon."""
        if not self.client or not self.access_token:
            return []

        all_findings: list[NormalizedMisconfiguration] = []
        next_token = None
        page = 0

        while True:
            params = {
                "filter": "status:'fail'",
                "limit": 500,
            }
            if next_token:
                params["next_token"] = next_token

            try:
                resp = await self.client.get(
                    "/detects/entities/iom/v2",
                    headers=self._headers(),
                    params=params,
                )

                # CSPM API may not be available — gracefully handle
                if resp.status_code == 403:
                    logger.info("crowdstrike_cspm_not_licensed")
                    break
                if resp.status_code == 404:
                    logger.info("crowdstrike_cspm_endpoint_not_found")
                    break

                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError:
                break
            except Exception as e:
                logger.error("crowdstrike_cspm_fetch_error", page=page, error=str(e))
                break

            resources = data.get("resources", [])
            if not resources:
                break

            for item in resources:
                policy = item.get("policy_statement", "")
                severity_raw = item.get("severity", "medium").lower()
                severity = CS_SEVERITY_MAP.get(severity_raw, "MEDIUM")

                category_raw = item.get("policy_type", "Other")
                category = CS_CSPM_CATEGORY_MAP.get(category_raw, "OTHER")

                cloud = item.get("cloud_provider", "").upper()
                if cloud not in ("AWS", "AZURE", "GCP"):
                    cloud = None

                finding = NormalizedMisconfiguration(
                    rule_id=item.get("policy_id", ""),
                    rule_name=item.get("policy_statement", "Unknown policy")[:500],
                    rule_description=item.get("policy_description"),
                    category=category,
                    severity=severity,
                    frameworks=item.get("benchmark", []),
                    resource_id=item.get("resource_id", ""),
                    resource_name=item.get("resource_name"),
                    resource_type=item.get("resource_type"),
                    resource_region=item.get("region"),
                    cloud_provider=cloud,
                    cloud_account_id=item.get("cloud_account_id"),
                    source_finding_id=item.get("id"),
                    remediation_info=item.get("remediation"),
                )
                all_findings.append(finding)

            meta = data.get("meta", {}).get("pagination", {})
            next_token = meta.get("next_token")
            if not next_token or len(resources) < 500:
                break
            page += 1

        logger.info("crowdstrike_cspm_fetched", count=len(all_findings))
        return all_findings

    async def close(self):
        if self.client:
            await self.client.aclose()
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Sync orchestrator
# ══════════════════════════════════════════════

cat > backend/app/connectors/sync.py << 'FILEEOF'
"""Sync orchestrator — runs connectors and persists normalized data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability
from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.service import get_decrypted_credentials
from app.cspm.models import Misconfiguration
from app.ticketing.models import ConnectorConfig, SyncLog
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

CONNECTOR_CLASSES: dict[str, type[BaseConnector]] = {
    "CROWDSTRIKE": CrowdStrikeConnector,
}


async def run_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a full sync for a connector."""
    now = datetime.now(timezone.utc)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING",
        started_at=now,
    )
    db.add(log)
    await db.flush()

    connector_cls = CONNECTOR_CLASSES.get(connector_config.connector_type)
    if not connector_cls:
        log.status = "FAILED"
        log.error_message = f"Unknown connector type: {connector_config.connector_type}"
        log.finished_at = datetime.now(timezone.utc)
        return log

    connector = connector_cls()
    credentials = get_decrypted_credentials(connector_config)

    try:
        # Authenticate
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "Authentication failed"
            log.finished_at = datetime.now(timezone.utc)
            return log

        # Fetch vulnerabilities
        vulns = await connector.fetch_vulnerabilities()
        vuln_created = 0
        vuln_updated = 0

        for v in vulns:
            asset = await _upsert_asset(db, connector_config.tenant_id, v, connector_config.connector_type)
            created = await _upsert_vulnerability(db, connector_config.tenant_id, v, asset.id, connector_config.connector_type)
            if created:
                vuln_created += 1
            else:
                vuln_updated += 1

        # Fetch CSPM misconfigurations
        misconfigs = await connector.fetch_misconfigurations()
        misconfig_created = 0

        for m in misconfigs:
            created = await _upsert_misconfiguration(db, connector_config.tenant_id, m, connector_config.connector_type)
            if created:
                misconfig_created += 1

        log.status = "SUCCESS"
        log.records_fetched = len(vulns) + len(misconfigs)
        log.records_created = vuln_created + misconfig_created
        log.records_updated = vuln_updated
        log.details = {
            "vulns_fetched": len(vulns),
            "vulns_created": vuln_created,
            "vulns_updated": vuln_updated,
            "misconfigs_fetched": len(misconfigs),
            "misconfigs_created": misconfig_created,
        }

        # Update connector metadata
        connector_config.last_sync_at = datetime.now(timezone.utc)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = log.records_fetched

    except Exception as e:
        logger.error("sync_error", connector=connector_config.connector_type, error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(timezone.utc)
        if hasattr(connector, "close"):
            await connector.close()

    return log


async def _upsert_asset(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, source: str,
) -> Asset:
    """Find or create an asset from a vulnerability finding."""
    hostname = (v.hostname or "unknown").lower().strip()

    result = await db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname)
    )
    asset = result.scalar_one_or_none()

    if asset is None:
        asset = Asset(
            tenant_id=tenant_id,
            hostname=hostname,
            ip_addresses=v.ip_addresses,
            os_name=v.os_name,
            os_version=v.os_version,
            asset_type=v.asset_type,
            seen_by_sources=[source],
        )
        db.add(asset)
        await db.flush()
    else:
        sources = asset.seen_by_sources or []
        if source not in sources:
            asset.seen_by_sources = sources + [source]

    return asset


async def _upsert_vulnerability(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability,
    asset_id: uuid.UUID, source: str,
) -> bool:
    """Upsert a vulnerability. Returns True if created, False if updated."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.cve_id == v.cve_id,
            Vulnerability.asset_id == asset_id,
            Vulnerability.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = v.severity
        existing.exploit_available = v.exploit_available
        return False
    else:
        vuln = Vulnerability(
            tenant_id=tenant_id,
            cve_id=v.cve_id,
            vulnerability_name=v.vulnerability_name,
            cvss_v3_score=v.cvss_v3_score,
            severity=v.severity,
            exploit_available=v.exploit_available,
            cisa_kev=v.cisa_kev,
            asset_id=asset_id,
            source=source,
            source_vuln_id=v.source_vuln_id,
            affected_product=v.affected_product,
            affected_version=v.affected_version,
            fixed_version=v.fixed_version,
            remediation_info=v.remediation_info,
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
        )
        db.add(vuln)
        await db.flush()
        return True


async def _upsert_misconfiguration(
    db: AsyncSession, tenant_id: uuid.UUID, m: NormalizedMisconfiguration, source: str,
) -> bool:
    """Upsert a misconfiguration. Returns True if created."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Misconfiguration).where(
            Misconfiguration.tenant_id == tenant_id,
            Misconfiguration.rule_id == m.rule_id,
            Misconfiguration.resource_id == m.resource_id,
            Misconfiguration.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = m.severity
        return False
    else:
        misconfig = Misconfiguration(
            tenant_id=tenant_id,
            rule_id=m.rule_id,
            rule_name=m.rule_name,
            rule_description=m.rule_description,
            category=m.category,
            severity=m.severity,
            frameworks=m.frameworks,
            resource_id=m.resource_id,
            resource_name=m.resource_name,
            resource_type=m.resource_type,
            resource_region=m.resource_region,
            cloud_provider=m.cloud_provider,
            cloud_account_id=m.cloud_account_id,
            cloud_account_name=m.cloud_account_name,
            source=source,
            source_finding_id=m.source_finding_id,
            remediation_info=m.remediation_info,
            remediation_url=m.remediation_url,
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
            details=m.details,
        )
        db.add(misconfig)
        await db.flush()
        return True
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Add sync trigger endpoint to connector router
# ══════════════════════════════════════════════

cat >> backend/app/connectors/router.py << 'FILEEOF'


@router.post("/{connector_id}/sync")
async def trigger_sync(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Trigger a manual sync for a connector. Requires Admin."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig
    from app.connectors.sync import run_sync

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    log = await run_sync(db, connector)
    await db.commit()

    return {
        "status": log.status,
        "records_fetched": log.records_fetched,
        "records_created": log.records_created,
        "records_updated": log.records_updated,
        "details": log.details,
        "error": log.error_message,
    }
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Register CSPM router in main.py
# ══════════════════════════════════════════════

cat > backend/app/main.py << 'FILEEOF'
"""GetVul API — entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.vulnerabilities.router import router as vuln_router
from app.assets.router import router as asset_router
from app.tenants.router import router as tenant_router
from app.connectors.router import router as connector_router
from app.cspm.router import router as cspm_router
from app.config import settings

app = FastAPI(
    title="GetVul API",
    description="Unified Vulnerability Aggregation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else ["https://*.getvul.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])
app.include_router(connector_router, prefix="/api/v1/connectors", tags=["Connectors"])
app.include_router(cspm_router, prefix="/api/v1/cspm", tags=["CSPM"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}


if settings.environment == "development":
    from app.db.session import get_db
    from app.seed import seed_database
    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    @app.post("/dev/seed", tags=["Dev"])
    async def seed(db: AsyncSession = Depends(get_db)):
        return await seed_database(db)
FILEEOF

# ══════════════════════════════════════════════
#  BACKEND: Add CSPM sample data to seed
# ══════════════════════════════════════════════

cat >> backend/app/seed.py << 'PYEOF'


# ── CSPM Sample Data ──

SAMPLE_MISCONFIGS = [
    ("CIS-1.2.1", "S3 bucket without encryption", "ENCRYPTION", "HIGH", "aws_s3_bucket", "AWS"),
    ("CIS-1.3.5", "Public S3 bucket ACL", "STORAGE", "CRITICAL", "aws_s3_bucket", "AWS"),
    ("CIS-2.1.1", "CloudTrail not enabled", "LOGGING", "HIGH", "aws_cloudtrail", "AWS"),
    ("CIS-3.4.2", "Security group allows 0.0.0.0/0 ingress on port 22", "NETWORK", "CRITICAL", "aws_security_group", "AWS"),
    ("CIS-1.4.1", "Root account has active access keys", "IAM", "CRITICAL", "aws_iam_user", "AWS"),
    ("CIS-1.5.3", "MFA not enabled for IAM users", "IAM", "HIGH", "aws_iam_user", "AWS"),
    ("CIS-4.1.1", "EBS volumes not encrypted", "ENCRYPTION", "MEDIUM", "aws_ebs_volume", "AWS"),
    ("CIS-2.2.1", "RDS instance publicly accessible", "DATABASE", "CRITICAL", "aws_rds_instance", "AWS"),
    ("AZ-1.1.1", "Storage account allows public blob access", "STORAGE", "HIGH", "azure_storage_account", "AZURE"),
    ("AZ-2.1.3", "NSG allows inbound from any source", "NETWORK", "CRITICAL", "azure_nsg", "AZURE"),
    ("AZ-3.1.1", "Key Vault soft delete not enabled", "ENCRYPTION", "MEDIUM", "azure_key_vault", "AZURE"),
    ("AZ-4.1.2", "SQL Server auditing disabled", "DATABASE", "HIGH", "azure_sql_server", "AZURE"),
    ("GCP-1.1.1", "Default service account used", "IAM", "HIGH", "gcp_compute_instance", "GCP"),
    ("GCP-2.1.1", "Firewall rule allows 0.0.0.0/0", "NETWORK", "CRITICAL", "gcp_firewall_rule", "GCP"),
    ("WIZ-SEC-01", "Container running as root", "CONTAINER", "HIGH", "k8s_pod", "AWS"),
    ("WIZ-SEC-02", "Secret exposed in environment variable", "SECRETS", "CRITICAL", "k8s_deployment", "AWS"),
    ("CS-CSPM-101", "Unrotated access keys older than 90 days", "IAM", "MEDIUM", "aws_iam_access_key", "AWS"),
    ("CS-CSPM-202", "VPC flow logs disabled", "LOGGING", "MEDIUM", "aws_vpc", "AWS"),
    ("DEF-CLOUD-01", "VM disk encryption disabled", "ENCRYPTION", "HIGH", "azure_vm", "AZURE"),
    ("DEF-CLOUD-02", "Web app does not use HTTPS only", "NETWORK", "MEDIUM", "azure_web_app", "AZURE"),
]

CSPM_SOURCES = ["CROWDSTRIKE", "WIZ", "DEFENDER"]
CSPM_FRAMEWORKS = [
    ["CIS AWS 1.5"], ["CIS AWS 1.5", "SOC2"], ["PCI-DSS 3.2.1"],
    ["CIS Azure 2.0"], ["HIPAA"], ["SOC2", "ISO 27001"], ["NIST 800-53"],
]
CSPM_REGIONS = [
    "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
    "eastus", "westeurope", "us-central1", "asia-east1",
]
CSPM_ACCOUNTS = [
    ("123456789012", "prod-account"), ("987654321098", "dev-account"),
    ("sub-abc-123", "Azure Prod"), ("sub-def-456", "Azure Dev"),
    ("proj-main-001", "GCP Main"),
]


async def seed_cspm_data(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Seed CSPM misconfiguration data."""
    from app.cspm.models import Misconfiguration

    count = 0
    now = datetime.now(timezone.utc)

    for _ in range(200):
        rule_id, rule_name, category, severity, res_type, cloud = random.choice(SAMPLE_MISCONFIGS)
        source = random.choice(CSPM_SOURCES)
        account = random.choice(CSPM_ACCOUNTS)
        region = random.choice(CSPM_REGIONS)
        frameworks = random.choice(CSPM_FRAMEWORKS)
        days_ago = random.randint(1, 120)
        status = random.choice(["OPEN", "OPEN", "OPEN", "REMEDIATED", "SUPPRESSED"])

        resource_id = f"arn:{cloud.lower()}:{res_type}:{region}:{account[0]}:{uuid.uuid4().hex[:8]}"

        m = Misconfiguration(
            tenant_id=tenant_id,
            rule_id=rule_id,
            rule_name=rule_name,
            category=category,
            severity=severity,
            frameworks=frameworks,
            resource_id=resource_id,
            resource_name=f"{res_type}-{uuid.uuid4().hex[:6]}",
            resource_type=res_type,
            resource_region=region,
            cloud_provider=cloud,
            cloud_account_id=account[0],
            cloud_account_name=account[1],
            source=source,
            source_finding_id=f"{source}-{uuid.uuid4().hex[:8]}",
            status=status,
            first_detected_at=now - timedelta(days=days_ago),
            last_seen_at=now - timedelta(days=random.randint(0, min(3, days_ago))),
            remediated_at=(now - timedelta(days=random.randint(0, days_ago // 2))) if status == "REMEDIATED" else None,
        )

        try:
            async with db.begin_nested():
                db.add(m)
                await db.flush()
            count += 1
        except Exception:
            continue

    await db.commit()
    return count
PYEOF

# Update seed_database to also seed CSPM data
# We need to add the call at the end of seed_database
python3 -c "
content = open('backend/app/seed.py').read()
# Find the return statement in seed_database and add CSPM seeding before it
old = '''    return {
        \"message\": \"Database seeded\",'''
new = '''    # Seed CSPM data
    cspm_count = await seed_cspm_data(db, tenant.id)

    return {
        \"message\": \"Database seeded\",'''
content = content.replace(old, new)
# Add cspm count to return
old2 = '''        \"vulnerabilities_skipped\": skipped,
    }'''
new2 = '''        \"vulnerabilities_skipped\": skipped,
        \"misconfigurations_created\": cspm_count,
    }'''
content = content.replace(old2, new2)
open('backend/app/seed.py', 'w').write(content)
"

# ══════════════════════════════════════════════
#  FRONTEND: CSPM types
# ══════════════════════════════════════════════

cat > frontend/src/types/cspm.ts << 'FILEEOF'
export interface MisconfigSummary {
  id: string;
  rule_id: string;
  rule_name: string;
  category: string;
  severity: string;
  source: string;
  status: string;
  resource_id: string;
  resource_name: string | null;
  resource_type: string | null;
  cloud_provider: string | null;
  first_detected_at: string;
  last_seen_at: string;
}

export interface CSPMDashboardStats {
  total_findings: number;
  open_findings: number;
  by_severity: { severity: string; count: number }[];
  by_category: { category: string; count: number }[];
  by_source: { source: string; count: number }[];
  by_cloud_provider: { provider: string; count: number }[];
  compliance_pass_rate: number | null;
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: CSPM Dashboard + Findings page
# ══════════════════════════════════════════════

mkdir -p frontend/src/app/dashboard/cspm

cat > frontend/src/app/dashboard/cspm/page.tsx << 'FILEEOF'
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Cloud,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Search,
  X,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import Pagination from "@/components/ui/Pagination";
import { cn } from "@/lib/utils";
import type { MisconfigSummary, CSPMDashboardStats } from "@/types/cspm";

interface PaginatedFindings {
  items: MisconfigSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const CATEGORIES = ["IAM", "NETWORK", "ENCRYPTION", "LOGGING", "STORAGE", "COMPUTE", "DATABASE", "CONTAINER", "SECRETS"];
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SOURCES = ["CROWDSTRIKE", "WIZ", "DEFENDER"];
const CLOUDS = ["AWS", "AZURE", "GCP"];

const categoryIcons: Record<string, string> = {
  IAM: "👤", NETWORK: "🌐", ENCRYPTION: "🔐", LOGGING: "📋",
  STORAGE: "💾", COMPUTE: "🖥️", DATABASE: "🗄️", CONTAINER: "📦", SECRETS: "🔑",
};

const sevColors: Record<string, string> = {
  CRITICAL: "border-red-500/40 bg-red-500/10 text-red-400",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-400",
  MEDIUM: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400",
  LOW: "border-blue-500/40 bg-blue-500/10 text-blue-400",
};

export default function CSPMPage() {
  const [stats, setStats] = useState<CSPMDashboardStats | null>(null);
  const [data, setData] = useState<PaginatedFindings | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Filters
  const [search, setSearch] = useState("");
  const [selSeverity, setSelSeverity] = useState<string[]>([]);
  const [selCategory, setSelCategory] = useState<string[]>([]);
  const [selSource, setSelSource] = useState<string[]>([]);
  const [selCloud, setSelCloud] = useState<string | null>(null);

  const toggle = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];

  const loadStats = useCallback(async () => {
    try {
      const s = await api<CSPMDashboardStats>("/api/v1/cspm/stats");
      setStats(s);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadFindings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "25");
      if (search) params.set("search", search);
      selSeverity.forEach((s) => params.append("severity", s));
      selCategory.forEach((s) => params.append("category", s));
      selSource.forEach((s) => params.append("source", s));
      if (selCloud) params.set("cloud_provider", selCloud);

      const d = await api<PaginatedFindings>(`/api/v1/cspm?${params.toString()}`);
      setData(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, search, selSeverity, selCategory, selSource, selCloud]);

  useEffect(() => { loadStats(); }, [loadStats]);

  useEffect(() => {
    const t = setTimeout(loadFindings, 300);
    return () => clearTimeout(t);
  }, [loadFindings]);

  useEffect(() => { setPage(1); }, [search, selSeverity, selCategory, selSource, selCloud]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cloud className="h-6 w-6 text-sky-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Cloud Security Posture</h1>
            <p className="text-sm text-gray-400">Misconfigurations across cloud environments</p>
          </div>
        </div>
        <button onClick={() => { loadStats(); loadFindings(); }} className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={<Cloud className="h-5 w-5 text-sky-400" />} label="Total Findings" value={stats.total_findings.toLocaleString()} />
            <StatCard icon={<AlertTriangle className="h-5 w-5 text-orange-400" />} label="Open" value={stats.open_findings.toLocaleString()} />
            <StatCard icon={<ShieldCheck className="h-5 w-5 text-emerald-400" />} label="Compliance Pass Rate" value={stats.compliance_pass_rate !== null ? `${stats.compliance_pass_rate}%` : "N/A"} />
            <StatCard
              icon={<Cloud className="h-5 w-5 text-purple-400" />}
              label="Cloud Providers"
              value={stats.by_cloud_provider.length.toString()}
            />
          </div>

          {/* Category breakdown */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h2 className="mb-4 text-sm font-medium text-gray-400">By Category</h2>
              <div className="space-y-2.5">
                {stats.by_category.sort((a, b) => b.count - a.count).map((c) => (
                  <div key={c.category} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-gray-300">
                      <span>{categoryIcons[c.category] || "📌"}</span>
                      {c.category}
                    </span>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-28 overflow-hidden rounded-full bg-gray-800">
                        <div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.max(3, (c.count / stats.total_findings) * 100)}%` }} />
                      </div>
                      <span className="w-12 text-right text-sm font-medium text-white">{c.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h2 className="mb-4 text-sm font-medium text-gray-400">By Severity</h2>
              <div className="space-y-2.5">
                {stats.by_severity.map((s) => (
                  <div key={s.severity} className="flex items-center justify-between">
                    <SeverityBadge severity={s.severity} />
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-28 overflow-hidden rounded-full bg-gray-800">
                        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(3, (s.count / stats.total_findings) * 100)}%` }} />
                      </div>
                      <span className="w-12 text-right text-sm font-medium text-white">{s.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search rule, resource..." className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"><X className="h-4 w-4" /></button>}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500"><Filter className="h-3.5 w-3.5" />Filters</div>

          <div className="flex gap-1.5">
            {SEVERITIES.map((s) => (
              <button key={s} onClick={() => setSelSeverity(toggle(selSeverity, s))} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selSeverity.includes(s) ? sevColors[s] : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{s}</button>
            ))}
          </div>
          <div className="h-4 w-px bg-gray-700" />
          <div className="flex gap-1.5">
            {CATEGORIES.map((c) => (
              <button key={c} onClick={() => setSelCategory(toggle(selCategory, c))} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selCategory.includes(c) ? "border-sky-500/40 bg-sky-500/15 text-sky-400" : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{categoryIcons[c] || ""} {c}</button>
            ))}
          </div>
          <div className="h-4 w-px bg-gray-700" />
          <div className="flex gap-1.5">
            {CLOUDS.map((c) => (
              <button key={c} onClick={() => setSelCloud(selCloud === c ? null : c)} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selCloud === c ? "border-purple-500/40 bg-purple-500/15 text-purple-400" : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{c}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      {loading && !data ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Rule</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Category</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Resource</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Cloud</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Detected</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(data?.items || []).map((m) => (
                  <tr key={m.id} className="transition-colors hover:bg-gray-800/30">
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-xs text-gray-400">{m.rule_id}</div>
                      <div className="max-w-[250px] truncate text-sm text-white">{m.rule_name}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1 text-xs text-gray-300">
                        {categoryIcons[m.category] || "📌"} {m.category}
                      </span>
                    </td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={m.severity} /></td>
                    <td className="px-3 py-2.5"><SourceBadge source={m.source} /></td>
                    <td className="px-3 py-2.5"><StatusBadge status={m.status} /></td>
                    <td className="max-w-[200px] truncate px-3 py-2.5 text-xs text-gray-400">{m.resource_name || m.resource_id}</td>
                    <td className="px-3 py-2.5">
                      {m.cloud_provider && (
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-300">{m.cloud_provider}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-500">{new Date(m.first_detected_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && <div className="py-12 text-center text-gray-500">No findings match your filters</div>}
          </div>
          {data && data.total_pages > 1 && <Pagination page={data.page} totalPages={data.total_pages} total={data.total} pageSize={data.page_size} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">{icon}<span className="text-sm text-gray-400">{label}</span></div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Add CSPM to sidebar
# ══════════════════════════════════════════════

cat > frontend/src/components/layout/Sidebar.tsx << 'FILEEOF'
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bug,
  Cloud,
  Server,
  Plug,
  Ticket,
  Settings,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/vulnerabilities", label: "Vulnerabilities", icon: Bug },
  { href: "/dashboard/cspm", label: "Cloud Posture", icon: Cloud },
  { href: "/dashboard/assets", label: "Assets", icon: Server },
  { href: "/dashboard/connectors", label: "Connectors", icon: Plug },
  { href: "/dashboard/tickets", label: "Tickets", icon: Ticket },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-gray-800 bg-gray-950">
      <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-6">
        <Shield className="h-6 w-6 text-indigo-500" />
        <span className="text-lg font-bold text-white">GetVul</span>
      </div>
      <nav className="mt-4 space-y-1 px-3">
        {nav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-indigo-600/20 text-indigo-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  REBUILD & TEST
# ══════════════════════════════════════════════

echo "🔄 Rebuilding..."
docker compose down -v
docker compose build --no-cache
docker compose up -d

echo "⏳ Waiting (35s)..."
sleep 35

echo "🔍 Seeding (vulns + CSPM)..."
curl -s -X POST http://localhost:8000/dev/seed | python3 -m json.tool 2>/dev/null || curl -s -X POST http://localhost:8000/dev/seed
echo ""

echo "🔍 Testing CSPM stats..."
curl -s "http://localhost:8000/api/v1/cspm/stats" -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || curl -s "http://localhost:8000/api/v1/cspm/stats" -H "Authorization: Bearer dev-token"
echo ""

echo "🔍 Testing CSPM findings list..."
curl -s "http://localhost:8000/api/v1/cspm?page_size=3" -H "Authorization: Bearer dev-token" | head -c 500
echo ""

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

echo ""
echo "📝 Committing..."

git add -A
git commit -m "feat: CSPM dashboard + CrowdStrike connector

Backend:
- Misconfigurations table + migration (CSPM data model)
- CSPM API: list, filter, stats, status update, bulk actions
- Base connector interface (vulns + misconfigurations)
- CrowdStrike connector: Spotlight vulns + Horizon CSPM
- Sync orchestrator: upsert assets, vulns, misconfigs
- Manual sync trigger endpoint
- CSPM sample data in seeder (200 findings)

Frontend:
- Cloud Posture page in sidebar navigation
- CSPM dashboard: stats cards, category breakdown, severity bars
- CSPM findings explorer: filterable table with category, severity,
  source, cloud provider, and text search
- Pagination support

API Endpoints:
- GET /api/v1/cspm — List misconfigurations (filtered + paginated)
- GET /api/v1/cspm/stats — CSPM dashboard stats
- GET /api/v1/cspm/{id} — Finding detail
- PATCH /api/v1/cspm/{id}/status — Update status
- POST /api/v1/cspm/bulk-status — Bulk update
- POST /api/v1/connectors/{id}/sync — Trigger manual sync"

git push -u origin feat/cspm-crowdstrike

gh pr create \
  --title "feat: CSPM dashboard + CrowdStrike connector" \
  --body "Adds Cloud Security Posture Management and the first real connector.

## CSPM
- New \`misconfigurations\` table for policy violations
- Categories: IAM, Network, Encryption, Logging, Storage, Compute, Database, Container, Secrets
- Full API with filters, stats, bulk actions
- Dashboard with category/severity breakdown and compliance pass rate
- Findings explorer with cloud provider filter

## CrowdStrike Connector
- OAuth2 authentication
- Spotlight vulnerability ingestion with pagination
- Horizon CSPM misconfiguration ingestion
- Sync orchestrator with asset upsert + deduplication
- Manual sync trigger via API

## How to Test
\`\`\`bash
make dev
# Open http://localhost:3000/dashboard → Seed data
# Navigate to Cloud Posture page
\`\`\`" \
  --base main

echo ""
echo "✅ Done! PR created."
echo ""
echo "   CSPM Dashboard: http://localhost:3000/dashboard/cspm"
echo "   CSPM API: http://localhost:8000/docs#/CSPM"
echo ""
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
