"""Sync orchestrator — runs connectors and persists normalized data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.classification import classify_asset_from_data
from app.assets.models import Asset
from app.assets.risk_score import compute_risk_scores
from app.connectors.base import BaseConnector, NormalizedMisconfiguration, NormalizedVulnerability
from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.defender import DefenderConnector
from app.connectors.nessus import NessusConnector
from app.connectors.qualys import QualysConnector
from app.connectors.rapid7 import Rapid7Connector
from app.connectors.service import get_decrypted_credentials
from app.connectors.wiz import WizConnector
from app.cspm.models import Misconfiguration
from app.ticketing.models import ConnectorConfig, SyncLog
from app.vulnerabilities.correlation_service import run_correlations
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

CONNECTOR_CLASSES: dict[str, type[BaseConnector]] = {
    "CROWDSTRIKE": CrowdStrikeConnector,
    "NESSUS": NessusConnector,
    "DEFENDER": DefenderConnector,
    "WIZ": WizConnector,
    "QUALYS": QualysConnector,
    "RAPID7": Rapid7Connector,
}

# Special connectors that don't follow the standard vuln/cspm pattern
SPECIAL_CONNECTORS = {"JAMF", "HUMAANS", "ASANA", "JIRA", "GOOGLE_WORKSPACE", "AZURE_ENTRA_ID", "OKTA", "INTUNE"}


async def run_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    now = datetime.now(UTC)
    log = SyncLog(
        connector_id=connector_config.id, tenant_id=connector_config.tenant_id, status="RUNNING", started_at=now
    )
    db.add(log)
    await db.flush()

    # Special connectors that don't follow the standard vuln/cspm pattern
    if connector_config.connector_type == "JAMF":
        from app.connectors.jamf_sync import run_jamf_sync

        return await run_jamf_sync(db, connector_config)

    if connector_config.connector_type == "HUMAANS":
        from app.connectors.humaans_sync import run_humaans_sync

        return await run_humaans_sync(db, connector_config)

    if connector_config.connector_type in ("GOOGLE_WORKSPACE", "AZURE_ENTRA_ID"):
        from app.connectors.directory_sync import run_directory_sync

        return await run_directory_sync(db, connector_config)

    if connector_config.connector_type == "OKTA":
        from app.connectors.okta_sync import run_okta_sync

        return await run_okta_sync(db, connector_config)

    if connector_config.connector_type == "INTUNE":
        from app.connectors.intune_sync import run_intune_sync

        return await run_intune_sync(db, connector_config)

    if connector_config.connector_type in ("ASANA", "JIRA"):
        # Asana is a ticketing connector — no data to sync, just config storage
        log.status = "SUCCESS"
        log.finished_at = datetime.now(UTC)
        log.details = {"message": "Asana is a ticketing connector, no data sync needed"}
        return log

    connector_cls = CONNECTOR_CLASSES.get(connector_config.connector_type)
    if not connector_cls:
        log.status = "FAILED"
        log.error_message = f"Unknown connector: {connector_config.connector_type}"
        log.finished_at = datetime.now(UTC)
        return log

    connector = connector_cls()
    credentials = get_decrypted_credentials(connector_config)

    try:
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "Authentication failed"
            log.finished_at = datetime.now(UTC)
            return log

        vulns = await connector.fetch_vulnerabilities()
        vc, vu = 0, 0
        for v in vulns:
            asset = await _upsert_asset(db, connector_config.tenant_id, v, connector_config.connector_type)
            created = await _upsert_vulnerability(
                db, connector_config.tenant_id, v, asset.id, connector_config.connector_type
            )
            if created:
                vc += 1
            else:
                vu += 1

        misconfigs = await connector.fetch_misconfigurations()
        mc = 0
        for m in misconfigs:
            if await _upsert_misconfiguration(db, connector_config.tenant_id, m, connector_config.connector_type):
                mc += 1

        # Post-sync: run correlation engine and risk score computation
        corr_stats = await run_correlations(db, connector_config.tenant_id)
        risk_stats = await compute_risk_scores(db, connector_config.tenant_id)

        log.status = "SUCCESS"
        log.records_fetched = len(vulns) + len(misconfigs)
        log.records_created = vc + mc
        log.records_updated = vu
        log.details = {
            "vulns_fetched": len(vulns),
            "vulns_created": vc,
            "vulns_updated": vu,
            "misconfigs_fetched": len(misconfigs),
            "misconfigs_created": mc,
            "correlations": corr_stats,
            "risk_scores": risk_stats,
        }
        connector_config.last_sync_at = datetime.now(UTC)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = log.records_fetched

    except Exception as e:
        logger.error("sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(UTC)
        if hasattr(connector, "close"):
            await connector.close()

    return log


async def _upsert_asset(db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, source: str) -> Asset:
    hostname = (v.hostname or "unknown").lower().strip()
    result = await db.execute(select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname))
    asset = result.scalar_one_or_none()

    # Classify using all available hints from the source
    platform_name = getattr(v, "platform_name", None) or ""
    product_type_desc = getattr(v, "product_type_desc", None) or ""
    device_category = classify_asset_from_data(
        hostname=hostname,
        os_name=v.os_name or "",
        platform_name=platform_name,
        product_type_desc=product_type_desc,
    )

    # Parse timestamps from source
    _last_login_at = _parse_ts(getattr(v, "last_login_at", None))
    _last_seen_at = _parse_ts(getattr(v, "last_seen_at", None))

    # Build model name from manufacturer + product
    _manufacturer = getattr(v, "system_manufacturer", None) or ""
    _product_name = getattr(v, "system_product_name", None) or ""
    _model = f"{_manufacturer} {_product_name}".strip() if (_manufacturer or _product_name) else None

    if asset is None:
        asset = Asset(
            tenant_id=tenant_id,
            hostname=hostname,
            ip_addresses=v.ip_addresses,
            mac_addresses=[v.mac_address] if getattr(v, "mac_address", None) else [],
            os_name=v.os_name,
            os_version=v.os_version,
            asset_type=product_type_desc or v.asset_type,
            seen_by_sources=[source],
            device_category=device_category,
            # CrowdStrike device enrichment
            serial_number=getattr(v, "serial_number", None),
            model=_model,
            system_manufacturer=_manufacturer or None,
            external_ip=getattr(v, "external_ip", None),
            last_login_user=getattr(v, "last_login_user", None),
            last_login_at=_last_login_at,
            last_seen_at=_last_seen_at,
            host_status=getattr(v, "host_status", None),
            crowdstrike_aid=getattr(v, "crowdstrike_aid", None),
            defender_device_id=getattr(v, "defender_device_id", None),
            wiz_asset_id=getattr(v, "wiz_asset_id", None),
            nessus_host_id=getattr(v, "nessus_host_id", None),
        )
        db.add(asset)
        await db.flush()
    else:
        sources = asset.seen_by_sources or []
        if source not in sources:
            asset.seen_by_sources = sources + [source]
        # Update classification if we now have better data (e.g., product_type_desc)
        if product_type_desc or not asset.device_category or asset.device_category == "OTHER":
            asset.device_category = device_category
        if product_type_desc:
            asset.asset_type = product_type_desc
        if v.os_version and (not asset.os_version or len(v.os_version) > len(asset.os_version or "")):
            asset.os_version = v.os_version
        # Always update volatile device fields from source
        if getattr(v, "serial_number", None):
            asset.serial_number = v.serial_number
        if _model:
            asset.model = _model
        if _manufacturer:
            asset.system_manufacturer = _manufacturer
        if getattr(v, "external_ip", None):
            asset.external_ip = v.external_ip
        if getattr(v, "mac_address", None):
            asset.mac_addresses = [v.mac_address]
        if getattr(v, "last_login_user", None):
            asset.last_login_user = v.last_login_user
        if _last_login_at:
            asset.last_login_at = _last_login_at
        if _last_seen_at:
            asset.last_seen_at = _last_seen_at
        if getattr(v, "host_status", None):
            asset.host_status = v.host_status
        if getattr(v, "crowdstrike_aid", None):
            asset.crowdstrike_aid = v.crowdstrike_aid
        if getattr(v, "defender_device_id", None):
            asset.defender_device_id = v.defender_device_id
        if getattr(v, "wiz_asset_id", None):
            asset.wiz_asset_id = v.wiz_asset_id
        if getattr(v, "nessus_host_id", None):
            asset.nessus_host_id = v.nessus_host_id
    return asset


def _parse_ts(val: str | None) -> datetime | None:
    """Parse an ISO timestamp string to datetime, or return None."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


