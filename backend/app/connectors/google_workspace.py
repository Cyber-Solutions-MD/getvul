"""Google Workspace directory connector — syncs users and groups via Admin SDK.

Uses a service account with domain-wide delegation, or an admin OAuth token.
API: https://developers.google.com/admin-sdk/directory/reference/rest

Required scopes:
  - https://www.googleapis.com/auth/admin.directory.user.readonly
  - https://www.googleapis.com/auth/admin.directory.group.readonly
  - https://www.googleapis.com/auth/admin.directory.group.member.readonly
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger()

BASE_URL = "https://admin.googleapis.com/admin/directory/v1"


@dataclass
class GoogleUser:
    email: str
    name: str
    department: str | None = None
    job_title: str | None = None
    is_active: bool = True
    avatar_url: str | None = None
    groups: list[str] = field(default_factory=list)


class GoogleWorkspaceConnector:
    """Connector for Google Workspace Admin Directory API."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.domain: str | None = None
        self.client: httpx.AsyncClient | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Authenticate with OAuth access token (from service account or admin consent)."""
        self.access_token = credentials.get("access_token", "")
        self.domain = config.get("domain", credentials.get("domain", ""))

        if not self.access_token:
            logger.error("google_workspace_no_token")
            return False

        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

        try:
            # Test with a simple users list
            resp = await self.client.get("/users", params={"domain": self.domain, "maxResults": 1})
            if resp.status_code == 200:
                logger.info("google_workspace_auth_success")
                return True
            logger.error("google_workspace_auth_failed", status=resp.status_code)
            return False
        except Exception as e:
            logger.error("google_workspace_auth_error", error=str(e))
            return False

    async def fetch_users(self) -> list[GoogleUser]:
        """Fetch all users from the domain."""
        if not self.client:
            return []

        users: list[GoogleUser] = []
        page_token = None

        while True:
            params: dict = {"domain": self.domain, "maxResults": 200, "projection": "full"}
            if page_token:
                params["pageToken"] = page_token

            resp = await self.client.get("/users", params=params)
            if resp.status_code != 200:
                logger.warning("google_workspace_users_error", status=resp.status_code)
                break

            data = resp.json()
            for u in data.get("users", []):
                name_obj = u.get("name", {})
                orgs = u.get("organizations", [])
                dept = ""
                title = ""
                if orgs and isinstance(orgs, list):
                    dept = orgs[0].get("department", "")
                    title = orgs[0].get("title", "")

                users.append(GoogleUser(
                    email=u.get("primaryEmail", ""),
                    name=f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip(),
                    department=dept or None,
                    job_title=title or None,
                    is_active=not u.get("suspended", False),
                    avatar_url=u.get("thumbnailPhotoUrl"),
                ))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info("google_workspace_users_fetched", count=len(users))
        return users

    async def fetch_groups(self) -> dict[str, list[str]]:
        """Fetch all groups and their members. Returns {group_name: [member_emails]}."""
        if not self.client:
            return {}

        groups_map: dict[str, list[str]] = {}
        page_token = None

        # List all groups
        while True:
            params: dict = {"domain": self.domain, "maxResults": 200}
            if page_token:
                params["pageToken"] = page_token

            resp = await self.client.get("/groups", params=params)
            if resp.status_code != 200:
                break

            data = resp.json()
            for g in data.get("groups", []):
                group_name = g.get("name", g.get("email", ""))
                group_email = g.get("email", "")

                # Fetch members
                members = await self._fetch_group_members(group_email)
                groups_map[group_name] = members

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        logger.info("google_workspace_groups_fetched", count=len(groups_map))
        return groups_map

    async def _fetch_group_members(self, group_email: str) -> list[str]:
        """Fetch member emails for a group."""
        members: list[str] = []
        page_token = None

        while True:
            params: dict = {"maxResults": 200}
            if page_token:
                params["pageToken"] = page_token

            resp = await self.client.get(f"/groups/{group_email}/members", params=params)
            if resp.status_code != 200:
                break

            data = resp.json()
            for m in data.get("members", []):
                if m.get("type") == "USER" and m.get("email"):
                    members.append(m["email"].lower())

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return members

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
