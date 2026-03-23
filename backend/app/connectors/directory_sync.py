"""Directory sync — syncs users and groups from Google Workspace or Azure Entra ID."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.service import get_decrypted_credentials
from app.tenants.models import User
from app.ticketing.models import ConnectorConfig, SyncLog

logger = structlog.get_logger()


async def run_directory_sync(db: AsyncSession, connector_config: ConnectorConfig) -> SyncLog:
    """Run a directory sync — fetches users and groups from IdP."""
    now = datetime.now(UTC)

    log = SyncLog(
        connector_id=connector_config.id,
        tenant_id=connector_config.tenant_id,
        status="RUNNING", started_at=now,
    )
    db.add(log)
    await db.flush()

    credentials = get_decrypted_credentials(connector_config)
    config = connector_config.config or {}
    connector_type = connector_config.connector_type

    try:
        if connector_type == "GOOGLE_WORKSPACE":
            from app.connectors.google_workspace import GoogleWorkspaceConnector
            connector = GoogleWorkspaceConnector()
        elif connector_type == "AZURE_ENTRA_ID":
            from app.connectors.azure_entra import AzureEntraConnector
            connector = AzureEntraConnector()
        else:
            log.status = "FAILED"
            log.error_message = f"Unknown directory connector: {connector_type}"
            log.finished_at = datetime.now(UTC)
            return log

        authed = await connector.authenticate(credentials, config)
        if not authed:
            log.status = "FAILED"
            log.error_message = "Authentication failed"
            log.finished_at = datetime.now(UTC)
            return log

        # Fetch users
        idp_users = await connector.fetch_users()

        # Fetch groups and build email → groups mapping
        groups_map = await connector.fetch_groups()
        email_groups: dict[str, list[str]] = {}
        for group_name, member_emails in groups_map.items():
            for email in member_emails:
                email_groups.setdefault(email, []).append(group_name)

        # Sync users into the database
        created = 0
        updated = 0
        source = "google" if connector_type == "GOOGLE_WORKSPACE" else "azure"

        for idp_user in idp_users:
            if not idp_user.email:
                continue

            email = idp_user.email.lower()
            user_groups = email_groups.get(email, [])

            result = await db.execute(
                select(User).where(
                    User.tenant_id == connector_config.tenant_id,
                    User.email == email,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing user with directory data
                if idp_user.name:
                    existing.display_name = idp_user.name
                if idp_user.department:
                    existing.department = idp_user.department
                if idp_user.job_title:
                    existing.job_title = idp_user.job_title
                if idp_user.avatar_url:
                    existing.avatar_url = idp_user.avatar_url
                existing.groups = user_groups
                existing.idp_source = source
                existing.is_active = idp_user.is_active
                flag_modified(existing, "groups")
                updated += 1
            else:
                # Create new user from directory
                new_user = User(
                    tenant_id=connector_config.tenant_id,
                    email=email,
                    display_name=idp_user.name,
                    department=idp_user.department,
                    job_title=idp_user.job_title,
                    avatar_url=idp_user.avatar_url,
                    role="VIEWER",
                    is_active=idp_user.is_active,
                    groups=user_groups,
                    idp_source=source,
                    allow_password_login=False,  # SSO users don't get password by default
                )
                db.add(new_user)
                created += 1

        log.status = "SUCCESS"
        log.records_fetched = len(idp_users)
        log.records_created = created
        log.records_updated = updated
        log.details = {
            "users_fetched": len(idp_users),
            "users_created": created,
            "users_updated": updated,
            "groups_fetched": len(groups_map),
            "total_group_memberships": sum(len(v) for v in groups_map.values()),
        }

        connector_config.last_sync_at = datetime.now(UTC)
        connector_config.last_sync_status = "SUCCESS"
        connector_config.last_sync_record_count = len(idp_users)

    except Exception as e:
        logger.error("directory_sync_error", error=str(e))
        log.status = "FAILED"
        log.error_message = str(e)[:2000]
        connector_config.last_sync_status = "FAILED"
    finally:
        log.finished_at = datetime.now(UTC)
        if 'connector' in locals():
            await connector.close()

    return log
