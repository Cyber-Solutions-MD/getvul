"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plug, Plus, TestTube2, Trash2, CheckCircle2, XCircle, AlertCircle,
  Loader2, Eye, EyeOff, Play, Shield, ExternalLink, Info,
  Search, Bug, Ticket, Users, Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { ConnectorType, ConnectorConfig, ConnectorTestResult } from "@/types/connector";

const CONNECTOR_META: Record<string, { color: string; icon: string }> = {
  CROWDSTRIKE: { color: "text-red-400", icon: "CS" },
  NESSUS: { color: "text-green-400", icon: "NS" },
  DEFENDER: { color: "text-blue-400", icon: "MD" },
  WIZ: { color: "text-purple-400", icon: "WZ" },
  GOOGLE_WORKSPACE: { color: "text-green-400", icon: "GW" },
  AZURE_ENTRA_ID: { color: "text-blue-400", icon: "AZ" },
  ASANA: { color: "text-orange-400", icon: "AS" },
  HUMAANS: { color: "text-cyan-400", icon: "HU" },
  JAMF: { color: "text-pink-400", icon: "JF" },
  JIRA: { color: "text-blue-400", icon: "JR" },
  QUALYS: { color: "text-red-400", icon: "QL" },
  OKTA: { color: "text-indigo-400", icon: "OK" },
  INTUNE: { color: "text-blue-400", icon: "IN" },
  RAPID7: { color: "text-orange-400", icon: "R7" },
};

const CATEGORY_INFO: Record<string, { label: string; description: string; icon: typeof Bug }> = {
  vulnerability_scanner: {
    label: "Vulnerability Scanners",
    description: "Connect your vulnerability management tools to aggregate and correlate findings",
    icon: Bug,
  },
  ticketing: {
    label: "Ticketing & Workflow",
    description: "Create and track remediation tickets automatically",
    icon: Ticket,
  },
  identity_provider: {
    label: "Identity Providers",
    description: "SSO authentication and user/group directory sync",
    icon: Users,
  },
  enrichment: {
    label: "Enrichment & MDM",
    description: "Enrich asset and user data from HR platforms and device management",
    icon: Wrench,
  },
};

const CATEGORY_ORDER = ["vulnerability_scanner", "ticketing", "identity_provider", "enrichment"];

