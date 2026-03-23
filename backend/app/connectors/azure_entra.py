"""Azure Entra ID directory connector — syncs users and groups via Microsoft Graph.

Uses client credentials (app registration) with Application permissions.
API: https://learn.microsoft.com/en-us/graph/api/overview

Required permissions:
  - User.Read.All (Application)
  - Group.Read.All (Application)
  - GroupMember.Read.All (Application)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger()

GRAPH_URL = "https://graph.microsoft.com/v1.0"


@dataclass
class AzureUser:
    email: str
    name: str
    department: str | None = None
    job_title: str | None = None
    is_active: bool = True
    avatar_url: str | None = None
    groups: list[str] = field(default_factory=list)
    azure_id: str | None = None


class AzureEntraConnector:
    """Connector for Azure Entra ID via Microsoft Graph API."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Authenticate with client credentials (app registration)."""
        tenant_id = credentials.get("tenant_id", "")
        client_id = credentials.get("client_id", "")
        client_secret = credentials.get("client_secret", "")

        if not all([tenant_id, client_id, client_secret]):
            logger.error("azure_entra_missing_credentials")
            return False

        try:
            async with httpx.AsyncClient(timeout=30) as auth_client:
                resp = await auth_client.post(
                    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                if resp.status_code != 200:
                    logger.error("azure_entra_auth_failed", status=resp.status_code)
                    return False

                self.access_token = resp.json().get("access_token")

            self.client = httpx.AsyncClient(
                base_url=GRAPH_URL,
                timeout=30,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            # Test
            test = await self.client.get("/users", params={"$top": 1, "$select": "id"})
            if test.status_code == 200:
                logger.info("azure_entra_auth_success")
                return True

            logger.error("azure_entra_test_failed", status=test.status_code)
            return False
        except Exception as e:
            logger.error("azure_entra_auth_error", error=str(e))
            return False

    async def fetch_users(self) -> list[AzureUser]:
        """Fetch all users from Azure AD."""
        if not self.client:
            return []

        users: list[AzureUser] = []
        url = "/users"
        params = {
            "$select": "id,displayName,mail,userPrincipalName,department,jobTitle,accountEnabled",
            "$top": "999",
        }

        while url:
            resp = await self.client.get(url, params=params if "?" not in url else None)
            if resp.status_code != 200:
                logger.warning("azure_entra_users_error", status=resp.status_code)
                break

            data = resp.json()
            for u in data.get("value", []):
                email = u.get("mail") or u.get("userPrincipalName", "")
                if not email or "#EXT#" in email:
                    continue
                users.append(
                    AzureUser(
                        email=email.lower(),
                        name=u.get("displayName", ""),
                        department=u.get("department"),
                        job_title=u.get("jobTitle"),
                        is_active=u.get("accountEnabled", True),
                        azure_id=u.get("id"),
                    )
                )

            url = data.get("@odata.nextLink", "")
            params = {}  # nextLink includes params

        logger.info("azure_entra_users_fetched", count=len(users))
        return users

    async def fetch_groups(self) -> dict[str, list[str]]:
        """Fetch all groups and their members."""
        if not self.client:
            return {}

        groups_map: dict[str, list[str]] = {}
        url = "/groups"
        params = {"$select": "id,displayName,mailEnabled,securityEnabled", "$top": "999"}

        while url:
            resp = await self.client.get(url, params=params if "?" not in url else None)
            if resp.status_code != 200:
                break

            data = resp.json()
            for g in data.get("value", []):
                group_name = g.get("displayName", "")
                group_id = g.get("id", "")
                members = await self._fetch_group_members(group_id)
                groups_map[group_name] = members

            url = data.get("@odata.nextLink", "")
            params = {}

        logger.info("azure_entra_groups_fetched", count=len(groups_map))
        return groups_map

    async def _fetch_group_members(self, group_id: str) -> list[str]:
        """Fetch member emails for a group."""
        members: list[str] = []
        url = f"/groups/{group_id}/members"
        params = {"$select": "mail,userPrincipalName", "$top": "999"}

        while url:
            resp = await self.client.get(url, params=params if "?" not in url else None)
            if resp.status_code != 200:
                break

            data = resp.json()
            for m in data.get("value", []):
                email = m.get("mail") or m.get("userPrincipalName", "")
                if email and "#EXT#" not in email:
                    members.append(email.lower())

            url = data.get("@odata.nextLink", "")
            params = {}

        return members

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
