"""Sync orchestrator — runs connectors and persists normalized data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability
from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.service import get_decrypted_credentials
from app.cspm.models import Misconfiguration
from app.ticketing.models import ConnectorConfig, SyncLog
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

CONNECTOR_CLASSES: dict[str, type[BaseConnector]] = {
    "CROWDSTRIKE": CrowdStrikeConnector,
}


async def run_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a full sync for a connector."""
    now = datetime.now(timezone.utc)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING",
        started_at=now,
    )
    db.add(log)
    await db.flush()

    connector_cls = CONNECTOR_CLASSES.get(connector_config.connector_type)
    if not connector_cls:
        log.status = "FAILED"
        log.error_message = f"Unknown connector type: {connector_config.connector_type}"
        log.finished_at = datetime.now(timezone.utc)
        return log

    connector = connector_cls()
    credentials = get_decrypted_credentials(connector_config)

    try:
        # Authenticate
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "Authentication failed"
            log.finished_at = datetime.now(timezone.utc)
            return log

        # Fetch vulnerabilities
        vulns = await connector.fetch_vulnerabilities()
        vuln_created = 0
        vuln_updated = 0

        for v in vulns:
            asset = await _upsert_asset(db, connector_config.tenant_id, v, connector_config.connector_type)
            created = await _upsert_vulnerability(db, connector_config.tenant_id, v, asset.id, connector_config.connector_type)
            if created:
                vuln_created += 1
            else:
                vuln_updated += 1

        # Fetch CSPM misconfigurations
        misconfigs = await connector.fetch_misconfigurations()
        misconfig_created = 0

        for m in misconfigs:
            created = await _upsert_misconfiguration(db, connector_config.tenant_id, m, connector_config.connector_type)
            if created:
                misconfig_created += 1

        log.status = "SUCCESS"
        log.records_fetched = len(vulns) + len(misconfigs)
        log.records_created = vuln_created + misconfig_created
        log.records_updated = vuln_updated
        log.details = {
            "vulns_fetched": len(vulns),
            "vulns_created": vuln_created,
            "vulns_updated": vuln_updated,
            "misconfigs_fetched": len(misconfigs),
            "misconfigs_created": misconfig_created,
        }

        # Update connector metadata
        connector_config.last_sync_at = datetime.now(timezone.utc)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = log.records_fetched

    except Exception as e:
        logger.error("sync_error", connector=connector_config.connector_type, error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(timezone.utc)
        if hasattr(connector, "close"):
            await connector.close()

    return log


async def _upsert_asset(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, source: str,
) -> Asset:
    """Find or create an asset from a vulnerability finding."""
    hostname = (v.hostname or "unknown").lower().strip()

    result = await db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname)
    )
    asset = result.scalar_one_or_none()

    if asset is None:
        asset = Asset(
            tenant_id=tenant_id,
            hostname=hostname,
            ip_addresses=v.ip_addresses,
            os_name=v.os_name,
            os_version=v.os_version,
            asset_type=v.asset_type,
            seen_by_sources=[source],
        )
        db.add(asset)
        await db.flush()
    else:
        sources = asset.seen_by_sources or []
        if source not in sources:
            asset.seen_by_sources = sources + [source]

    return asset


async def _upsert_vulnerability(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability,
    asset_id: uuid.UUID, source: str,
) -> bool:
    """Upsert a vulnerability. Returns True if created, False if updated."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.cve_id == v.cve_id,
            Vulnerability.asset_id == asset_id,
            Vulnerability.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = v.severity
        existing.exploit_available = v.exploit_available
        return False
    else:
        vuln = Vulnerability(
            tenant_id=tenant_id,
            cve_id=v.cve_id,
            vulnerability_name=v.vulnerability_name,
            cvss_v3_score=v.cvss_v3_score,
            severity=v.severity,
            exploit_available=v.exploit_available,
            cisa_kev=v.cisa_kev,
            asset_id=asset_id,
            source=source,
            source_vuln_id=v.source_vuln_id,
            affected_product=v.affected_product,
            affected_version=v.affected_version,
            fixed_version=v.fixed_version,
            remediation_info=v.remediation_info,
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
        )
        db.add(vuln)
        await db.flush()
        return True


async def _upsert_misconfiguration(
    db: AsyncSession, tenant_id: uuid.UUID, m: NormalizedMisconfiguration, source: str,
) -> bool:
    """Upsert a misconfiguration. Returns True if created."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Misconfiguration).where(
            Misconfiguration.tenant_id == tenant_id,
            Misconfiguration.rule_id == m.rule_id,
            Misconfiguration.resource_id == m.resource_id,
            Misconfiguration.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.last_seen_at = now
        existing.severity = m.severity
        return False
    else:
        misconfig = Misconfiguration(
            tenant_id=tenant_id,
            rule_id=m.rule_id,
            rule_name=m.rule_name,
            rule_description=m.rule_description,
            category=m.category,
            severity=m.severity,
            frameworks=m.frameworks,
            resource_id=m.resource_id,
            resource_name=m.resource_name,
            resource_type=m.resource_type,
            resource_region=m.resource_region,
            cloud_provider=m.cloud_provider,
            cloud_account_id=m.cloud_account_id,
            cloud_account_name=m.cloud_account_name,
            source=source,
            source_finding_id=m.source_finding_id,
            remediation_info=m.remediation_info,
            remediation_url=m.remediation_url,
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
            details=m.details,
        )
        db.add(misconfig)
        await db.flush()
        return True
