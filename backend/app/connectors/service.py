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


async def list_connectors(
    db: AsyncSession, tenant_id: uuid.UUID,
) -> list[ConnectorConfigResponse]:
    """List all connectors for a tenant."""
    result = await db.execute(
        select(ConnectorConfig)
        .where(ConnectorConfig.tenant_id == tenant_id)
        .order_by(ConnectorConfig.connector_type)
    )
    connectors = result.scalars().all()

    return [
        ConnectorConfigResponse(
            id=c.id,
            connector_type=c.connector_type,
            connector_name=CONNECTOR_TYPES.get(c.connector_type, {}).get("name", c.connector_type),
            is_enabled=c.is_enabled,
            config=c.config or {},
            has_credentials=c.credentials_secret_arn is not None and c.credentials_secret_arn != "",
            last_sync_at=c.last_sync_at,
            last_sync_status=c.last_sync_status,
            last_sync_record_count=c.last_sync_record_count,
            sync_interval_minutes=c.sync_interval_minutes,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in connectors
    ]


async def create_connector(
    db: AsyncSession, tenant_id: uuid.UUID, body: ConnectorCreate,
) -> ConnectorConfigResponse:
    """Create a new connector with encrypted credentials."""

    # Encrypt all credential values
    encrypted_creds = json.dumps({
        k: encrypt_value(v) for k, v in body.credentials.items()
    })

    connector = ConnectorConfig(
        tenant_id=tenant_id,
        connector_type=body.connector_type,
        is_enabled=body.is_enabled,
        credentials_secret_arn=encrypted_creds,
        config=body.config,
        sync_interval_minutes=body.sync_interval_minutes,
    )
    db.add(connector)
    await db.flush()

    type_info = CONNECTOR_TYPES.get(body.connector_type, {})
    return ConnectorConfigResponse(
        id=connector.id,
        connector_type=connector.connector_type,
        connector_name=type_info.get("name", connector.connector_type),
        is_enabled=connector.is_enabled,
        config=connector.config or {},
        has_credentials=True,
        last_sync_at=None,
        last_sync_status=None,
        last_sync_record_count=None,
        sync_interval_minutes=connector.sync_interval_minutes,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


async def update_connector(
    db: AsyncSession, tenant_id: uuid.UUID, connector_id: uuid.UUID, body: ConnectorUpdate,
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
        encrypted_creds = json.dumps({
            k: encrypt_value(v) for k, v in body.credentials.items()
        })
        connector.credentials_secret_arn = encrypted_creds

    if body.config is not None:
        connector.config = body.config
    if body.is_enabled is not None:
        connector.is_enabled = body.is_enabled
    if body.sync_interval_minutes is not None:
        connector.sync_interval_minutes = body.sync_interval_minutes

    await db.flush()

    type_info = CONNECTOR_TYPES.get(connector.connector_type, {})
    return ConnectorConfigResponse(
        id=connector.id,
        connector_type=connector.connector_type,
        connector_name=type_info.get("name", connector.connector_type),
        is_enabled=connector.is_enabled,
        config=connector.config or {},
        has_credentials=connector.credentials_secret_arn is not None,
        last_sync_at=connector.last_sync_at,
        last_sync_status=connector.last_sync_status,
        last_sync_record_count=connector.last_sync_record_count,
        sync_interval_minutes=connector.sync_interval_minutes,
        created_at=connector.created_at,
        updated_at=connector.updated_at,
    )


async def delete_connector(
    db: AsyncSession, tenant_id: uuid.UUID, connector_id: uuid.UUID,
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
