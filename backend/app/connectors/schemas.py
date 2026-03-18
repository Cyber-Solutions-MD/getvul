"""Pydantic schemas for connector management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


CONNECTOR_TYPES = {
    "CROWDSTRIKE": {
        "name": "CrowdStrike Falcon",
        "fields": ["client_id", "client_secret", "base_url"],
        "defaults": {"base_url": "https://api.crowdstrike.com"},
        "description": "Collect vulnerability assessments from Spotlight and cloud posture findings from Horizon CSPM.",
        "setup_url": "https://falcon.crowdstrike.com/api-clients-and-keys/",
        "permissions": [
            {"scope": "Spotlight vulnerabilities", "access": "Read", "purpose": "Fetch vulnerability findings per host"},
            {"scope": "Hosts", "access": "Read", "purpose": "Resolve device details (hostname, OS, IP)"},
            {"scope": "CSPM Registration", "access": "Read", "purpose": "Fetch cloud posture policy evaluations"},
            {"scope": "Detections", "access": "Read", "purpose": "Fetch indicators of misconfiguration (IoM)"},
        ],
        "base_urls": {
            "US-1": "https://api.crowdstrike.com",
            "US-2": "https://api.us-2.crowdstrike.com",
            "EU-1": "https://api.eu-1.crowdstrike.com",
            "US-GOV": "https://api.laggar.gcw.crowdstrike.com",
        },
        "notes": "Create an API client in Falcon Console → Support & Resources → API Clients and Keys. Select your cloud region for the correct Base URL.",
    },
    "NESSUS": {
        "name": "Nessus Professional",
        "fields": ["access_key", "secret_key", "base_url"],
        "defaults": {"base_url": "https://localhost:8834"},
        "description": "Collect scan results and vulnerability findings from Tenable Nessus.",
        "setup_url": "https://docs.tenable.com/nessus/Content/GenerateAnAPIKey.htm",
        "permissions": [
            {"scope": "API Keys", "access": "Admin", "purpose": "Full access to scan results and host data"},
        ],
        "base_urls": {},
        "notes": "Generate API keys in Nessus → Settings → My Account → API Keys. Nessus must be network-accessible from GetVul (self-hosted or VPN). For Tenable.io (cloud), use the Tenable.io base URL instead.",
    },
    "DEFENDER": {
        "name": "Microsoft Defender for Endpoint",
        "fields": ["tenant_id", "client_id", "client_secret"],
        "defaults": {},
        "description": "Collect vulnerability and device data from Microsoft Defender Vulnerability Management, plus Defender for Cloud posture findings.",
        "setup_url": "https://learn.microsoft.com/en-us/defender-endpoint/api/exposed-apis-create-app-webapp",
        "permissions": [
            {"scope": "Vulnerability.Read.All", "access": "Application", "purpose": "Read all vulnerability data across the tenant"},
            {"scope": "Machine.Read.All", "access": "Application", "purpose": "Read all machine/device information"},
            {"scope": "SecurityRecommendation.Read.All", "access": "Application", "purpose": "Read security recommendations and patching guidance"},
            {"scope": "SecurityBaseline.Read.All", "access": "Application", "purpose": "Read security baseline assessments (CSPM)"},
        ],
        "base_urls": {},
        "notes": "Register an App in Azure Entra ID → App registrations → New registration. Add API permissions under 'Microsoft Threat Protection' or 'WindowsDefenderATP'. Grant admin consent. Use the Application (client) ID and create a client secret.",
    },
    "WIZ": {
        "name": "Wiz",
        "fields": ["client_id", "client_secret", "api_endpoint_url", "auth_url"],
        "defaults": {
            "auth_url": "https://auth.app.wiz.io/oauth/token",
            "api_endpoint_url": "https://api.us1.app.wiz.io/graphql",
        },
        "description": "Collect cloud vulnerability findings, misconfigurations, and security issues from Wiz.",
        "setup_url": "https://docs.wiz.io/wiz-docs/docs/set-up-wiz-service-accounts",
        "permissions": [
            {"scope": "read:vulnerabilities", "access": "Service Account", "purpose": "Read vulnerability findings across all cloud accounts"},
            {"scope": "read:resources", "access": "Service Account", "purpose": "Read cloud resource inventory and metadata"},
            {"scope": "read:issues", "access": "Service Account", "purpose": "Read security issues including misconfigs and secrets"},
            {"scope": "read:cloud_configuration", "access": "Service Account", "purpose": "Read cloud configuration assessments (CSPM)"},
        ],
        "base_urls": {
            "US": "https://api.us1.app.wiz.io/graphql",
            "US2": "https://api.us2.app.wiz.io/graphql",
            "EU": "https://api.eu1.app.wiz.io/graphql",
        },
        "notes": "Create a Service Account in Wiz → Settings → Service Accounts. Assign the 'Global Reader' role for read-only access. The API endpoint URL depends on your Wiz data region.",
    },
}


class ConnectorPermission(BaseModel):
    scope: str
    access: str
    purpose: str


class ConnectorTypeInfo(BaseModel):
    type: str
    name: str
    fields: list[str]
    defaults: dict[str, str]
    description: str
    setup_url: str
    permissions: list[ConnectorPermission]
    base_urls: dict[str, str]
    notes: str


class ConnectorConfigResponse(BaseModel):
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
    connector_type: str = Field(..., pattern="^(CROWDSTRIKE|NESSUS|DEFENDER|WIZ)$")
    credentials: dict[str, str] = Field(..., description="Key-value pairs of credentials (will be encrypted)")
    config: dict = Field(default_factory=dict, description="Additional config (base_url, etc.)")
    is_enabled: bool = True
    sync_interval_minutes: int = Field(15, ge=5, le=1440)


class ConnectorUpdate(BaseModel):
    credentials: dict[str, str] | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(None, ge=5, le=1440)


class ConnectorTestRequest(BaseModel):
    connector_type: str = Field(..., pattern="^(CROWDSTRIKE|NESSUS|DEFENDER|WIZ)$")
    credentials: dict[str, str]
    config: dict = Field(default_factory=dict)


class ConnectorTestResult(BaseModel):
    success: bool
    message: str
    details: dict | None = None
