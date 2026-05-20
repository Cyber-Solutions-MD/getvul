"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import ConfirmModal from "@/components/ui/ConfirmModal";

export default function SettingsPage() {
  const { user } = useAuth();
  const [tenant, setTenant] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"general" | "auth" | "users" | "audit">("general");
  const [confirmModal, setConfirmModal] = useState<{ title: string; message: string; variant?: "danger" | "warning" | "info"; onConfirm: () => void } | null>(null);

  const isOwner = user?.role === "OWNER";
  const isAdmin = user?.role === "OWNER" || user?.role === "ADMIN";

  const load = useCallback(async () => {
    try {
      const [t, s, u] = await Promise.all([
        api("/api/v1/tenant/me"),
        isAdmin ? api("/api/v1/tenant/settings").catch(() => null) : null,
        isAdmin ? api("/api/v1/tenant/users").catch(() => []) : [],
      ]);
      setTenant(t);
      if (s) setSettings(s);
      if (Array.isArray(u)) setUsers(u);
    } catch {} finally { setLoading(false); }
  }, [isAdmin]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" /></div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        {["general", "auth", "users", "audit"].map(t => (
          <button key={t} onClick={() => setTab(t as any)}
            className={`pb-2 text-sm font-medium capitalize transition ${tab === t ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
            {t === "auth" ? "Authentication" : t === "audit" ? "Audit Log" : t}
          </button>
        ))}
      </div>

      {/* General */}
      {tab === "general" && tenant && (
        <div className="space-y-6">
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="text-lg font-medium text-white mb-4">Organization</h2>
            <div className="grid grid-cols-2 gap-6 text-sm">
              <OrgField label="Name" field="name" value={tenant.name} editable={isOwner} onSave={async (v) => { await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ name: v }) }); load(); }} />
              <OrgField label="Slug" field="slug" value={tenant.slug} editable={isOwner} mono onSave={async (v) => { await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ slug: v }) }); load(); }} />
              <OrgField label="Domain" field="domain" value={tenant.domain || ""} editable={isOwner} onSave={async (v) => { await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ domain: v }) }); load(); }} />
              <div>
                <span className="text-gray-500">Timezone</span>
                {isOwner ? (
                  <select value={tenant.timezone || "UTC"}
                    onChange={async (e) => { await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ timezone: e.target.value }) }); load(); }}
                    className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
                    {["UTC","Europe/London","Europe/Berlin","Europe/Paris","Europe/Zurich","Europe/Amsterdam","Europe/Warsaw","Europe/Bucharest","Europe/Istanbul",
                      "US/Eastern","US/Central","US/Mountain","US/Pacific","America/New_York","America/Chicago","America/Los_Angeles",
                      "Asia/Tokyo","Asia/Shanghai","Asia/Singapore","Asia/Kolkata","Asia/Dubai",
                      "Australia/Sydney","Pacific/Auckland"].map(tz => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                ) : (
                  <p className="text-white mt-1">{tenant.timezone || "UTC"}</p>
                )}
              </div>
            </div>
          </div>

          {/* Report Branding */}
          {isOwner && <BrandingConfig />}

          {/* SLA Policy */}
          {isOwner && <SlaConfig />}

          {/* TLS Certificate */}
          {isOwner && <TlsCertificatePanel />}

          {/* SMTP / Email */}
          {isOwner && <SmtpConfig />}
        </div>
      )}

      {/* Authentication */}
      {tab === "auth" && settings && tenant && (
        <AuthTab tenant={tenant} settings={settings} isOwner={isOwner} onReload={load} />
      )}

      {/* Users */}
      {tab === "users" && isAdmin && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-400">{users.length} users in this organization</p>
            {isOwner && <AddUserButton onAdded={load} />}
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-700">
            <table className="w-full text-sm text-left">
              <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Password Login</th>
                  {isOwner && <th className="px-4 py-3">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {users.map((u: any) => (
                  <tr key={u.id} className="bg-gray-900 hover:bg-gray-800">
                    <td className="px-4 py-3">
                      <EditableField value={u.display_name || ""} placeholder="Name"
                        onSave={async (v) => { await api(`/api/v1/tenant/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ display_name: v }) }); load(); }}
                        editable={isOwner} className="text-white font-medium" />
                    </td>
                    <td className="px-4 py-3">
                      <EditableField value={u.email} placeholder="Email"
                        onSave={async (v) => { await api(`/api/v1/tenant/users/${u.id}`, { method: "PATCH", body: JSON.stringify({ email: v }) }); load(); }}
                        editable={isOwner} className="text-gray-400 text-xs" />
                    </td>
                    <td className="px-4 py-3">
                      {isOwner && u.id !== user?.id ? (
                        <select value={u.role}
                          onChange={async (e) => {
                            await api(`/api/v1/tenant/users/${u.id}/role`, {
                              method: "PATCH",
                              body: JSON.stringify({ role: e.target.value }),
                            });
                            load();
                          }}
                          className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white">
                          <option value="OWNER">Owner</option>
                          <option value="ADMIN">Admin</option>
                          <option value="ANALYST">Analyst</option>
                          <option value="VIEWER">Viewer</option>
                        </select>
                      ) : (
                        <span className="text-xs text-gray-300">{u.role}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${u.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isOwner ? (
                        <button
                          onClick={async () => {
                            await api(`/api/v1/tenant/users/${u.id}/allow-password`, {
                              method: "PATCH",
                              body: JSON.stringify({ allow: !u.allow_password_login }),
                            });
                            load();
                          }}
                          className={`rounded-full px-2 py-0.5 text-xs cursor-pointer ${
                            u.allow_password_login ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400"
                          }`}>
                          {u.allow_password_login ? "Allowed" : "Disabled"}
                        </button>
                      ) : (
                        <span className="text-xs text-gray-500">{u.allow_password_login ? "Yes" : "No"}</span>
                      )}
                    </td>
                    {isOwner && (
                      <td className="px-4 py-3">
                        {u.id !== user?.id && (
                          <div className="flex gap-2">
                            {u.is_active && (
                              <button onClick={() => {
                                setConfirmModal({
                                  title: "Deactivate User",
                                  message: `Deactivate ${u.email}?`,
                                  variant: "warning",
                                  onConfirm: async () => {
                                    setConfirmModal(null);
                                    await api(`/api/v1/tenant/users/${u.id}/deactivate`, { method: "PATCH" });
                                    load();
                                  },
                                });
                              }}
                                className="text-xs text-gray-500 hover:text-orange-400">
                                Deactivate
                              </button>
                            )}
                            <button onClick={() => {
                              setConfirmModal({
                                title: "Delete User",
                                message: `Permanently delete ${u.email}? This cannot be undone.`,
                                variant: "danger",
                                onConfirm: async () => {
                                  setConfirmModal(null);
                                  await api(`/api/v1/tenant/users/${u.id}`, { method: "DELETE" });
                                  load();
                                },
                              });
                            }}
                              className="text-xs text-gray-500 hover:text-red-400">
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Audit Log */}
      {tab === "audit" && isAdmin && (
        <div className="space-y-6">
          {isOwner && <SyslogConfig />}
          <AuditLogPanel />
        </div>
      )}

      <ConfirmModal
        open={!!confirmModal}
        title={confirmModal?.title || ""}
        message={confirmModal?.message || ""}
        variant={confirmModal?.variant}
        confirmLabel="Confirm"
        onConfirm={() => confirmModal?.onConfirm()}
        onCancel={() => setConfirmModal(null)}
      />
    </div>
  );
}

function AuthTab({ tenant, settings, isOwner, onReload }: { tenant: any; settings: any; isOwner: boolean; onReload: () => void }) {
  const [connectors, setConnectors] = useState<any[]>([]);

  useEffect(() => {
    api("/api/v1/connectors").then(d => setConnectors(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const hasGoogle = connectors.some(c => c.connector_type === "GOOGLE_WORKSPACE" && c.has_credentials);
  const hasAzure = connectors.some(c => c.connector_type === "AZURE_ENTRA_ID" && c.has_credentials);
  const currentIdp = tenant.idp_provider || "LOCAL";

  const providers = [
    { id: "LOCAL", name: "Local", desc: "Email & password only", icon: "🔑", available: true },
    { id: "GOOGLE", name: "Google Workspace", desc: "SSO via Google", icon: "🔵", available: hasGoogle,
      hint: !hasGoogle ? "Configure Google Workspace connector first" : undefined },
    { id: "AZURE_ENTRA_ID", name: "Azure Entra ID", desc: "SSO via Microsoft", icon: "🟦", available: hasAzure,
      hint: !hasAzure ? "Configure Azure Entra ID connector first" : undefined },
  ];

  return (
    <div className="space-y-6">
      {/* Identity Provider */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-medium text-white mb-1">Identity Provider</h2>
        <p className="text-sm text-gray-400 mb-4">Select how users authenticate to GetVul</p>

        {isOwner ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {providers.map(p => (
              <button key={p.id}
                disabled={!p.available}
                onClick={async () => {
                  if (!p.available) return;
                  await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ idp_provider: p.id }) });
                  onReload();
                }}
                className={`rounded-lg border p-4 text-left transition ${
                  !p.available
                    ? "border-gray-800 bg-gray-900 opacity-40 cursor-not-allowed"
                    : currentIdp === p.id
                      ? "border-indigo-500 bg-indigo-500/10"
                      : "border-gray-700 bg-gray-800 hover:border-gray-600"
                }`}>
                <p className="text-lg mb-1">{p.icon}</p>
                <p className={`text-sm font-medium ${currentIdp === p.id ? "text-indigo-400" : "text-white"}`}>{p.name}</p>
                <p className="text-xs text-gray-500 mt-1">{p.desc}</p>
                {p.hint && <p className="text-xs text-orange-400 mt-2">{p.hint}</p>}
                {p.available && currentIdp === p.id && <p className="text-xs text-emerald-400 mt-2">Active</p>}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-white">{currentIdp}</p>
        )}
      </div>

      {/* SSO Enforcement — only when IdP is not LOCAL AND connector is configured */}
      {currentIdp !== "LOCAL" && ((currentIdp === "GOOGLE" && hasGoogle) || (currentIdp === "AZURE_ENTRA_ID" && hasAzure)) && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="text-lg font-medium text-white mb-1">SSO Enforcement</h2>
          <p className="text-sm text-gray-400 mb-4">
            When enforced, all users must login via {currentIdp === "GOOGLE" ? "Google" : "Microsoft"} SSO.
          </p>
          <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
            <div>
              <p className="text-sm text-white font-medium">Enforce SSO</p>
              <p className="text-xs text-gray-500">Users with "Password Login: Allowed" can still use email/password</p>
            </div>
            {isOwner ? (
              <button onClick={async () => {
                await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ sso_enforced: !settings.sso_enforced }) });
                onReload();
              }}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.sso_enforced ? "bg-indigo-600" : "bg-gray-700"}`}>
                <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${settings.sso_enforced ? "translate-x-6" : "translate-x-1"}`} />
              </button>
            ) : (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${settings.sso_enforced ? "bg-indigo-500/20 text-indigo-400" : "bg-gray-700 text-gray-400"}`}>
                {settings.sso_enforced ? "Enforced" : "Not enforced"}
              </span>
            )}
          </div>
          {settings.sso_enforced && (
            <p className="mt-3 text-xs text-emerald-400">
              SSO enforced — users are redirected to {currentIdp === "GOOGLE" ? "Google" : "Microsoft"}.
              Override per-user in Users tab → Password Login.
            </p>
          )}
        </div>
      )}

      {/* Warning if IdP selected but connector not configured */}
      {currentIdp !== "LOCAL" && !((currentIdp === "GOOGLE" && hasGoogle) || (currentIdp === "AZURE_ENTRA_ID" && hasAzure)) && (
        <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-4">
          <p className="text-sm text-orange-400">
            {currentIdp === "GOOGLE" ? "Google Workspace" : "Azure Entra ID"} is selected but the connector is not configured.
            Go to <strong>Connectors</strong> to set it up before enabling SSO enforcement.
          </p>
        </div>
      )}

      {/* Password Policy */}
      <PasswordPolicyConfig isOwner={isOwner} />
    </div>
  );
}

function PasswordPolicyConfig({ isOwner }: { isOwner: boolean }) {
  const [policy, setPolicy] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api("/api/v1/tenant/settings")
      .then(d => setPolicy(d.password_policy || { min_length: 8, require_uppercase: false, require_lowercase: false, require_digit: false, require_symbol: false, history_count: 0 }))
      .catch(() => {});
  }, []);

  if (!policy) return null;

  async function save() {
    setSaving(true); setMsg("");
    try {
      await api("/api/v1/tenant/settings", { method: "PATCH", body: JSON.stringify({ password_policy: policy }) });
      setMsg("Policy saved");
      setTimeout(() => setMsg(""), 2000);
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">Password Policy</h2>
      <p className="text-sm text-gray-400 mb-4">Configure password requirements for all users</p>

      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-300">Minimum Length</label>
          <div className="flex items-center gap-3">
            {[6, 8, 10, 12, 16].map(n => (
              <button key={n} onClick={() => isOwner && setPolicy({ ...policy, min_length: n })}
                className={`rounded-md border px-3 py-1.5 text-xs font-medium ${policy.min_length === n ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"} ${!isOwner ? "cursor-default" : ""}`}>
                {n}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium text-gray-300">Complexity Requirements</p>
          {[
            { key: "require_uppercase", label: "Require uppercase letter (A-Z)" },
            { key: "require_lowercase", label: "Require lowercase letter (a-z)" },
            { key: "require_digit", label: "Require digit (0-9)" },
            { key: "require_symbol", label: "Require symbol (!@#$%...)" },
          ].map(r => (
            <label key={r.key} className="flex items-center gap-3 text-sm text-gray-300">
              <input type="checkbox" checked={policy[r.key] || false}
                onChange={e => isOwner && setPolicy({ ...policy, [r.key]: e.target.checked })}
                disabled={!isOwner}
                className="rounded border-gray-600" />
              {r.label}
            </label>
          ))}
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-gray-300">Password History</label>
          <p className="text-xs text-gray-500 mb-2">Prevent users from reusing recent passwords</p>
          <div className="flex items-center gap-3">
            {[0, 3, 5, 10, 24].map(n => (
              <button key={n} onClick={() => isOwner && setPolicy({ ...policy, history_count: n })}
                className={`rounded-md border px-3 py-1.5 text-xs font-medium ${policy.history_count === n ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"} ${!isOwner ? "cursor-default" : ""}`}>
                {n === 0 ? "Off" : `Last ${n}`}
              </button>
            ))}
          </div>
        </div>

        {msg && <p className={`text-xs ${msg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

        {isOwner && (
          <button onClick={save} disabled={saving}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {saving ? "Saving..." : "Save Policy"}
          </button>
        )}
      </div>
    </div>
  );
}

function SyslogConfig() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("514");
  const [protocol, setProtocol] = useState("udp");
  const [facility, setFacility] = useState("local0");
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    api("/api/v1/tenant/settings")
      .then(d => {
        const cfg = d.syslog_config || {};
        setHost(cfg.host || "");
        setPort(String(cfg.port || 514));
        setProtocol(cfg.protocol || "udp");
        setFacility(cfg.facility || "local0");
        setEnabled(cfg.enabled || false);
        setConfig(cfg);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true); setMsg("");
    try {
      await api("/api/v1/tenant/settings", {
        method: "PATCH",
        body: JSON.stringify({
          syslog_config: { host, port: parseInt(port), protocol, facility, enabled },
        }),
      });
      setMsg(enabled && host ? "Syslog forwarding enabled" : "Syslog forwarding disabled");
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  if (loading) return null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">SIEM / Syslog Forwarding</h2>
      <p className="text-xs text-gray-500 mb-4">Forward audit events to your SIEM solution (Splunk, QRadar, Sentinel, ELK) via syslog in CEF format</p>

      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
          <div>
            <p className="text-sm text-white font-medium">Enable Syslog Forwarding</p>
            <p className="text-xs text-gray-500">All audit events will be sent to the configured syslog server</p>
          </div>
          <button onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-indigo-600" : "bg-gray-700"}`}>
            <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
          </button>
        </div>

        {enabled && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-gray-400">Syslog Host</label>
              <input value={host} onChange={e => setHost(e.target.value)} placeholder="siem.company.com"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Port</label>
              <input value={port} onChange={e => setPort(e.target.value)} placeholder="514"
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Protocol</label>
              <select value={protocol} onChange={e => setProtocol(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
                <option value="udp">UDP</option>
                <option value="tcp">TCP</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">Facility</label>
              <select value={facility} onChange={e => setFacility(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
                <option value="local0">local0</option>
                <option value="local1">local1</option>
                <option value="local2">local2</option>
                <option value="local3">local3</option>
                <option value="auth">auth</option>
                <option value="authpriv">authpriv</option>
              </select>
            </div>
          </div>
        )}

        {msg && <p className={`text-xs ${msg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

        <button onClick={handleSave} disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          {saving ? "Saving..." : "Save Configuration"}
        </button>
      </div>
    </div>
  );
}

function AuditLogPanel() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: "30" });
    if (actionFilter) params.set("action", actionFilter);
    if (resourceFilter) params.set("resource_type", resourceFilter);
    api(`/api/v1/tenant/audit-log?${params}`)
      .then(d => { setLogs(d.items || []); setTotal(d.total || 0); setPages(d.pages || 0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, actionFilter, resourceFilter]);

  const actionColors: Record<string, string> = {
    "auth.login": "text-blue-400", "auth.register": "text-blue-400", "auth.logout": "text-gray-400",
    "vuln.suppress": "text-orange-400", "vuln.unsuppress": "text-emerald-400", "vuln.status_update": "text-yellow-400", "vuln.bulk_status": "text-yellow-400",
    "ticket.create": "text-indigo-400", "ticket.close": "text-emerald-400", "ticket.delete": "text-red-400",
    "user.create": "text-blue-400", "user.delete": "text-red-400", "settings.update": "text-purple-400",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <select value={actionFilter} onChange={e => { setActionFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
          <option value="">All Actions</option>
          <option value="auth">Auth</option>
          <option value="vuln">Vulnerabilities</option>
          <option value="ticket">Tickets</option>
          <option value="user">Users</option>
          <option value="settings">Settings</option>
          <option value="connector">Connectors</option>
          <option value="rule">Rules</option>
        </select>
        <select value={resourceFilter} onChange={e => { setResourceFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
          <option value="">All Resources</option>
          <option value="user">User</option>
          <option value="vulnerability">Vulnerability</option>
          <option value="remediation">Remediation</option>
          <option value="ticket">Ticket</option>
          <option value="connector">Connector</option>
        </select>
        <span className="ml-auto text-sm text-gray-500">{total} entries</span>
      </div>

      {loading ? <p className="text-gray-500 text-sm py-8 text-center">Loading...</p> : (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Resource</th>
                <th className="px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {logs.map((l: any) => (
                <tr key={l.id} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-2 text-gray-500 text-xs whitespace-nowrap">
                    {l.created_at ? new Date(l.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-2 text-gray-300 text-xs">{l.user_email || "system"}</td>
                  <td className="px-4 py-2">
                    <span className={`text-xs font-medium ${actionColors[l.action] || "text-gray-400"}`}>{l.action}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-400 text-xs">
                    {l.resource_type}{l.resource_id ? ` #${l.resource_id.substring(0, 8)}` : ""}
                  </td>
                  <td className="px-4 py-2 text-gray-500 text-xs max-w-[200px] truncate">
                    {l.details ? JSON.stringify(l.details) : "—"}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">No audit logs yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40">Previous</button>
          <span className="text-sm text-gray-500">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40">Next</button>
        </div>
      )}
    </div>
  );
}

function TlsCertificatePanel() {
  const [cert, setCert] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);
  const [certPem, setCertPem] = useState("");
  const [keyPem, setKeyPem] = useState("");
  const [hostname, setHostname] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    api("/api/v1/certificates").then(setCert).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const reload = () => { api("/api/v1/certificates").then(setCert).catch(() => {}); };

  async function handleUpload() {
    if (!certPem || !keyPem) return;
    setSaving(true); setMsg("");
    try {
      const r = await api("/api/v1/certificates/upload", { method: "POST", body: JSON.stringify({ certificate: certPem, private_key: keyPem }) });
      setMsg(r.error || r.message || "Saved"); setCertPem(""); setKeyPem(""); setShowUpload(false); reload();
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  async function handleGenerate() {
    setSaving(true); setMsg("");
    try {
      const r = await api("/api/v1/certificates/self-signed", { method: "POST", body: JSON.stringify({ hostname: hostname || "getvul.local" }) });
      setMsg(r.error || r.message || "Generated"); setShowGenerate(false); reload();
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  function handleDelete() {
    setShowDeleteConfirm(true);
  }

  if (loading) return null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">TLS / SSL Certificate</h2>
      <p className="text-sm text-gray-400 mb-4">Configure HTTPS for secure access</p>

      {cert?.installed ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-sm font-medium text-emerald-400">Certificate Installed</span>
              {cert.self_signed && <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400">Self-signed</span>}
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
              {cert.subject && <div>Subject: <span className="text-gray-300">{cert.subject}</span></div>}
              {cert.issuer && <div>Issuer: <span className="text-gray-300">{cert.issuer}</span></div>}
              {cert.valid_from && <div>Valid from: <span className="text-gray-300">{cert.valid_from}</span></div>}
              {cert.valid_until && <div>Valid until: <span className="text-gray-300">{cert.valid_until}</span></div>}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowUpload(true)} className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800">Replace Certificate</button>
            <button onClick={handleDelete} className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-500 hover:text-red-400">Remove</button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">No certificate installed. The app is accessible via HTTP only.</p>
          <div className="flex gap-2">
            <button onClick={() => setShowUpload(true)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
              Upload Certificate
            </button>
            <button onClick={() => setShowGenerate(true)}
              className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800">
              Generate Self-Signed
            </button>
          </div>
        </div>
      )}

      {/* Upload modal */}
      {showUpload && (
        <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3">
          <p className="text-sm font-medium text-white">Upload TLS Certificate</p>
          <p className="text-xs text-gray-500">Paste the certificate and private key in PEM format. Supports certificates from Microsoft CA, Let's Encrypt, or any CA.</p>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Certificate (PEM)</label>
            <textarea value={certPem} onChange={e => setCertPem(e.target.value)} rows={4}
              placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white font-mono placeholder-gray-600 focus:border-indigo-500 focus:outline-none resize-none" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Private Key (PEM)</label>
            <textarea value={keyPem} onChange={e => setKeyPem(e.target.value)} rows={4}
              placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-white font-mono placeholder-gray-600 focus:border-indigo-500 focus:outline-none resize-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={handleUpload} disabled={saving || !certPem || !keyPem}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving ? "Uploading..." : "Upload"}
            </button>
            <button onClick={() => setShowUpload(false)} className="text-xs text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      {/* Generate self-signed */}
      {showGenerate && (
        <div className="mt-4 rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3">
          <p className="text-sm font-medium text-white">Generate Self-Signed Certificate</p>
          <p className="text-xs text-gray-500">For testing or internal use. Not trusted by browsers without manual import.</p>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Hostname</label>
            <input value={hostname} onChange={e => setHostname(e.target.value)} placeholder="getvul.local"
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={handleGenerate} disabled={saving}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving ? "Generating..." : "Generate"}
            </button>
            <button onClick={() => setShowGenerate(false)} className="text-xs text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      {msg && <p className={`mt-3 text-xs ${msg.startsWith("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

      <ConfirmModal
        open={showDeleteConfirm}
        title="Remove TLS Certificate"
        message="Remove the TLS certificate? HTTPS will stop working."
        confirmLabel="Remove"
        variant="danger"
        onConfirm={async () => {
          setShowDeleteConfirm(false);
          await api("/api/v1/certificates", { method: "DELETE" });
          reload(); setMsg("Certificate removed");
        }}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}

function SlaConfig() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [critical, setCritical] = useState(7);
  const [high, setHigh] = useState(30);
  const [medium, setMedium] = useState(90);
  const [low, setLow] = useState(180);
  const [info, setInfo] = useState(365);

  useEffect(() => {
    api("/api/v1/tenant/settings")
      .then(d => {
        const cfg = d.sla_config?.days || {};
        setCritical(cfg.CRITICAL ?? 7);
        setHigh(cfg.HIGH ?? 30);
        setMedium(cfg.MEDIUM ?? 90);
        setLow(cfg.LOW ?? 180);
        setInfo(cfg.INFO ?? 365);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true); setMsg("");
    try {
      await api("/api/v1/tenant/settings", {
        method: "PATCH",
        body: JSON.stringify({
          sla_config: { days: { CRITICAL: critical, HIGH: high, MEDIUM: medium, LOW: low, INFO: info } },
        }),
      });
      // Recalculate SLA due dates
      const result = await api("/api/v1/vulnerabilities/sla/recalculate", { method: "POST" });
      setMsg(`SLA policy saved. ${result.recalculated || 0} vulnerabilities updated.`);
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  if (loading) return null;

  const fields = [
    { label: "Critical", value: critical, set: setCritical, color: "border-red-500/30" },
    { label: "High", value: high, set: setHigh, color: "border-orange-500/30" },
    { label: "Medium", value: medium, set: setMedium, color: "border-yellow-500/30" },
    { label: "Low", value: low, set: setLow, color: "border-blue-500/30" },
    { label: "Info", value: info, set: setInfo, color: "border-gray-500/30" },
  ];

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">SLA Policy</h2>
      <p className="text-xs text-gray-500 mb-4">Define remediation deadlines per severity level (days from first detection)</p>

      <div className="grid grid-cols-5 gap-3 mb-4">
        {fields.map(f => (
          <div key={f.label} className={`rounded-lg border ${f.color} bg-gray-800 p-3`}>
            <label className="mb-1 block text-xs text-gray-400">{f.label}</label>
            <div className="flex items-center gap-1">
              <input type="number" min={1} max={999} value={f.value}
                onChange={e => f.set(Number(e.target.value))}
                className="w-full rounded border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white text-center focus:border-indigo-500 focus:outline-none" />
              <span className="text-xs text-gray-500">days</span>
            </div>
          </div>
        ))}
      </div>

      {msg && <p className={`text-xs mb-3 ${msg.includes("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

      <button onClick={handleSave} disabled={saving}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
        {saving ? "Saving..." : "Save SLA Policy"}
      </button>
    </div>
  );
}

function SmtpConfig() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("587");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [useTls, setUseTls] = useState(false);
  const [useStarttls, setUseStarttls] = useState(true);

  useEffect(() => {
    api("/api/v1/tenant/settings")
      .then(d => {
        const cfg = d.smtp_config || {};
        setEnabled(cfg.enabled || false);
        setHost(cfg.host || "");
        setPort(String(cfg.port || 587));
        setUsername(cfg.username || "");
        setPassword(cfg.password || "");
        setFromEmail(cfg.from_email || "");
        setUseTls(cfg.use_tls || false);
        setUseStarttls(cfg.use_starttls !== false);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true); setMsg("");
    try {
      await api("/api/v1/tenant/settings", {
        method: "PATCH",
        body: JSON.stringify({
          smtp_config: { enabled, host, port: parseInt(port), username, password, from_email: fromEmail, use_tls: useTls, use_starttls: useStarttls },
        }),
      });
      setMsg(enabled && host ? "SMTP configuration saved" : "SMTP disabled");
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  async function handleTest() {
    setTesting(true); setMsg("");
    try {
      const r = await api("/api/v1/smtp/test", { method: "POST", body: JSON.stringify({}) });
      setMsg(r.ok ? "Connection successful" : `Failed: ${r.error}`);
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setTesting(false); }
  }

  async function handleTestEmail() {
    setTesting(true); setMsg("");
    try {
      const r = await api("/api/v1/smtp/test-email", { method: "POST", body: JSON.stringify({}) });
      setMsg(r.ok ? "Test email sent — check your inbox" : `Failed: ${r.error}`);
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setTesting(false); }
  }

  if (loading) return null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">Email / SMTP</h2>
      <p className="text-xs text-gray-500 mb-4">Configure SMTP to deliver scheduled reports and notifications by email</p>

      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
          <div>
            <p className="text-sm text-white font-medium">Enable Email Delivery</p>
            <p className="text-xs text-gray-500">Scheduled reports will be emailed to configured recipients</p>
          </div>
          <button onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-indigo-600" : "bg-gray-700"}`}>
            <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
          </button>
        </div>

        {enabled && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs text-gray-400">SMTP Host</label>
                <input value={host} onChange={e => setHost(e.target.value)} placeholder="smtp.gmail.com"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Port</label>
                <input value={port} onChange={e => setPort(e.target.value)} placeholder="587"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Username</label>
                <input value={username} onChange={e => setUsername(e.target.value)} placeholder="apikey or email"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Password / API Key</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">From Email</label>
                <input value={fromEmail} onChange={e => setFromEmail(e.target.value)} placeholder="noreply@company.com"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Encryption</label>
                <select value={useTls ? "tls" : useStarttls ? "starttls" : "none"}
                  onChange={e => {
                    const v = e.target.value;
                    setUseTls(v === "tls");
                    setUseStarttls(v === "starttls");
                    if (v === "tls" && port === "587") setPort("465");
                    if (v === "starttls" && port === "465") setPort("587");
                  }}
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
                  <option value="starttls">STARTTLS (port 587)</option>
                  <option value="tls">Implicit TLS (port 465)</option>
                  <option value="none">None (port 25)</option>
                </select>
              </div>
            </div>

            <p className="text-xs text-gray-600">
              Common providers: Gmail (smtp.gmail.com:587, use App Password), SendGrid (smtp.sendgrid.net:587, username: apikey),
              Microsoft 365 (smtp.office365.com:587), Amazon SES (email-smtp.region.amazonaws.com:587)
            </p>
          </>
        )}

        {msg && <p className={`text-xs ${msg.includes("Error") || msg.includes("Failed") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

        <div className="flex gap-2">
          <button onClick={handleSave} disabled={saving}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {saving ? "Saving..." : "Save Configuration"}
          </button>
          {enabled && host && (
            <>
              <button onClick={handleTest} disabled={testing}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
                {testing ? "Testing..." : "Test Connection"}
              </button>
              <button onClick={handleTestEmail} disabled={testing}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
                Send Test Email
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function BrandingConfig() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [tagline, setTagline] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#4f46e5");
  const [accentColor, setAccentColor] = useState("#f0f0fa");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [hasLogo, setHasLogo] = useState(false);

  useEffect(() => {
    api("/api/v1/tenant/settings")
      .then(d => {
        const b = d.branding || {};
        setCompanyName(b.company_name || "");
        setTagline(b.tagline || "");
        if (b.primary_color_r !== undefined) {
          const r = b.primary_color_r, g = b.primary_color_g, b2 = b.primary_color_b;
          setPrimaryColor(`#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${b2.toString(16).padStart(2,"0")}`);
        }
        if (b.accent_color_r !== undefined) {
          const r = b.accent_color_r, g = b.accent_color_g, b2 = b.accent_color_b;
          setAccentColor(`#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${b2.toString(16).padStart(2,"0")}`);
        }
        setHasLogo(!!b.logo_path);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function hexToRgb(hex: string) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return { r, g, b };
  }

  async function handleSave() {
    setSaving(true); setMsg("");
    try {
      const pc = hexToRgb(primaryColor);
      const ac = hexToRgb(accentColor);
      await api("/api/v1/tenant/settings", {
        method: "PATCH",
        body: JSON.stringify({
          branding: {
            company_name: companyName,
            tagline,
            primary_color_r: pc.r, primary_color_g: pc.g, primary_color_b: pc.b,
            accent_color_r: ac.r, accent_color_g: ac.g, accent_color_b: ac.b,
          },
        }),
      });
      setMsg("Branding saved");
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  async function handleLogoUpload() {
    if (!logoFile) return;
    setSaving(true); setMsg("");
    try {
      const formData = new FormData();
      formData.append("file", logoFile);
      const token = localStorage.getItem("getvul_token") || "";
      const API = process.env.NEXT_PUBLIC_API_URL || "";
      const resp = await fetch(`${API}/api/v1/tenant/branding/logo`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || "Upload failed");
      setHasLogo(true);
      setLogoFile(null);
      setMsg("Logo uploaded");
    } catch (e: any) { setMsg(`Error: ${e.message}`); } finally { setSaving(false); }
  }

  if (loading) return null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
      <h2 className="text-lg font-medium text-white mb-1">Report Branding</h2>
      <p className="text-xs text-gray-500 mb-4">Customize executive PDF reports with your logo, company name, and colors</p>

      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-gray-400">Company Name</label>
            <input value={companyName} onChange={e => setCompanyName(e.target.value)} placeholder="Your Organization"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Tagline</label>
            <input value={tagline} onChange={e => setTagline(e.target.value)} placeholder="Security Report"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Primary Color</label>
            <div className="flex items-center gap-2">
              <input type="color" value={primaryColor} onChange={e => setPrimaryColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-gray-700 bg-gray-800" />
              <input value={primaryColor} onChange={e => setPrimaryColor(e.target.value)}
                className="w-28 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white font-mono focus:border-indigo-500 focus:outline-none" />
              <span className="text-xs text-gray-500">Title & section headers</span>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Accent Color</label>
            <div className="flex items-center gap-2">
              <input type="color" value={accentColor} onChange={e => setAccentColor(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded border border-gray-700 bg-gray-800" />
              <input value={accentColor} onChange={e => setAccentColor(e.target.value)}
                className="w-28 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white font-mono focus:border-indigo-500 focus:outline-none" />
              <span className="text-xs text-gray-500">Section backgrounds</span>
            </div>
          </div>
        </div>

        {/* Logo upload */}
        <div>
          <label className="mb-1 block text-xs text-gray-400">Logo (PNG/JPG, max 500KB)</label>
          <div className="flex items-center gap-3">
            <input type="file" accept="image/png,image/jpeg" onChange={e => setLogoFile(e.target.files?.[0] || null)}
              className="text-sm text-gray-400 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-600/20 file:px-3 file:py-1.5 file:text-sm file:text-indigo-400 hover:file:bg-indigo-600/30" />
            {logoFile && (
              <button onClick={handleLogoUpload} disabled={saving}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">
                Upload
              </button>
            )}
            {hasLogo && <span className="text-xs text-emerald-400">Logo configured</span>}
          </div>
        </div>

        {/* Preview bar */}
        <div className="rounded-lg border border-gray-700 p-4">
          <p className="text-xs text-gray-500 mb-2">Preview</p>
          <div className="rounded" style={{ borderTop: `3px solid ${primaryColor}` }}>
            <div className="p-3">
              <p className="text-sm font-bold" style={{ color: primaryColor }}>{companyName || "Company"} — Executive Summary</p>
              <p className="text-xs text-gray-500">{tagline ? `${tagline}  |  ` : ""}Generated: {new Date().toLocaleDateString()}</p>
            </div>
            <div className="rounded px-3 py-1.5 text-xs font-medium" style={{ backgroundColor: accentColor, color: primaryColor }}>
              Section Title
            </div>
          </div>
        </div>

        {msg && <p className={`text-xs ${msg.includes("Error") ? "text-red-400" : "text-emerald-400"}`}>{msg}</p>}

        <button onClick={handleSave} disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          {saving ? "Saving..." : "Save Branding"}
        </button>
      </div>
    </div>
  );
}

function OrgField({ label, field, value, editable, mono, onSave }: {
  label: string; field: string; value: string; editable: boolean; mono?: boolean;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  return (
    <div>
      <span className="text-gray-500">{label}</span>
      {editable && editing ? (
        <input value={draft} onChange={e => setDraft(e.target.value)} autoFocus
          onBlur={async () => { if (draft !== value) await onSave(draft); setEditing(false); }}
          onKeyDown={async e => { if (e.key === "Enter") { if (draft !== value) await onSave(draft); setEditing(false); } if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
          className={`mt-1 w-full rounded-lg border border-indigo-500 bg-gray-800 px-3 py-2 text-sm text-white focus:outline-none ${mono ? "font-mono" : ""}`} />
      ) : (
        <p className={`mt-1 ${mono ? "font-mono" : ""} ${editable ? "text-white cursor-pointer hover:text-indigo-400" : "text-white"}`}
          onClick={() => editable && setEditing(true)}>
          {value || <span className="text-gray-600">Not set</span>}
          {editable && <span className="ml-2 text-xs text-gray-600">click to edit</span>}
        </p>
      )}
    </div>
  );
}

function EditableField({ value, placeholder, onSave, editable, className }: {
  value: string; placeholder: string; onSave: (v: string) => Promise<void>; editable: boolean; className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (!editable || !editing) {
    return (
      <span className={`${className} ${editable ? "cursor-pointer hover:text-indigo-400" : ""}`}
        onClick={() => editable && setEditing(true)}
        title={editable ? "Click to edit" : undefined}>
        {value || <span className="text-gray-600">{placeholder}</span>}
      </span>
    );
  }

  return (
    <input value={draft} onChange={e => setDraft(e.target.value)} autoFocus
      onBlur={async () => { if (draft !== value) await onSave(draft); setEditing(false); }}
      onKeyDown={async e => { if (e.key === "Enter") { if (draft !== value) await onSave(draft); setEditing(false); } if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
      className="rounded border border-indigo-500 bg-gray-900 px-2 py-0.5 text-sm text-white focus:outline-none w-full" />
  );
}

function AddUserButton({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"manual" | "import">("import");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Humaans people for import
  const [people, setPeople] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [loadingPeople, setLoadingPeople] = useState(false);

  useEffect(() => {
    if (open && mode === "import") {
      setLoadingPeople(true);
      const API = process.env.NEXT_PUBLIC_API_URL || "";
      const token = localStorage.getItem("getvul_token") || "dev-token";
      fetch(`${API}/api/v1/tickets/assignees`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then(d => { setPeople(Array.isArray(d) ? d : []); })
        .catch(() => { setPeople([]); })
        .finally(() => setLoadingPeople(false));
    }
  }, [open, mode]);

  const filtered = search
    ? people.filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || p.email.toLowerCase().includes(search.toLowerCase())).slice(0, 10)
    : people.slice(0, 10);

  async function handleCreate() {
    if (!email) return;
    setSaving(true); setError("");
    try {
      // Create or update user via admin endpoint
      await api("/api/v1/tenant/users", {
        method: "POST",
        body: JSON.stringify({
          email,
          display_name: name || email.split("@")[0],
          password: password || undefined,
          role,
        }),
      });
      setOpen(false); setEmail(""); setName(""); setPassword(""); setSearch("");
      onAdded();
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)}
      className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
      + Add User
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-bold text-white mb-4">Add User</h2>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-4">
          <button onClick={() => setMode("import")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${mode === "import" ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>
            From HR Directory
          </button>
          <button onClick={() => setMode("manual")}
            className={`rounded-md border px-3 py-1.5 text-xs font-medium ${mode === "manual" ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>
            Manual
          </button>
        </div>

        {mode === "import" ? (
          <div className="space-y-3">
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search by name or email..."
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
            {loadingPeople ? <p className="text-sm text-gray-500 py-4 text-center">Loading...</p> : (
              <div className="max-h-60 overflow-y-auto rounded-lg border border-gray-700">
                {filtered.map(p => (
                  <button key={p.email} onClick={() => { setEmail(p.email); setName(p.name); setMode("manual"); }}
                    className={`w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-gray-800 border-b border-gray-800 last:border-0 ${email === p.email ? "bg-indigo-500/10" : ""}`}>
                    <div>
                      <p className="text-sm text-white">{p.name}</p>
                      <p className="text-xs text-gray-500">{p.email}</p>
                    </div>
                    <span className="text-xs text-gray-600">Select</span>
                  </button>
                ))}
                {filtered.length === 0 && <p className="p-3 text-xs text-gray-500 text-center">No people found</p>}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">Email <span className="text-red-400">*</span></label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="user@company.com"
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">Display Name</label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="John Doe"
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">Password</label>
              <input type="text" value={password} onChange={e => setPassword(e.target.value)} placeholder="Leave empty for auto-generated"
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              <p className="mt-1 text-xs text-gray-600">Min 8 chars. User can change after first login.</p>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-300">Role</label>
              <select value={role} onChange={e => setRole(e.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none">
                <option value="VIEWER">Viewer</option>
                <option value="ANALYST">Analyst</option>
                <option value="ADMIN">Admin</option>
                <option value="OWNER">Owner</option>
              </select>
            </div>
          </div>
        )}

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={() => { setOpen(false); setError(""); }} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
          {mode === "manual" && (
            <button onClick={handleCreate} disabled={saving || !email}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {saving ? "Creating..." : "Add User"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

