"""SLA tracking — compute due dates, check breaches, report compliance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# Default SLA days per severity (used if tenant has no custom config)
DEFAULT_SLA_DAYS = {
    "CRITICAL": 7,
    "HIGH": 30,
    "MEDIUM": 90,
    "LOW": 180,
    "INFO": 365,
}


def get_sla_days(tenant: Tenant | None) -> dict[str, int]:
    """Get SLA days config for a tenant, falling back to defaults."""
    if tenant and tenant.sla_config and tenant.sla_config.get("days"):
        custom = tenant.sla_config["days"]
        return {
            "CRITICAL": custom.get("CRITICAL", DEFAULT_SLA_DAYS["CRITICAL"]),
            "HIGH": custom.get("HIGH", DEFAULT_SLA_DAYS["HIGH"]),
            "MEDIUM": custom.get("MEDIUM", DEFAULT_SLA_DAYS["MEDIUM"]),
            "LOW": custom.get("LOW", DEFAULT_SLA_DAYS["LOW"]),
            "INFO": custom.get("INFO", DEFAULT_SLA_DAYS["INFO"]),
        }
    return dict(DEFAULT_SLA_DAYS)


async def backfill_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Set sla_due_at for all open vulns that don't have one yet."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)

    updated = 0
    for severity, days in sla_days.items():
        result = await db.execute(
            update(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == severity,
                Vulnerability.sla_due_at.is_(None),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.first_detected_at.isnot(None),
            )
            .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
        )
        updated += result.rowcount

    return {"backfilled": updated}


async def recalculate_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Recalculate sla_due_at for ALL open vulns based on current SLA config."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)

    updated = 0
    for severity, days in sla_days.items():
        result = await db.execute(
            update(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == severity,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.first_detected_at.isnot(None),
            )
            .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
        )
        updated += result.rowcount

    return {"recalculated": updated}


async def check_sla_breaches(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Mark vulns as breached if past their SLA due date."""
    now = datetime.now(UTC)

    # Mark newly breached
    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.sla_due_at < now,
            Vulnerability.sla_breached.is_(False),
        )
        .values(sla_breached=True)
    )
    newly_breached = result.rowcount

    # Un-breach vulns that were remediated/suppressed (cleanup)
    cleanup = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.sla_breached.is_(True),
            Vulnerability.status.in_(["REMEDIATED", "SUPPRESSED", "FALSE_POSITIVE"]),
        )
        .values(sla_breached=False)
    )

    return {"newly_breached": newly_breached, "cleaned_up": cleanup.rowcount}


async def get_sla_metrics(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get comprehensive SLA compliance metrics."""
    now = datetime.now(UTC)

    # Get tenant SLA config for display
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)

    # Open vulns with SLA tracking
    open_with_sla = (await db.execute(
        select(func.count(Vulnerability.id)).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_due_at.isnot(None),
        )
    )).scalar_one()

    # Breached (open + past due)
    breached = (await db.execute(
        select(func.count(Vulnerability.id)).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_breached.is_(True),
        )
    )).scalar_one()

    # At risk (due within 72 hours)
    at_risk_cutoff = now + timedelta(hours=72)
    at_risk = (await db.execute(
        select(func.count(Vulnerability.id)).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.sla_due_at <= at_risk_cutoff,
            Vulnerability.sla_due_at > now,
            Vulnerability.sla_breached.is_(False),
        )
    )).scalar_one()

    # Within SLA (open, not breached, not at risk)
    within_sla = open_with_sla - breached - at_risk

    # Compliance % (remediated within SLA in last 90 days)
    ninety_days_ago = now - timedelta(days=90)
    remediated_total = (await db.execute(
        select(func.count(Vulnerability.id)).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status == "REMEDIATED",
            Vulnerability.remediated_at >= ninety_days_ago,
            Vulnerability.sla_due_at.isnot(None),
        )
    )).scalar_one()

    remediated_within_sla = (await db.execute(
        select(func.count(Vulnerability.id)).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status == "REMEDIATED",
            Vulnerability.remediated_at >= ninety_days_ago,
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.remediated_at <= Vulnerability.sla_due_at,
        )
    )).scalar_one()

    compliance_pct = round((remediated_within_sla / remediated_total * 100), 1) if remediated_total > 0 else 100.0

    # Breach breakdown by severity
    breach_by_sev_q = (
        select(Vulnerability.severity, func.count(Vulnerability.id))
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_breached.is_(True),
        )
        .group_by(Vulnerability.severity)
    )
    breach_by_sev = {r[0]: r[1] for r in (await db.execute(breach_by_sev_q)).all()}

    # Average days remaining for open vulns
    avg_days_remaining = (await db.execute(
        select(func.avg(
            func.extract("epoch", Vulnerability.sla_due_at - func.now()) / 86400
        )).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.sla_breached.is_(False),
        )
    )).scalar_one()

    return {
        "sla_config": sla_days,
        "open_with_sla": open_with_sla,
        "breached": breached,
        "at_risk": at_risk,
        "within_sla": within_sla,
        "compliance_pct": compliance_pct,
        "remediated_within_sla": remediated_within_sla,
        "remediated_total": remediated_total,
        "breach_by_severity": breach_by_sev,
        "avg_days_remaining": round(float(avg_days_remaining), 1) if avg_days_remaining else None,
    }