export default function ConnectorsPage() {
  const [connectorTypes, setConnectorTypes] = useState<(ConnectorType & { category?: string })[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [editingConnector, setEditingConnector] = useState<ConnectorConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    try {
      const [types, conns] = await Promise.all([
        api<(ConnectorType & { category?: string })[]>("/api/v1/connectors/types").catch(() => []),
        api<ConnectorConfig[]>("/api/v1/connectors").catch(() => []),
      ]);
      setConnectorTypes(types);
      setConnectors(conns);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll for sync status
  useEffect(() => {
    if (syncingIds.size === 0) return;
    const interval = setInterval(async () => {
      let anyRunning = false;
      for (const id of Array.from(syncingIds)) {
        try {
          const status = await api<{ is_running: boolean }>(`/api/v1/connectors/${id}/sync-status`);
          if (status.is_running) { anyRunning = true; }
          else { setSyncingIds(prev => { const next = new Set(prev); next.delete(id); return next; }); loadData(); }
        } catch {}
      }
      if (!anyRunning) { setSyncingIds(new Set()); loadData(); }
    }, 3000);
    return () => clearInterval(interval);
  }, [syncingIds, loadData]);

  async function handleSync(connectorId: string) {
    try {
      const result = await api<{ status: string }>(`/api/v1/connectors/${connectorId}/sync`, { method: "POST" });
      if (result.status === "STARTED" || result.status === "ALREADY_RUNNING") {
        setSyncingIds(prev => new Set(prev).add(connectorId));
      }
    } catch (e: any) { alert(`Sync failed: ${e.message}`); }
  }

  async function handleDelete(connectorId: string) {
    if (!confirm("Delete this connector? Synced data will remain.")) return;
    try { await api(`/api/v1/connectors/${connectorId}`, { method: "DELETE" }); loadData(); }
    catch (e: any) { alert(`Delete failed: ${e.message}`); }
  }

  const configuredTypes = new Set(connectors.map(c => c.connector_type));
  const connectorsByType = Object.fromEntries(connectors.map(c => [c.connector_type, c]));

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Connectors</h1>
        <p className="mt-1 text-sm text-gray-400">Connect your security tools, ticketing systems, and enrichment sources</p>
      </div>

      {/* Summary bar */}
      <div className="flex items-center gap-6">
        {CATEGORY_ORDER.map(cat => {
          const info = CATEGORY_INFO[cat];
          const typesInCat = connectorTypes.filter(t => t.category === cat);
          const configuredCount = typesInCat.filter(t => configuredTypes.has(t.type)).length;
          return (
            <div key={cat} className="flex items-center gap-2 text-sm">
              <info.icon className={`h-4 w-4 ${configuredCount > 0 ? "text-emerald-400" : "text-gray-600"}`} />
              <span className="text-gray-400">{info.label.split(" ")[0]}</span>
              <span className={`font-mono text-xs ${configuredCount > 0 ? "text-emerald-400" : "text-gray-600"}`}>
                {configuredCount}/{typesInCat.length}
              </span>
            </div>
          );
        })}
      </div>

      {/* Category sections */}
      {CATEGORY_ORDER.map(cat => {
        const info = CATEGORY_INFO[cat];
        const Icon = info.icon;
        const typesInCat = connectorTypes.filter(t => t.category === cat);
        if (typesInCat.length === 0) return null;

        return (
          <div key={cat} className="space-y-4">
            {/* Category header */}
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-gray-800 p-2">
                <Icon className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h2 className="text-lg font-medium text-white">{info.label}</h2>
                <p className="text-xs text-gray-500">{info.description}</p>
              </div>
            </div>

            {/* Connector cards in this category */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {typesInCat.map(type => {
                const conn = connectorsByType[type.type];
                const isConfigured = !!conn;
                const isSyncing = conn ? syncingIds.has(conn.id) : false;
                const meta = CONNECTOR_META[type.type];

                return (
                  <div key={type.type}
                    className={cn(
                      "rounded-xl border p-5 transition-all",
                      isConfigured
                        ? "border-gray-700 bg-gray-900/80"
                        : "border-gray-800 bg-gray-900/30 hover:border-indigo-500/40 hover:bg-gray-900/50"
                    )}>
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg text-xs font-bold", isConfigured ? "bg-gray-800" : "bg-gray-800/50")}>
                          <span className={meta?.color || "text-gray-400"}>{meta?.icon || type.type.slice(0, 2)}</span>
                        </div>
                        <div>
                          <h3 className="font-medium text-white">{type.name}</h3>
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{type.description}</p>
                        </div>
                      </div>
                      {isConfigured && (
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium",
                          conn.is_enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400"
                        )}>
                          {conn.is_enabled ? "Active" : "Disabled"}
                        </span>
                      )}
                    </div>

                    {isConfigured ? (
                      <>
                        {/* Sync status */}
                        <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
                          {isSyncing ? (
                            <><Loader2 className="h-3 w-3 animate-spin text-indigo-400" /><span className="text-indigo-400">Syncing...</span></>
                          ) : conn.last_sync_status === "SUCCESS" ? (
                            <><CheckCircle2 className="h-3 w-3 text-emerald-400" />
                              {conn.last_sync_at ? `Synced ${timeAgo(conn.last_sync_at)}` : "Never synced"}
                              {conn.last_sync_record_count != null && <span className="text-gray-500">· {conn.last_sync_record_count} records</span>}
                            </>
                          ) : conn.last_sync_status === "FAILED" ? (
                            <><XCircle className="h-3 w-3 text-red-400" /><span className="text-red-400">Sync failed</span></>
                          ) : (
                            <><AlertCircle className="h-3 w-3 text-gray-500" />Never synced</>
                          )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2">
                          <button onClick={() => handleSync(conn.id)} disabled={isSyncing}
                            className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-2.5 py-1.5 text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-50">
                            {isSyncing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                            Sync
                          </button>
                          <button onClick={() => setEditingConnector(conn)}
                            className="rounded-lg border border-gray-700 px-2.5 py-1.5 text-xs text-gray-300 hover:bg-gray-800">
                            Edit
                          </button>
                          <button onClick={() => handleDelete(conn.id)}
                            className="ml-auto rounded-lg border border-gray-700 p-1.5 text-gray-500 hover:bg-gray-800 hover:text-red-400">
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </>
                    ) : (
                      <button onClick={() => { setSelectedType(type.type); setShowAddModal(true); }}
                        className="flex items-center gap-1.5 rounded-lg border border-dashed border-gray-700 px-3 py-2 text-xs text-indigo-400 hover:border-indigo-500/50 hover:bg-indigo-500/5 w-full justify-center mt-1">
                        <Plus className="h-3 w-3" />Configure
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {showAddModal && selectedType && (
        <AddConnectorModal
          type={connectorTypes.find(t => t.type === selectedType)!}
          onClose={() => { setShowAddModal(false); setSelectedType(null); }}
          onSaved={() => { setShowAddModal(false); setSelectedType(null); loadData(); }}
        />
      )}

      {editingConnector && (
        <EditConnectorModal
          connector={editingConnector}
          type={connectorTypes.find(t => t.type === editingConnector.connector_type)!}
          onClose={() => setEditingConnector(null)}
          onSaved={() => { setEditingConnector(null); loadData(); }}
        />
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return `${Math.floor(diffHrs / 24)}d ago`;
}

function AddConnectorModal({ type, onClose, onSaved }: { type: ConnectorType; onClose: () => void; onSaved: () => void }) {
  const [credentials, setCredentials] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    type.fields.forEach(f => { initial[f] = type.defaults[f] || ""; });
    return initial;
  });
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [syncInterval, setSyncInterval] = useState(15);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPerms, setShowPerms] = useState(false);

  const isSecretField = (f: string) => f.includes("secret") || f.includes("key") || f.includes("password") || f.includes("token");
  const fieldLabel = (f: string) => f.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

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
            <span className={cn("text-sm font-bold", CONNECTOR_META[type.type]?.color || "text-gray-400")}>
              {CONNECTOR_META[type.type]?.icon || type.type.slice(0, 2)}
            </span>
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
                  {type.permissions.map(p => (
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
          {type.fields.map(field => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{fieldLabel(field)}</label>
              <div className="relative">
                <input type={isSecretField(field) && !showSecrets[field] ? "password" : "text"} value={credentials[field] || ""}
                  onChange={e => setCredentials({ ...credentials, [field]: e.target.value })}
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
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Sync Interval</label>
            <div className="flex items-center gap-3">
              {[5, 15, 30, 60].map(m => (
                <button key={m} onClick={() => setSyncInterval(m)}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    syncInterval === m ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"
                  )}>{m === 60 ? "1 hr" : `${m} min`}</button>
              ))}
            </div>
          </div>
        </div>

        {testResult && (
          <div className={cn("mt-4 rounded-lg border p-3 text-sm", testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
            <div className="flex items-center gap-2">{testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{testResult.message}</div>
          </div>
        )}
        {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

        <div className="mt-6 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing} className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}Test
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
            <button onClick={handleSave} disabled={saving} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EditConnectorModal({ connector, type, onClose, onSaved }: {
  connector: ConnectorConfig; type: ConnectorType; onClose: () => void; onSaved: () => void;
}) {
  const [credentials, setCredentials] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    if (type?.fields) type.fields.forEach(f => { initial[f] = ""; });
    return initial;
  });
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [syncInterval, setSyncInterval] = useState(connector.sync_interval_minutes);
  const [isEnabled, setIsEnabled] = useState(connector.is_enabled);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectorTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSecretField = (f: string) => f.includes("secret") || f.includes("key") || f.includes("password") || f.includes("token");
  const fieldLabel = (f: string) => f.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const hasNewCredentials = Object.values(credentials).some(v => v.trim() !== "");

  async function handleTest() {
    if (!hasNewCredentials) { setError("Enter new credentials to test"); return; }
    setTesting(true); setTestResult(null); setError(null);
    try {
      const result = await api<ConnectorTestResult>("/api/v1/connectors/test", {
        method: "POST", body: JSON.stringify({ connector_type: connector.connector_type, credentials, config: connector.config || {} }),
      });
      setTestResult(result);
    } catch (e: any) { setTestResult({ success: false, message: e.message }); }
    finally { setTesting(false); }
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      const body: any = { sync_interval_minutes: syncInterval, is_enabled: isEnabled };
      if (hasNewCredentials) body.credentials = credentials;
      await api(`/api/v1/connectors/${connector.id}`, { method: "PATCH", body: JSON.stringify(body) });
      onSaved();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  }

  if (!type) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-lg bg-gray-800 p-2">
            <span className={cn("text-sm font-bold", CONNECTOR_META[connector.connector_type]?.color || "text-gray-400")}>
              {CONNECTOR_META[connector.connector_type]?.icon || connector.connector_type.slice(0, 2)}
            </span>
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Edit {connector.connector_name}</h2>
            <p className="text-sm text-gray-400">Update credentials or settings</p>
          </div>
        </div>

        <div className="mb-4 flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900/50 px-4 py-3">
          <span className="text-sm text-gray-300">Connector Enabled</span>
          <button onClick={() => setIsEnabled(!isEnabled)}
            className={cn("relative inline-flex h-6 w-11 items-center rounded-full transition-colors", isEnabled ? "bg-indigo-600" : "bg-gray-700")}>
            <span className={cn("inline-block h-4 w-4 rounded-full bg-white transition-transform", isEnabled ? "translate-x-6" : "translate-x-1")} />
          </button>
        </div>

        <div className="space-y-4">
          <p className="text-xs text-gray-500">Leave credential fields blank to keep existing values.</p>
          {type.fields.map(field => (
            <div key={field}>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">{fieldLabel(field)}</label>
              <div className="relative">
                <input type={isSecretField(field) && !showSecrets[field] ? "password" : "text"} value={credentials[field] || ""}
                  onChange={e => setCredentials({ ...credentials, [field]: e.target.value })}
                  placeholder={`Enter new ${fieldLabel(field)} (or leave blank)`}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
                {isSecretField(field) && (
                  <button type="button" onClick={() => setShowSecrets({ ...showSecrets, [field]: !showSecrets[field] })} className="absolute right-2 top-2.5 text-gray-500 hover:text-gray-300">
                    {showSecrets[field] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                )}
              </div>
            </div>
          ))}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Sync Interval</label>
            <div className="flex items-center gap-3">
              {[5, 15, 30, 60].map(m => (
                <button key={m} onClick={() => setSyncInterval(m)}
                  className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                    syncInterval === m ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"
                  )}>{m === 60 ? "1 hr" : `${m} min`}</button>
              ))}
            </div>
          </div>
        </div>

        {testResult && (
          <div className={cn("mt-4 rounded-lg border p-3 text-sm", testResult.success ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : "border-red-500/30 bg-red-500/10 text-red-400")}>
            <div className="flex items-center gap-2">{testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{testResult.message}</div>
          </div>
        )}
        {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

        <div className="mt-6 flex items-center justify-between">
          <button onClick={handleTest} disabled={testing || !hasNewCredentials}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <TestTube2 className="h-4 w-4" />}Test
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}Update
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
