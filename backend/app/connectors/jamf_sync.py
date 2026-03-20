"""JAMF sync — enriches existing assets with MDM data from Jamf Pro."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.assets.classification import classify_asset_from_data
from app.assets.models import Asset
from app.connectors.jamf import JamfConnector
from app.connectors.service import get_decrypted_credentials
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger()


async def run_jamf_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a JAMF sync — fetches computers and enriches asset inventory."""
    now = datetime.now(timezone.utc)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING", started_at=now,
    )
    db.add(log)
    await db.flush()

    credentials = get_decrypted_credentials(connector_config)
    config = connector_config.config or {}
    base_url = config.get("base_url", credentials.get("base_url", ""))

    if not base_url:
        log.status = "FAILED"
        log.error_message = "Base URL is required for Jamf Pro"
        log.finished_at = datetime.now(timezone.utc)
        return log

    connector = JamfConnector(
        base_url=base_url,
        client_id=credentials.get("client_id", ""),
        client_secret=credentials.get("client_secret", ""),
    )

    try:
        authed = await connector.authenticate()
        if not authed:
            log.status = "FAILED"
            log.error_message = "JAMF authentication failed"
            log.finished_at = datetime.now(timezone.utc)
            return log

        computers = await connector.fetch_computers()
        created, updated = 0, 0

        for comp in computers:
            was_created = await _upsert_jamf_device(db, connector_config.tenant_id, comp)
            if was_created:
                created += 1
            else:
                updated += 1

        log.status = "SUCCESS"
        log.records_fetched = len(computers)
        log.records_created = created
        log.records_updated = updated
        log.details = {"computers_fetched": len(computers), "created": created, "updated": updated}

        connector_config.last_sync_at = datetime.now(timezone.utc)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = len(computers)

    except Exception as e:
        logger.error("jamf_sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(timezone.utc)

    return log


async def _upsert_jamf_device(
    db: AsyncSession, tenant_id: uuid.UUID, comp: dict,
) -> bool:
    """Match JAMF computer to existing asset by serial number, login user, or hostname. Returns True if created."""
    hostname = (comp.get("name") or "unknown").lower().strip()
    serial = (comp.get("serial_number") or "").strip()
    login_user = (comp.get("last_login_user") or "").strip().lower()

    asset = None

    # Strategy 1: Serial number match (most reliable)
    if serial:
        result = await db.execute(
            select(Asset).where(Asset.tenant_id == tenant_id, Asset.serial_number == serial)
        )
        asset = result.scalars().first()

    # Strategy 2: Login user match (Jamf lastLoggedInUsernameBinary == CrowdStrike last_login_user)
    if asset is None and login_user:
        result = await db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                func.lower(Asset.last_login_user) == login_user,
                Asset.device_category == "WORKSTATION",
            )
        )
        asset = result.scalars().first()

    # Strategy 3: Hostname match
    if asset is None:
        result = await db.execute(
            select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname)
        )
        asset = result.scalar_one_or_none()

    os_name = comp.get("os_name", "")
    os_version = comp.get("os_version", "")
    category = classify_asset_from_data(
        hostname=hostname, os_name=os_name, platform_name=os_name,
    )

    # Build MDM security details
    mdm_details = {}
    if comp.get("filevault_enabled") is not None:
        mdm_details["filevault_enabled"] = comp["filevault_enabled"]
    if comp.get("sip_enabled") is not None:
        mdm_details["sip_enabled"] = comp["sip_enabled"]
    if comp.get("gatekeeper_enabled") is not None:
        mdm_details["gatekeeper_enabled"] = comp["gatekeeper_enabled"]

    # Parse last checkin timestamp
    last_checkin = None
    if comp.get("last_checkin"):
        try:
            last_checkin = datetime.fromisoformat(comp["last_checkin"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    if asset is None:
        asset = Asset(
            tenant_id=tenant_id,
            hostname=hostname,
            ip_addresses=[comp["ip_address"]] if comp.get("ip_address") else [],
            mac_addresses=[comp["mac_address"]] if comp.get("mac_address") else [],
            os_name=os_name,
            os_version=os_version,
            device_category=category,
            jamf_id=comp.get("jamf_id"),
            serial_number=serial or None,
            model=comp.get("model"),
            department=comp.get("department") or None,
            building=comp.get("building") or None,
            assigned_user=comp.get("assigned_user") or None,
            managed_by="JAMF",
            last_checkin_at=last_checkin,
            mdm_details=mdm_details or None,
            seen_by_sources=["JAMF"],
        )
        db.add(asset)
        await db.flush()
        return True
    else:
        # Enrich existing asset with Jamf data
        asset.jamf_id = comp.get("jamf_id")
        if serial:
            asset.serial_number = serial
        if comp.get("model"):
            asset.model = comp["model"]
        if comp.get("department"):
            asset.department = comp["department"]
        if comp.get("building"):
            asset.building = comp["building"]
        # Only set Jamf username if no richer name from Humaans exists
        if comp.get("assigned_user") and not asset.assigned_user:
            asset.assigned_user = comp["assigned_user"]
        asset.managed_by = "JAMF"
        asset.last_checkin_at = last_checkin
        if category != "OTHER":
            asset.device_category = category

        # Merge MDM details (preserve existing Humaans data)
        existing_mdm = dict(asset.mdm_details or {})
        existing_mdm.update(mdm_details)
        asset.mdm_details = existing_mdm
        flag_modified(asset, "mdm_details")

        # Add JAMF to seen_by_sources
        sources = asset.seen_by_sources or []
        if "JAMF" not in sources:
            asset.seen_by_sources = sources + ["JAMF"]
            flag_modified(asset, "seen_by_sources")

        return False
