"""Humaans sync — fetches people from Humaans and matches them to CrowdStrike assets.

Matching strategy (in priority order):
  1. Serial number: Humaans equipment serial → asset.serial_number
  2. Username: Humaans email local part → asset.last_login_user
  3. Name: Humaans preferred/first name (lowercase) → asset.last_login_user
  4. Hostname: Humaans first name → hostname pattern (e.g., "agustinuss-macbook")

Stores all Humaans people in a JSONB cache on the sync log for the users API.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.assets.models import Asset
from app.connectors.humaans import HumaansConnector, HumaansPerson
from app.connectors.service import get_decrypted_credentials
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger()


async def run_humaans_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a Humaans sync — fetches people and enriches matching assets."""
    now = datetime.now(UTC)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING",
        started_at=now,
    )
    db.add(log)
    await db.flush()

    connector = HumaansConnector()
    credentials = get_decrypted_credentials(connector_config)

    try:
        authed = await connector.authenticate(credentials, connector_config.config or {})
        if not authed:
            log.status = "FAILED"
            log.error_message = "Humaans authentication failed"
            log.finished_at = datetime.now(UTC)
            return log

        people = await connector.fetch_people_with_devices()

        matched = 0
        unmatched = 0

        for person in people:
            assets = await _find_matching_assets(db, connector_config.tenant_id, person)
            if assets:
                for asset in assets:
                    _enrich_asset(asset, person)
                matched += 1
            else:
                unmatched += 1

        log.status = "SUCCESS"
        log.records_fetched = len(people)
        log.records_created = 0
        log.records_updated = matched
        log.details = {
            "people_fetched": len(people),
            "people_matched_to_assets": matched,
            "people_unmatched": unmatched,
        }

        connector_config.last_sync_at = datetime.now(UTC)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = len(people)

    except Exception as e:
        logger.error("humaans_sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(UTC)
        await connector.close()

    return log


async def _find_matching_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    person: HumaansPerson,
) -> list[Asset]:
    """Find assets that belong to this person using multiple matching strategies."""
    # Build a set of candidate usernames from the Humaans person
    candidates: set[str] = set()

    # Email local part (e.g., "agustinus@parity.io" → "agustinus")
    if person.email and "@" in person.email:
        local = person.email.split("@")[0].lower().strip()
        if local:
            candidates.add(local)
            # Also try without dots (andrei.trandafir → andreitrandafir)
            candidates.add(local.replace(".", ""))

    # Preferred name and first name (lowercase)
    if person.preferred_name:
        candidates.add(person.preferred_name.lower().strip())
    if person.first_name:
        candidates.add(person.first_name.lower().strip())

    # Full name variants for hostname matching
    first_lower = (person.first_name or "").lower().strip()
    (person.last_name or "").lower().strip()

    if not candidates:
        return []

    # Strategy 1: Match serial numbers from equipment
    matched_assets: list[Asset] = []
    for device in person.devices:
        if device.serial_number:
            result = await db.execute(
                select(Asset).where(
                    Asset.tenant_id == tenant_id,
                    Asset.serial_number.ilike(device.serial_number.strip()),
                )
            )
            for asset in result.scalars().all():
                if asset not in matched_assets:
                    matched_assets.append(asset)

    if matched_assets:
        return matched_assets

    # Strategy 2: Match last_login_user against candidate usernames
    result = await db.execute(
        select(Asset).where(
            Asset.tenant_id == tenant_id,
            func.lower(Asset.last_login_user).in_(candidates),
        )
    )
    matched_assets = list(result.scalars().all())
    if matched_assets:
        return matched_assets

    # Strategy 3: Match hostname patterns (e.g., "agustinuss-macbook-pro.local")
    if first_lower and len(first_lower) >= 3:
        result = await db.execute(
            select(Asset).where(
                Asset.tenant_id == tenant_id,
                Asset.hostname.ilike(f"{first_lower}%"),
                Asset.device_category == "WORKSTATION",
            )
        )
        matched_assets = list(result.scalars().all())
        if matched_assets:
            return matched_assets

    return []


def _enrich_asset(asset: Asset, person: HumaansPerson) -> None:
    """Enrich an asset with Humaans person data."""
    display_name = person.preferred_name or person.first_name
    full_name = f"{display_name} {person.last_name}".strip()

    asset.assigned_user = full_name
    if person.department:
        asset.department = person.department

    # Store Humaans-specific data in mdm_details JSONB
    # Copy the dict to ensure SQLAlchemy detects the mutation
    humaans_data = dict(asset.mdm_details or {})
    humaans_data["humaans_person_id"] = person.person_id
    humaans_data["humaans_email"] = person.email
    humaans_data["humaans_job_title"] = person.job_title
    humaans_data["humaans_status"] = person.status
    if person.github_handle:
        humaans_data["github_handle"] = person.github_handle
    if person.linkedin_handle:
        humaans_data["linkedin_handle"] = person.linkedin_handle
    if person.element_handle:
        humaans_data["element_handle"] = person.element_handle
    if person.teams:
        humaans_data["humaans_teams"] = person.teams
    if person.timezone:
        humaans_data["humaans_timezone"] = person.timezone
    if person.remote_city or person.remote_country:
        humaans_data["humaans_location"] = ", ".join(filter(None, [person.remote_city, person.remote_country]))
    # Store device names from Humaans equipment
    if person.devices:
        humaans_data["humaans_devices"] = [
            {"name": d.name, "serial": d.serial_number, "type": d.equipment_type} for d in person.devices
        ]
    asset.mdm_details = humaans_data
    flag_modified(asset, "mdm_details")

    # Add HUMAANS to seen_by_sources
    sources = asset.seen_by_sources or []
    if "HUMAANS" not in sources:
        asset.seen_by_sources = sources + ["HUMAANS"]
        flag_modified(asset, "seen_by_sources")
