"""Pydantic schemas for connector management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


CONNECTOR_TYPES = {
    "CROWDSTRIKE": {
        "name": "CrowdStrike Spotlight",
        "fields": ["client_id", "client_secret", "base_url"],
        "defaults": {"base_url": "https://api.crowdstrike.com"},
    },
    "NESSUS": {
        "name": "Nessus Professional",
        "fields": ["access_key", "secret_key", "base_url"],
        "defaults": {"base_url": "https://localhost:8834"},
    },
    "DEFENDER": {
        "name": "Microsoft Defender for Endpoint",
        "fields": ["tenant_id", "client_id", "client_secret"],
        "defaults": {},
    },
    "WIZ": {
        "name": "Wiz",
        "fields": ["client_id", "client_secret", "api_endpoint_url", "auth_url"],
        "defaults": {"auth_url": "https://auth.app.wiz.io/oauth/token"},
    },
}


class ConnectorTypeInfo(BaseModel):
    """Describes a connector type and its required fields."""
    type: str
    name: str
    fields: list[str]
    defaults: dict[str, str]


class ConnectorConfigResponse(BaseModel):
    """Connector config response (credentials are masked)."""
    id: uuid.UUID
    connector_type: str
    connector_name: str
    is_enabled: bool
    config: dict
    has_credentials: bool
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_record_count: int | None
    sync_interval_minutes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorCreate(BaseModel):
    """Create a new connector with credentials."""
    connector_type: str = Field(..., pattern="^(CROWDSTRIKE|NESSUS|DEFENDER|WIZ)$")
    credentials: dict[str, str] = Field(
        ..., description="Key-value pairs of credentials (will be encrypted)",
    )
    config: dict = Field(default_factory=dict, description="Additional config (base_url, etc.)")
    is_enabled: bool = True
    sync_interval_minutes: int = Field(15, ge=5, le=1440)


class ConnectorUpdate(BaseModel):
    """Update connector config and/or credentials."""
    credentials: dict[str, str] | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(None, ge=5, le=1440)


class ConnectorTestRequest(BaseModel):
    """Test connector credentials without saving."""
    connector_type: str = Field(..., pattern="^(CROWDSTRIKE|NESSUS|DEFENDER|WIZ)$")
    credentials: dict[str, str]
    config: dict = Field(default_factory=dict)


class ConnectorTestResult(BaseModel):
    """Result of a connector test."""
    success: bool
    message: str
    details: dict | None = None
