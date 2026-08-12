"""Trend analytics — time-series queries and daily snapshot capture."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import Date, DateTime, ForeignKey, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.assets.models import Asset
from app.db.base import Base
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION

logger = structlog.get_logger()


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ── Trend queries (derived from existing data) ──


async def get_vuln_trends(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
    """Get vulnerability trend data over the past N days.

    Returns daily counts of new, resolved, and open vulns derived from timestamps.
    """
    now = datetime.now(UTC)
    start = now - timedelta(days=days)

    # New vulns per day (by first_detected_at)
    new_q = (
        select(
            cast(Vulnerability.first_detected_at, Date).label("day"),
            func.count(Vulnerability.id).label("count"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.first_detected_at >= start,
        )
        .group_by(cast(Vulnerability.first_detected_at, Date))
        .order_by(cast(Vulnerability.first_detected_at, Date))
    )
    new_rows = (await db.execute(new_q)).all()

    # Resolved vulns per day (by remediated_at)
    resolved_q = (
        select(
            cast(Vulnerability.remediated_at, Date).label("day"),
            func.count(Vulnerability.id).label("count"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.remediated_at >= start,
            Vulnerability.status.in_(["REMEDIATED", "SUPPRESSED"]),
        )
        .group_by(cast(Vulnerability.remediated_at, Date))
        .order_by(cast(Vulnerability.remediated_at, Date))
    )
    resolved_rows = (await db.execute(resolved_q)).all()

    # New vulns by severity per day
    new_by_sev_q = (
        select(
            cast(Vulnerability.first_detected_at, Date).label("day"),
            Vulnerability.severity,
            func.count(Vulnerability.id).label("count"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.first_detected_at >= start,
        )
        .group_by(cast(Vulnerability.first_detected_at, Date), Vulnerability.severity)
        .order_by(cast(Vulnerability.first_detected_at, Date))
    )
    sev_rows = (await db.execute(new_by_sev_q)).all()

    # Build per-day severity map
    sev_by_day: dict[str, dict[str, int]] = {}
    for r in sev_rows:
        day_str = r.day.isoformat()
        if day_str not in sev_by_day:
            sev_by_day[day_str] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        sev_by_day[day_str][r.severity] = r.count

    new_map = {r.day.isoformat(): r.count for r in new_rows}
    resolved_map = {r.day.isoformat(): r.count for r in resolved_rows}

    # Build complete day series
    timeline = []
    for i in range(days):
        d = (start + timedelta(days=i + 1)).date()
        day_str = d.isoformat()
        timeline.append(
            {
                "date": day_str,
                "new": new_map.get(day_str, 0),
                "resolved": resolved_map.get(day_str, 0),
                "net": new_map.get(day_str, 0) - resolved_map.get(day_str, 0),
                "by_severity": sev_by_day.get(day_str, {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}),
            }
        )

    return {
        "period_days": days,
        "timeline": timeline,
        "totals": {
            "new": sum(r.count for r in new_rows),
            "resolved": sum(r.count for r in resolved_rows),
        },
    }


async def get_mttr_trend(db: AsyncSession, tenant_id: uuid.UUID, days: int = 90) -> list[dict]:
    """Get weekly MTTR trend over the past N days."""
    now = datetime.now(UTC)
    start = now - timedelta(days=days)

    # Group remediated vulns by week and compute avg remediation time
    week_expr = func.date_trunc("week", Vulnerability.remediated_at)
    mttr_q = (
        select(
            week_expr.label("week"),
            func.avg(
                func.extract("epoch", Vulnerability.remediated_at - Vulnerability.first_detected_at) / 86400
            ).label("avg_days"),
            func.count(Vulnerability.id).label("count"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status == "REMEDIATED",
            Vulnerability.remediated_at >= start,
            Vulnerability.remediated_at.isnot(None),
            Vulnerability.first_detected_at.isnot(None),
        )
        .group_by(week_expr)
        .order_by(week_expr)
    )
    rows = (await db.execute(mttr_q)).all()

    return [
        {
            "week": r.week.date().isoformat() if r.week else None,
            "mttr_days": round(float(r.avg_days), 1) if r.avg_days else None,
            "count": r.count,
        }
        for r in rows
    ]


async def get_risk_score_trend(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    """Get risk score trend from daily snapshots."""
    rows = (
        await db.execute(
            select(DailySnapshot.snapshot_date, DailySnapshot.metrics)
            .where(DailySnapshot.tenant_id == tenant_id)
            .order_by(DailySnapshot.snapshot_date.desc())
            .limit(90)
        )
    ).all()

    return [
        {
            "date": r.snapshot_date.isoformat(),
            "avg_risk": r.metrics.get("avg_risk_score", 0),
            # RISK-10 (Phase 34 Plan 04): additional key, NEW series, so a
            # continuity-aware consumer can read the dual-written
            # risk_exposure_score-based average without breaking the
            # existing `avg_risk` wire contract (byte-identical source/name).
            "avg_risk_exposure": r.metrics.get("avg_risk_exposure_score", 0),
            "open_vulns": r.metrics.get("open_vulns", 0),
            "critical": r.metrics.get("critical_open", 0),
            "sla_breached": r.metrics.get("sla_breached", 0),
            "compliance_pct": r.metrics.get("compliance_pct", 100),
        }
        for r in reversed(rows)
    ]


async def get_all_trends(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
    """Get all trend data in one call."""
    vuln_trends = await get_vuln_trends(db, tenant_id, days)
    mttr_trend = await get_mttr_trend(db, tenant_id, days=90)
    risk_trend = await get_risk_score_trend(db, tenant_id)

    # D-B-01 / D-C-09: reshape the timeline into the {date: {c,h,m,l}} dict
    # the Phase 10 TrendChart consumes. Length == days (one bucket per day).
    severity_trends = {
        d["date"]: {
            "critical": d["by_severity"].get("CRITICAL", 0),
            "high": d["by_severity"].get("HIGH", 0),
            "medium": d["by_severity"].get("MEDIUM", 0),
            "low": d["by_severity"].get("LOW", 0),
        }
        for d in vuln_trends["timeline"]
    }

    return {
        "vuln_trends": vuln_trends,
        "mttr_trend": mttr_trend,
        "risk_trend": risk_trend,
        "severity_trends": severity_trends,
    }


# ── Daily snapshot capture (called by scheduler) ──


async def capture_daily_snapshot(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Capture today's metrics snapshot. Idempotent — skips if already exists."""
    today = datetime.now(UTC).date()

    # Check if snapshot already exists
    existing = (
        await db.execute(
            select(DailySnapshot).where(DailySnapshot.tenant_id == tenant_id, DailySnapshot.snapshot_date == today)
        )
    ).scalar_one_or_none()

    if existing:
        return {"captured": False, "date": today.isoformat(), "reason": "already_exists"}

    # Gather metrics
    base = Vulnerability.tenant_id == tenant_id

    total = (await db.execute(select(func.count(Vulnerability.id)).where(base))).scalar_one()
    open_vulns = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(base, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
        )
    ).scalar_one()
    critical_open = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]), Vulnerability.severity == "CRITICAL"
            )
        )
    ).scalar_one()
    high_open = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]), Vulnerability.severity == "HIGH"
            )
        )
    ).scalar_one()
    remediated = (
        await db.execute(select(func.count(Vulnerability.id)).where(base, Vulnerability.status == "REMEDIATED"))
    ).scalar_one()
    sla_breached = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base, Vulnerability.sla_breached.is_(True), Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])
            )
        )
    ).scalar_one()

    # Phase 10 / D-S-01: snapshot today's KEV count so the dashboard tile can
    # compute a 7-day delta tomorrow. Old snapshots return 0 via .get default.
    kev_count = (
        await db.execute(
            select(func.count(Vulnerability.id)).where(
                base,
                Vulnerability.cisa_kev.is_(True),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            )
        )
    ).scalar_one()

    # Average risk score
    avg_risk = (
        await db.execute(
            select(func.avg(Asset.risk_score)).where(
                Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False), Asset.risk_score.isnot(None)
            )
        )
    ).scalar_one()

    # RISK-10 (Phase 34 Plan 04): dual-write the new-model risk metrics
    # UNCONDITIONALLY (not gated on Tenant.cutover_risk_exposure_scoring) so
    # real trend/spike-notification history exists before any tenant ever
    # flips the flag — this is the structural fix for both the trend cliff
    # and the alert storm (34-CONTEXT RESOLVED A2). Average of the NEW score:
    avg_risk_exposure = (
        await db.execute(
            select(func.avg(Asset.risk_exposure_score)).where(
                Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False), Asset.risk_exposure_score.isnot(None)
            )
        )
    ).scalar_one()

    # One bulk fetch builds BOTH per-asset dicts (mirrors the total_assets
    # filter shape below: tenant-scoped + is_ignored excluded). This also
    # fixes the pre-existing dead-code bug in
    # alerts._check_risk_score_changes, which has always read
    # asset_risk_scores — a key this function never wrote until now.
    asset_score_rows = (
        await db.execute(
            select(Asset.id, Asset.risk_score, Asset.risk_exposure_score).where(
                Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False)
            )
        )
    ).all()
    asset_risk_scores = {str(r.id): r.risk_score for r in asset_score_rows if r.risk_score is not None}
    asset_risk_exposure_scores = {
        str(r.id): r.risk_exposure_score for r in asset_score_rows if r.risk_exposure_score is not None
    }

    # Total assets
    total_assets = (
        await db.execute(select(func.count(Asset.id)).where(Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False)))
    ).scalar_one()

    # Open tickets
    open_tickets = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_url))).where(
                Ticket.tenant_id == tenant_id, Ticket.resolved_at.is_(None)
            )
        )
    ).scalar_one()

    # SLA compliance
    from app.vulnerabilities.sla_service import get_sla_metrics

    sla = await get_sla_metrics(db, tenant_id)

    metrics = {
        "total_vulns": total,
        "open_vulns": open_vulns,
        "critical_open": critical_open,
        "high_open": high_open,
        "remediated": remediated,
        "sla_breached": sla_breached,
        "avg_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
        "total_assets": total_assets,
        "open_tickets": open_tickets,
        "compliance_pct": sla.get("compliance_pct", 100),
        "kev_count": kev_count,  # D-S-01 — tile delta source
        # RISK-10 (Phase 34 Plan 04) — unconditional dual-write, see above.
        "avg_risk_exposure_score": round(float(avg_risk_exposure), 1) if avg_risk_exposure else 0,
        "asset_risk_scores": asset_risk_scores,
        "asset_risk_exposure_scores": asset_risk_exposure_scores,
        "risk_model_version_snapshot": RISK_MODEL_VERSION,
    }

    snapshot = DailySnapshot(
        tenant_id=tenant_id,
        snapshot_date=today,
        metrics=metrics,
        created_at=datetime.now(UTC),
    )
    db.add(snapshot)

    logger.info("daily_snapshot_captured", tenant_id=str(tenant_id), date=today.isoformat(), metrics=metrics)
    return {"captured": True, "date": today.isoformat(), "metrics": metrics}


async def capture_all_snapshots(db: AsyncSession) -> dict:
    """Capture snapshots for all active tenants."""
    from app.tenants.models import Tenant

    tenants = (await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))).scalars().all()
    captured = 0
    for t in tenants:
        result = await capture_daily_snapshot(db, t.id)
        if result.get("captured"):
            captured += 1
    if captured > 0:
        await db.commit()
    return {"tenants": len(tenants), "captured": captured}
