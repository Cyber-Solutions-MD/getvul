"""Alert engine — periodic checks that create notifications for security events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.notifications.models import Notification
from app.notifications.service import create_notification
from app.tenants.models import Tenant, User
from app.ticketing.models import ConnectorConfig
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.trends import DailySnapshot

logger = structlog.get_logger()


async def run_alert_checks(db: AsyncSession) -> dict:
    """Check all alert conditions across tenants and create notifications."""
    tenants = (await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))).scalars().all()

    total_alerts = 0
    for tenant in tenants:
        alerts = 0
        alerts += await _check_new_critical_vulns(db, tenant)
        alerts += await _check_sla_breaches(db, tenant)
        alerts += await _check_sync_failures(db, tenant)
        alerts += await _check_risk_score_changes(db, tenant)
        total_alerts += alerts

    await db.commit()
    logger.info("alert_checks_complete", tenants_checked=len(tenants), alerts_created=total_alerts)
    return {"tenants_checked": len(tenants), "alerts_created": total_alerts}


# ---------------------------------------------------------------------------
# Individual alert checks
# ---------------------------------------------------------------------------


async def _check_new_critical_vulns(db: AsyncSession, tenant: Tenant) -> int:
    """Find critical vulnerabilities detected in the last 2 hours with no existing notification."""
    cutoff = datetime.now(UTC) - timedelta(hours=2)
    alerts_created = 0

    vulns = (
        await db.execute(
            select(Vulnerability, Asset)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant.id,
                Vulnerability.severity == "CRITICAL",
                Vulnerability.first_detected_at >= cutoff,
            )
        )
    ).all()

    for vuln, asset in vulns:
        resource_id = vuln.cve_id or str(vuln.id)

        # Deduplicate — skip if notification already exists for this vuln
        if await _notification_exists(db, tenant.id, "new_critical_vuln", "vulnerability", resource_id, hours=2):
            continue

        hostname = asset.hostname if asset else "Unknown host"
        score = vuln.cvss_v3_score or "N/A"
        vuln_name = vuln.vulnerability_name or vuln.cve_id or "Unknown vulnerability"

        # Create broadcast notification (user_id=None)
        await create_notification(
            db,
            tenant_id=tenant.id,
            title=f"New Critical Vulnerability: {resource_id}",
            message=f"{vuln_name} detected on {hostname} — CVSS {score}",
            severity="critical",
            category="new_critical_vuln",
            resource_type="vulnerability",
            resource_id=resource_id,
            details={"cve_id": vuln.cve_id, "asset_id": str(vuln.asset_id) if vuln.asset_id else None},
        )
        alerts_created += 1

        # Send email to OWNER and ADMIN users
        await _email_owners_and_admins(
            db,
            tenant,
            f"New Critical Vulnerability: {resource_id}",
            f"{vuln_name} detected on {hostname} — CVSS {score}",
            "new_critical_vuln",
        )

    return alerts_created


async def _check_sla_breaches(db: AsyncSession, tenant: Tenant) -> int:
    """D-08 reconciliation (Phase 36 Plan 03): retired to a no-op.

    This was a flat, severity-agnostic 24h-lookahead in-app breach warning.
    It has been superseded by the risk-tier SLA engine's own in-app twin
    (`app.vulnerabilities.sla_tier_service.detect_and_escalate`, category=
    "sla_escalation") -- keeping both alive would double-fire two unrelated
    in-app signals for the same finding on every breach (36-RESEARCH.md
    Pitfall 1). Kept as a callable no-op (rather than deleted + removing
    its call site in `run_alert_checks`) so the diff stays minimal and the
    reconciliation intent is self-documented at the retired function's own
    definition. `tenant`/`db` are accepted but unused -- preserved for
    call-site compatibility.
    """
    return 0


async def _check_sync_failures(db: AsyncSession, tenant: Tenant) -> int:
    """Find connectors with failed sync status."""
    alerts_created = 0

    connectors = (
        (
            await db.execute(
                select(ConnectorConfig).where(
                    ConnectorConfig.tenant_id == tenant.id,
                    ConnectorConfig.is_enabled.is_(True),
                    ConnectorConfig.last_sync_status.in_(["error", "FAILED", "failed"]),
                )
            )
        )
        .scalars()
        .all()
    )

    for connector in connectors:
        resource_id = str(connector.id)

        # Only create if no existing sync_failure for this connector in last 4 hours
        if await _notification_exists(db, tenant.id, "sync_failure", "connector", resource_id, hours=4):
            continue

        sync_time = connector.last_sync_at.isoformat() if connector.last_sync_at else "unknown"

        await create_notification(
            db,
            tenant_id=tenant.id,
            title=f"Connector Sync Failed: {connector.connector_type}",
            message=f"{connector.connector_type} sync failed at {sync_time}",
            severity="medium",
            category="sync_failure",
            resource_type="connector",
            resource_id=resource_id,
            details={"connector_type": connector.connector_type, "last_sync_at": sync_time},
        )
        alerts_created += 1

    return alerts_created


async def _check_risk_score_changes(db: AsyncSession, tenant: Tenant) -> int:
    """Find assets where risk score spiked 20+ points since yesterday's snapshot.

    RISK-10 (Phase 34 Plan 04) version-boundary guard: reads
    `tenant.cutover_risk_exposure_scoring` once and diffs SAME-VERSION-only —
    new-vs-new (Vulnerability/Asset.risk_exposure_score-derived) when ON,
    old-vs-old (Asset.risk_score-derived) when OFF. NEVER cross-version
    (new-vs-old or old-vs-new), so a risk_model_version change across the
    day this flag flips cannot manufacture a synthetic scale-jump alert
    storm — see 34-CONTEXT.md RESOLVED A2 / 34-RESEARCH.md:308-312.
    """
    alerts_created = 0
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()

    # Get yesterday's snapshot
    snapshot = (
        await db.execute(
            select(DailySnapshot).where(
                DailySnapshot.tenant_id == tenant.id,
                DailySnapshot.snapshot_date == yesterday,
            )
        )
    ).scalar_one_or_none()

    if not snapshot or not snapshot.metrics:
        return 0

    cutover_enabled = tenant.cutover_risk_exposure_scoring
    metrics_key = "asset_risk_exposure_scores" if cutover_enabled else "asset_risk_scores"
    score_column = Asset.risk_exposure_score if cutover_enabled else Asset.risk_score

    # Check if the snapshot has per-asset risk scores for the ACTIVE version
    asset_scores_yesterday = snapshot.metrics.get(metrics_key, {})
    if not asset_scores_yesterday:
        return 0

    # Get current assets with a populated score on the ACTIVE version
    assets = (
        (
            await db.execute(
                select(Asset).where(
                    Asset.tenant_id == tenant.id,
                    score_column.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )

    for asset in assets:
        old_score = asset_scores_yesterday.get(str(asset.id))
        if old_score is None:
            continue

        new_score = (asset.risk_exposure_score if cutover_enabled else asset.risk_score) or 0
        delta = new_score - old_score

        if delta >= 20:
            resource_id = str(asset.id)

            if await _notification_exists(db, tenant.id, "risk_change", "asset", resource_id, hours=24):
                continue

            hostname = asset.hostname or "Unknown host"

            await create_notification(
                db,
                tenant_id=tenant.id,
                title=f"Risk Score Spike: {hostname}",
                message=f"{hostname} risk score changed from {old_score} to {new_score}",
                severity="high",
                category="risk_change",
                resource_type="asset",
                resource_id=resource_id,
                details={"old_score": old_score, "new_score": new_score, "delta": delta},
            )
            alerts_created += 1

    return alerts_created


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _notification_exists(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    category: str,
    resource_type: str,
    resource_id: str,
    *,
    hours: int,
) -> bool:
    """Check if a notification with matching dedup key exists within the lookback window."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.category == category,
            Notification.resource_type == resource_type,
            Notification.resource_id == resource_id,
            Notification.created_at >= cutoff,
        )
    )
    return result.scalar_one() > 0


async def _email_owners_and_admins(
    db: AsyncSession,
    tenant: Tenant,
    title: str,
    message: str,
    category: str,
) -> None:
    """Send notification email to all OWNER and ADMIN users of a tenant."""
    from app.notifications.service import _send_notification_email

    users = (
        (
            await db.execute(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.is_active.is_(True),
                    User.role.in_(["OWNER", "ADMIN"]),
                )
            )
        )
        .scalars()
        .all()
    )

    for user in users:
        await _send_notification_email(db, tenant.id, user.email, title, message, category)
