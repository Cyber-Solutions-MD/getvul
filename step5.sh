#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔌 Building core API endpoints..."

# Make sure we're on main and up to date
git checkout main
git pull

# Create feature branch
git checkout -b feat/core-endpoints

# ══════════════════════════════════════════════
#  backend/app/pagination.py — Shared Pagination
# ══════════════════════════════════════════════

cat > backend/app/pagination.py << 'FILEEOF'
"""Shared pagination utilities."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""

    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=200, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PaginationParams) -> "PaginatedResponse[T]":
        total_pages = max(1, -(-total // params.page_size))  # ceiling division
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
        )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/vulnerabilities/schemas.py
# ══════════════════════════════════════════════

cat > backend/app/vulnerabilities/schemas.py << 'FILEEOF'
"""Pydantic schemas for vulnerability endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Responses ──


class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cve_id: str | None
    vulnerability_name: str | None
    cvss_v3_score: Decimal | None
    cvss_v3_vector: str | None
    severity: str
    epss_score: Decimal | None
    exploit_available: bool
    cisa_kev: bool
    asset_id: uuid.UUID | None
    source: str
    source_vuln_id: str | None
    affected_product: str | None
    affected_version: str | None
    fixed_version: str | None
    remediation_info: str | None
    status: str
    first_detected_at: datetime
    last_seen_at: datetime
    remediated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Joined fields (optional, populated on detail view)
    asset_hostname: str | None = None
    correlation_sources_count: int | None = None

    model_config = {"from_attributes": True}


class VulnerabilitySummary(BaseModel):
    """Lightweight vuln for list views."""

    id: uuid.UUID
    cve_id: str | None
    severity: str
    source: str
    status: str
    exploit_available: bool
    cisa_kev: bool
    affected_product: str | None
    asset_id: uuid.UUID | None
    asset_hostname: str | None = None
    first_detected_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


# ── Filters ──


class VulnerabilityFilter(BaseModel):
    """Filter parameters for vulnerability queries."""

    severity: list[str] | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    cve_id: str | None = None
    exploit_available: bool | None = None
    cisa_kev: bool | None = None
    asset_id: uuid.UUID | None = None
    search: str | None = Field(None, description="Search CVE ID or product name")
    age_days_min: int | None = Field(None, ge=0)
    age_days_max: int | None = Field(None, ge=0)


# ── Requests ──


class VulnerabilityStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


class BulkStatusUpdate(BaseModel):
    vulnerability_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    status: str = Field(..., pattern="^(OPEN|IN_PROGRESS|REMEDIATED|SUPPRESSED|FALSE_POSITIVE)$")


# ── Dashboard Stats ──


class SeverityCount(BaseModel):
    severity: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int


class DashboardStats(BaseModel):
    total_vulnerabilities: int
    open_vulnerabilities: int
    by_severity: list[SeverityCount]
    by_source: list[SourceCount]
    exploitable_count: int
    cisa_kev_count: int
    correlated_cves: int
    mttr_days: float | None = None
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/vulnerabilities/service.py
# ══════════════════════════════════════════════

