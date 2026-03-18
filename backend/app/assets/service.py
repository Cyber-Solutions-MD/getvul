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
    db: AsyncSession, tenant_id: uuid.UUID, filters: AssetFilter, pagination: PaginationParams,
) -> PaginatedResponse[AssetSummary]:
    count_q = _apply_filters(select(func.count(Asset.id)), tenant_id, filters)
    total = (await db.execute(count_q)).scalar_one()

    # Subquery: open vuln counts per severity per asset
    vuln_sub = (
        select(
            Vulnerability.asset_id,
            func.count(Vulnerability.id).label("open_vuln_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "CRITICAL").label("critical_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "HIGH").label("high_count"),
            func.count(Vulnerability.id).filter(Vulnerability.exploit_available.is_(True)).label("exploitable_count"),
            func.count(Vulnerability.id).filter(Vulnerability.cisa_kev.is_(True)).label("kev_count"),
        )
        .where(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "OPEN")
        .group_by(Vulnerability.asset_id)
        .subquery()
    )

    data_q = (
        _apply_filters(select(Asset), tenant_id, filters)
        .outerjoin(vuln_sub, Asset.id == vuln_sub.c.asset_id)
        .add_columns(
            func.coalesce(vuln_sub.c.open_vuln_count, 0).label("open_vuln_count"),
            func.coalesce(vuln_sub.c.critical_count, 0).label("critical_count"),
            func.coalesce(vuln_sub.c.high_count, 0).label("high_count"),
            func.coalesce(vuln_sub.c.exploitable_count, 0).label("exploitable_count"),
            func.coalesce(vuln_sub.c.kev_count, 0).label("kev_count"),
        )
        .order_by(Asset.risk_score.desc().nullslast(), Asset.hostname.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    results = (await db.execute(data_q)).all()

    items = []
    for row in results:
        asset = row[0]
        items.append(AssetSummary(
            id=asset.id,
            hostname=asset.hostname,
            os_name=asset.os_name,
            os_version=asset.os_version,
            asset_type=asset.asset_type,
            cloud_provider=asset.cloud_provider,
            seen_by_sources=asset.seen_by_sources,
            risk_score=asset.risk_score,
            open_vuln_count=row.open_vuln_count,
            critical_count=row.critical_count,
            high_count=row.high_count,
            exploitable_count=row.exploitable_count,
            kev_count=row.kev_count,
        ))

    return PaginatedResponse.create(items=items, total=total, params=pagination)


async def get_asset(db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> AssetResponse | None:
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        return None

    sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(Vulnerability.asset_id == asset_id, Vulnerability.tenant_id == tenant_id, Vulnerability.status == "OPEN")
        .group_by(Vulnerability.severity)
    )
    sev_rows = (await db.execute(sev_q)).all()
    vuln_counts = {r[0]: r[1] for r in sev_rows}

    return AssetResponse(
        id=asset.id, tenant_id=asset.tenant_id, hostname=asset.hostname,
        ip_addresses=asset.ip_addresses, mac_addresses=asset.mac_addresses,
        os_name=asset.os_name, os_version=asset.os_version,
        asset_type=asset.asset_type, cloud_provider=asset.cloud_provider,
        cloud_resource_id=asset.cloud_resource_id,
        seen_by_sources=asset.seen_by_sources, risk_score=asset.risk_score,
        created_at=asset.created_at, updated_at=asset.updated_at,
        vuln_counts=vuln_counts,
    )


async def get_asset_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Dashboard stats for assets."""
    total = (await db.execute(
        select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id)
    )).scalar_one()

    # By OS
    os_rows = (await db.execute(
        select(Asset.os_name, func.count(Asset.id))
        .where(Asset.tenant_id == tenant_id, Asset.os_name.isnot(None))
        .group_by(Asset.os_name).order_by(func.count(Asset.id).desc()).limit(10)
    )).all()

    # By risk score range
    risk_q = select(
        case(
            (Asset.risk_score >= 80, "Critical (80-100)"),
            (Asset.risk_score >= 50, "High (50-79)"),
            (Asset.risk_score >= 20, "Medium (20-49)"),
            else_="Low (0-19)",
        ).label("risk_range"),
        func.count(Asset.id),
    ).where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None)).group_by("risk_range")
    risk_rows = (await db.execute(risk_q)).all()

    # Scanner coverage
    sources = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"]
    coverage = {}
    for src in sources:
        cnt = (await db.execute(
            select(func.count(Asset.id))
            .where(Asset.tenant_id == tenant_id, Asset.seen_by_sources.contains([src]))
        )).scalar_one()
        if cnt > 0:
            coverage[src] = cnt

    # Average risk score
    avg_risk = (await db.execute(
        select(func.avg(Asset.risk_score))
        .where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None))
    )).scalar_one()

    return {
        "total_assets": total,
        "average_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
        "by_os": [{"os": r[0], "count": r[1]} for r in os_rows],
        "by_risk_range": [{"range": r[0], "count": r[1]} for r in risk_rows],
        "scanner_coverage": coverage,
    }
