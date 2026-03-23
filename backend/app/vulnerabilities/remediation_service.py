"""Remediation-centric queries: group by remediation, group by host."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


def _base_open_vulns(tenant_id: uuid.UUID, show_suppressed: str = "active"):
    """Base conditions for vulns.

    show_suppressed: "active" (default), "ignored", or "all"
    """
    if show_suppressed == "ignored":
        return and_(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status == "SUPPRESSED",
        )
    if show_suppressed == "all":
        return and_(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "SUPPRESSED"]),
        )
    return and_(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
    )


def _apply_common_filters(
    q, severity: list[str] | None = None,
    exploit_only: bool = False, kev_only: bool = False,
):
    if severity:
        q = q.where(Vulnerability.severity.in_(severity))
    if exploit_only:
        q = q.where(Vulnerability.exploit_available.is_(True))
    if kev_only:
        q = q.where(Vulnerability.cisa_kev.is_(True))
    return q


async def get_remediations_grouped(
    db: AsyncSession, tenant_id: uuid.UUID,
    severity: list[str] | None = None,
    exploit_only: bool = False,
    kev_only: bool = False,
    search: str | None = None,
    show_suppressed: str = "active",
    page: int = 1, page_size: int = 25,
) -> dict:
    """Group vulns by remediation_id. show_suppressed: active, ignored, or all."""

    base = select(
        Vulnerability.remediation_id,
        Vulnerability.remediation_action,
        Vulnerability.affected_product,
        func.count(func.distinct(Vulnerability.asset_id)).label("affected_hosts"),
        func.count(Vulnerability.id).label("vuln_count"),
        func.max(case(
            (Vulnerability.severity == "CRITICAL", 4),
            (Vulnerability.severity == "HIGH", 3),
            (Vulnerability.severity == "MEDIUM", 2),
            (Vulnerability.severity == "LOW", 1),
            else_=0,
        )).label("max_severity_rank"),
        func.count().filter(Vulnerability.status == "SUPPRESSED").label("suppressed_count"),
    ).join(Asset, Vulnerability.asset_id == Asset.id).where(
        _base_open_vulns(tenant_id, show_suppressed=show_suppressed),
        Vulnerability.remediation_id.isnot(None),
        Vulnerability.remediation_id != "",
        Asset.is_ignored.is_(False),
    ).group_by(
        Vulnerability.remediation_id,
        Vulnerability.remediation_action,
        Vulnerability.affected_product,
    )

    base = _apply_common_filters(base, severity, exploit_only, kev_only)

    if search:
        base = base.having(
            func.coalesce(Vulnerability.remediation_action, "").ilike(f"%{search}%") |
            func.coalesce(Vulnerability.affected_product, "").ilike(f"%{search}%")
        )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    data_q = base.order_by(
        func.max(case(
            (Vulnerability.severity == "CRITICAL", 4),
            (Vulnerability.severity == "HIGH", 3),
            (Vulnerability.severity == "MEDIUM", 2),
            else_=1,
        )).desc(),
        func.count(func.distinct(Vulnerability.asset_id)).desc(),
    ).offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(data_q)).all()
    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "INFO"}

    return {
        "items": [{
            "remediation_id": r.remediation_id,
            "remediation_action": r.remediation_action,
            "affected_product": r.affected_product,
            "affected_hosts": r.affected_hosts,
            "vuln_count": r.vuln_count,
            "max_severity": sev_map.get(r.max_severity_rank, "MEDIUM"),
            "is_suppressed": r.suppressed_count == r.vuln_count,
            "suppressed_count": r.suppressed_count,
        } for r in rows],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def get_hosts_for_remediation(
    db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str,
    severity: list[str] | None = None,
    exploit_only: bool = False, kev_only: bool = False,
) -> list[dict]:
    """Get all hosts affected by a specific remediation, with filters."""
    q = (
        select(
            Asset.id, Asset.hostname, Asset.os_name, Asset.os_version,
            Vulnerability.cve_id, Vulnerability.severity,
            Vulnerability.exploit_available, Vulnerability.cisa_kev,
            Vulnerability.exploit_status_name,
        )
        .join(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            _base_open_vulns(tenant_id),
            Vulnerability.remediation_id == remediation_id,
            Asset.is_ignored.is_(False),
        )
        .order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 1),
                (Vulnerability.severity == "HIGH", 2),
                (Vulnerability.severity == "MEDIUM", 3),
                else_=4,
            ),
            Asset.hostname,
        )
    )

    q = _apply_common_filters(q, severity, exploit_only, kev_only)

    rows = (await db.execute(q)).all()
    return [{
        "asset_id": str(r.id), "hostname": r.hostname,
        "os_name": r.os_name, "os_version": r.os_version,
        "cve_id": r.cve_id, "severity": r.severity,
        "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
        "exploit_status": r.exploit_status_name,
    } for r in rows]


async def get_remediations_for_host(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID,
    severity: list[str] | None = None,
    exploit_only: bool = False, kev_only: bool = False,
) -> list[dict]:
    """Get all remediations needed for a specific host, with filters."""
    q = (
        select(
            Vulnerability.remediation_id,
            Vulnerability.remediation_action,
            Vulnerability.cve_id,
            Vulnerability.severity,
            Vulnerability.affected_product,
            Vulnerability.exploit_available,
            Vulnerability.cisa_kev,
            Vulnerability.exploit_status_name,
            Vulnerability.exploit_status_id,
        )
        .where(
            _base_open_vulns(tenant_id),
            Vulnerability.asset_id == asset_id,
            Vulnerability.remediation_id.isnot(None),
        )
        .order_by(
            case(
                (Vulnerability.severity == "CRITICAL", 1),
                (Vulnerability.severity == "HIGH", 2),
                (Vulnerability.severity == "MEDIUM", 3),
                else_=4,
            ),
            Vulnerability.cve_id,
        )
    )

    q = _apply_common_filters(q, severity, exploit_only, kev_only)

    rows = (await db.execute(q)).all()
    return [{
        "remediation_id": r.remediation_id,
        "remediation_action": r.remediation_action,
        "cve_id": r.cve_id, "severity": r.severity,
        "affected_product": r.affected_product,
        "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
        "exploit_status": r.exploit_status_name,
        "exploit_status_id": r.exploit_status_id,
    } for r in rows]