cat > backend/app/vulnerabilities/service.py << 'FILEEOF'
"""Vulnerability business logic and database queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, and_, case, distinct, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.assets.models import Asset
from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation
from app.vulnerabilities.schemas import (
    BulkStatusUpdate,
    DashboardStats,
    SeverityCount,
    SourceCount,
    VulnerabilityFilter,
    VulnerabilityResponse,
    VulnerabilitySummary,
)


def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: VulnerabilityFilter) -> Select:
    """Apply filter conditions to a vulnerability query."""
    query = query.where(Vulnerability.tenant_id == tenant_id)

    if filters.severity:
        query = query.where(Vulnerability.severity.in_(filters.severity))
    if filters.source:
        query = query.where(Vulnerability.source.in_(filters.source))
    if filters.status:
        query = query.where(Vulnerability.status.in_(filters.status))
    if filters.cve_id:
        query = query.where(Vulnerability.cve_id.ilike(f"%{filters.cve_id}%"))
    if filters.exploit_available is not None:
        query = query.where(Vulnerability.exploit_available == filters.exploit_available)
    if filters.cisa_kev is not None:
        query = query.where(Vulnerability.cisa_kev == filters.cisa_kev)
    if filters.asset_id:
        query = query.where(Vulnerability.asset_id == filters.asset_id)
    if filters.search:
        query = query.where(
            or_(
                Vulnerability.cve_id.ilike(f"%{filters.search}%"),
                Vulnerability.affected_product.ilike(f"%{filters.search}%"),
                Vulnerability.vulnerability_name.ilike(f"%{filters.search}%"),
            )
        )
    if filters.age_days_min is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=filters.age_days_min)
        query = query.where(Vulnerability.first_detected_at <= cutoff)
    if filters.age_days_max is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=filters.age_days_max)
        query = query.where(Vulnerability.first_detected_at >= cutoff)

    return query


async def list_vulnerabilities(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: VulnerabilityFilter,
    pagination: PaginationParams,
) -> PaginatedResponse[VulnerabilitySummary]:
    """List vulnerabilities with filters and pagination."""

    # Count query
    count_q = _apply_filters(
        select(func.count(Vulnerability.id)), tenant_id, filters,
    )
    total = (await db.execute(count_q)).scalar_one()

    # Data query with optional asset join
    data_q = (
        _apply_filters(select(Vulnerability), tenant_id, filters)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .add_columns(Asset.hostname.label("asset_hostname"))
        .order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 1),
                (Vulnerability.severity == "HIGH", 2),
                (Vulnerability.severity == "MEDIUM", 3),
                (Vulnerability.severity == "LOW", 4),
                else_=5,
            ),
            Vulnerability.last_seen_at.desc(),
        )
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    results = (await db.execute(data_q)).all()

    items = []
    for row in results:
        vuln = row[0] if hasattr(row, "__getitem__") else row.Vulnerability
        hostname = row.asset_hostname if hasattr(row, "asset_hostname") else None
        items.append(
            VulnerabilitySummary(
                id=vuln.id,
                cve_id=vuln.cve_id,
                severity=vuln.severity,
                source=vuln.source,
                status=vuln.status,
                exploit_available=vuln.exploit_available,
                cisa_kev=vuln.cisa_kev,
                affected_product=vuln.affected_product,
                asset_id=vuln.asset_id,
                asset_hostname=hostname,
                first_detected_at=vuln.first_detected_at,
                last_seen_at=vuln.last_seen_at,
            )
        )

    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_vulnerability(
    db: AsyncSession, tenant_id: uuid.UUID, vuln_id: uuid.UUID,
) -> VulnerabilityResponse | None:
    """Get a single vulnerability by ID with asset hostname."""
    query = (
        select(Vulnerability)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .add_columns(Asset.hostname.label("asset_hostname"))
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
    )
    result = (await db.execute(query)).first()
    if result is None:
        return None

    vuln = result[0]
    hostname = result.asset_hostname

    # Get correlation count
    corr_count = None
    if vuln.cve_id and vuln.asset_id:
        corr_q = select(VulnerabilityCorrelation.sources_count).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.cve_id == vuln.cve_id,
            VulnerabilityCorrelation.asset_id == vuln.asset_id,
        )
        corr_result = (await db.execute(corr_q)).scalar_one_or_none()
        corr_count = corr_result

    return VulnerabilityResponse(
        id=vuln.id,
        tenant_id=vuln.tenant_id,
        cve_id=vuln.cve_id,
        vulnerability_name=vuln.vulnerability_name,
        cvss_v3_score=vuln.cvss_v3_score,
        cvss_v3_vector=vuln.cvss_v3_vector,
        severity=vuln.severity,
        epss_score=vuln.epss_score,
        exploit_available=vuln.exploit_available,
        cisa_kev=vuln.cisa_kev,
        asset_id=vuln.asset_id,
        source=vuln.source,
        source_vuln_id=vuln.source_vuln_id,
        affected_product=vuln.affected_product,
        affected_version=vuln.affected_version,
        fixed_version=vuln.fixed_version,
        remediation_info=vuln.remediation_info,
        status=vuln.status,
        first_detected_at=vuln.first_detected_at,
        last_seen_at=vuln.last_seen_at,
        remediated_at=vuln.remediated_at,
        created_at=vuln.created_at,
        updated_at=vuln.updated_at,
        asset_hostname=hostname,
        correlation_sources_count=corr_count,
    )


async def update_vulnerability_status(
    db: AsyncSession, tenant_id: uuid.UUID, vuln_id: uuid.UUID, new_status: str,
) -> bool:
    """Update status of a single vulnerability."""
    now = datetime.now(timezone.utc)
    values: dict = {"status": new_status, "updated_at": now}
    if new_status == "REMEDIATED":
        values["remediated_at"] = now

    result = await db.execute(
        update(Vulnerability)
        .where(Vulnerability.id == vuln_id, Vulnerability.tenant_id == tenant_id)
        .values(**values)
    )
    return result.rowcount > 0


async def bulk_update_status(
    db: AsyncSession, tenant_id: uuid.UUID, body: BulkStatusUpdate,
) -> int:
    """Bulk update status for multiple vulnerabilities."""
    now = datetime.now(timezone.utc)
    values: dict = {"status": body.status, "updated_at": now}
    if body.status == "REMEDIATED":
        values["remediated_at"] = now

    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.id.in_(body.vulnerability_ids),
            Vulnerability.tenant_id == tenant_id,
        )
        .values(**values)
    )
    return result.rowcount


async def get_dashboard_stats(
    db: AsyncSession, tenant_id: uuid.UUID,
) -> DashboardStats:
    """Compute dashboard statistics."""

    # Total and open counts
    total_q = select(func.count(Vulnerability.id)).where(Vulnerability.tenant_id == tenant_id)
    total = (await db.execute(total_q)).scalar_one()

    open_q = total_q.where(Vulnerability.status == "OPEN")
    open_count = (await db.execute(open_q)).scalar_one()

    # By severity
    sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id)
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()
    by_severity = [SeverityCount(severity=r[0], count=r[1]) for r in sev_rows]

    # By source
    src_q = (
        select(Vulnerability.source, func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id)
        .group_by(Vulnerability.source)
    )
    src_rows = (await db.execute(src_q)).all()
    by_source = [SourceCount(source=r[0], count=r[1]) for r in src_rows]

    # Exploitable
    exploit_q = select(func.count(Vulnerability.id)).where(
        Vulnerability.tenant_id == tenant_id, Vulnerability.exploit_available.is_(True),
    )
    exploitable = (await db.execute(exploit_q)).scalar_one()

    # CISA KEV
    kev_q = select(func.count(Vulnerability.id)).where(
        Vulnerability.tenant_id == tenant_id, Vulnerability.cisa_kev.is_(True),
    )
    kev_count = (await db.execute(kev_q)).scalar_one()

    # Correlated CVEs (confirmed by 2+ sources)
    corr_q = select(func.count(VulnerabilityCorrelation.id)).where(
        VulnerabilityCorrelation.tenant_id == tenant_id,
        VulnerabilityCorrelation.sources_count >= 2,
    )
    correlated = (await db.execute(corr_q)).scalar_one()

    # MTTR (mean time to remediate) — for vulns remediated in last 90 days
    mttr_q = select(
        func.avg(
            func.extract("epoch", Vulnerability.remediated_at - Vulnerability.first_detected_at) / 86400
        )
    ).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status == "REMEDIATED",
        Vulnerability.remediated_at >= datetime.now(timezone.utc) - timedelta(days=90),
    )
    mttr = (await db.execute(mttr_q)).scalar_one()

    return DashboardStats(
        total_vulnerabilities=total,
        open_vulnerabilities=open_count,
        by_severity=by_severity,
        by_source=by_source,
        exploitable_count=exploitable,
        cisa_kev_count=kev_count,
        correlated_cves=correlated,
        mttr_days=round(float(mttr), 1) if mttr else None,
    )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/vulnerabilities/router.py
# ══════════════════════════════════════════════

cat > backend/app/vulnerabilities/router.py << 'FILEEOF'
"""Vulnerability API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.schemas import (
    BulkStatusUpdate,
    DashboardStats,
    VulnerabilityFilter,
    VulnerabilityResponse,
    VulnerabilitySummary,
    VulnerabilityStatusUpdate,
)
from app.vulnerabilities.service import (
    bulk_update_status,
    get_dashboard_stats,
    get_vulnerability,
    list_vulnerabilities,
    update_vulnerability_status,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[VulnerabilitySummary])
