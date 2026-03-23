"""Asset business logic and database queries."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
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
    if filters.device_category:
        query = query.where(Asset.device_category == filters.device_category)
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
