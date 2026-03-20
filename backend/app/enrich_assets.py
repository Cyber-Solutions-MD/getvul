"""Enrich assets with CrowdStrike product_type_desc and reclassify."""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability  # noqa: F401
from app.tenants.models import Tenant, User  # noqa: F401
from app.connectors.service import get_decrypted_credentials
from app.db.session import async_session_factory
from app.ticketing.models import ConnectorConfig
from app.assets.classification import classify_asset_from_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def enrich():
    async with async_session_factory() as db:
        # Get CS connector
        r = await db.execute(
            select(ConnectorConfig).where(ConnectorConfig.connector_type == "CROWDSTRIKE")
        )
        conn = r.scalar_one_or_none()
        if not conn:
            print("No CrowdStrike connector found")
            return

        creds = get_decrypted_credentials(conn)
        base_url = (conn.config or {}).get("base_url", creds.get("base_url", "https://api.crowdstrike.com"))

        async with httpx.AsyncClient(timeout=60) as client:
            # Auth
            resp = await client.post(
                f"{base_url}/oauth2/token",
                data={"client_id": creds["client_id"], "client_secret": creds["client_secret"]},
            )
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Get ALL assets from DB — build multiple lookup keys
            result = await db.execute(select(Asset))
            assets = result.scalars().all()

            # Build lookup maps (case-insensitive)
            by_hostname_lower = {}
            by_hostname_stripped = {}  # without .local suffix
            for a in assets:
                if a.hostname:
                    h = a.hostname.lower()
                    by_hostname_lower[h] = a
                    # Also try without .local
                    if h.endswith(".local"):
                        by_hostname_stripped[h.replace(".local", "")] = a

            logger.info(f"DB has {len(assets)} assets, {len(by_hostname_lower)} unique hostnames")

            # Paginate through ALL CrowdStrike hosts
            offset = 0
            limit = 5000
            matched = 0
            unmatched = 0
            by_category = {}
            cs_total = 0

            while True:
                resp = await client.get(
                    f"{base_url}/devices/queries/devices/v1",
                    headers=headers,
                    params={"limit": limit, "offset": offset, "sort": "hostname.asc"},
                )
                if resp.status_code != 200:
                    logger.error(f"Query failed: {resp.status_code}")
                    break

                data = resp.json()
                aids = data.get("resources", [])
                if not aids:
                    break

                # Get full device details in batches of 100
                for batch_start in range(0, len(aids), 100):
                    batch = aids[batch_start : batch_start + 100]
                    resp2 = await client.get(
                        f"{base_url}/devices/entities/devices/v2",
                        headers=headers,
                        params={"ids": batch},
                    )
                    if resp2.status_code != 200:
                        continue

                    for device in resp2.json().get("resources", []):
                        cs_hostname = (device.get("hostname") or "").lower()
                        product_type_desc = device.get("product_type_desc", "")
                        platform_name = device.get("platform_name", "")
                        device_id = device.get("device_id", "")
                        cs_total += 1

                        # Try matching: exact → without .local → stripped
                        asset = (
                            by_hostname_lower.get(cs_hostname)
                            or by_hostname_stripped.get(cs_hostname)
                            or by_hostname_lower.get(cs_hostname + ".local")
                        )

                        if not asset:
                            unmatched += 1
                            continue

                        # Save AID
                        asset.crowdstrike_aid = device_id

                        # Update seen_by_sources with metadata
                        asset.seen_by_sources = {
                            "CROWDSTRIKE": {
                                "product_type_desc": product_type_desc,
                                "platform_name": platform_name,
                                "system_manufacturer": device.get("system_manufacturer", ""),
                                "system_product_name": device.get("system_product_name", ""),
                            }
                        }

                        # Classify
                        category = classify_asset_from_data(
                            hostname=asset.hostname or "",
                            os_name=asset.os_name or "",
                            platform_name=platform_name,
                            product_type_desc=product_type_desc,
                        )
                        asset.device_category = category
                        by_category[category] = by_category.get(category, 0) + 1
                        matched += 1

                total_hosts = data.get("meta", {}).get("pagination", {}).get("total", 0)
                logger.info(f"Processed {offset + len(aids)}/{total_hosts} CS hosts, matched {matched}")

                offset += limit
                if offset >= total_hosts:
                    break

            # For any remaining assets that didn't match CrowdStrike, reclassify from hostname/OS
            remaining = await db.execute(
                select(Asset).where(
                    (Asset.crowdstrike_aid.is_(None)) | (Asset.crowdstrike_aid == "")
                )
            )
            remaining_count = 0
            for asset in remaining.scalars().all():
                category = classify_asset_from_data(
                    hostname=asset.hostname or "",
                    os_name=asset.os_name or "",
                )
                if asset.device_category != category:
                    asset.device_category = category
                    by_category[category] = by_category.get(category, 0) + 1
                    remaining_count += 1

            await db.commit()
            logger.info(
                f"Done! CS hosts scanned: {cs_total}, "
                f"matched: {matched}, unmatched: {unmatched}, "
                f"reclassified from hostname: {remaining_count}"
            )
            logger.info(f"Categories: {by_category}")

asyncio.run(enrich())
