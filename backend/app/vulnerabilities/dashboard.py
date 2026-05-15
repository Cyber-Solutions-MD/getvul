"""Enhanced dashboard stats — top risky hosts, ticket status, connector health.

Phase 10 additions (Plan 10-01):
  - compute_dashboard_tiles_v10:    /stats.dashboard_tiles with 7d delta
  - compute_top_vuln_v10:           highest-CVSS OPEN CRITICAL row + Asset.hostname
  - detect_onboarding_state:        no_scanners / no_data_yet / ready
  - compute_nav_counts_v10:         vuln_open, asset_total, ticket_open counts
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.ticketing.models import ConnectorConfig, Ticket
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.schemas import DashboardTiles, TileValue, TopVuln
from app.vulnerabilities.trends import DailySnapshot


async def get_overview_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get comprehensive dashboard overview data."""

    # Top 10 riskiest hosts
    top_hosts_q = (
        select(
            Asset.id,
            Asset.hostname,
            Asset.risk_score,
            Asset.device_category,
            Asset.assigned_user,
            Asset.host_status,
            func.count(Vulnerability.id).label("vuln_count"),
            func.count(Vulnerability.id).filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count(Vulnerability.id).filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
        )
        .outerjoin(
            Vulnerability, (Vulnerability.asset_id == Asset.id) & Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])
        )
        .where(Asset.tenant_id == tenant_id, Asset.risk_score.isnot(None))
        .group_by(Asset.id)
        .order_by(Asset.risk_score.desc())
        .limit(10)
    )
    top_hosts = [
        {
            "id": str(r.id),
            "hostname": r.hostname,
            "risk_score": r.risk_score or 0,
            "device_category": r.device_category,
            "assigned_user": r.assigned_user,
            "host_status": r.host_status,
            "vuln_count": r.vuln_count,
            "critical": r.critical,
            "exploitable": r.exploitable,
        }
        for r in (await db.execute(top_hosts_q)).all()
    ]

    # Ticket stats
    now = datetime.now(UTC)
    ticket_total = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(Ticket.tenant_id == tenant_id)
        )
    ).scalar_one()
    ticket_open = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(
                Ticket.tenant_id == tenant_id,
                Ticket.resolved_at.is_(None),
            )
        )
    ).scalar_one()

    # Overdue tickets (open + past due date — we approximate from ticket age)
    week_ago = now - timedelta(days=7)
    overdue = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(
                Ticket.tenant_id == tenant_id,
                Ticket.resolved_at.is_(None),
                Ticket.ticket_created_at < week_ago,
            )
        )
    ).scalar_one()

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
    risk_q = select(
        func.count().filter(Asset.risk_score >= 80).label("critical"),
        func.count().filter((Asset.risk_score >= 50) & (Asset.risk_score < 80)).label("high"),
        func.count().filter((Asset.risk_score >= 20) & (Asset.risk_score < 50)).label("medium"),
        func.count().filter((Asset.risk_score < 20) | (Asset.risk_score.is_(None))).label("low"),
    ).where(Asset.tenant_id == tenant_id)
    risk_dist = (await db.execute(risk_q)).one()

    # User stats
    from app.tenants.models import User

    total_users = (
        await db.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id, User.is_active.is_(True)))
    ).scalar_one()

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


# ── Phase 10 / Plan 01 helpers ───────────────────────────────────────────────
#
# Every helper below filters by `tenant_id` from the caller's CurrentUser
# (TENANT-01 + ASVS V8 — see threat_model T-10-05 / T-10-06 / T-10-07).
# ─────────────────────────────────────────────────────────────────────────────


