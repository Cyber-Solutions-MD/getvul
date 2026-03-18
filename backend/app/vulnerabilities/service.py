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
