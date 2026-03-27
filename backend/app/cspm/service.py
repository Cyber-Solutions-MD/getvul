"""CSPM business logic and database queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import Select, case, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cspm.models import Misconfiguration
from app.cspm.schemas import (
    BulkMisconfigStatusUpdate,
    CategoryCount,
    CSPMDashboardStats,
    MisconfigFilter,
    MisconfigResponse,
    MisconfigSummary,
    SeverityCount,
    SourceCount,
)
from app.pagination import PaginatedResponse, PaginationParams

logger = structlog.get_logger()


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
    db: AsyncSession,
    tenant_id: uuid.UUID,
    filters: MisconfigFilter,
    pagination: PaginationParams,
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
    db: AsyncSession,
    tenant_id: uuid.UUID,
    misconfig_id: uuid.UUID,
) -> MisconfigResponse | None:
    result = await db.execute(
        select(Misconfiguration).where(
            Misconfiguration.id == misconfig_id,
            Misconfiguration.tenant_id == tenant_id,
        )
    )
    m = result.scalar_one_or_none()
    if m is None:
        return None
    return MisconfigResponse.model_validate(m)


async def update_misconfig_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    misconfig_id: uuid.UUID,
    new_status: str,
) -> bool:
    now = datetime.now(UTC)
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
    db: AsyncSession,
    tenant_id: uuid.UUID,
    body: BulkMisconfigStatusUpdate,
) -> int:
    now = datetime.now(UTC)
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
    open_count = (
        await db.execute(select(func.count(Misconfiguration.id)).where(base, Misconfiguration.status == "OPEN"))
    ).scalar_one()

    sev_rows = (
        await db.execute(
            select(Misconfiguration.severity, func.count(Misconfiguration.id))
            .where(base)
            .group_by(Misconfiguration.severity)
        )
    ).all()

    cat_rows = (
        await db.execute(
            select(Misconfiguration.category, func.count(Misconfiguration.id))
            .where(base)
            .group_by(Misconfiguration.category)
        )
    ).all()

    src_rows = (
        await db.execute(
            select(Misconfiguration.source, func.count(Misconfiguration.id))
            .where(base)
            .group_by(Misconfiguration.source)
        )
    ).all()

    cloud_rows = (
        await db.execute(
            select(Misconfiguration.cloud_provider, func.count(Misconfiguration.id))
            .where(base, Misconfiguration.cloud_provider.isnot(None))
            .group_by(Misconfiguration.cloud_provider)
        )
    ).all()

    remediated = (
        await db.execute(select(func.count(Misconfiguration.id)).where(base, Misconfiguration.status == "REMEDIATED"))
    ).scalar_one()
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


# ---------------------------------------------------------------------------
# Compliance dashboard
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4, "INFO": 5}


async def get_compliance_dashboard(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return compliance posture grouped by framework."""
    logger.info("get_compliance_dashboard", tenant_id=str(tenant_id))

    framework_col = func.jsonb_array_elements_text(Misconfiguration.frameworks).label("framework")

    base_q = select(
        framework_col,
        Misconfiguration.rule_id,
        Misconfiguration.status,
        Misconfiguration.severity,
    ).where(
        Misconfiguration.tenant_id == tenant_id,
        Misconfiguration.frameworks.isnot(None),
    )

    # Wrap as subquery so we can group on the unnested framework value
    sub = base_q.subquery()

    rows = (
        await db.execute(
            select(
                sub.c.framework,
                func.count(func.distinct(sub.c.rule_id)).label("total_controls"),
                func.count(func.distinct(sub.c.rule_id)).filter(sub.c.status == "REMEDIATED").label("passed"),
                func.count(func.distinct(sub.c.rule_id))
                .filter(sub.c.status.in_(["OPEN", "IN_PROGRESS"]))
                .label("failed"),
                func.count(func.distinct(sub.c.rule_id)).filter(sub.c.status == "SUPPRESSED").label("suppressed"),
                func.count(1).filter(sub.c.severity == "CRITICAL").label("critical"),
                func.count(1).filter(sub.c.severity == "HIGH").label("high"),
                func.count(1).filter(sub.c.severity == "MEDIUM").label("medium"),
                func.count(1).filter(sub.c.severity == "LOW").label("low"),
                func.count(1).filter(sub.c.severity == "INFO").label("info"),
            ).group_by(sub.c.framework)
        )
    ).all()

    results: list[dict] = []
    for r in rows:
        total = r.total_controls
        passed = r.passed
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0
        results.append(
            {
                "name": r.framework,
                "total": total,
                "passed": passed,
                "failed": r.failed,
                "suppressed": r.suppressed,
                "pass_rate": pass_rate,
                "by_severity": {
                    "critical": r.critical,
                    "high": r.high,
                    "medium": r.medium,
                    "low": r.low,
                    "info": r.info,
                },
            }
        )

    return results


# ---------------------------------------------------------------------------
# Cloud resource inventory
# ---------------------------------------------------------------------------


