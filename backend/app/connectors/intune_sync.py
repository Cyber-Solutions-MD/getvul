"""Microsoft Intune MDM sync — fetches managed devices and enriches Asset records."""

import asyncio
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.assets.classification import classify_asset_from_data
from app.assets.models import Asset
from app.connectors.service import get_decrypted_credentials
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


async def _get_access_token(
    client: httpx.AsyncClient,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Authenticate via Azure AD OAuth2 client_credentials flow."""
    url = TOKEN_URL.format(tenant_id=tenant_id)
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }
    resp = await client.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _fetch_managed_devices(
    client: httpx.AsyncClient,
    token: str,
) -> list[dict]:
    """Fetch all managed devices, handling pagination and rate limits."""
    devices: list[dict] = []
    url = f"{GRAPH_BASE}/deviceManagement/managedDevices"
    headers = {"Authorization": f"Bearer {token}"}

    while url:
        resp = await client.get(url, headers=headers)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("intune_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            continue

        resp.raise_for_status()
        body = resp.json()
        devices.extend(body.get("value", []))
        url = body.get("@odata.nextLink")

    return devices


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _enrich_asset(asset: Asset, device: dict) -> None:
    """Apply Intune device fields onto an Asset record."""
    asset.os_name = device.get("operatingSystem") or asset.os_name
    asset.os_version = device.get("osVersion") or asset.os_version
    asset.serial_number = device.get("serialNumber") or asset.serial_number

    manufacturer = device.get("manufacturer") or ""
    model = device.get("model") or ""
    if manufacturer or model:
        asset.model = f"{manufacturer} {model}".strip()
    asset.system_manufacturer = manufacturer or asset.system_manufacturer

    asset.assigned_user = device.get("userDisplayName") or device.get("userPrincipalName") or asset.assigned_user
    asset.managed_by = "INTUNE"

    last_sync = _parse_iso(device.get("lastSyncDateTime"))
    if last_sync:
        asset.last_checkin_at = last_sync

    asset.mdm_details = {
        "complianceState": device.get("complianceState"),
        "managementAgent": device.get("managementAgent"),
        "enrolledDateTime": device.get("enrolledDateTime"),
        "managedDeviceOwnerType": device.get("managedDeviceOwnerType"),
        "intune_device_id": device.get("id"),
    }
    flag_modified(asset, "mdm_details")

    # Ensure INTUNE is recorded in seen_by_sources
    sources = asset.seen_by_sources or []
    if "INTUNE" not in sources:
        sources.append("INTUNE")
        asset.seen_by_sources = sources
        flag_modified(asset, "seen_by_sources")

    classify_asset_from_data(asset)


async def run_intune_sync(
    db: AsyncSession,
    connector_config: ConnectorConfig,
) -> SyncLog:
    """Run a full Intune managed-device sync and enrich/create Asset records."""

    sync_log = SyncLog(
        connector_config_id=connector_config.id,
        status="running",
        started_at=datetime.now(UTC),
        records_fetched=0,
        records_created=0,
        records_updated=0,
    )
    db.add(sync_log)
    await db.flush()

    creds = get_decrypted_credentials(connector_config)
    tenant_id = creds["tenant_id"]
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await _get_access_token(client, tenant_id, client_id, client_secret)
            devices = await _fetch_managed_devices(client, token)

        sync_log.records_fetched = len(devices)
        logger.info("intune_devices_fetched", count=len(devices))

        for device in devices:
            device_name = (device.get("deviceName") or "").strip().lower()
            serial = (device.get("serialNumber") or "").strip()

            # Try to match by hostname
            asset: Asset | None = None
            if device_name:
                result = await db.execute(select(Asset).where(Asset.hostname == device_name))
                asset = result.scalars().first()

            # Try to match by serial number
            if asset is None and serial:
                result = await db.execute(select(Asset).where(Asset.serial_number == serial))
                asset = result.scalars().first()

            if asset:
                _enrich_asset(asset, device)
                sync_log.records_updated += 1
            elif device_name:
                asset = Asset(hostname=device_name)
                _enrich_asset(asset, device)
                db.add(asset)
                sync_log.records_created += 1

        sync_log.status = "success"
        sync_log.finished_at = datetime.now(UTC)
        await db.flush()
        logger.info(
            "intune_sync_complete",
            fetched=sync_log.records_fetched,
            created=sync_log.records_created,
            updated=sync_log.records_updated,
        )

    except Exception as exc:
        sync_log.status = "error"
        sync_log.error_message = str(exc)[:2000]
        sync_log.finished_at = datetime.now(UTC)
        await db.flush()
        logger.error("intune_sync_failed", error=str(exc))

    return sync_log