async def compute_dashboard_tiles_v10(db: AsyncSession, tenant_id: uuid.UUID) -> DashboardTiles:
    """D-B-02 / D-S-01..04: 4 tiles with 7-day delta from DailySnapshot.

    mttr_30d.delta is intentionally always None per RESEARCH Open Question 2
    (delta on a 30-day rolling window is too noisy to be useful).
    """
    base = Vulnerability.tenant_id == tenant_id

    critical_open_today = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.severity == "CRITICAL",
            )
        )
    ).scalar_one()
    sla_at_risk_today = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base,
                Vulnerability.sla_breached.is_(True),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
        )
    ).scalar_one()
    kev_today = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base,
                Vulnerability.cisa_kev.is_(True),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
        )
    ).scalar_one()
    # MTTR over last 30 days (days). Server formats as e.g. "4.2d" so the
    # frontend can render verbatim (Warning-6 fix — value typed int|str).
    mttr_30d_raw = (
        await db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch", Vulnerability.remediated_at - Vulnerability.first_detected_at
                    )
                    / 86400
                )
            ).where(
                base,
                Vulnerability.status == "REMEDIATED",
                Vulnerability.remediated_at >= datetime.now(UTC) - timedelta(days=30),
            )
        )
    ).scalar_one()
    mttr_30d_value: int | str = (
        f"{round(float(mttr_30d_raw), 1)}d" if mttr_30d_raw else "—"
    )

    seven_days_ago = (datetime.now(UTC) - timedelta(days=7)).date()
    prior_metrics: dict | None = (
        await db.execute(
            select(DailySnapshot.metrics).where(
                DailySnapshot.tenant_id == tenant_id,
                DailySnapshot.snapshot_date == seven_days_ago,
            )
        )
    ).scalar_one_or_none()

    def _tile(today_value: int, snapshot_key: str) -> TileValue:
        if prior_metrics is None:
            # Pitfall 8: when there is no snapshot at -7d, delta MUST be None
            # so the UI renders "Δ —" rather than misleading 0.
            return TileValue(value=today_value, delta=None, delta_direction=None)
        prior = int(prior_metrics.get(snapshot_key, 0))
        d = today_value - prior
        direction: str = "up" if d > 0 else "down" if d < 0 else "flat"
        return TileValue(value=today_value, delta=d, delta_direction=direction)

    return DashboardTiles(
        critical_open=_tile(critical_open_today, "critical_open"),
        sla_at_risk=_tile(sla_at_risk_today, "sla_breached"),
        kev=_tile(kev_today, "kev_count"),
        mttr_30d=TileValue(value=mttr_30d_value, delta=None, delta_direction=None),
    )


async def compute_top_vuln_v10(db: AsyncSession, tenant_id: uuid.UUID) -> TopVuln | None:
    """D-B-02 / D-H-03: highest-CVSS OPEN CRITICAL vuln + Asset.hostname.

    Returns None when no OPEN CRITICAL rows exist — triggers the 'quiet-win'
    Hero swap on the frontend per D-O-04.
    """
    row = (
        await db.execute(
            select(
                Vulnerability.id,
                Vulnerability.cve_id,
                Vulnerability.cvss_v3_score,
                Vulnerability.cisa_kev,
                Vulnerability.exploit_available,
                Vulnerability.affected_product,
                Asset.hostname,
            )
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == "CRITICAL",
                Vulnerability.status == "OPEN",
            )
            .order_by(nulls_last(desc(Vulnerability.cvss_v3_score)))
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return TopVuln(
        id=row.id,
        cve_id=row.cve_id,
        host=row.hostname,
        path=row.affected_product,
        cvss=row.cvss_v3_score,
        on_kev=bool(row.cisa_kev),
        exploited=bool(row.exploit_available),
    )


async def compute_nav_counts_v10(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """D-B-02: vuln_open, asset_total, ticket_open — all tenant-scoped."""
    vuln_open = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
        )
    ).scalar_one()
    asset_total = (
        await db.execute(
            select(func.count(Asset.id)).where(
                Asset.tenant_id == tenant_id,
                Asset.is_ignored.is_(False),
            )
        )
    ).scalar_one()
    ticket_open = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(
                Ticket.tenant_id == tenant_id,
                Ticket.resolved_at.is_(None),
            )
        )
    ).scalar_one()
    return {
        "vuln_open_count": int(vuln_open),
        "asset_total_count": int(asset_total),
        "ticket_open_count": int(ticket_open),
    }


async def detect_onboarding_state(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """D-O-01: tenant onboarding signal for the empty-state Hero swap.

    Decision tree:
      no enabled ConnectorConfig rows               → 'no_scanners'
      enabled rows exist, no row with status SUCCESS → 'no_data_yet'
      at least one enabled row with status SUCCESS  → 'ready'
    """
    enabled_count = (
        await db.execute(
            select(func.count(ConnectorConfig.id)).where(
                ConnectorConfig.tenant_id == tenant_id,
                ConnectorConfig.is_enabled.is_(True),
            )
        )
    ).scalar_one()
    if enabled_count == 0:
        return "no_scanners"
    success_count = (
        await db.execute(
            select(func.count(ConnectorConfig.id)).where(
                ConnectorConfig.tenant_id == tenant_id,
                ConnectorConfig.is_enabled.is_(True),
                ConnectorConfig.last_sync_status == "SUCCESS",
            )
        )
    ).scalar_one()
    if success_count == 0:
        return "no_data_yet"
    return "ready"
