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
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  ConnectorType,
  ConnectorConfig,
  ConnectorTestResult,
} from "@/types/connector";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Connector type metadata (fetched from API, but also hardcoded as fallback)
const CONNECTOR_META: Record<string, { color: string; description: string }> = {
  CROWDSTRIKE: {
    color: "text-red-400",
    description: "Collect vulnerability assessments from CrowdStrike Falcon Spotlight",
  },
  NESSUS: {
    color: "text-green-400",
    description: "Collect scan results and findings from Tenable Nessus",
  },
  DEFENDER: {
    color: "text-blue-400",
    description: "Collect vulnerability data from Microsoft Defender for Endpoint",
  },
  WIZ: {
    color: "text-purple-400",
    description: "Collect cloud vulnerability and misconfiguration findings from Wiz",
  },
};

export default function ConnectorsPage() {
  const [connectorTypes, setConnectorTypes] = useState<ConnectorType[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      // Load connector types (public endpoint)
      const typesRes = await fetch(`${API_URL}/api/v1/connectors/types`);
      if (typesRes.ok) setConnectorTypes(await typesRes.json());

      // Load configured connectors (requires auth — will 401 for now)
      const connRes = await fetch(`${API_URL}/api/v1/connectors`, {
        headers: { Authorization: "Bearer demo-token" },
      });
      if (connRes.ok) setConnectors(await connRes.json());
    } catch (e) {
      console.error("Failed to load connectors:", e);
    } finally {
      setLoading(false);
    }
  }

  const configuredTypes = new Set(connectors.map((c) => c.connector_type));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Connectors</h1>
          <p className="mt-1 text-sm text-gray-400">
            Connect your security tools to start aggregating vulnerabilities
          </p>
        </div>
      </div>

      {/* Active Connectors */}
      {connectors.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-gray-400">Active Connectors</h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {connectors.map((conn) => (
              <ConnectorCard key={conn.id} connector={conn} onRefresh={loadData} />
            ))}
          </div>
        </div>
      )}

      {/* Available Connectors */}
      <div className="space-y-4">
        <h2 className="text-sm font-medium text-gray-400">
          {connectors.length > 0 ? "Add More Connectors" : "Available Connectors"}
        </h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {connectorTypes
            .filter((t) => !configuredTypes.has(t.type))
            .map((type) => (
              <button
                key={type.type}
                onClick={() => {
                  setSelectedType(type.type);
                  setShowAddModal(true);
                }}
                className="flex items-start gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 text-left transition-colors hover:border-indigo-500/50 hover:bg-gray-900"
              >
                <div className="rounded-lg bg-gray-800 p-2.5">
                  <Plug
                    className={cn(
                      "h-5 w-5",
                      CONNECTOR_META[type.type]?.color || "text-gray-400"
                    )}
                  />
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-white">{type.name}</h3>
                  <p className="mt-1 text-sm text-gray-400">
                    {CONNECTOR_META[type.type]?.description || "Security scanner integration"}
                  </p>
                  <div className="mt-3 flex items-center gap-1 text-xs text-indigo-400">
                    <Plus className="h-3 w-3" />
                    Configure
                  </div>
                </div>
              </button>
            ))}
        </div>
      </div>

      {/* Add Connector Modal */}
      {showAddModal && selectedType && (
        <AddConnectorModal
          type={connectorTypes.find((t) => t.type === selectedType)!}
          onClose={() => {
            setShowAddModal(false);
            setSelectedType(null);
          }}
          onSaved={() => {
            setShowAddModal(false);
            setSelectedType(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

function ConnectorCard({
  connector,
  onRefresh,
}: {
  connector: ConnectorConfig;
  onRefresh: () => void;
}) {
  const meta = CONNECTOR_META[connector.connector_type];
  const statusIcon =
    connector.last_sync_status === "SUCCESS" ? (
      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
    ) : connector.last_sync_status === "FAILED" ? (
      <XCircle className="h-4 w-4 text-red-400" />
    ) : (
      <AlertCircle className="h-4 w-4 text-gray-500" />
    );

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-gray-800 p-2.5">
            <Plug className={cn("h-5 w-5", meta?.color || "text-gray-400")} />
          </div>
          <div>
            <h3 className="font-medium text-white">{connector.connector_name}</h3>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
              {statusIcon}
              {connector.last_sync_at
                ? `Last sync: ${new Date(connector.last_sync_at).toLocaleString()}`
                : "Never synced"}
              {connector.last_sync_record_count !== null && (
                <span>· {connector.last_sync_record_count} records</span>
              )}
            </div>
          </div>
        </div>
        <div
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            connector.is_enabled
              ? "bg-emerald-500/20 text-emerald-400"
              : "bg-gray-700 text-gray-400"
          )}
        >
          {connector.is_enabled ? "Active" : "Disabled"}
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2">
        <span className="text-xs text-gray-500">
          Sync every {connector.sync_interval_minutes} min
        </span>
        <span className="text-xs text-gray-600">·</span>
        <span className="text-xs text-gray-500">
          Credentials: {connector.has_credentials ? "✓ Configured" : "✗ Missing"}
        </span>
      </div>
    </div>
  );
}

function AddConnectorModal({
  type,
  onClose,
  onSaved,
}: {
  type: ConnectorType;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [credentials, setCredentials] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    type.fields.forEach((f) => {
      initial[f] = type.defaults[f] || "";
    });
    return initial;
  });
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [syncInterval, setSyncInterval] = useState(15);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSecretField = (field: string) =>
    field.includes("secret") || field.includes("key") || field.includes("password");

  const fieldLabel = (field: string) =>
    field
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/connectors/test`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer demo-token",
        },
        body: JSON.stringify({
          connector_type: type.type,
          credentials,
          config: {},
        }),
      });
      const result = await res.json();
      setTestResult(result);
    } catch (e: any) {
      setTestResult({ success: false, message: e.message });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/connectors`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer demo-token",
        },
        body: JSON.stringify({
          connector_type: type.type,
          credentials,
          config: {},
          is_enabled: true,
          sync_interval_minutes: syncInterval,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to save connector");
      }

      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="rounded-lg bg-gray-800 p-2">
            <Plug
              className={cn(
                "h-5 w-5",
                CONNECTOR_META[type.type]?.color || "text-gray-400"
              )}
            />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">
              Configure {type.name}
            </h2>
            <p className="text-sm text-gray-400">
              Enter your API credentials below. They will be encrypted at rest.
            </p>
          </div>
        </div>

        {/* Credential fields */}
        <div className="space-y-4">
          {type.fields.map((field) => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">
                {fieldLabel(field)}
              </label>
              <div className="relative">
                <input
                  type={
                    isSecretField(field) && !showSecrets[field]
                      ? "password"
                      : "text"
                  }
                  value={credentials[field] || ""}
                  onChange={(e) =>
                    setCredentials({ ...credentials, [field]: e.target.value })
                  }
                  placeholder={type.defaults[field] || `Enter ${fieldLabel(field)}`}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                {isSecretField(field) && (
                  <button
                    type="button"
                    onClick={() =>
                      setShowSecrets({
                        ...showSecrets,
                        [field]: !showSecrets[field],
                      })
                    }
                    className="absolute right-2 top-2.5 text-gray-500 hover:text-gray-300"
                  >
                    {showSecrets[field] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Sync interval */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">
              Sync Interval (minutes)
            </label>
            <input
              type="number"
              min={5}
              max={1440}
              value={syncInterval}
              onChange={(e) => setSyncInterval(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Test result */}
        {testResult && (
          <div
            className={cn(
              "mt-4 rounded-lg border p-3 text-sm",
              testResult.success
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                : "border-red-500/30 bg-red-500/10 text-red-400"
            )}
          >
            <div className="flex items-center gap-2">
              {testResult.success ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              {testResult.message}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={handleTest}
            disabled={testing}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 disabled:opacity-50"
          >
            {testing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <TestTube2 className="h-4 w-4" />
            )}
            Test Connection
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 transition-colors hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save Connector
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
