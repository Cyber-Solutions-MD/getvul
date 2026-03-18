"""Jamf Pro connector — enriches asset inventory with MDM data."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class JamfConnector(BaseConnector):
    """Connector for Jamf Pro MDM platform."""

    CONNECTOR_TYPE = "JAMF"

    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: str | None = None

    async def authenticate(self) -> bool:
        """Authenticate using Jamf Pro API client credentials."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/oauth/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",
                    },
                )
                if resp.status_code == 200:
                    self.token = resp.json()["access_token"]
                    logger.info("jamf_auth_success")
                    return True
                logger.error("jamf_auth_failed status=%d", resp.status_code)
                return False
        except Exception as e:
            logger.error("jamf_auth_error: %s", e)
            return False

    async def test_connection(self) -> dict[str, Any]:
        """Test JAMF credentials and return scope info."""
        ok = await self.authenticate()
        if not ok:
            return {"success": False, "message": "Authentication failed", "scopes": {}}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"Authorization": f"Bearer {self.token}"}
                # Test computer access
                resp = await client.get(
                    f"{self.base_url}/api/v1/computers-inventory?page=0&page-size=1",
                    headers=headers,
                )
                has_computers = resp.status_code == 200
                return {
                    "success": has_computers,
                    "message": "Successfully connected to Jamf Pro" if has_computers else "Connected but cannot read computers",
                    "scopes": {
                        "Computers": has_computers,
                    },
                }
        except Exception as e:
            return {"success": False, "message": str(e), "scopes": {}}

    async def fetch_computers(self) -> list[dict[str, Any]]:
        """Fetch all computers from Jamf Pro inventory."""
        if not self.token:
            await self.authenticate()

        computers: list[dict[str, Any]] = []
        page = 0
        page_size = 100

        async with httpx.AsyncClient(timeout=60) as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            while True:
                resp = await client.get(
                    f"{self.base_url}/api/v1/computers-inventory",
                    headers=headers,
                    params={
                        "page": page,
                        "page-size": page_size,
                        "section": "GENERAL,HARDWARE,OPERATING_SYSTEM,USER_AND_LOCATION,SECURITY",
                    },
                )
                if resp.status_code != 200:
                    logger.error("jamf_fetch_failed status=%d page=%d", resp.status_code, page)
                    break

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for comp in results:
                    general = comp.get("general", {})
                    hardware = comp.get("hardware", {})
                    os_info = comp.get("operatingSystem", {})
                    user_loc = comp.get("userAndLocation", {})
                    security = comp.get("security", {})

                    computers.append({
                        "jamf_id": str(comp.get("id", "")),
                        "name": general.get("name", ""),
                        "serial_number": hardware.get("serialNumber", ""),
                        "model": hardware.get("model", ""),
                        "os_name": os_info.get("name", ""),
                        "os_version": os_info.get("version", ""),
                        "ip_address": general.get("lastIpAddress", ""),
                        "mac_address": general.get("macAddress", ""),
                        "assigned_user": user_loc.get("username", ""),
                        "department": user_loc.get("department", ""),
                        "building": user_loc.get("building", ""),
                        "last_checkin": general.get("lastContactTime", ""),
                        "filevault_enabled": security.get("fileVault2Status", "") == "ALL_ENCRYPTED",
                        "sip_enabled": security.get("sipStatus", "") == "ENABLED",
                        "gatekeeper_enabled": security.get("gatekeeperStatus", "") == "APP_STORE_AND_IDENTIFIED_DEVELOPERS",
                    })

                total = data.get("totalCount", 0)
                if (page + 1) * page_size >= total:
                    break
                page += 1

        logger.info("jamf_fetched computers=%d", len(computers))
        return computers

    async def sync_vulnerabilities(self, tenant_id, db):
        """JAMF doesn't provide vulnerabilities — no-op."""
        return []

    async def sync_cspm(self, tenant_id, db):
        """JAMF doesn't provide CSPM findings — no-op."""
        return []
