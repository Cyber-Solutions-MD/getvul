"""Google Workspace directory connector — syncs users and groups via Admin SDK.

Supports two auth methods:
1. Service Account JSON key (recommended — auto-refreshes, no expiry)
2. OAuth access token (legacy — expires after ~1 hour)

Required scopes (configure in Admin Console → Domain-wide delegation):
  - https://www.googleapis.com/auth/admin.directory.user.readonly
  - https://www.googleapis.com/auth/admin.directory.group.readonly
  - https://www.googleapis.com/auth/admin.directory.group.member.readonly

API: https://developers.google.com/admin-sdk/directory/reference/rest
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx
import structlog
from jose import jwt as jose_jwt

logger = structlog.get_logger()

BASE_URL = "https://admin.googleapis.com/admin/directory/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
]


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
        self._service_account: dict | None = None
        self._admin_email: str | None = None

    async def authenticate(self, credentials: dict, config: dict) -> bool:
        """Authenticate with service account JSON or OAuth access token.

        credentials:
            service_account_json: str — full JSON key file content (preferred)
            admin_email: str — admin email for domain-wide delegation impersonation
            access_token: str — fallback: raw OAuth token
            domain: str — Google Workspace domain
        """
        self._admin_email = credentials.get("admin_email", "")
        self.domain = config.get("domain", credentials.get("domain", ""))
        # Auto-detect domain from admin email if not provided
        if not self.domain and self._admin_email and "@" in self._admin_email:
            self.domain = self._admin_email.split("@")[1]

        # Try service account JSON first
        sa_json = credentials.get("service_account_json", "")
        if sa_json:
            try:
                self._service_account = json.loads(sa_json) if isinstance(sa_json, str) else sa_json
                token = await self._get_sa_token()
                if token:
                    self.access_token = token
                    logger.info("google_workspace_sa_auth_success")
                else:
                    logger.error("google_workspace_sa_token_failed")
                    return False
            except Exception as e:
                logger.error("google_workspace_sa_parse_error", error=str(e))
                return False
        else:
            # Fallback: raw access token
            self.access_token = credentials.get("access_token", "")
            if not self.access_token:
                logger.error("google_workspace_no_credentials")
                return False

        if not self.domain:
            logger.error("google_workspace_no_domain")
            return False

        self.client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

        # Test connectivity
        try:
            resp = await self.client.get("/users", params={"domain": self.domain, "maxResults": 1})
            if resp.status_code == 200:
                logger.info("google_workspace_auth_success")
                return True
            logger.error("google_workspace_auth_failed", status=resp.status_code, body=resp.text[:300])
            return False
        except Exception as e:
            logger.error("google_workspace_auth_error", error=str(e))
            return False

    async def _get_sa_token(self) -> str | None:
        """Generate an access token from service account credentials using JWT assertion."""
        sa = self._service_account
        if not sa:
            return None

        now = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": " ".join(SCOPES),
            "aud": TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        # For domain-wide delegation, impersonate the admin user
        if self._admin_email:
            payload["sub"] = self._admin_email

        # Sign JWT with the service account private key (RS256)
        private_key = sa["private_key"]
        signed_jwt = jose_jwt.encode(payload, private_key, algorithm="RS256")

        # Exchange JWT for access token
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed_jwt,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
            logger.error("google_workspace_token_exchange_failed", status=resp.status_code, body=resp.text[:300])
            return None

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

                users.append(
                    GoogleUser(
                        email=u.get("primaryEmail", ""),
                        name=f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip(),
                        department=dept or None,
                        job_title=title or None,
                        is_active=not u.get("suspended", False),
                        avatar_url=u.get("thumbnailPhotoUrl"),
                    )
                )

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