async def get_cloud_resources(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    cloud_provider: str | None = None,
    resource_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Aggregate findings into a paginated cloud resource inventory."""
    logger.info(
        "get_cloud_resources",
        tenant_id=str(tenant_id),
        cloud_provider=cloud_provider,
        resource_type=resource_type,
        page=page,
    )

    group_cols = [
        Misconfiguration.resource_id,
        Misconfiguration.resource_name,
        Misconfiguration.resource_type,
        Misconfiguration.cloud_provider,
        Misconfiguration.resource_region,
    ]

    base_filter = Misconfiguration.tenant_id == tenant_id

    data_q = (
        select(
            *group_cols,
            func.count(Misconfiguration.id).label("total_findings"),
            func.count(Misconfiguration.id)
            .filter(Misconfiguration.status.in_(["OPEN", "IN_PROGRESS"]))
            .label("open_findings"),
            func.count(Misconfiguration.id).filter(Misconfiguration.severity == "CRITICAL").label("critical_findings"),
            func.max(
                case(
                    (Misconfiguration.severity == "CRITICAL", 1),
                    (Misconfiguration.severity == "HIGH", 2),
                    (Misconfiguration.severity == "MEDIUM", 3),
                    (Misconfiguration.severity == "LOW", 4),
                    (Misconfiguration.severity == "INFO", 5),
                    else_=6,
                )
            ).label("worst_severity_rank"),
            func.max(Misconfiguration.last_seen_at).label("last_seen_at"),
        )
        .where(base_filter)
        .group_by(*group_cols)
    )

    if cloud_provider:
        data_q = data_q.where(Misconfiguration.cloud_provider == cloud_provider)
    if resource_type:
        data_q = data_q.where(Misconfiguration.resource_type.ilike(f"%{resource_type}%"))
    if search:
        data_q = data_q.where(
            or_(
                Misconfiguration.resource_name.ilike(f"%{search}%"),
                Misconfiguration.resource_id.ilike(f"%{search}%"),
            )
        )

    # Count total groups via subquery
    count_sub = data_q.subquery()
    total = (await db.execute(select(func.count()).select_from(count_sub))).scalar_one()

    # Order by worst severity, then total findings desc
    data_q = data_q.order_by(
        literal_column("worst_severity_rank").asc(),
        literal_column("total_findings").desc(),
    )

    offset = (page - 1) * page_size
    rows = (await db.execute(data_q.offset(offset).limit(page_size))).all()

    severity_rank_map = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM", 4: "LOW", 5: "INFO"}

    items: list[dict] = []
    for r in rows:
        # Fetch distinct frameworks for this resource
        fw_rows = (
            (
                await db.execute(
                    select(func.distinct(func.jsonb_array_elements_text(Misconfiguration.frameworks))).where(
                        Misconfiguration.tenant_id == tenant_id,
                        Misconfiguration.resource_id == r.resource_id,
                        Misconfiguration.frameworks.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        items.append(
            {
                "resource_id": r.resource_id,
                "resource_name": r.resource_name,
                "resource_type": r.resource_type,
                "cloud_provider": r.cloud_provider,
                "resource_region": r.resource_region,
                "total_findings": r.total_findings,
                "open_findings": r.open_findings,
                "critical_findings": r.critical_findings,
                "worst_severity": severity_rank_map.get(r.worst_severity_rank, "UNKNOWN"),
                "frameworks": sorted(fw_rows),
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
            }
        )

    total_pages = max(1, -(-total // page_size))
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# CSPM trends
# ---------------------------------------------------------------------------


async def get_cspm_trends(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 30,
) -> dict:
    """Generate time-series trend data for CSPM findings."""
    logger.info("get_cspm_trends", tenant_id=str(tenant_id), days=days)

    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)
    base = Misconfiguration.tenant_id == tenant_id

    # New findings per day (based on first_detected_at)
    new_rows = (
        await db.execute(
            select(
                func.date_trunc("day", Misconfiguration.first_detected_at).label("day"),
                func.count(Misconfiguration.id).label("cnt"),
            )
            .where(base, Misconfiguration.first_detected_at >= start_date)
            .group_by(literal_column("day"))
            .order_by(literal_column("day"))
        )
    ).all()

    # Resolved findings per day (based on remediated_at)
    resolved_rows = (
        await db.execute(
            select(
                func.date_trunc("day", Misconfiguration.remediated_at).label("day"),
                func.count(Misconfiguration.id).label("cnt"),
            )
            .where(
                base,
                Misconfiguration.remediated_at.isnot(None),
                Misconfiguration.remediated_at >= start_date,
            )
            .group_by(literal_column("day"))
            .order_by(literal_column("day"))
        )
    ).all()

    # Total detected before the window (baseline for cumulative)
    total_before = (
        await db.execute(
            select(func.count(Misconfiguration.id)).where(base, Misconfiguration.first_detected_at < start_date)
        )
    ).scalar_one()

    remediated_before = (
        await db.execute(
            select(func.count(Misconfiguration.id)).where(
                base,
                Misconfiguration.remediated_at.isnot(None),
                Misconfiguration.remediated_at < start_date,
            )
        )
    ).scalar_one()

    # Build lookup dicts
    new_by_day: dict[str, int] = {r.day.strftime("%Y-%m-%d"): r.cnt for r in new_rows}
    resolved_by_day: dict[str, int] = {r.day.strftime("%Y-%m-%d"): r.cnt for r in resolved_rows}

    # Build timeline
    timeline: list[dict] = []
    cumulative_detected = total_before
    cumulative_remediated = remediated_before
    new_in_period = 0
    resolved_in_period = 0

    for i in range(days):
        day = start_date + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_new = new_by_day.get(day_str, 0)
        day_resolved = resolved_by_day.get(day_str, 0)

        cumulative_detected += day_new
        cumulative_remediated += day_resolved
        new_in_period += day_new
        resolved_in_period += day_resolved

        timeline.append(
            {
                "date": day_str,
                "new": day_new,
                "resolved": day_resolved,
                "open_cumulative": cumulative_detected - cumulative_remediated,
            }
        )

    # Current total open
    total_open = (
        await db.execute(
            select(func.count(Misconfiguration.id)).where(base, Misconfiguration.status.in_(["OPEN", "IN_PROGRESS"]))
        )
    ).scalar_one()

    return {
        "timeline": timeline,
        "summary": {
            "total_open": total_open,
            "new_in_period": new_in_period,
            "resolved_in_period": resolved_in_period,
        },
    }
