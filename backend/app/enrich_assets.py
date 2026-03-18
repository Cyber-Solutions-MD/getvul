"""Enrich assets with CrowdStrike product_type_desc and reclassify."""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability  # noqa: F401 — resolve relationships
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

            # Get ALL assets from DB
            result = await db.execute(select(Asset))
            assets = result.scalars().all()
            hostname_to_asset = {a.hostname.lower(): a for a in assets if a.hostname}
            logger.info(f"Found {len(assets)} total assets, {len(hostname_to_asset)} unique hostnames")

            # Paginate through ALL CrowdStrike hosts
            offset = 0
            limit = 500
            matched = 0
            by_category = {}

            while True:
                # Get batch of device IDs
                resp = await client.get(
                    f"{base_url}/devices/queries/devices/v1",
                    headers=headers,
                    params={"limit": limit, "offset": offset},
                )
                if resp.status_code != 200:
                    logger.error(f"Query failed: {resp.status_code}")
                    break

                aids = resp.json().get("resources", [])
                if not aids:
                    break

                # Get full device details
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
                        hostname = (device.get("hostname") or "").lower()
                        asset = hostname_to_asset.get(hostname)
                        if not asset:
                            continue

                        product_type_desc = device.get("product_type_desc", "")
                        platform_name = device.get("platform_name", "")
                        device_id = device.get("device_id", "")

                        # Save AID for future use
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

                logger.info(f"Processed {offset + len(aids)} hosts, matched {matched} assets so far")

                total = resp.json().get("meta", {}).get("pagination", {}).get("total", 0)
                offset += limit
                if offset >= total:
                    break

            await db.commit()
            logger.info(f"Done! Enriched {matched} assets: {by_category}")

asyncio.run(enrich())