async def list_vulns(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    cve_id: str | None = Query(None),
    exploit_available: bool | None = Query(None),
    cisa_kev: bool | None = Query(None),
    asset_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    age_days_min: int | None = Query(None, ge=0),
    age_days_max: int | None = Query(None, ge=0),
):
    """List vulnerabilities with filtering and pagination."""
    filters = VulnerabilityFilter(
        severity=severity,
        source=source,
        status=status,
        cve_id=cve_id,
        exploit_available=exploit_available,
        cisa_kev=cisa_kev,
        asset_id=asset_id,
        search=search,
        age_days_min=age_days_min,
        age_days_max=age_days_max,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_vulnerabilities(db, user.tenant_id, filters, pagination)


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get dashboard statistics for the tenant."""
    return await get_dashboard_stats(db, user.tenant_id)


@router.get("/{vuln_id}", response_model=VulnerabilityResponse)
async def get_vuln(
    vuln_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get a single vulnerability with full details."""
    vuln = await get_vulnerability(db, user.tenant_id, vuln_id)
    if vuln is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return vuln


@router.patch("/{vuln_id}/status")
async def update_status(
    vuln_id: uuid.UUID,
    body: VulnerabilityStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Update the status of a vulnerability. Requires Analyst role."""
    updated = await update_vulnerability_status(db, user.tenant_id, vuln_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return {"message": "Status updated", "status": body.status}


@router.post("/bulk-status")
async def bulk_status(
    body: BulkStatusUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Bulk update status for multiple vulnerabilities. Requires Analyst role."""
    count = await bulk_update_status(db, user.tenant_id, body)
    return {"message": f"Updated {count} vulnerabilities", "count": count}
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/assets/schemas.py
# ══════════════════════════════════════════════

cat > backend/app/assets/schemas.py << 'FILEEOF'
"""Pydantic schemas for asset endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    hostname: str | None
    ip_addresses: list | None
    mac_addresses: list | None
    os_name: str | None
    os_version: str | None
    asset_type: str | None
    cloud_provider: str | None
    cloud_resource_id: str | None
    seen_by_sources: list | None
    risk_score: int | None
    created_at: datetime
    updated_at: datetime

    # Computed on detail view
    vuln_counts: dict | None = None

    model_config = {"from_attributes": True}


class AssetSummary(BaseModel):
    id: uuid.UUID
    hostname: str | None
    os_name: str | None
    asset_type: str | None
    cloud_provider: str | None
    seen_by_sources: list | None
    risk_score: int | None
    open_vuln_count: int = 0

    model_config = {"from_attributes": True}


class AssetFilter(BaseModel):
    hostname: str | None = None
    os_name: str | None = None
    asset_type: str | None = None
    cloud_provider: str | None = None
    source: str | None = Field(None, description="Filter by scanner source")
    risk_score_min: int | None = Field(None, ge=0, le=100)
    search: str | None = None
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/assets/service.py
# ══════════════════════════════════════════════

cat > backend/app/assets/service.py << 'FILEEOF'
"""Asset business logic and database queries."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.schemas import AssetFilter, AssetResponse, AssetSummary
from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.models import Vulnerability


def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: AssetFilter) -> Select:
    query = query.where(Asset.tenant_id == tenant_id)

    if filters.hostname:
        query = query.where(Asset.hostname.ilike(f"%{filters.hostname}%"))
    if filters.os_name:
        query = query.where(Asset.os_name.ilike(f"%{filters.os_name}%"))
    if filters.asset_type:
        query = query.where(Asset.asset_type == filters.asset_type)
    if filters.cloud_provider:
        query = query.where(Asset.cloud_provider == filters.cloud_provider)
    if filters.source:
        query = query.where(Asset.seen_by_sources.contains([filters.source]))
    if filters.risk_score_min is not None:
        query = query.where(Asset.risk_score >= filters.risk_score_min)
    if filters.search:
        query = query.where(
            or_(
                Asset.hostname.ilike(f"%{filters.search}%"),
                Asset.os_name.ilike(f"%{filters.search}%"),
            )
        )

    return query


async def list_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: AssetFilter,
    pagination: PaginationParams,
) -> PaginatedResponse[AssetSummary]:
    """List assets with filters, pagination, and open vuln count."""

    count_q = _apply_filters(select(func.count(Asset.id)), tenant_id, filters)
    total = (await db.execute(count_q)).scalar_one()

    # Subquery for open vuln count per asset
    vuln_count_sub = (
        select(
            Vulnerability.asset_id,
            func.count(Vulnerability.id).label("open_vuln_count"),
        )
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "OPEN")
        .group_by(Vulnerability.asset_id)
        .subquery()
    )

    data_q = (
        _apply_filters(select(Asset), tenant_id, filters)
        .outerjoin(vuln_count_sub, Asset.id == vuln_count_sub.c.asset_id)
        .add_columns(func.coalesce(vuln_count_sub.c.open_vuln_count, 0).label("open_vuln_count"))
        .order_by(Asset.risk_score.desc().nullslast(), Asset.hostname.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    results = (await db.execute(data_q)).all()

    items = []
    for row in results:
        asset = row[0]
        open_count = row.open_vuln_count
        items.append(
            AssetSummary(
                id=asset.id,
                hostname=asset.hostname,
                os_name=asset.os_name,
                asset_type=asset.asset_type,
                cloud_provider=asset.cloud_provider,
                seen_by_sources=asset.seen_by_sources,
                risk_score=asset.risk_score,
                open_vuln_count=open_count,
            )
        )

    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_asset(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID,
) -> AssetResponse | None:
    """Get asset detail with vuln counts by severity."""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        return None

    # Vuln counts by severity
    sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(
            Vulnerability.asset_id == asset_id,
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status == "OPEN",
        )
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()
    vuln_counts = {r[0]: r[1] for r in sev_rows}

    return AssetResponse(
        id=asset.id,
        tenant_id=asset.tenant_id,
        hostname=asset.hostname,
        ip_addresses=asset.ip_addresses,
        mac_addresses=asset.mac_addresses,
        os_name=asset.os_name,
        os_version=asset.os_version,
        asset_type=asset.asset_type,
        cloud_provider=asset.cloud_provider,
        cloud_resource_id=asset.cloud_resource_id,
        seen_by_sources=asset.seen_by_sources,
        risk_score=asset.risk_score,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        vuln_counts=vuln_counts,
    )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/assets/router.py
# ══════════════════════════════════════════════

cat > backend/app/assets/router.py << 'FILEEOF'
"""Asset API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.rbac import require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.pagination import PaginatedResponse, PaginationParams
from app.assets.schemas import AssetFilter, AssetResponse, AssetSummary
from app.assets.service import get_asset, list_assets

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AssetSummary])
async def list_all_assets(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    hostname: str | None = Query(None),
    os_name: str | None = Query(None),
    asset_type: str | None = Query(None),
    cloud_provider: str | None = Query(None),
    source: str | None = Query(None),
    risk_score_min: int | None = Query(None, ge=0, le=100),
    search: str | None = Query(None),
):
    """List assets with filtering and pagination."""
    filters = AssetFilter(
        hostname=hostname,
        os_name=os_name,
        asset_type=asset_type,
        cloud_provider=cloud_provider,
        source=source,
        risk_score_min=risk_score_min,
        search=search,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_assets(db, user.tenant_id, filters, pagination)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_single_asset(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get full asset detail with vulnerability counts."""
    asset = await get_asset(db, user.tenant_id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/{asset_id}/vulnerabilities")
async def get_asset_vulns(
    asset_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
):
    """List all vulnerabilities for a specific asset."""
    from app.vulnerabilities.schemas import VulnerabilityFilter
    from app.vulnerabilities.service import list_vulnerabilities

    filters = VulnerabilityFilter(
        asset_id=asset_id,
        severity=severity,
        status=status,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await list_vulnerabilities(db, user.tenant_id, filters, pagination)
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/tenants/schemas.py
# ══════════════════════════════════════════════

cat > backend/app/tenants/schemas.py << 'FILEEOF'
"""Pydantic schemas for tenant and user management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: str | None
    idp_provider: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: str
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/tenants/router.py
# ══════════════════════════════════════════════

cat > backend/app/tenants/router.py << 'FILEEOF'
"""Tenant and user management routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_admin, require_owner
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.tenants.models import Tenant, User
from app.tenants.schemas import TenantResponse, UserResponse, UserRoleUpdate

router = APIRouter()


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(db: DBSession, user: AuthenticatedUser):
    """Get the current user's tenant info."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """List all users in the tenant. Requires Admin role."""
    result = await db.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.email)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Update a user's role. Requires Owner role."""
    if body.role not in ("OWNER", "ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = body.role
    await db.flush()
    return target_user


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Deactivate a user. Requires Owner role."""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.tenant_id == user.tenant_id)
        .values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deactivated"}
FILEEOF

# ══════════════════════════════════════════════
#  Update backend/app/main.py — Register all routers
# ══════════════════════════════════════════════

cat > backend/app/main.py << 'FILEEOF'
"""GetVul API — entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.vulnerabilities.router import router as vuln_router
from app.assets.router import router as asset_router
from app.tenants.router import router as tenant_router
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

# ── Routes ──
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}
FILEEOF

# ══════════════════════════════════════════════
#  backend/tests/test_vulnerabilities.py
# ══════════════════════════════════════════════

cat > backend/tests/test_vulnerabilities.py << 'FILEEOF'
"""Tests for vulnerability schemas and pagination."""

import uuid

from app.pagination import PaginatedResponse, PaginationParams
from app.vulnerabilities.schemas import (
    DashboardStats,
    SeverityCount,
    SourceCount,
    VulnerabilityFilter,
    VulnerabilitySummary,
)


class TestPagination:
    def test_offset_calculation(self):
        params = PaginationParams(page=1, page_size=50)
        assert params.offset == 0

        params = PaginationParams(page=3, page_size=20)
        assert params.offset == 40

    def test_paginated_response_create(self):
        params = PaginationParams(page=1, page_size=10)
        response = PaginatedResponse.create(items=["a", "b"], total=25, params=params)
        assert response.total == 25
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 3

    def test_paginated_response_single_page(self):
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse.create(items=[], total=5, params=params)
        assert response.total_pages == 1


class TestVulnerabilityFilter:
    def test_default_filter(self):
        f = VulnerabilityFilter()
        assert f.severity is None
        assert f.source is None
        assert f.search is None

    def test_filter_with_values(self):
        f = VulnerabilityFilter(
            severity=["CRITICAL", "HIGH"],
            source=["CROWDSTRIKE"],
            exploit_available=True,
        )
        assert f.severity == ["CRITICAL", "HIGH"]
        assert f.exploit_available is True


class TestDashboardStats:
    def test_stats_model(self):
        stats = DashboardStats(
            total_vulnerabilities=1000,
            open_vulnerabilities=800,
            by_severity=[
                SeverityCount(severity="CRITICAL", count=50),
                SeverityCount(severity="HIGH", count=200),
            ],
            by_source=[
                SourceCount(source="CROWDSTRIKE", count=600),
            ],
            exploitable_count=75,
            cisa_kev_count=30,
            correlated_cves=142,
            mttr_days=12.5,
        )
        assert stats.total_vulnerabilities == 1000
        assert len(stats.by_severity) == 2
        assert stats.mttr_days == 12.5
FILEEOF

# ══════════════════════════════════════════════
#  REBUILD & TEST
# ══════════════════════════════════════════════

echo "🔄 Rebuilding backend..."
docker compose down
docker compose up --build -d

echo "⏳ Waiting for services..."
sleep 15

echo "🔍 Testing..."
echo ""
echo "Health:"
curl -s http://localhost:8000/health
echo ""
echo ""
echo "Vulns (expect 401):"
curl -s http://localhost:8000/api/v1/vulnerabilities
echo ""
echo ""
echo "Assets (expect 401):"
curl -s http://localhost:8000/api/v1/assets
echo ""
echo ""
echo "Tenant (expect 401):"
curl -s http://localhost:8000/api/v1/tenant/me
echo ""

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

echo ""
echo "📝 Committing..."

git add -A
git commit -m "feat: core API endpoints — vulns, assets, tenants

- Vulnerabilities: list (filtered + paginated), detail, status update, bulk update, dashboard stats
- Assets: list (filtered + paginated), detail, per-asset vulnerability list
- Tenants: tenant info, user list, role update, user deactivation
- Shared pagination utility (PaginatedResponse)
- RBAC enforcement on all endpoints
- Tests: pagination, filters, dashboard stats"

git push -u origin feat/core-endpoints

gh pr create \
  --title "feat: core API endpoints — vulnerabilities, assets, tenants" \
  --body "## Endpoints Added

### Vulnerabilities (/api/v1/vulnerabilities)
- \`GET /\` — List with filtering (severity, source, status, CVE, exploit, CISA KEV, age) + pagination
- \`GET /stats\` — Dashboard stats (counts by severity/source, MTTR, correlations)
- \`GET /{id}\` — Full vulnerability detail with asset hostname and correlation count
- \`PATCH /{id}/status\` — Update status (Analyst+)
- \`POST /bulk-status\` — Bulk status update (Analyst+)

### Assets (/api/v1/assets)
- \`GET /\` — List with filtering (hostname, OS, type, cloud, source, risk score) + pagination
- \`GET /{id}\` — Full asset detail with vuln counts by severity
- \`GET /{id}/vulnerabilities\` — Vulns for a specific asset

### Tenant (/api/v1/tenant)
- \`GET /me\` — Current tenant info
- \`GET /users\` — List users (Admin+)
- \`PATCH /users/{id}/role\` — Change role (Owner only)
- \`PATCH /users/{id}/deactivate\` — Deactivate user (Owner only)

All endpoints enforce RBAC. Swagger docs at /docs." \
  --base main

echo ""
echo "✅ Done! PR created. Once CI passes:"
echo "   gh pr merge --squash"
echo "   git checkout main && git pull"
