"""JAMF sync — enriches existing assets or creates new ones."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.classifier import classify_device
from app.assets.models import Asset
from app.connectors.jamf import JAMFConnector, NormalizedJAMFDevice
from app.connectors.service import get_decrypted_credentials
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger()


async def run_jamf_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a JAMF sync — fetches devices and enriches asset inventory."""
    now = datetime.now(timezone.utc)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING", started_at=now,
    )
    db.add(log)
    await db.flush()

    connector = JAMFConnector()
    credentials = get_decrypted_credentials(connector_config)

    try:
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "JAMF authentication failed"
            log.finished_at = datetime.now(timezone.utc)
            return log

        devices = await connector.fetch_devices()
        created, updated = 0, 0

        for device in devices:
            was_created = await _upsert_jamf_device(db, connector_config.tenant_id, device)
            if was_created:
                created += 1
            else:
                updated += 1

        log.status = "SUCCESS"
        log.records_fetched = len(devices)
        log.records_created = created
        log.records_updated = updated
        log.details = {"devices_fetched": len(devices), "created": created, "updated": updated}

        connector_config.last_sync_at = datetime.now(timezone.utc)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = len(devices)

    except Exception as e:
        logger.error("jamf_sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(timezone.utc)
        await connector.close()

    return log


async def _upsert_jamf_device(
    db: AsyncSession, tenant_id: uuid.UUID, device: NormalizedJAMFDevice,
) -> bool:
    """Match JAMF device to existing asset or create new. Returns True if created."""
    hostname = device.hostname.lower().strip()

    # Try to match by hostname
    result = await db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.hostname == hostname)
    )
    asset = result.scalar_one_or_none()

    # Also try matching by serial number if hostname didn't match
    if asset is None and device.serial_number:
        result = await db.execute(
            select(Asset).where(Asset.tenant_id == tenant_id, Asset.serial_number == device.serial_number)
        )
        asset = result.scalar_one_or_none()

    category = classify_device(hostname, device.os_name, device.os_version)

    if asset is None:
        asset = Asset(
            tenant_id=tenant_id,
            hostname=hostname,
            ip_addresses=[device.ip_address] if device.ip_address else [],
            mac_addresses=[device.mac_address] if device.mac_address else [],
            os_name=device.os_name,
            os_version=device.os_version,
            device_category=category,
            jamf_id=device.jamf_id,
            serial_number=device.serial_number,
            model=device.model,
            department=device.department,
            building=device.building,
            assigned_user=device.assigned_user,
            managed_by="JAMF",
            last_checkin_at=device.last_checkin,
            mdm_details=device.mdm_details,
            seen_by_sources=["JAMF"],
        )
        db.add(asset)
        await db.flush()
        return True
    else:
        # Enrich existing asset
        asset.jamf_id = device.jamf_id
        asset.serial_number = device.serial_number or asset.serial_number
        asset.model = device.model or asset.model
        asset.department = device.department or asset.department
        asset.building = device.building or asset.building
        asset.assigned_user = device.assigned_user or asset.assigned_user
        asset.managed_by = "JAMF"
        asset.last_checkin_at = device.last_checkin
        asset.mdm_details = device.mdm_details
        asset.device_category = category

        # Add JAMF to seen_by_sources
        sources = asset.seen_by_sources or []
        if "JAMF" not in sources:
            asset.seen_by_sources = sources + ["JAMF"]

        return False
