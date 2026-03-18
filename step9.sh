#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "📋 Adding connector permission docs..."

git checkout main
git pull
git checkout -b feat/connector-permissions

# ══════════════════════════════════════════════
#  BACKEND: Update connector types with permissions
# ══════════════════════════════════════════════

cat > backend/app/connectors/schemas.py << 'FILEEOF'
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
FILEEOF

# Update router to return full type info
cat > backend/app/connectors/router.py << 'FILEEOF'
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
    """List all supported connector types, required fields, and permissions."""
    return [
        ConnectorTypeInfo(
            type=k,
            name=v["name"],
            fields=v["fields"],
            defaults=v["defaults"],
            description=v["description"],
            setup_url=v["setup_url"],
            permissions=v["permissions"],
            base_urls=v.get("base_urls", {}),
            notes=v["notes"],
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
    """Trigger a manual sync for a connector. Requires Admin."""
    from sqlalchemy import select
    from app.ticketing.models import ConnectorConfig
    from app.connectors.sync import run_sync

    result = await db.execute(
        select(ConnectorConfig).where(
            ConnectorConfig.id == connector_id,
            ConnectorConfig.tenant_id == user.tenant_id,
        )
    )
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    log = await run_sync(db, connector)
    await db.commit()

    return {
        "status": log.status,
        "records_fetched": log.records_fetched,
        "records_created": log.records_created,
        "records_updated": log.records_updated,
        "details": log.details,
        "error": log.error_message,
    }
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Update connector types
# ══════════════════════════════════════════════

cat > frontend/src/types/connector.ts << 'FILEEOF'
export interface ConnectorPermission {
  scope: string;
  access: string;
  purpose: string;
}

export interface ConnectorType {
  type: string;
  name: string;
  fields: string[];
  defaults: Record<string, string>;
  description: string;
  setup_url: string;
  permissions: ConnectorPermission[];
  base_urls: Record<string, string>;
  notes: string;
}

export interface ConnectorConfig {
  id: string;
  connector_type: string;
  connector_name: string;
  is_enabled: boolean;
  config: Record<string, string>;
  has_credentials: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_record_count: number | null;
  sync_interval_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorTestResult {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}
FILEEOF

# ══════════════════════════════════════════════
#  FRONTEND: Updated connectors page with permissions + sync
# ══════════════════════════════════════════════

cat > frontend/src/app/dashboard/connectors/page.tsx << 'FILEEOF'
"use client";

import { useEffect, useState } from "react";
import {
  Plug,
  Plus,
  TestTube2,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  ExternalLink,
  Info,
  Play,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type {
  ConnectorType,
  ConnectorConfig,
  ConnectorTestResult,
} from "@/types/connector";

const CONNECTOR_META: Record<string, { color: string }> = {
  CROWDSTRIKE: { color: "text-red-400" },
  NESSUS: { color: "text-green-400" },
  DEFENDER: { color: "text-blue-400" },
  WIZ: { color: "text-purple-400" },
};

export default function ConnectorsPage() {
  const [connectorTypes, setConnectorTypes] = useState<ConnectorType[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    try {
      const typesRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/connectors/types`);
      if (typesRes.ok) setConnectorTypes(await typesRes.json());

      try {
        const conns = await api<ConnectorConfig[]>("/api/v1/connectors");
        setConnectors(conns);
      } catch (e) {
        // 401 expected if no user seeded
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync(connectorId: string) {
    setSyncing(connectorId);
    try {
      const result = await api(`/api/v1/connectors/${connectorId}/sync`, { method: "POST" });
      alert(`Sync ${result.status}: ${result.records_fetched} records fetched, ${result.records_created} created`);
      await loadData();
    } catch (e: any) {
      alert(`Sync failed: ${e.message}`);
    } finally {
      setSyncing(null);
    }
  }

  async function handleDelete(connectorId: string) {
    if (!confirm("Delete this connector? This will not remove synced data.")) return;
    try {
      await api(`/api/v1/connectors/${connectorId}`, { method: "DELETE" });
      await loadData();
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    }
  }

  const configuredTypes = new Set(connectors.map((c) => c.connector_type));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Connectors</h1>
        <p className="mt-1 text-sm text-gray-400">Connect your security tools to aggregate vulnerabilities and posture findings</p>
      </div>

      {/* Active connectors */}
      {connectors.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-gray-400">Active Connectors</h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {connectors.map((conn) => (
              <div key={conn.id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-gray-800 p-2.5">
                      <Plug className={cn("h-5 w-5", CONNECTOR_META[conn.connector_type]?.color || "text-gray-400")} />
                    </div>
                    <div>
                      <h3 className="font-medium text-white">{conn.connector_name}</h3>
                      <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                        {conn.last_sync_status === "SUCCESS" ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : conn.last_sync_status === "FAILED" ? <XCircle className="h-3.5 w-3.5 text-red-400" /> : <AlertCircle className="h-3.5 w-3.5 text-gray-500" />}
                        {conn.last_sync_at ? `Last sync: ${new Date(conn.last_sync_at).toLocaleString()}` : "Never synced"}
                        {conn.last_sync_record_count !== null && <span>· {conn.last_sync_record_count} records</span>}
                      </div>
                    </div>
                  </div>
                  <div className={cn("rounded-full px-2 py-0.5 text-xs font-medium", conn.is_enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400")}>
                    {conn.is_enabled ? "Active" : "Disabled"}
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs text-gray-500">Every {conn.sync_interval_minutes} min · Credentials: {conn.has_credentials ? "✓" : "✗"}</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleSync(conn.id)}
                      disabled={syncing === conn.id}
                      className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50"
                    >
                      {syncing === conn.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                      Sync Now
                    </button>
                    <button
                      onClick={() => handleDelete(conn.id)}
                      className="rounded-lg border border-gray-700 p-1.5 text-gray-500 hover:bg-gray-800 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available connectors */}
      <div className="space-y-4">
        <h2 className="text-sm font-medium text-gray-400">{connectors.length > 0 ? "Add More Connectors" : "Available Connectors"}</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {connectorTypes.filter((t) => !configuredTypes.has(t.type)).map((type) => (
            <button
              key={type.type}
              onClick={() => { setSelectedType(type.type); setShowAddModal(true); }}
              className="flex items-start gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 text-left transition-colors hover:border-indigo-500/50 hover:bg-gray-900"
            >
              <div className="rounded-lg bg-gray-800 p-2.5">
                <Plug className={cn("h-5 w-5", CONNECTOR_META[type.type]?.color || "text-gray-400")} />
              </div>
              <div className="flex-1">
                <h3 className="font-medium text-white">{type.name}</h3>
                <p className="mt-1 text-sm text-gray-400">{type.description}</p>
                <div className="mt-2 flex items-center gap-1 text-xs text-indigo-400"><Plus className="h-3 w-3" />Configure</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Add modal */}
      {showAddModal && selectedType && (
        <AddConnectorModal
          type={connectorTypes.find((t) => t.type === selectedType)!}
          onClose={() => { setShowAddModal(false); setSelectedType(null); }}
          onSaved={() => { setShowAddModal(false); setSelectedType(null); loadData(); }}
        />
      )}
    </div>
  );
}

function AddConnectorModal({ type, onClose, onSaved }: { type: ConnectorType; onClose: () => void; onSaved: () => void }) {
  const [credentials, setCredentials] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    type.fields.forEach((f) => { initial[f] = type.defaults[f] || ""; });
    return initial;
  });
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [syncInterval, setSyncInterval] = useState(15);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPerms, setShowPerms] = useState(false);

  const isSecretField = (f: string) => f.includes("secret") || f.includes("key") || f.includes("password");
  const fieldLabel = (f: string) => f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  async function handleTest() {
    setTesting(true); setTestResult(null); setError(null);
    try {
      const result = await api<ConnectorTestResult>("/api/v1/connectors/test", {
        method: "POST",
        body: JSON.stringify({ connector_type: type.type, credentials, config: {} }),
      });
      setTestResult(result);
    } catch (e: any) {
      setTestResult({ success: false, message: e.message });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      await api("/api/v1/connectors", {
        method: "POST",
        body: JSON.stringify({ connector_type: type.type, credentials, config: {}, is_enabled: true, sync_interval_minutes: syncInterval }),
      });
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-lg bg-gray-800 p-2">
            <Plug className={cn("h-5 w-5", CONNECTOR_META[type.type]?.color || "text-gray-400")} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Configure {type.name}</h2>
            <p className="text-sm text-gray-400">{type.description}</p>
          </div>
        </div>

        {/* Permissions info */}
        <div className="mb-4 rounded-lg border border-gray-800 bg-gray-900/50">
          <button
            onClick={() => setShowPerms(!showPerms)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <Shield className="h-4 w-4 text-indigo-400" />
              Required Permissions ({type.permissions.length})
            </div>
            <span className="text-xs text-gray-500">{showPerms ? "Hide" : "Show"}</span>
          </button>
          {showPerms && (
            <div className="border-t border-gray-800 px-4 py-3 space-y-3">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-500">
                    <th className="pb-2 text-left font-medium">Scope</th>
                    <th className="pb-2 text-left font-medium">Access</th>
                    <th className="pb-2 text-left font-medium">Purpose</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {type.permissions.map((p) => (
                    <tr key={p.scope}>
                      <td className="py-1.5 font-mono text-indigo-400">{p.scope}</td>
                      <td className="py-1.5 text-gray-400">{p.access}</td>
                      <td className="py-1.5 text-gray-500">{p.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {type.notes && (
                <div className="flex gap-2 rounded-md bg-gray-800/50 p-2.5 text-xs text-gray-400">
                  <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-500" />
                  <span>{type.notes}</span>
                </div>
              )}

              <a
                href={type.setup_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"
              >
                <ExternalLink className="h-3 w-3" />
                Setup documentation
              </a>
            </div>
          )}
        </div>

        {/* Base URL selector (if multiple) */}
        {Object.keys(type.base_urls).length > 1 && (
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Region</label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(type.base_urls).map(([region, url]) => (
                <button
                  key={region}
                  onClick={() => setCredentials({ ...credentials, base_url: url, api_endpoint_url: url })}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    (credentials.base_url === url || credentials.api_endpoint_url === url)
                      ? "border-indigo-500 bg-indigo-500/15 text-indigo-400"
                      : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-300"
                  )}
                >
                  {region}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Credential fields */}
        <div className="space-y-4">
          {type.fields.map((field) => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{fieldLabel(field)}</label>
              <div className="relative">
                <input
                  type={isSecretField(field) && !showSecrets[field] ? "password" : "text"}
                  value={credentials[field] || ""}
                  onChange={(e) => setCredentials({ ...credentials, [field]: e.target.value })}
                  placeholder={type.defaults[field] || `Enter ${fieldLabel(field)}`}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                {isSecretField(field) && (
                  <button type="button" onClick={() => setShowSecrets({ ...showSecrets, [field]: !showSecrets[field] })} className="absolute right-2 top-2.5 text-gray-500 hover:text-gray-300">
                    {showSecrets[field] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                )}
              </div>
            </div>
          ))}

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Sync Interval (minutes)</label>
            <input type="number" min={5} max={1440} value={syncInterval} onChange={(e) => setSyncInterval(Number(e.target.value))} className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none" />
          </div>
        </div>

        {/* Test result */}
        {testResult && (
          <div className={cn("mt-4 rounded-lg border p-3 text-sm", testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
            <div className="flex items-center gap-2">
              {testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              {testResult.message}
            </div>
          </div>
        )}

        {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing} className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}
            Test Connection
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Cancel</button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save Connector
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
FILEEOF

# ══════════════════════════════════════════════
#  REBUILD & TEST
# ══════════════════════════════════════════════

echo "🔄 Rebuilding..."
docker compose down
docker compose up --build -d

echo "⏳ Waiting (30s)..."
sleep 30

echo "🔍 Testing connector types API..."
curl -s "http://localhost:8000/api/v1/connectors/types" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for ct in data:
    print(f\"\n{ct['name']}:\")
    print(f\"  Fields: {', '.join(ct['fields'])}\")
    print(f\"  Permissions:\")
    for p in ct['permissions']:
        print(f\"    - {p['scope']} ({p['access']}): {p['purpose']}\")
"
echo ""

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

git add -A
git commit -m "feat: connector permission docs + sync button + region selector

- Each connector type now includes required permissions, setup URL, and notes
- Permissions shown in expandable section in connector config modal
- Region selector for CrowdStrike (US-1/US-2/EU-1/GOV) and Wiz (US/US2/EU)
- Sync Now button on active connectors
- Delete connector button
- API returns full ConnectorTypeInfo with permissions and base_urls"

git push -u origin feat/connector-permissions

gh pr create \
  --title "feat: connector permission docs + sync + region selector" \
  --body "## Changes
- Connector types now include required permissions, setup docs, and notes
- Modal shows expandable permission table before you enter credentials
- Region selector buttons for CrowdStrike and Wiz
- Active connectors have Sync Now and Delete buttons

## Connector Permissions

### CrowdStrike
| Scope | Purpose |
|---|---|
| Spotlight vulnerabilities (Read) | Vulnerability findings |
| Hosts (Read) | Device details |
| CSPM Registration (Read) | Cloud posture evaluations |
| Detections (Read) | Indicators of misconfiguration |

### Nessus
| Scope | Purpose |
|---|---|
| API Keys (Admin) | Full scan result access |

### Microsoft Defender
| Scope | Purpose |
|---|---|
| Vulnerability.Read.All | Vulnerability data |
| Machine.Read.All | Machine information |
| SecurityRecommendation.Read.All | Patching guidance |
| SecurityBaseline.Read.All | CSPM baselines |

### Wiz
| Scope | Purpose |
|---|---|
| read:vulnerabilities | Vulnerability findings |
| read:resources | Cloud resource inventory |
| read:issues | Security issues + misconfigs |
| read:cloud_configuration | CSPM assessments |" \
  --base main

echo ""
echo "✅ Done! PR created."
echo ""
echo "To test CrowdStrike ingestion:"
echo "  1. Open http://localhost:3000/dashboard/connectors"
echo "  2. Click 'CrowdStrike Falcon'"
echo "  3. Expand 'Required Permissions' to see what scopes you need"
echo "  4. Select your region (US-1, US-2, EU-1, or GOV)"
echo "  5. Enter Client ID + Client Secret"
echo "  6. Click 'Test Connection'"
echo "  7. If successful, click 'Save Connector'"
echo "  8. Click 'Sync Now' on the active connector card"
echo ""
echo "   To merge: gh pr merge --squash && git checkout main && git pull"
