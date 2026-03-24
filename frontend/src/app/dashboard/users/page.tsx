"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import ExportButton from "@/components/ui/ExportButton";

const SOURCE_COLORS: Record<string, string> = {
  google: "bg-blue-500/20 text-blue-400",
  azure: "bg-blue-500/20 text-blue-400",
  okta: "bg-indigo-500/20 text-indigo-400",
  humaans: "bg-cyan-500/20 text-cyan-400",
  local: "bg-gray-500/20 text-gray-400",
};

export default function UsersPage() {
  const router = useRouter();
  const [stats, setStats] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [deptFilter, setDeptFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [sortBy, setSortBy] = useState("display_name");
  const [sortDir, setSortDir] = useState("asc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [tab, setTab] = useState<"directory" | "devices" | "groups">("directory");
  const pageSize = 25;

  const loadStats = useCallback(async () => {
    try { setStats(await api("/api/v1/users/stats")); } catch {}
  }, []);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({
        page: String(page), page_size: String(pageSize),
        status: statusFilter, sort_by: sortBy, sort_dir: sortDir,
      });
      if (search) p.set("search", search);
      if (deptFilter) p.set("department", deptFilter);
      if (sourceFilter) p.set("source", sourceFilter);
      const data = await api(`/api/v1/users/directory?${p}`);
      setUsers(data.items || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
    } catch {} finally { setLoading(false); }
  }, [page, search, statusFilter, deptFilter, sourceFilter, sortBy, sortDir]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadUsers(); }, [loadUsers]);

  const toggleSort = (col: string) => {
    if (sortBy === col) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortBy(col); setSortDir("asc"); }
    setPage(1);
  };

  const sortArrow = (col: string) => sortBy === col ? (sortDir === "asc" ? " ↑" : " ↓") : "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Users</h1>
        <ExportButton resource="users" />
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <StatCard label="Total Users" value={stats.total_users} />
          <StatCard label="Active" value={stats.active} accent="emerald" />
          <StatCard label="Suspended" value={stats.suspended} accent="orange" />
          <StatCard label="With Department" value={stats.has_department} accent="indigo" />
          <StatCard label="Assigned Devices" value={stats.assigned_assets} accent="blue" />
        </div>
      )}

      {/* Source breakdown */}
      {stats?.by_source && (
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-gray-500">Sources:</span>
          {Object.entries(stats.by_source as Record<string, number>).map(([src, count]) => (
            <button key={src} onClick={() => { setSourceFilter(sourceFilter === src ? "" : src); setPage(1); }}
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition ${
                sourceFilter === src ? "ring-1 ring-indigo-500" : ""
              } ${SOURCE_COLORS[src] || "bg-gray-700 text-gray-300"}`}>
              {src}: {count}
            </button>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        {(["directory", "devices", "groups"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`pb-2 text-sm font-medium capitalize transition ${
              tab === t ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"
            }`}>
            {t === "directory" ? "Directory" : t === "devices" ? "Device Owners" : "Groups"}
          </button>
        ))}
      </div>

      {tab === "groups" && <GroupsPanel />}

      {tab === "devices" && <DeviceOwnersPanel />}

      {tab === "directory" && (
        <>
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <input type="text" placeholder="Search name, email, department..."
              value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="w-72 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />

            {/* Status toggle */}
            <div className="flex items-center gap-1 rounded-lg border border-gray-700 bg-gray-800 p-0.5">
              {(["active", "suspended", "all"] as const).map(s => (
                <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }}
                  className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition ${
                    statusFilter === s ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"
                  }`}>{s}</button>
              ))}
            </div>

            {/* Department filter */}
            {stats?.departments?.length > 0 && (
              <select value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setPage(1); }}
                className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
                <option value="">All Departments</option>
                {stats.departments.map((d: any) => (
                  <option key={d.name} value={d.name}>{d.name} ({d.count})</option>
                ))}
              </select>
            )}

            <span className="ml-auto text-sm text-gray-500">{total} users</span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-lg border border-gray-700">
            <table className="w-full text-sm text-left">
              <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
                <tr>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort("display_name")}>
                    User{sortArrow("display_name")}
                  </th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort("email")}>
                    Email{sortArrow("email")}
                  </th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort("department")}>
                    Department{sortArrow("department")}
                  </th>
                  <th className="px-4 py-3">Job Title</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Groups</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort("last_login_at")}>
                    Last Login{sortArrow("last_login_at")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {loading ? (
                  <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-500">Loading...</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-500">No users found</td></tr>
                ) : users.map(u => (
                  <tr key={u.id} className={`transition hover:bg-gray-800 ${!u.is_active ? "opacity-50" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        {u.avatar_url ? (
                          <img src={u.avatar_url} alt="" className="h-7 w-7 rounded-full" />
                        ) : (
                          <div className="h-7 w-7 rounded-full bg-indigo-600/50 flex items-center justify-center text-xs text-white font-bold">
                            {(u.display_name || u.email || "?")[0]?.toUpperCase()}
                          </div>
                        )}
                        <span className="font-medium text-white">{u.display_name || u.email}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{u.email}</td>
                    <td className="px-4 py-3 text-gray-300 text-xs">{u.department || "—"}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs max-w-[150px] truncate">{u.job_title || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${SOURCE_COLORS[u.idp_source] || "bg-gray-700 text-gray-400"}`}>
                        {u.idp_source}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {u.groups?.length > 0 ? (
                        <span title={u.groups.join(", ")}>{u.groups.length} groups</span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        u.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                      }`}>
                        {u.is_active ? "Active" : "Suspended"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {u.last_login_at ? timeAgo(u.last_login_at) : "Never"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

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

          {/* Departments breakdown */}
          {stats?.departments?.length > 0 && (
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h3 className="text-sm font-medium text-gray-400 mb-3">Departments (Active Users)</h3>
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                {stats.departments.map((d: any) => (
                  <button key={d.name} onClick={() => { setDeptFilter(deptFilter === d.name ? "" : d.name); setPage(1); }}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 text-xs transition ${
                      deptFilter === d.name ? "border-indigo-500 bg-indigo-500/10 text-indigo-400" : "border-gray-800 bg-gray-900 text-gray-300 hover:border-gray-700"
                    }`}>
                    <span className="truncate">{d.name}</span>
                    <span className="ml-2 font-bold">{d.count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DeviceOwnersPanel() {
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ page: String(page), page_size: "25", sort_by: "risk_score", sort_dir: "desc" });
      if (search) p.set("search", search);
      const data = await api(`/api/v1/users?${p}`);
      setUsers(data.items || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
    } catch {} finally { setLoading(false); }
  }, [page, search]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <input type="text" placeholder="Search by name, email, or hostname..."
          value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="w-72 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
        <span className="ml-auto text-sm text-gray-500">{total} users with devices</span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="w-full text-sm text-left">
          <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3 text-center">Devices</th>
              <th className="px-4 py-3 text-center">Vulns</th>
              <th className="px-4 py-3 text-center">Crit / High</th>
              <th className="px-4 py-3 text-center">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-500">Loading...</td></tr>
            ) : users.map(u => (
              <DeviceOwnerRow key={u.user_key} user={u} expanded={expanded === u.user_key}
                onToggle={() => setExpanded(expanded === u.user_key ? null : u.user_key)}
                onAssetClick={(id: string) => router.push(`/dashboard/assets/${id}`)} />
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 disabled:opacity-40">Previous</button>
          <span className="text-sm text-gray-500">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(p => p + 1)}
            className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 disabled:opacity-40">Next</button>
        </div>
      )}
    </div>
  );
}

