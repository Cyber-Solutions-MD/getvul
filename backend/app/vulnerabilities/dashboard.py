"""Enhanced dashboard stats — top risky hosts, ticket status, connector health."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.ticketing.models import ConnectorConfig, Ticket
from app.vulnerabilities.models import Vulnerability


async def get_overview_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get comprehensive dashboard overview data."""

    # Top 10 riskiest hosts
    top_hosts_q = (
        select(
            Asset.id, Asset.hostname, Asset.risk_score, Asset.device_category,
            Asset.assigned_user, Asset.host_status,
            func.count(Vulnerability.id).label("vuln_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count(Vulnerability.id).filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
        )
        .outerjoin(Vulnerability, (Vulnerability.asset_id == Asset.id) & Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
        .where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None))
        .group_by(Asset.id)
        .order_by(Asset.risk_score.desc())
        .limit(10)
    )
    top_hosts = [
        {
            "id": str(r.id), "hostname": r.hostname, "risk_score": r.risk_score or 0,
            "device_category": r.device_category, "assigned_user": r.assigned_user,
            "host_status": r.host_status, "vuln_count": r.vuln_count,
            "critical": r.critical, "exploitable": r.exploitable,
        }
        for r in (await db.execute(top_hosts_q)).all()
    ]

    # Ticket stats
    now = datetime.now(UTC)
    ticket_total = (await db.execute(
        select(func.count(func.distinct(Ticket.external_ticket_url))).where(Ticket.tenant_id == tenant_id)
    )).scalar_one()
    ticket_open = (await db.execute(
        select(func.count(func.distinct(Ticket.external_ticket_url))).where(
            Ticket.tenant_id == tenant_id, Ticket.resolved_at.is_(None),
        )
    )).scalar_one()

    # Overdue tickets (open + past due date — we approximate from ticket age)
    week_ago = now - timedelta(days=7)
    overdue = (await db.execute(
        select(func.count(func.distinct(Ticket.external_ticket_url))).where(
            Ticket.tenant_id == tenant_id,
            Ticket.resolved_at.is_(None),
            Ticket.ticket_created_at < week_ago,
        )
    )).scalar_one()

    # Connector health
    connectors_q = (
        select(
            ConnectorConfig.connector_type,
            ConnectorConfig.is_enabled,
            ConnectorConfig.last_sync_at,
            ConnectorConfig.last_sync_status,
            ConnectorConfig.last_sync_record_count,
        )
        .where(ConnectorConfig.tenant_id == tenant_id)
        .order_by(ConnectorConfig.connector_type)
    )
    connectors = [
        {
            "type": r.connector_type,
            "enabled": r.is_enabled,
            "last_sync": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "status": r.last_sync_status,
            "records": r.last_sync_record_count,
        }
        for r in (await db.execute(connectors_q)).all()
    ]

    # Severity trend — vulns by status
    status_q = (
        select(Vulnerability.status, func.count(Vulnerability.id))
        .where(Vulnerability.tenant_id == tenant_id)
        .group_by(Vulnerability.status)
    )
    by_status = {r[0]: r[1] for r in (await db.execute(status_q)).all()}

    # Risk distribution across assets
    risk_q = (
        select(
            func.count().filter(Asset.risk_score >= 80).label("critical"),
            func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)).label("high"),
            func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)).label("medium"),
            func.count().filter((Asset.risk_score < 20) | (Asset.risk_score.is_(None))).label("low"),
        )
        .where(Asset.tenant_id == tenant_id)
    )
    risk_dist = (await db.execute(risk_q)).one()

    # User stats
    from app.tenants.models import User
    total_users = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )).scalar_one()

    # SLA metrics
    from app.vulnerabilities.sla_service import get_sla_metrics
    sla = await get_sla_metrics(db, tenant_id)

    return {
        "top_risky_hosts": top_hosts,
        "sla": sla,
        "tickets": {
            "total": ticket_total,
            "open": ticket_open,
            "resolved": ticket_total - ticket_open,
            "overdue": overdue,
        },
        "connectors": connectors,
        "by_status": by_status,
        "risk_distribution": {
            "critical": risk_dist.critical,
            "high": risk_dist.high,
            "medium": risk_dist.medium,
            "low": risk_dist.low,
        },
        "total_users": total_users,
    }
