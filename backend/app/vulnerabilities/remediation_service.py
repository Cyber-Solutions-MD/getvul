"""Remediation-centric queries: group by remediation, group by host."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability


async def get_remediations_grouped(
    db: AsyncSession, tenant_id: uuid.UUID,
    severity: list[str] | None = None,
    exploit_only: bool = False,
    kev_only: bool = False,
    search: str | None = None,
    page: int = 1, page_size: int = 25,
) -> dict:
    """Group open vulns by remediation_id — shows each unique remediation and how many hosts are affected."""

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
    ).where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status == "OPEN",
        Vulnerability.remediation_id.isnot(None),
        Vulnerability.remediation_id != "",
    ).group_by(
        Vulnerability.remediation_id,
        Vulnerability.remediation_action,
        Vulnerability.affected_product,
    )

    if severity:
        base = base.where(Vulnerability.severity.in_(severity))
    if exploit_only:
        base = base.where(Vulnerability.exploit_available.is_(True))
    if kev_only:
        base = base.where(Vulnerability.cisa_kev.is_(True))
    if search:
        base = base.having(
            func.coalesce(Vulnerability.remediation_action, "").ilike(f"%{search}%") |
            func.coalesce(Vulnerability.affected_product, "").ilike(f"%{search}%")
        )

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Data
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

    items = []
    for row in rows:
        items.append({
            "remediation_id": row.remediation_id,
            "remediation_action": row.remediation_action,
            "affected_product": row.affected_product,
            "affected_hosts": row.affected_hosts,
            "vuln_count": row.vuln_count,
            "max_severity": sev_map.get(row.max_severity_rank, "MEDIUM"),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


async def get_hosts_for_remediation(
    db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str,
) -> list[dict]:
    """Get all hosts affected by a specific remediation."""
    q = (
        select(
            Asset.id, Asset.hostname, Asset.os_name, Asset.os_version,
            Vulnerability.cve_id, Vulnerability.severity,
            Vulnerability.exploit_available, Vulnerability.cisa_kev,
            Vulnerability.exploit_status_name,
        )
        .join(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status == "OPEN",
        )
        .order_by(Asset.hostname)
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "asset_id": str(r.id), "hostname": r.hostname,
            "os_name": r.os_name, "os_version": r.os_version,
            "cve_id": r.cve_id, "severity": r.severity,
            "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
            "exploit_status": r.exploit_status_name,
        }
        for r in rows
    ]


async def get_remediations_for_host(
    db: AsyncSession, tenant_id: uuid.UUID, asset_id: uuid.UUID,
) -> list[dict]:
    """Get all remediations needed for a specific host."""
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
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.asset_id == asset_id,
            Vulnerability.status == "OPEN",
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
    rows = (await db.execute(q)).all()
    return [
        {
            "remediation_id": r.remediation_id,
            "remediation_action": r.remediation_action,
            "cve_id": r.cve_id, "severity": r.severity,
            "affected_product": r.affected_product,
            "exploit_available": r.exploit_available, "cisa_kev": r.cisa_kev,
            "exploit_status": r.exploit_status_name,
            "exploit_status_id": r.exploit_status_id,
        }
        for r in rows
    ]