function DeviceOwnerRow({ user: u, expanded, onToggle, onAssetClick }: {
  user: any; expanded: boolean; onToggle: () => void; onAssetClick: (id: string) => void;
}) {
  return (
    <>
      <tr className="bg-gray-900 hover:bg-gray-800 cursor-pointer" onClick={onToggle}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600">{expanded ? "▼" : "▶"}</span>
            <div>
              <p className="font-medium text-white">{u.name}</p>
              {u.job_title && <p className="text-xs text-gray-500">{u.job_title}</p>}
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-gray-400 text-xs">{u.email || "—"}</td>
        <td className="px-4 py-3 text-center text-gray-300">{u.device_count}</td>
        <td className="px-4 py-3 text-center text-gray-300">{u.total_vulns}</td>
        <td className="px-4 py-3 text-center">
          <span className="text-red-400">{u.critical_vulns}</span>
          <span className="text-gray-600"> / </span>
          <span className="text-orange-400">{u.high_vulns}</span>
        </td>
        <td className="px-4 py-3 text-center">
          <span className={`inline-block w-10 rounded border px-1.5 py-0.5 text-center text-xs font-bold ${riskBg(u.max_risk_score)} ${riskColor(u.max_risk_score)}`}>
            {u.max_risk_score}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-950">
          <td colSpan={6} className="px-6 py-4">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {u.devices.map((d: any) => (
                <div key={d.id} onClick={e => { e.stopPropagation(); onAssetClick(d.id); }}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-3 cursor-pointer hover:border-gray-600 transition">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{d.hostname}</p>
                    <p className="text-xs text-gray-500">{d.os_name} {d.serial_number && `· ${d.serial_number}`}</p>
                  </div>
                  <span className={`text-xs font-bold ${riskColor(d.risk_score)}`}>{d.risk_score}</span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function GroupsPanel() {
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api("/api/v1/tenant/groups").then(d => setGroups(Array.isArray(d) ? d : [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const filtered = search ? groups.filter(g => g.name.toLowerCase().includes(search.toLowerCase())) : groups;

  async function handleExport() {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const token = typeof window !== "undefined" ? localStorage.getItem("getvul_token") || "" : "";
    const resp = await fetch(`${API}/api/v1/tenant/groups/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `groups_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return <p className="text-gray-500 text-sm py-8 text-center">Loading groups...</p>;
  if (groups.length === 0) return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-12 text-center">
      <p className="text-gray-400">No groups found</p>
      <p className="mt-2 text-sm text-gray-500">Connect Google Workspace or Azure Entra ID to sync groups</p>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search groups..."
          className="w-72 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{filtered.length} groups</span>
          <button onClick={handleExport}
            className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800 transition">
            Export CSV
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {filtered.map(g => (
          <div key={g.name} className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
            <button onClick={() => setExpanded(expanded === g.name ? null : g.name)}
              className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-gray-800/50">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-600">{expanded === g.name ? "▼" : "▶"}</span>
                <p className="text-sm font-medium text-white">{g.name}</p>
              </div>
              <span className="rounded-full bg-gray-800 px-2.5 py-0.5 text-xs text-gray-400">{g.member_count}</span>
            </button>
            {expanded === g.name && (
              <div className="border-t border-gray-800 px-5 py-3">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {g.members.map((m: any) => (
                    <div key={m.id} className="flex items-center gap-2 rounded-lg bg-gray-800/50 px-3 py-2">
                      <div className="h-6 w-6 rounded-full bg-indigo-600/50 flex items-center justify-center text-xs text-indigo-300">
                        {(m.display_name || m.email)[0]?.toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs text-white truncate">{m.display_name || m.email}</p>
                        <p className="text-xs text-gray-500 truncate">{m.email}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  const colors: Record<string, string> = {
    emerald: "text-emerald-400", orange: "text-orange-400",
    indigo: "text-indigo-400", blue: "text-blue-400", gray: "text-gray-400",
  };
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <p className="text-sm text-gray-400">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent ? colors[accent] || "text-white" : "text-white"}`}>
        {(value ?? 0).toLocaleString()}
      </p>
    </div>
  );
}

function riskColor(s: number) {
  if (s >= 80) return "text-red-400";
  if (s >= 50) return "text-orange-400";
  if (s >= 20) return "text-yellow-400";
  return "text-green-400";
}

function riskBg(s: number) {
  if (s >= 80) return "bg-red-500/10 border-red-500/30";
  if (s >= 50) return "bg-orange-500/10 border-orange-500/30";
  if (s >= 20) return "bg-yellow-500/10 border-yellow-500/30";
  return "bg-green-500/10 border-green-500/30";
}

function timeAgo(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}
