"""Connector management — CRUD with encrypted credentials."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.schemas import (
    CONNECTOR_TYPES,
    ConnectorConfigResponse,
    ConnectorCreate,
    ConnectorUpdate,
)
from app.encryption import decrypt_value, encrypt_value
from app.ticketing.models import ConnectorConfig


def _get_connector_name(connector_type: str) -> str:
    """Get display name for a connector type."""
    info = CONNECTOR_TYPES.get(connector_type)
    if info is None:
        return connector_type
    return info.name if hasattr(info, "name") else connector_type


# Wire-boundary normalization (CR-06 precedent): the DB/sync harness only ever
# writes uppercase "SUCCESS"/"FAILED"/None to last_sync_status (see sync.py),
# but the frontend SyncStatusPill union is 'ok'|'failed'|'syncing'|null. Map
# raw DB values to the lowercase wire contract here, not in the frontend.
_SYNC_STATUS_MAP = {
    "SUCCESS": "ok",
    "FAILED": "failed",
    "SYNCING": "syncing",
}


def _normalize_sync_status(raw: str | None) -> str | None:
    """Map a raw DB sync-status value to the lowercase wire contract."""
    if raw is None:
        return None
    return _SYNC_STATUS_MAP.get(raw, raw)


def _to_response(c: ConnectorConfig) -> ConnectorConfigResponse:
    """Convert DB model to response schema."""
    return ConnectorConfigResponse(
        id=str(c.id),
        connector_type=c.connector_type,
        connector_name=_get_connector_name(c.connector_type),
        is_enabled=c.is_enabled,
        config=c.config or {},
        has_credentials=bool(c.credentials_secret_arn),
        last_sync_at=c.last_sync_at,
        last_sync_status=_normalize_sync_status(c.last_sync_status),
        last_sync_record_count=c.last_sync_record_count,
        last_error=c.last_error,
        consecutive_failure_count=c.consecutive_failure_count,
        sync_interval_minutes=c.sync_interval_minutes,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


async def list_connectors(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[ConnectorConfigResponse]:
    """List all connectors for a tenant."""
    result = await db.execute(
        select(ConnectorConfig).where(ConnectorConfig.tenant_id == tenant_id).order_by(ConnectorConfig.connector_type)
    )
    return [_to_response(c) for c in result.scalars().all()]


async def create_connector(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    body: ConnectorCreate,
) -> ConnectorConfigResponse:
    """Create a new connector with encrypted credentials."""
    encrypted_creds = json.dumps({k: encrypt_value(v) for k, v in body.credentials.items()})

    connector = ConnectorConfig(
        tenant_id=tenant_id,
        connector_type=body.connector_type,
        is_enabled=True,
        credentials_secret_arn=encrypted_creds,
        config=body.config,
        sync_interval_minutes=body.sync_interval_minutes,
    )
    db.add(connector)
    await db.flush()
    await db.refresh(connector)

    return _to_response(connector)


async def update_connector(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
) -> ConnectorConfigResponse | None:
    """Update a connector's config and/or credentials."""
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        return None

    if body.credentials is not None:
        encrypted_creds = json.dumps({k: encrypt_value(v) for k, v in body.credentials.items()})
        connector.credentials_secret_arn = encrypted_creds

    if body.config is not None:
        connector.config = body.config
    if body.is_enabled is not None:
        connector.is_enabled = body.is_enabled
    if body.sync_interval_minutes is not None:
        connector.sync_interval_minutes = body.sync_interval_minutes

    await db.flush()
    return _to_response(connector)


async def delete_connector(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    connector_id: uuid.UUID,
) -> bool:
    """Delete a connector."""
    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        return False
    await db.delete(connector)
    return True


def get_decrypted_credentials(connector: ConnectorConfig) -> dict[str, str]:
    """Decrypt stored credentials for use in sync. Internal use only."""
    if not connector.credentials_secret_arn:
        return {}
    try:
        encrypted_map = json.loads(connector.credentials_secret_arn)
        return {k: decrypt_value(v) for k, v in encrypted_map.items()}
    except Exception:
        return {}
