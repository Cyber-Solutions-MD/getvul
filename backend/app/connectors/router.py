"""Connector management API routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth.rbac import require_admin
from app.auth.schemas import CurrentUser
from app.connectors.scheduler import is_sync_running, trigger_background_sync
from app.connectors.schemas import (
    CONNECTOR_TYPES,
    ConnectorConfigResponse,
    ConnectorCreate,
    ConnectorTestRequest,
    ConnectorTestResult,
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


CONNECTOR_CATEGORIES = {
    "CROWDSTRIKE": "vulnerability_scanner",
    "NESSUS": "vulnerability_scanner",
    "DEFENDER": "vulnerability_scanner",
    "WIZ": "vulnerability_scanner",
    "QUALYS": "vulnerability_scanner",
    "RAPID7": "vulnerability_scanner",
    "ASANA": "ticketing",
    "JIRA": "ticketing",
    "GITHUB": "ticketing",
    "GOOGLE_WORKSPACE": "identity_provider",
    "AZURE_ENTRA_ID": "identity_provider",
    "OKTA": "identity_provider",
    "HUMAANS": "enrichment",
    "JAMF": "enrichment",
    "INTUNE": "enrichment",
    "ANTHROPIC": "ai_assistant",
}


@router.get("/types")
async def get_connector_types():
    """Return connector types in the format the frontend expects."""
    result = []
    for k, v in CONNECTOR_TYPES.items():
        field_names = [
            f["name"] if isinstance(f, dict) else f for f in (v.fields if isinstance(v.fields, list) else [])
        ]
        defaults = {}
        # field_specs: additive, keyed-by-name per-field metadata (type/required/
        # options/config-destination/help) alongside the flattened `fields`
        # name list above. Existing consumers (ConnectorForm, page.tsx) only
        # ever read `fields`/`defaults` and are unaffected; the add-connector
        # wizard is the first consumer of the richer shape (select options with
        # per-option guidance, required=False gating, credentials-vs-config
        # routing) — needed for the ANTHROPIC model dropdown + optional budget
        # field (D-01/D-05/D-06).
        field_specs: dict[str, dict[str, Any]] = {}
        for f in v.fields if isinstance(v.fields, list) else []:
            if isinstance(f, dict):
                name = f.get("name", "")
                if f.get("type") == "select" and isinstance(v.base_urls, dict) and v.base_urls:
                    defaults[name] = list(v.base_urls.values())[0]
                else:
                    defaults[f.get("name", "")] = ""
                if name:
                    field_specs[name] = {
                        "type": f.get("type", "text"),
                        "label": f.get("label", name),
                        "required": f.get("required", True),
                        "config": f.get("config", False),
                        "options": f.get("options"),
                        "help": f.get("help"),
                    }
            else:
                defaults[f] = ""
        result.append(
            {
                "type": v.id if hasattr(v, "id") else k,
                "name": v.name if hasattr(v, "name") else k,
                "description": v.description if hasattr(v, "description") else "",
                "fields": field_names,
                "field_specs": field_specs,
                "defaults": defaults,
                "permissions": [
                    {"scope": p.scope, "access": p.access, "purpose": p.purpose}
                    for p in (v.permissions if hasattr(v, "permissions") else [])
                ],
                "setup_url": v.setup_url if hasattr(v, "setup_url") else "",
                "base_urls": dict(v.base_urls) if hasattr(v, "base_urls") else {},
                "notes": v.notes if hasattr(v, "notes") else "",
                "category": CONNECTOR_CATEGORIES.get(k, "other"),
            }
        )
    return result


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
