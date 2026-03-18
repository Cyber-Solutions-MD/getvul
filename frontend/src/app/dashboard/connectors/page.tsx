"use client";

import { useEffect, useState, useCallback } from "react";
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
  Play,
  Shield,
  ExternalLink,
  Info,
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
  JAMF: { color: "text-pink-400" },
};

export default function ConnectorsPage() {
  const [connectorTypes, setConnectorTypes] = useState<ConnectorType[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    try {
      const typesRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/connectors/types`);
      if (typesRes.ok) setConnectorTypes(await typesRes.json());
      try {
        const conns = await api<ConnectorConfig[]>("/api/v1/connectors");
        setConnectors(conns);
      } catch {}
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll for sync status when syncs are running
  useEffect(() => {
    if (syncingIds.size === 0) return;
    const interval = setInterval(async () => {
      let anyRunning = false;
      for (const id of syncingIds) {
        try {
          const status = await api<{ is_running: boolean }>(`/api/v1/connectors/${id}/sync-status`);
          if (status.is_running) {
            anyRunning = true;
          } else {
            setSyncingIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
            loadData(); // Refresh to show updated sync results
          }
        } catch {}
      }
      if (!anyRunning) {
        setSyncingIds(new Set());
        loadData();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [syncingIds, loadData]);

  async function handleSync(connectorId: string) {
    try {
      const result = await api<{ status: string; message: string }>(`/api/v1/connectors/${connectorId}/sync`, { method: "POST" });
      if (result.status === "STARTED") {
        setSyncingIds((prev) => new Set(prev).add(connectorId));
      } else if (result.status === "ALREADY_RUNNING") {
        setSyncingIds((prev) => new Set(prev).add(connectorId));
      }
    } catch (e: any) {
      alert(`Sync failed: ${e.message}`);
    }
  }

  async function handleDelete(connectorId: string) {
    if (!confirm("Delete this connector? Synced data will remain.")) return;
    try {
      await api(`/api/v1/connectors/${connectorId}`, { method: "DELETE" });
      loadData();
    } catch (e: any) { alert(`Delete failed: ${e.message}`); }
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
            {connectors.map((conn) => {
              const isSyncing = syncingIds.has(conn.id);
              return (
                <div key={conn.id} className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-gray-800 p-2.5">
                        <Plug className={cn("h-5 w-5", CONNECTOR_META[conn.connector_type]?.color || "text-gray-400")} />
                      </div>
                      <div>
                        <h3 className="font-medium text-white">{conn.connector_name}</h3>
                        <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
                          {isSyncing ? (
                            <><Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" /><span className="text-indigo-400">Syncing...</span></>
                          ) : conn.last_sync_status === "SUCCESS" ? (
                            <><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />{conn.last_sync_at ? `Last sync: ${new Date(conn.last_sync_at).toLocaleString()}` : "Never synced"}</>
                          ) : conn.last_sync_status === "FAILED" ? (
                            <><XCircle className="h-3.5 w-3.5 text-red-400" />Last sync failed</>
                          ) : (
                            <><AlertCircle className="h-3.5 w-3.5 text-gray-500" />Never synced</>
                          )}
                          {conn.last_sync_record_count !== null && !isSyncing && (
                            <span>· {conn.last_sync_record_count} records</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className={cn("rounded-full px-2 py-0.5 text-xs font-medium", conn.is_enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400")}>
                      {conn.is_enabled ? "Active" : "Disabled"}
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-gray-500">
                      Auto-sync every {conn.sync_interval_minutes} min · Credentials: {conn.has_credentials ? "✓" : "✗"}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSync(conn.id)}
                        disabled={isSyncing}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50"
                      >
                        {isSyncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                        {isSyncing ? "Syncing..." : "Sync Now"}
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
              );
            })}
          </div>
        </div>
      )}

      {/* Available connectors */}
      <div className="space-y-4">
        <h2 className="text-sm font-medium text-gray-400">{connectors.length > 0 ? "Add More Connectors" : "Available Connectors"}</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {connectorTypes.filter((t) => !configuredTypes.has(t.type)).map((type) => (
            <button key={type.type} onClick={() => { setSelectedType(type.type); setShowAddModal(true); }}
              className="flex items-start gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 text-left transition-colors hover:border-indigo-500/50 hover:bg-gray-900">
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
        method: "POST", body: JSON.stringify({ connector_type: type.type, credentials, config: {} }),
      });
      setTestResult(result);
    } catch (e: any) { setTestResult({ success: false, message: e.message }); }
    finally { setTesting(false); }
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      await api("/api/v1/connectors", {
        method: "POST",
        body: JSON.stringify({ connector_type: type.type, credentials, config: {}, is_enabled: true, sync_interval_minutes: syncInterval }),
      });
      onSaved();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-lg bg-gray-800 p-2">
            <Plug className={cn("h-5 w-5", CONNECTOR_META[type.type]?.color || "text-gray-400")} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Configure {type.name}</h2>
            <p className="text-sm text-gray-400">{type.description}</p>
          </div>
        </div>

        {/* Permissions */}
        <div className="mb-4 rounded-lg border border-gray-800 bg-gray-900/50">
          <button onClick={() => setShowPerms(!showPerms)} className="flex w-full items-center justify-between px-4 py-3 text-left">
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <Shield className="h-4 w-4 text-indigo-400" />Required Permissions ({type.permissions.length})
            </div>
            <span className="text-xs text-gray-500">{showPerms ? "Hide" : "Show"}</span>
          </button>
          {showPerms && (
            <div className="border-t border-gray-800 px-4 py-3 space-y-3">
              <table className="w-full text-xs">
                <thead><tr className="text-gray-500"><th className="pb-2 text-left font-medium">Scope</th><th className="pb-2 text-left font-medium">Access</th><th className="pb-2 text-left font-medium">Purpose</th></tr></thead>
                <tbody className="divide-y divide-gray-800">
                  {type.permissions.map((p) => (
                    <tr key={p.scope}><td className="py-1.5 font-mono text-indigo-400">{p.scope}</td><td className="py-1.5 text-gray-400">{p.access}</td><td className="py-1.5 text-gray-500">{p.purpose}</td></tr>
                  ))}
                </tbody>
              </table>
              {type.notes && <div className="flex gap-2 rounded-md bg-gray-800/50 p-2.5 text-xs text-gray-400"><Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-gray-500" /><span>{type.notes}</span></div>}
              <a href={type.setup_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"><ExternalLink className="h-3 w-3" />Setup documentation</a>
            </div>
          )}
        </div>

        {/* Region selector */}
        {Object.keys(type.base_urls).length > 1 && (
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Region</label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(type.base_urls).map(([region, url]) => (
                <button key={region} onClick={() => setCredentials({ ...credentials, base_url: url, api_endpoint_url: url })}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    (credentials.base_url === url || credentials.api_endpoint_url === url)
                      ? "border-indigo-500 bg-indigo-500/15 text-indigo-400"
                      : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-300"
                  )}>{region}</button>
              ))}
            </div>
          </div>
        )}

        {/* Fields */}
        <div className="space-y-4">
          {type.fields.map((field) => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{fieldLabel(field)}</label>
              <div className="relative">
                <input type={isSecretField(field) && !showSecrets[field] ? "password" : "text"} value={credentials[field] || ""}
                  onChange={(e) => setCredentials({ ...credentials, [field]: e.target.value })}
                  placeholder={type.defaults[field] || `Enter ${fieldLabel(field)}`}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
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
            <div className="flex items-center gap-3">
              {[5, 15, 30, 60].map((m) => (
                <button key={m} onClick={() => setSyncInterval(m)}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    syncInterval === m ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400 hover:text-gray-300"
                  )}>{m === 60 ? "1 hr" : `${m} min`}</button>
              ))}
              <input type="number" min={5} max={1440} value={syncInterval}
                onChange={(e) => setSyncInterval(Number(e.target.value))}
                className="w-20 rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none" />
              <span className="text-xs text-gray-500">min</span>
            </div>
          </div>
        </div>

        {/* Result */}
        {testResult && (
          <div className={cn("mt-4 rounded-lg border p-3 text-sm", testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
            <div className="flex items-center gap-2">{testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{testResult.message}</div>
          </div>
        )}
        {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

        {/* Actions */}
        <div className="mt-6 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing} className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}Test Connection
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-medium text-gray-400 hover:text-white">Cancel</button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}Save Connector
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
