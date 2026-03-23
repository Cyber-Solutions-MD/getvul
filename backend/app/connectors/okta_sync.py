"""Okta directory sync connector — imports users and groups."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.service import get_decrypted_credentials
from app.tenants.models import User
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger(__name__)

OKTA_PAGE_LIMIT = 200
REQUEST_TIMEOUT = 30.0
RATE_LIMIT_MAX_RETRIES = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(api_token: str) -> dict[str, str]:
    return {
        "Authorization": f"SSWS {api_token}",
        "Accept": "application/json",
    }


def _parse_next_link(link_header: str | None) -> str | None:
    """Extract the URL with rel=\"next\" from an Okta Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            # Format: <https://...>; rel="next"
            url = part.split(";")[0].strip().strip("<>")
            return url
    return None


async def _paginated_get(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> list[dict]:
    """Fetch all pages from a paginated Okta endpoint."""
    results: list[dict] = []
    next_url: str | None = url

    while next_url:
        response = await _request_with_retry(client, next_url, headers)
        response.raise_for_status()
        results.extend(response.json())
        next_url = _parse_next_link(response.headers.get("link"))

    return results


async def _request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> httpx.Response:
    """Execute a GET request, retrying on 429 rate-limit responses."""
    for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 1):
        response = await client.get(url, headers=headers)

        if response.status_code != 429:
            return response

        reset_epoch = response.headers.get("X-Rate-Limit-Reset")
        if reset_epoch:
            wait = max(int(reset_epoch) - int(time.time()), 1)
        else:
            wait = 2 ** attempt

        logger.warning(
            "okta_rate_limited",
            attempt=attempt,
            wait_seconds=wait,
            url=url,
        )
        await asyncio.sleep(wait)

    # Return the last 429 so the caller can raise
    return response  # type: ignore[possibly-undefined]


# ---------------------------------------------------------------------------
# Main sync entry-point
# ---------------------------------------------------------------------------

async def run_okta_sync(
    db: AsyncSession,
    connector_config: ConnectorConfig,
) -> SyncLog:
    """Synchronise users and groups from Okta into the GetVul User model."""

    tenant_id = connector_config.tenant_id
    log = structlog.get_logger(__name__).bind(
        connector_id=str(connector_config.id),
        tenant_id=str(tenant_id),
    )

    # -- Create SyncLog with RUNNING status --------------------------------
    sync_log = SyncLog(
        connector_config_id=connector_config.id,
        tenant_id=tenant_id,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        details={},
    )
    db.add(sync_log)
    await db.flush()

    users_synced = 0
    groups_synced = 0

    try:
        # -- 1. Decrypt credentials ----------------------------------------
        creds = get_decrypted_credentials(connector_config)
        domain: str = creds["domain"]
        api_token: str = creds["api_token"]
        base_url = f"https://{domain}/api/v1"
        headers = _auth_headers(api_token)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # -- 2. Fetch all users ----------------------------------------
            log.info("okta_sync_fetching_users")
            okta_users = await _paginated_get(
                client,
                f"{base_url}/users?limit={OKTA_PAGE_LIMIT}",
                headers,
            )
            log.info("okta_sync_users_fetched", count=len(okta_users))

            # -- 3. Upsert active users ------------------------------------
            active_users: dict[str, dict] = {}
            for ou in okta_users:
                if ou.get("status") != "ACTIVE":
                    continue
                profile = ou.get("profile", {})
                email = (profile.get("email") or "").lower().strip()
                if not email:
                    continue
                active_users[ou["id"]] = {
                    "okta_id": ou["id"],
                    "email": email,
                    "display_name": f'{profile.get("firstName", "")} {profile.get("lastName", "")}'.strip(),
                    "department": profile.get("department"),
                    "job_title": profile.get("title"),
                    "mobile_phone": profile.get("mobilePhone"),
                    "login": profile.get("login"),
                }

            # Build lookup of existing users by email
            existing_q = await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.email.in_([u["email"] for u in active_users.values()]),
                )
            )
            existing_users: dict[str, User] = {
                u.email.lower(): u for u in existing_q.scalars().all()
            }

            okta_id_to_email: dict[str, str] = {}

            for okta_id, data in active_users.items():
                email = data["email"]
                okta_id_to_email[okta_id] = email

                user = existing_users.get(email)
                if user:
                    user.display_name = data["display_name"] or user.display_name
                    user.department = data["department"] or user.department
                    user.job_title = data["job_title"] or user.job_title
                    user.idp_source = "okta"
                    user.idp_subject = okta_id
                else:
                    user = User(
                        tenant_id=tenant_id,
                        email=email,
                        display_name=data["display_name"],
                        department=data["department"],
                        job_title=data["job_title"],
                        idp_source="okta",
                        idp_subject=okta_id,
                    )
                    db.add(user)
                    existing_users[email] = user

                users_synced += 1

            await db.flush()

            # -- 4. Fetch all groups ---------------------------------------
            log.info("okta_sync_fetching_groups")
            okta_groups = await _paginated_get(
                client,
                f"{base_url}/groups?limit={OKTA_PAGE_LIMIT}",
                headers,
            )
            log.info("okta_sync_groups_fetched", count=len(okta_groups))

            # -- 5. For each group, fetch members and build mapping --------
            # email -> list of group names
            user_groups: dict[str, list[str]] = {}

            for group in okta_groups:
                group_name = group.get("profile", {}).get("name", "")
                group_id = group["id"]
                if not group_name:
                    continue

                members = await _paginated_get(
                    client,
                    f"{base_url}/groups/{group_id}/users?limit={OKTA_PAGE_LIMIT}",
                    headers,
                )

                for member in members:
                    member_id = member.get("id")
                    email = okta_id_to_email.get(member_id)
                    if email:
                        user_groups.setdefault(email, []).append(group_name)

                groups_synced += 1

            # -- 6. Update User.groups JSONB field -------------------------
            for email, group_names in user_groups.items():
                user = existing_users.get(email)
                if user:
                    user.groups = sorted(set(group_names))
                    flag_modified(user, "groups")

            await db.flush()

        # -- Finalize sync log ---------------------------------------------
        sync_log.status = "SUCCESS"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.details = {
            "users_synced": users_synced,
            "groups_synced": groups_synced,
        }
        log.info(
            "okta_sync_complete",
            users_synced=users_synced,
            groups_synced=groups_synced,
        )

    except Exception as exc:
        sync_log.status = "FAILED"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.details = {"error": str(exc)}
        log.error("okta_sync_failed", error=str(exc))

    await db.commit()
    return sync_log
