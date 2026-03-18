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
from app.dependencies import DBSession

router = APIRouter()


@router.get("/types", response_model=list[ConnectorTypeInfo])
async def get_connector_types():
    """List all supported connector types and their required fields."""
    return [
        ConnectorTypeInfo(type=k, name=v["name"], fields=v["fields"], defaults=v["defaults"])
        for k, v in CONNECTOR_TYPES.items()
    ]


@router.get("", response_model=list[ConnectorConfigResponse])
async def list_all_connectors(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """List all configured connectors for the tenant. Requires Admin."""
    return await list_connectors(db, user.tenant_id)


@router.post("", response_model=ConnectorConfigResponse, status_code=201)
async def create_new_connector(
    body: ConnectorCreate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Create a new connector. Credentials are encrypted at rest. Requires Admin."""
    return await create_connector(db, user.tenant_id, body)


@router.patch("/{connector_id}", response_model=ConnectorConfigResponse)
async def update_existing_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Update a connector's config or credentials. Requires Admin."""
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
    """Delete a connector. Requires Admin."""
    deleted = await delete_connector(db, user.tenant_id, connector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": "Connector deleted"}


@router.post("/test", response_model=ConnectorTestResult)
async def test_connector_credentials(
    body: ConnectorTestRequest,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """Test connector credentials without saving. Requires Admin."""
    return await test_connector(body.connector_type, body.credentials, body.config)