async def _upsert_vulnerability(
    db: AsyncSession, tenant_id: uuid.UUID, v: NormalizedVulnerability, asset_id: uuid.UUID, source: str
) -> bool:
    now = datetime.now(UTC)
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
        existing.cisa_kev = v.cisa_kev
        existing.remediation_id = getattr(v, "remediation_id", None)
        existing.remediation_action = getattr(v, "remediation_action", None) or v.remediation_info
        existing.exploit_status_id = getattr(v, "exploit_status_id", None)
        existing.exploit_status_name = getattr(v, "exploit_status_name", None)
        if getattr(v, "file_paths", None):
            existing.file_paths = v.file_paths
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
            remediation_id=getattr(v, "remediation_id", None),
            remediation_action=getattr(v, "remediation_action", None) or v.remediation_info,
            remediation_info=v.remediation_info,
            exploit_status_id=getattr(v, "exploit_status_id", None),
            exploit_status_name=getattr(v, "exploit_status_name", None),
            file_paths=getattr(v, "file_paths", None),
            status="OPEN",
            first_detected_at=now,
            last_seen_at=now,
        )
        db.add(vuln)
        await db.flush()
        return True


async def _upsert_misconfiguration(
    db: AsyncSession, tenant_id: uuid.UUID, m: NormalizedMisconfiguration, source: str
) -> bool:
    now = datetime.now(UTC)
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
        mc = Misconfiguration(
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
        db.add(mc)
        await db.flush()
        return True
