"""Connector management API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.connectors.schemas import (
    CONNECTOR_TYPES,
    ConnectorConfigResponse,
    ConnectorCreate,
    ConnectorTestRequest,
    ConnectorTestResult,
    ConnectorTypeInfo,
    ConnectorUpdate,
)
from app.connectors.service import (
    create_connector,
    delete_connector,
    list_connectors,
    update_connector,
)
from app.connectors.tester import test_connector
from app.connectors.scheduler import trigger_background_sync, is_sync_running
from app.dependencies import DBSession

router = APIRouter()


@router.get("/types", response_model=list[ConnectorTypeInfo])
async def get_connector_types():
    """List all supported connector types, required fields, and permissions."""
    return [
        ConnectorTypeInfo(
            type=k, name=v["name"], fields=v["fields"], defaults=v["defaults"],
            description=v["description"], setup_url=v["setup_url"],
            permissions=v["permissions"], base_urls=v.get("base_urls", {}), notes=v["notes"],
        )
        for k, v in CONNECTOR_TYPES.items()
    ]


@router.get("", response_model=list[ConnectorConfigResponse])
async def list_all_connectors(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await list_connectors(db, user.tenant_id)


@router.post("", response_model=ConnectorConfigResponse, status_code=201)
async def create_new_connector(
    body: ConnectorCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await create_connector(db, user.tenant_id, body)


@router.patch("/{connector_id}", response_model=ConnectorConfigResponse)
async def update_existing_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    result = await update_connector(db, user.tenant_id, connector_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return result


@router.delete("/{connector_id}")
async def delete_existing_connector(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    deleted = await delete_connector(db, user.tenant_id, connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": "Connector deleted"}


@router.post("/test", response_model=ConnectorTestResult)
async def test_connector_credentials(
    body: ConnectorTestRequest,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    return await test_connector(body.connector_type, body.credentials, body.config)


@router.post("/{connector_id}/sync")
async def trigger_sync(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Trigger a sync in the background. Returns immediately."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    if is_sync_running(str(connector_id)):
        return {"status": "ALREADY_RUNNING", "message": "Sync is already in progress"}

    triggered = trigger_background_sync(str(connector_id), str(user.tenant_id))
    if not triggered:
        return {"status": "ALREADY_RUNNING", "message": "Sync is already in progress"}

    return {"status": "STARTED", "message": "Sync started in background. Refresh to see results."}


@router.get("/{connector_id}/sync-status")
async def get_sync_status(
    connector_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Check if a sync is currently running and get last sync info."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    return {
        "is_running": is_sync_running(str(connector_id)),
        "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
        "last_sync_status": connector.last_sync_status,
        "last_sync_record_count": connector.last_sync_record_count,
        "sync_interval_minutes": connector.sync_interval_minutes,
    }
