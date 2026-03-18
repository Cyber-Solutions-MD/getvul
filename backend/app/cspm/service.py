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
