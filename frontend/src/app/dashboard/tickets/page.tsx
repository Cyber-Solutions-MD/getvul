"use client";

import { useEffect, useState, useCallback } from "react";
import ExportButton from "@/components/ui/ExportButton";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { getAuthHeaders, API_BASE } from "@/lib/fetch";
const headers = getAuthHeaders();

const SEV_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-green-500/20 text-green-400 border-green-500/30",
};

export default function TicketsPage() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [asanaConfig, setAsanaConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [showSetup, setShowSetup] = useState(false);
  const [showCreateFlow, setShowCreateFlow] = useState(false);
  const [tab, setTab] = useState<"tickets" | "rules">("tickets");
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [showCommentModal, setShowCommentModal] = useState(false);
  const [bulkLoading, setBulkLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ticketsResp, statsResp, configResp] = await Promise.all([
        fetch(`${API}/api/v1/tickets?page=${page}&page_size=25${statusFilter ? `&status=${statusFilter}` : ""}`, { headers }),
        fetch(`${API}/api/v1/tickets/stats`, { headers }),
        fetch(`${API}/api/v1/tickets/asana/config`, { headers }),  // fast DB-only check
      ]);
      if (ticketsResp.ok) {
        const d = await ticketsResp.json();
        setTickets(d.items || []);
        setTotal(d.total || 0);
        setPages(d.pages || 0);
      }
      if (statsResp.ok) setStats(await statsResp.json());
      if (configResp.ok) setAsanaConfig(await configResp.json());
    } catch (e) {
      console.error("Failed to load tickets:", e);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load]);

  async function handleSyncStatus() {
    setSyncing(true);
    try {
      await fetch(`${API}/api/v1/tickets/sync-status`, { method: "POST", headers });
      await load();
    } catch {} finally { setSyncing(false); }
  }

  const isConfigured = asanaConfig?.workspace_gid && asanaConfig?.project_gid;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Tickets</h1>
          <p className="mt-1 text-sm text-gray-400">Track vulnerability remediation tickets in Asana</p>
        </div>
        <div className="flex items-center gap-3">
          {isConfigured && (
            <button onClick={handleSyncStatus} disabled={syncing}
              className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
              {syncing ? "Syncing..." : "Sync Status from Asana"}
            </button>
          )}
          {isConfigured && (
            <button onClick={() => setShowCreateFlow(!showCreateFlow)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
              {showCreateFlow ? "Close" : "+ New Ticket"}
            </button>
          )}
          <ExportButton resource="tickets" />
          <button onClick={() => setShowSetup(true)}
            className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
            {isConfigured ? "Asana Settings" : "Configure Asana"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      {isConfigured && (
        <div className="flex gap-4 border-b border-gray-700">
          <button onClick={() => setTab("tickets")}
            className={`pb-2 text-sm font-medium transition ${tab === "tickets" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
            Tickets {stats?.total ? `(${stats.total})` : ""}
          </button>
          <button onClick={() => setTab("rules")}
            className={`pb-2 text-sm font-medium transition ${tab === "rules" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
            Automation Rules
          </button>
        </div>
      )}

      {/* Rules tab */}
      {tab === "rules" && isConfigured && <RulesPanel />}

      {/* Tickets tab content below */}
      {tab === "tickets" && <>

      {/* Setup prompt if not configured */}
      {!isConfigured && !loading && (
        <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-6 text-center">
          <p className="text-orange-400 font-medium">Asana not configured</p>
          <p className="mt-2 text-sm text-gray-400">Add an Asana connector in the Connectors page, then select a workspace and project here.</p>
          <button onClick={() => setShowSetup(true)}
            className="mt-4 rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-500">
            Configure Asana
          </button>
        </div>
      )}

      {/* Stats */}
      {stats && stats.total > 0 && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Total Tickets" value={stats.total} />
          <StatCard label="Open" value={stats.open} accent="orange" />
          <StatCard label="Resolved" value={stats.resolved} accent="emerald" />
          <StatCard label="Providers" value={Object.keys(stats.by_provider || {}).join(", ") || "—"} text />
        </div>
      )}

      {/* Host ticket creation flow */}
      {showCreateFlow && isConfigured && (
        <HostTicketFlow onCreated={() => { setShowCreateFlow(false); load(); }} />
      )}

      {/* Filters */}
      {stats && stats.total > 0 && (
        <div className="flex items-center gap-3">
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
            <option value="">All Tickets</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
          </select>
          <span className="ml-auto text-sm text-gray-500">{total} tickets</span>
        </div>
      )}

      {/* Bulk actions bar */}
      {selectedUrls.size > 0 && (
        <TicketBulkActions
          selectedCount={selectedUrls.size}
          loading={bulkLoading}
          onAction={async (action) => {
            if (action === "comment") { setShowCommentModal(true); return; }
            if (action === "close" && !confirm(`Close ${selectedUrls.size} ticket(s)? Asana tasks will be completed.`)) return;
            if (action === "delete" && !confirm(`Delete ${selectedUrls.size} ticket(s)? This removes them from GetVul (Asana tasks remain).`)) return;
            setBulkLoading(true);
            try {
              await fetch(`${API}/api/v1/tickets/bulk-action`, {
                method: "POST", headers,
                body: JSON.stringify({ ticket_urls: Array.from(selectedUrls), action }),
              });
              setSelectedUrls(new Set());
              load();
            } catch {} finally { setBulkLoading(false); }
          }}
        />
      )}

      {/* Comment modal */}
      {showCommentModal && (
        <CommentModal
          onClose={() => setShowCommentModal(false)}
          onSubmit={async (text) => {
            setBulkLoading(true);
            try {
              await fetch(`${API}/api/v1/tickets/bulk-action`, {
                method: "POST", headers,
                body: JSON.stringify({ ticket_urls: Array.from(selectedUrls), action: "comment", comment: text }),
              });
              setSelectedUrls(new Set());
              setShowCommentModal(false);
            } catch {} finally { setBulkLoading(false); }
          }}
        />
      )}

      {/* Ticket table */}
      {tickets.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr>
                <th className="px-3 py-3 w-8">
                  <input type="checkbox"
                    checked={tickets.length > 0 && selectedUrls.size === tickets.length}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedUrls(new Set(tickets.map((t: any) => t.external_ticket_url)));
                      else setSelectedUrls(new Set());
                    }}
                    className="rounded border-gray-600" />
                </th>
                <th className="px-4 py-3">Ticket</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3 text-center">Vulns</th>
                <th className="px-4 py-3 text-center">Crit / High</th>
                <th className="px-4 py-3">Assignee</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Link</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {tickets.map((t: any) => (
                <tr key={t.id} className={`hover:bg-gray-800 ${selectedUrls.has(t.external_ticket_url) ? "bg-indigo-500/5" : "bg-gray-900"}`}>
                  <td className="px-3 py-3">
                    <input type="checkbox"
                      checked={selectedUrls.has(t.external_ticket_url)}
                      onChange={(e) => {
                        const next = new Set(selectedUrls);
                        if (e.target.checked) next.add(t.external_ticket_url);
                        else next.delete(t.external_ticket_url);
                        setSelectedUrls(next);
                      }}
                      className="rounded border-gray-600" />
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-white font-medium truncate max-w-[300px]">{t.title || t.hostname || "—"}</p>
                    {t.subtitle && <p className="text-xs text-gray-500">{t.subtitle}</p>}
                  </td>
                  <td className="px-4 py-3">
                    {t.max_severity && (
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_COLORS[t.max_severity] || ""}`}>
                        {t.max_severity}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-gray-300">{t.vuln_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-red-400">{t.critical_count}</span>
                    <span className="text-gray-600"> / </span>
                    <span className="text-orange-400">{t.high_count}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{t.assignee || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${
                      t.external_status === "completed" ? "bg-emerald-500/20 text-emerald-400" :
                      "bg-orange-500/20 text-orange-400"
                    }`}>
                      {t.external_status || "open"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {t.ticket_created_at ? new Date(t.ticket_created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <a href={t.external_ticket_url} target="_blank" rel="noopener noreferrer"
                      className="text-indigo-400 hover:underline text-xs">
                      Open in Asana →
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && tickets.length === 0 && isConfigured && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-12 text-center">
          <p className="text-gray-400">No tickets yet</p>
          <p className="mt-2 text-sm text-gray-500">Create tickets from the Vulnerabilities page by selecting vulns and clicking "Create Ticket"</p>
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40">
            Previous
          </button>
          <span className="text-sm text-gray-500">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40">
            Next
          </button>
        </div>
      )}

      </>}

      {/* Asana setup modal */}
      {showSetup && asanaConfig && (
        <AsanaSetupModal config={asanaConfig} onClose={() => setShowSetup(false)} onSaved={() => { setShowSetup(false); load(); }} />
      )}
    </div>
  );
}

function AsanaSetupModal({ config, onClose, onSaved }: { config: any; onClose: () => void; onSaved: () => void }) {
  const [workspaceGid, setWorkspaceGid] = useState(config.workspace_gid || "");
  const [projectGid, setProjectGid] = useState(config.project_gid || "");
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [loadingSetup, setLoadingSetup] = useState(true);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [saving, setSaving] = useState(false);

  // Fetch full setup data (workspaces + projects) from Asana API when modal opens
  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API}/api/v1/tickets/asana/setup`, { headers });
        if (resp.ok) {
          const data = await resp.json();
          setWorkspaces(data.workspaces || []);
          setProjects(data.projects || []);
          if (data.workspace_gid) setWorkspaceGid(data.workspace_gid);
          if (data.project_gid) setProjectGid(data.project_gid);
        }
      } catch {} finally { setLoadingSetup(false); }
    })();
  }, []);

  async function handleWorkspaceChange(gid: string) {
    setWorkspaceGid(gid);
    setProjectGid("");
    setLoadingProjects(true);
    try {
      await fetch(`${API}/api/v1/tickets/asana/config`, {
        method: "PATCH", headers, body: JSON.stringify({ workspace_gid: gid }),
      });
      const resp = await fetch(`${API}/api/v1/tickets/asana/setup`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setProjects(data.projects || []);
      }
    } catch {} finally { setLoadingProjects(false); }
  }

  async function handleSave() {
    setSaving(true);
    try {
      await fetch(`${API}/api/v1/tickets/asana/config`, {
        method: "PATCH", headers,
        body: JSON.stringify({ workspace_gid: workspaceGid, project_gid: projectGid }),
      });
      onSaved();
    } catch {} finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-xl border border-gray-800 bg-gray-950 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Asana Configuration</h2>
        {loadingSetup ? (
          <p className="text-sm text-gray-500 py-8 text-center">Loading from Asana...</p>
        ) : (
          <>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">Workspace</label>
                <select value={workspaceGid} onChange={e => handleWorkspaceChange(e.target.value)}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none">
                  <option value="">Select workspace...</option>
                  {workspaces.map((w: any) => (
                    <option key={w.gid} value={w.gid}>{w.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-300">Default Project</label>
                {loadingProjects ? (
                  <p className="text-sm text-gray-500">Loading projects...</p>
                ) : (
                  <select value={projectGid} onChange={e => setProjectGid(e.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white focus:border-indigo-500 focus:outline-none"
                    disabled={!workspaceGid}>
                    <option value="">Select project...</option>
                    {projects.map((p: any) => (
                      <option key={p.gid} value={p.gid}>{p.name}</option>
                    ))}
                  </select>
                )}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
              <button onClick={handleSave} disabled={saving || !workspaceGid || !projectGid}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function HostTicketFlow({ onCreated }: { onCreated: () => void }) {
  const [hosts, setHosts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [minRisk, setMinRisk] = useState(50);
  const [creating, setCreating] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const resp = await fetch(
          `${API}/api/v1/assets?page_size=50&min_risk=${minRisk}&sort_by=risk_score&sort_dir=desc&device_category=WORKSTATION`,
          { headers }
        );
        if (resp.ok) {
          const data = await resp.json();
          setHosts(data.items || []);
        }
      } catch {} finally { setLoading(false); }
    })();
  }, [minRisk]);

  async function handleCreate(host: any) {
    setCreating(host.id);
    setResult(null);
    try {
      const resp = await fetch(`${API}/api/v1/tickets/host`, {
        method: "POST", headers,
        body: JSON.stringify({ asset_id: host.id, provider: "ASANA", project_key: "" }),
      });
      const data = await resp.json();
      if (resp.ok && data.task_url) {
        setResult(`Ticket created for ${host.hostname} — ${data.vulns_linked} vulns, assigned to ${data.assignee || "unassigned"}`);
        onCreated();
      } else {
        setResult(`Error: ${data.detail || data.error || "Failed"}`);
      }
    } catch (e: any) {
      setResult(`Error: ${e.message}`);
    } finally { setCreating(null); }
  }

  const riskColor = (s: number) => s >= 80 ? "text-red-400" : s >= 50 ? "text-orange-400" : s >= 20 ? "text-yellow-400" : "text-green-400";
  const riskBg = (s: number) => s >= 80 ? "bg-red-500/10 border-red-500/30" : s >= 50 ? "bg-orange-500/10 border-orange-500/30" : "bg-yellow-500/10 border-yellow-500/30";

  return (
    <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-white">Create Host Remediation Ticket</h3>
          <p className="text-xs text-gray-400 mt-1">Select a host to create an Asana ticket with all its remediations and auto-assign to the responsible user</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Min risk:</span>
          {[20, 50, 80].map(r => (
            <button key={r} onClick={() => setMinRisk(r)}
              className={`rounded px-2 py-1 text-xs font-medium ${minRisk === r ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
              {r}+
            </button>
          ))}
        </div>
      </div>

      {result && (
        <div className={`rounded-lg px-4 py-2 text-sm ${result.startsWith("Error") ? "bg-red-500/10 text-red-400" : "bg-emerald-500/10 text-emerald-400"}`}>
          {result}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500 py-4 text-center">Loading hosts...</p>
      ) : hosts.length === 0 ? (
        <p className="text-sm text-gray-500 py-4 text-center">No hosts with risk score {minRisk}+</p>
      ) : (
        <div className="max-h-80 overflow-y-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400 sticky top-0">
              <tr>
                <th className="px-3 py-2">Host</th>
                <th className="px-3 py-2">User</th>
                <th className="px-3 py-2 text-center">Risk</th>
                <th className="px-3 py-2 text-center">Vulns</th>
                <th className="px-3 py-2 text-center">Crit</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {hosts.map((h: any) => (
                <tr key={h.id} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-3 py-2">
                    <p className="text-white text-xs font-medium truncate max-w-[200px]">{h.hostname}</p>
                    <p className="text-gray-600 text-xs">{h.os_name} {h.os_version}</p>
                  </td>
                  <td className="px-3 py-2 text-gray-400 text-xs truncate max-w-[150px]">{h.assigned_user || "—"}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`inline-block w-8 rounded border px-1 py-0.5 text-center text-xs font-bold ${riskBg(h.risk_score)} ${riskColor(h.risk_score)}`}>
                      {h.risk_score}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center text-gray-300 text-xs">{h.total_vulns}</td>
                  <td className="px-3 py-2 text-center text-red-400 text-xs">{h.critical}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => handleCreate(h)}
                      disabled={creating === h.id}
                      className="rounded bg-orange-600 px-3 py-1 text-xs font-medium text-white hover:bg-orange-500 disabled:opacity-50 whitespace-nowrap"
                    >
                      {creating === h.id ? "Creating..." : "Create Ticket"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RulesPanel() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingRule, setEditingRule] = useState<any>(null);

  const loadRules = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/api/v1/tickets/rules`, { headers });
      if (resp.ok) setRules(await resp.json());
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadRules(); }, [loadRules]);

  async function handleToggle(rule: any) {
    await fetch(`${API}/api/v1/tickets/rules/${rule.id}`, {
      method: "PATCH", headers, body: JSON.stringify({ is_enabled: !rule.is_enabled }),
    });
    loadRules();
  }

  async function handleDelete(rule: any) {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    await fetch(`${API}/api/v1/tickets/rules/${rule.id}`, { method: "DELETE", headers });
    loadRules();
  }

  async function handleRun(rule: any) {
    const resp = await fetch(`${API}/api/v1/tickets/rules/${rule.id}/run`, { method: "POST", headers });
    const result = await resp.json();
    alert(`Rule executed: ${result.matched} hosts matched, ${result.created} tickets created, ${result.skipped} skipped`);
    loadRules();
  }

  const scheduleLabel = (m: number) => {
    if (m < 60) return `${m} min`;
    if (m < 1440) return `${Math.round(m / 60)}h`;
    return `${Math.round(m / 1440)}d`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">Rules run on a schedule to create tickets. Set filters in Vulnerabilities → Save Filter → Create Rule (→R)</p>
        <button onClick={() => setShowCreate(true)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          + New Rule
        </button>
      </div>

      {loading ? <p className="text-gray-500 text-sm py-8 text-center">Loading...</p> :
       rules.length === 0 ? <p className="text-gray-500 text-sm py-8 text-center">No automation rules yet</p> : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div key={rule.id} className={`rounded-xl border p-4 ${rule.is_enabled ? "border-gray-700 bg-gray-900/50" : "border-gray-800 bg-gray-950 opacity-60"}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium text-white">{rule.name}</h3>
                    <span className={`rounded-full px-2 py-0.5 text-xs ${rule.is_enabled ? "bg-emerald-500/20 text-emerald-400" : "bg-gray-700 text-gray-400"}`}>
                      {rule.is_enabled ? "Active" : "Disabled"}
                    </span>
                    <span className="text-xs text-gray-500">every {scheduleLabel(rule.schedule_minutes)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {rule.conditions.device_category?.map((c: string) => (
                      <span key={c} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300">{c}</span>
                    ))}
                    {rule.conditions.min_risk_score && <span className="rounded bg-orange-500/20 px-2 py-0.5 text-xs text-orange-400">Risk {rule.conditions.min_risk_score}+</span>}
                    {rule.conditions.severity?.map((s: string) => (
                      <span key={s} className={`rounded px-2 py-0.5 text-xs ${SEV_COLORS[s] || "bg-gray-800 text-gray-300"}`}>{s}</span>
                    ))}
                    {rule.conditions.exploit_available && <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">Exploitable</span>}
                    {rule.conditions.cisa_kev && <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-400">CISA KEV</span>}
                    {rule.conditions.min_critical_vulns > 0 && <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-400">{rule.conditions.min_critical_vulns}+ critical</span>}
                    <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-400">{rule.action?.ticket_mode === "per_remediation" ? "per remediation" : "per host"}</span>
                    <span className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-400">max {rule.action?.max_tickets || 10}</span>
                  </div>
                  {rule.last_run_at && (
                    <p className="mt-1 text-xs text-gray-600">
                      Last run: {new Date(rule.last_run_at).toLocaleString()} — {rule.last_run_status} ({rule.last_run_tickets_created ?? 0} tickets)
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => handleRun(rule)} className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:text-white">Run Now</button>
                  <button onClick={() => setEditingRule(rule)} className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:text-white">Edit</button>
                  <button onClick={() => handleToggle(rule)} className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:text-white">
                    {rule.is_enabled ? "Disable" : "Enable"}
                  </button>
                  <button onClick={() => handleDelete(rule)} className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-500 hover:text-red-400">Delete</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && <CreateRuleModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); loadRules(); }} />}
      {editingRule && <EditRuleModal rule={editingRule} onClose={() => setEditingRule(null)} onSaved={() => { setEditingRule(null); loadRules(); }} />}
    </div>
  );
}

function CreateRuleModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [savedFilters, setSavedFilters] = useState<any[]>([]);
  const [selectedFilterId, setSelectedFilterId] = useState("");
  const [scheduleMinutes, setScheduleMinutes] = useState(1440);
  const [ticketMode, setTicketMode] = useState("per_host");
  const [maxTickets, setMaxTickets] = useState(10);
  const [autoAssign, setAutoAssign] = useState(true);
  const [assigneeEmail, setAssigneeEmail] = useState("");
  const [assignees, setAssignees] = useState<{name: string; email: string}[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/v1/tickets/assignees`, { headers })
      .then(r => r.json()).then(setAssignees).catch(() => {});
    fetch(`${API}/api/v1/vulnerabilities/saved-filters`, { headers })
      .then(r => r.json()).then(d => setSavedFilters(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const selectedFilter = (savedFilters || []).find(f => f.id === selectedFilterId);

  async function handleSave() {
    if (!name.trim() || !selectedFilterId) return;
    // Build conditions from the saved filter
    const f = selectedFilter?.filters || {};
    const conditions: any = {};
    if (f.severity?.length) conditions.severity = f.severity;
    if (f.source?.length) conditions.source = f.source;
    if (f.exploit_available) conditions.exploit_available = true;
    if (f.cisa_kev) conditions.cisa_kev = true;
    if (f.device_category) conditions.device_category = Array.isArray(f.device_category) ? f.device_category : [f.device_category];
    if (f.min_risk_score) conditions.min_risk_score = f.min_risk_score;
    if (f.search) conditions.search = f.search;

    setSaving(true);
    try {
      await fetch(`${API}/api/v1/tickets/rules`, {
        method: "POST", headers,
        body: JSON.stringify({
          name,
          saved_filter_id: selectedFilterId,
          conditions,
          action: {
            provider: "ASANA", auto_assign: autoAssign, ticket_mode: ticketMode, max_tickets: maxTickets,
            ...(ticketMode === "per_remediation" && assigneeEmail ? { assignee_email: assigneeEmail } : {}),
          },
          schedule_minutes: scheduleMinutes,
        }),
      });
      onCreated();
    } catch {} finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-bold text-white mb-4">Create Automation Rule</h2>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Rule Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g., Daily critical workstation tickets"
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
          </div>

          <SavedFilterPicker
            filters={savedFilters}
            selectedId={selectedFilterId}
            onSelect={(sf) => { setSelectedFilterId(sf.id); if (!name) setName(sf.name); }}
          />

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Run Every</label>
            <div className="flex items-center gap-3">
              {[{l: "1h", v: 60}, {l: "6h", v: 360}, {l: "12h", v: 720}, {l: "1 day", v: 1440}, {l: "7 days", v: 10080}].map(s => (
                <button key={s.v} onClick={() => setScheduleMinutes(s.v)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${scheduleMinutes === s.v ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>
                  {s.l}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Max Tickets Per Run</label>
            <div className="flex items-center gap-3">
              {[5, 10, 25, 50, 100].map(n => (
                <button key={n} onClick={() => setMaxTickets(n)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${maxTickets === n ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>
                  {n}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Ticket Grouping</label>
            <div className="flex gap-3">
              <button onClick={() => setTicketMode("per_host")}
                className={`flex-1 rounded-lg border p-3 text-left text-xs ${ticketMode === "per_host" ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-900"}`}>
                <p className="font-medium text-white">Per Host</p>
                <p className="mt-1 text-gray-400">One ticket per host with all its remediations</p>
              </button>
              <button onClick={() => setTicketMode("per_remediation")}
                className={`flex-1 rounded-lg border p-3 text-left text-xs ${ticketMode === "per_remediation" ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-900"}`}>
                <p className="font-medium text-white">Per Remediation</p>
                <p className="mt-1 text-gray-400">One ticket per remediation action with affected hosts</p>
              </button>
            </div>
          </div>

          {ticketMode === "per_host" ? (
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" checked={autoAssign} onChange={e => setAutoAssign(e.target.checked)}
                className="rounded border-gray-600" />
              Auto-assign to host user (from Humaans)
            </label>
          ) : (
            <AssigneePicker assignees={assignees} value={assigneeEmail} onChange={setAssigneeEmail} />
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
          <button onClick={handleSave} disabled={saving || !name.trim() || !selectedFilterId}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {saving ? "Creating..." : "Create Rule"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditRuleModal({ rule, onClose, onSaved }: { rule: any; onClose: () => void; onSaved: () => void }) {
  const a = rule.action || {};
  const [name, setName] = useState(rule.name);
  const [savedFilters, setSavedFilters] = useState<any[]>([]);
  const [selectedFilterId, setSelectedFilterId] = useState(rule.saved_filter_id || "");
  const [scheduleMinutes, setScheduleMinutes] = useState(rule.schedule_minutes || 1440);
  const [ticketMode, setTicketMode] = useState(a.ticket_mode || "per_host");
  const [maxTickets, setMaxTickets] = useState(a.max_tickets || 10);
  const [autoAssign, setAutoAssign] = useState(a.auto_assign !== false);
  const [assigneeEmail, setAssigneeEmail] = useState(a.assignee_email || "");
  const [assignees, setAssignees] = useState<{name: string; email: string}[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/v1/tickets/assignees`, { headers })
      .then(r => r.json()).then(setAssignees).catch(() => {});
    fetch(`${API}/api/v1/vulnerabilities/saved-filters`, { headers })
      .then(r => r.json()).then(d => setSavedFilters(Array.isArray(d) ? d : [])).catch(() => {});
  }, []);

  const selectedFilter = (savedFilters || []).find(f => f.id === selectedFilterId);

  async function handleSave() {
    setSaving(true);
    // Build conditions from selected filter
    const f = selectedFilter?.filters || {};
    const conditions: any = {};
    if (f.severity?.length) conditions.severity = f.severity;
    if (f.source?.length) conditions.source = f.source;
    if (f.exploit_available) conditions.exploit_available = true;
    if (f.cisa_kev) conditions.cisa_kev = true;
    if (f.device_category) conditions.device_category = Array.isArray(f.device_category) ? f.device_category : [f.device_category];
    if (f.min_risk_score) conditions.min_risk_score = f.min_risk_score;
    if (f.search) conditions.search = f.search;

    try {
      await fetch(`${API}/api/v1/tickets/rules/${rule.id}`, {
        method: "PATCH", headers,
        body: JSON.stringify({
          name,
          conditions,
          action: {
            provider: "ASANA", auto_assign: autoAssign, ticket_mode: ticketMode, max_tickets: maxTickets,
            ...(ticketMode === "per_remediation" && assigneeEmail ? { assignee_email: assigneeEmail } : {}),
          },
          schedule_minutes: scheduleMinutes,
        }),
      });
      onSaved();
    } catch {} finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm py-8">
      <div className="mx-4 w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-bold text-white mb-4">Edit Rule</h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Rule Name</label>
            <input value={name} onChange={e => setName(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none" />
          </div>
          <SavedFilterPicker
            filters={savedFilters}
            selectedId={selectedFilterId}
            onSelect={(sf) => setSelectedFilterId(sf.id)}
          />
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Run Every</label>
            <div className="flex items-center gap-3">
              {[{l: "1h", v: 60}, {l: "6h", v: 360}, {l: "12h", v: 720}, {l: "1 day", v: 1440}, {l: "7 days", v: 10080}].map(s => (
                <button key={s.v} onClick={() => setScheduleMinutes(s.v)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${scheduleMinutes === s.v ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>{s.l}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Max Tickets Per Run</label>
            <div className="flex items-center gap-3">
              {[5, 10, 25, 50, 100].map(n => (
                <button key={n} onClick={() => setMaxTickets(n)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${maxTickets === n ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-400"}`}>
                  {n}
                </button>
              ))}
              <input type="number" min={1} max={500} value={maxTickets} onChange={e => setMaxTickets(Number(e.target.value))}
                className="w-16 rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-white text-center focus:border-indigo-500 focus:outline-none" />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Ticket Grouping</label>
            <div className="flex gap-3">
              <button onClick={() => setTicketMode("per_host")}
                className={`flex-1 rounded-lg border p-3 text-left text-xs ${ticketMode === "per_host" ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-900"}`}>
                <p className="font-medium text-white">Per Host</p>
                <p className="mt-1 text-gray-400">One ticket per host with all its remediations</p>
              </button>
              <button onClick={() => setTicketMode("per_remediation")}
                className={`flex-1 rounded-lg border p-3 text-left text-xs ${ticketMode === "per_remediation" ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-900"}`}>
                <p className="font-medium text-white">Per Remediation</p>
                <p className="mt-1 text-gray-400">One ticket per remediation action with affected hosts</p>
              </button>
            </div>
          </div>
          {ticketMode === "per_host" ? (
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" checked={autoAssign} onChange={e => setAutoAssign(e.target.checked)} className="rounded border-gray-600" />Auto-assign to host user
            </label>
          ) : (
            <AssigneePicker assignees={assignees} value={assigneeEmail} onChange={setAssigneeEmail} />
          )}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
          <button onClick={handleSave} disabled={saving || !name.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SavedFilterPicker({ filters, selectedId, onSelect }: {
  filters: any[];
  selectedId: string;
  onSelect: (sf: any) => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const selected = (filters || []).find(f => f.id === selectedId);

  const visible = search.length > 0
    ? (filters || []).filter(f => f.name.toLowerCase().includes(search.toLowerCase())).slice(0, 8)
    : (filters || []).slice(0, 5);

  if ((filters || []).length === 0) {
    return (
      <div>
        <label className="mb-1.5 block text-sm font-medium text-gray-300">Saved Filter <span className="text-red-400">*</span></label>
        <p className="text-xs text-gray-500 rounded-lg border border-gray-700 bg-gray-900 p-3">
          No saved filters. Go to Vulnerabilities → set filters → "+ Save current filter"
        </p>
      </div>
    );
  }

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-gray-300">Saved Filter <span className="text-red-400">*</span></label>
      <div className="relative">
        {selected ? (
          <div className="flex items-center justify-between rounded-lg border border-indigo-500 bg-indigo-500/10 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium text-indigo-400">{selected.name}</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {selected.filters.severity?.map((s: string) => <span key={s} className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400">{s}</span>)}
                {selected.filters.exploit_available && <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400">Exploitable</span>}
                {selected.filters.cisa_kev && <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">KEV</span>}
              </div>
            </div>
            <button onClick={() => { onSelect({ id: "" }); setSearch(""); }} className="text-xs text-gray-500 hover:text-red-400 ml-2">Change</button>
          </div>
        ) : (
          <>
            <input
              type="text" value={search}
              onChange={e => { setSearch(e.target.value); setOpen(true); }}
              onFocus={() => setOpen(true)}
              placeholder="Search saved filters..."
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
            />
            {open && (
              <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 shadow-lg max-h-60 overflow-y-auto">
                {visible.length === 0 ? (
                  <p className="p-3 text-xs text-gray-500 text-center">No filters found</p>
                ) : visible.map(sf => (
                  <button key={sf.id}
                    onClick={() => { onSelect(sf); setSearch(""); setOpen(false); }}
                    className="w-full px-3 py-2.5 text-left hover:bg-gray-800 border-b border-gray-800 last:border-0">
                    <p className="text-sm text-white font-medium">{sf.name}</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {sf.filters.severity?.map((s: string) => <span key={s} className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400">{s}</span>)}
                      {sf.filters.exploit_available && <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400">Exploitable</span>}
                      {sf.filters.cisa_kev && <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400">KEV</span>}
                      {sf.filters.source?.map((s: string) => <span key={s} className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400">{s}</span>)}
                      {sf.filters.search && <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-400">"{sf.filters.search}"</span>}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function AssigneePicker({ assignees, value, onChange }: {
  assignees: { name: string; email: string }[];
  value: string;
  onChange: (email: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = search.length > 0
    ? assignees.filter(u =>
        u.name.toLowerCase().includes(search.toLowerCase()) ||
        u.email.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 8)
    : [];

  const selected = assignees.find(u => u.email === value);

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-gray-300">Assign To</label>
      <div className="relative">
        {value && selected ? (
          <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5">
            <span className="text-sm text-white">{selected.name} <span className="text-gray-500">({selected.email})</span></span>
            <button onClick={() => { onChange(""); setSearch(""); }} className="text-xs text-gray-500 hover:text-red-400 ml-2">Clear</button>
          </div>
        ) : (
          <input
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder="Type to search users..."
            className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
          />
        )}
        {open && filtered.length > 0 && !value && (
          <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 shadow-lg max-h-48 overflow-y-auto">
            {filtered.map(u => (
              <button
                key={u.email}
                onClick={() => { onChange(u.email); setSearch(""); setOpen(false); }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-800 flex justify-between"
              >
                <span className="text-white">{u.name}</span>
                <span className="text-gray-500 text-xs">{u.email}</span>
              </button>
            ))}
          </div>
        )}
        {open && search.length > 0 && filtered.length === 0 && !value && (
          <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-700 bg-gray-900 p-3 text-center text-xs text-gray-500">
            No users found
          </div>
        )}
      </div>
    </div>
  );
}

function TicketBulkActions({ selectedCount, loading, onAction }: {
  selectedCount: number; loading: boolean; onAction: (action: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5">
      <span className="text-sm font-medium text-indigo-400">{selectedCount} selected</span>
      <div className="h-4 w-px bg-indigo-500/30" />
      <button onClick={() => onAction("close")} disabled={loading}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-gray-800 disabled:opacity-50">
        Close
      </button>
      <button onClick={() => onAction("comment")} disabled={loading}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-gray-800 disabled:opacity-50">
        Comment
      </button>
      <button onClick={() => onAction("sync-update")} disabled={loading}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-yellow-400 hover:bg-gray-800 disabled:opacity-50">
        Sync Update
      </button>
      <button onClick={() => onAction("delete")} disabled={loading}
        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-gray-800 disabled:opacity-50">
        Delete
      </button>
      {loading && <span className="text-xs text-gray-500">Processing...</span>}
    </div>
  );
}

function CommentModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-xl border border-gray-800 bg-gray-950 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Add Comment to Asana</h2>
        <textarea
          value={text} onChange={e => setText(e.target.value)}
          placeholder="Type your comment..."
          rows={4}
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none resize-none"
        />
        <div className="mt-4 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
          <button onClick={() => onSubmit(text)} disabled={!text.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            Post Comment
          </button>
        </div>
      </div>
    </div>
  );
}

function CloseTicketButton({ url, onDone }: { url: string; onDone: () => void }) {
  const [loading, setLoading] = useState(false);

  async function handleClose(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Close this ticket? The Asana task will be marked complete and all linked vulnerabilities will be marked as remediated.")) return;
    setLoading(true);
    try {
      await fetch(`${API}/api/v1/tickets/close`, {
        method: "POST", headers,
        body: JSON.stringify({ external_ticket_url: url }),
      });
      onDone();
    } catch {} finally { setLoading(false); }
  }

  return (
    <button onClick={handleClose} disabled={loading}
      className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-500 hover:text-emerald-400 hover:border-emerald-500/30 disabled:opacity-50">
      {loading ? "..." : "Close"}
    </button>
  );
}

function StatCard({ label, value, accent, text }: { label: string; value: number | string; accent?: string; text?: boolean }) {
  const colors: Record<string, string> = { orange: "text-orange-400", emerald: "text-emerald-400" };
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <p className="text-sm text-gray-400">{label}</p>
      <p className={`mt-2 ${text ? "text-sm" : "text-2xl font-bold"} ${accent ? colors[accent] || "text-white" : "text-white"}`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
}
