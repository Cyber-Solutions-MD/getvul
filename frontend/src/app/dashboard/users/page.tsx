"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN = "dev-token";
const headers: Record<string, string> = { Authorization: `Bearer ${TOKEN}` };

const SEV_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400",
  HIGH: "bg-orange-500/20 text-orange-400",
  MEDIUM: "bg-yellow-500/20 text-yellow-400",
  LOW: "bg-green-500/20 text-green-400",
};

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
  if (diffMin < 60) return `${diffMin}m`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h`;
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d`;
}

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [sortBy, setSortBy] = useState("risk_score");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const pageSize = 25;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (search) params.set("search", search);
      if (riskFilter) params.set("risk", riskFilter);

      const [usersResp, statsResp] = await Promise.all([
        fetch(`${API}/api/v1/users?${params}`, { headers }),
        fetch(`${API}/api/v1/users/stats`, { headers }),
      ]);
      const usersData = await usersResp.json();
      const statsData = await statsResp.json();
      setUsers(usersData.items || []);
      setTotal(usersData.total || 0);
      setPages(usersData.pages || 0);
      setStats(statsData);
    } catch (e) {
      console.error("Failed to load users:", e);
    } finally {
      setLoading(false);
    }
  }, [page, search, riskFilter, sortBy, sortDir]);

  useEffect(() => { load(); }, [load]);

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(d => d === "desc" ? "asc" : "desc");
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
    setPage(1);
  };

  const SortIcon = ({ col }: { col: string }) => (
    <span className="ml-1 text-gray-600">
      {sortBy === col ? (sortDir === "desc" ? "↓" : "↑") : "↕"}
    </span>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Users</h1>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Total Users" value={stats.total_users} />
          <StatCard label="Humaans Linked" value={stats.humaans_enriched} accent="indigo" />
          <StatCard label="Assigned Devices" value={stats.assigned_assets} accent="emerald" />
          <StatCard label="Unassigned Devices" value={stats.unassigned_assets} accent="gray" />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search by name, email, or hostname..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="w-72 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
        />
        <select
          value={riskFilter}
          onChange={e => { setRiskFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All Risk Levels</option>
          <option value="critical">Critical (80+)</option>
          <option value="high">High (50-79)</option>
          <option value="medium">Medium (20-49)</option>
          <option value="low">Low (&lt;20)</option>
        </select>
        <span className="ml-auto text-sm text-gray-500">{total} users</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="w-full text-sm text-left">
          <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
            <tr>
              <th className="px-4 py-3 cursor-pointer" onClick={() => toggleSort("name")}>
                User <SortIcon col="name" />
              </th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Handles</th>
              <th className="px-4 py-3 cursor-pointer text-center" onClick={() => toggleSort("devices")}>
                Devices <SortIcon col="devices" />
              </th>
              <th className="px-4 py-3 cursor-pointer text-center" onClick={() => toggleSort("vulns")}>
                Vulns <SortIcon col="vulns" />
              </th>
              <th className="px-4 py-3 text-center">Crit / High</th>
              <th className="px-4 py-3 cursor-pointer text-center" onClick={() => toggleSort("risk_score")}>
                Risk <SortIcon col="risk_score" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-500">Loading...</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-500">No users found</td></tr>
            ) : users.map((u) => (
              <UserRow
                key={u.user_key}
                user={u}
                expanded={expanded === u.user_key}
                onToggle={() => setExpanded(expanded === u.user_key ? null : u.user_key)}
                onAssetClick={(id: string) => router.push(`/dashboard/assets/${id}`)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">Page {page} of {pages}</span>
          <button
            disabled={page >= pages}
            onClick={() => setPage(p => p + 1)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function UserRow({ user, expanded, onToggle, onAssetClick }: {
  user: any; expanded: boolean; onToggle: () => void; onAssetClick: (id: string) => void;
}) {
  const u = user;
  return (
    <>
      <tr className="bg-gray-900 hover:bg-gray-800 cursor-pointer" onClick={onToggle}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600">{expanded ? "▼" : "▶"}</span>
            <div>
              <p className="font-medium text-white">{u.name}</p>
              {u.job_title && <p className="text-xs text-gray-500">{u.job_title}</p>}
              {u.department && <p className="text-xs text-gray-600">{u.department}</p>}
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-gray-400 text-xs">{u.email || "—"}</td>
        <td className="px-4 py-3">
          <div className="flex gap-2">
            {u.github_handle && (
              <a href={`https://github.com/${u.github_handle.replace(/^@/, "")}`}
                target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-indigo-400 hover:text-indigo-300"
                title={u.github_handle}>
                GH
              </a>
            )}
            {u.linkedin_handle && (
              <a href={`https://linkedin.com/in/${u.linkedin_handle}`}
                target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-blue-400 hover:text-blue-300"
                title={u.linkedin_handle}>
                LI
              </a>
            )}
            {u.element_handle && (
              <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-green-400" title={u.element_handle}>
                EL
              </span>
            )}
            {!u.github_handle && !u.linkedin_handle && !u.element_handle && <span className="text-xs text-gray-600">—</span>}
          </div>
        </td>
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

      {/* Expanded: device list */}
      {expanded && (
        <tr className="bg-gray-950">
          <td colSpan={7} className="px-6 py-4">
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Devices ({u.device_count})</p>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {u.devices.map((d: any) => (
                  <div
                    key={d.id}
                    onClick={(e) => { e.stopPropagation(); onAssetClick(d.id); }}
                    className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 p-3 cursor-pointer hover:border-gray-600 transition"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">{d.hostname}</p>
                      <p className="text-xs text-gray-500">
                        {d.os_name} {d.os_version}
                        {d.serial_number && <span> · {d.serial_number}</span>}
                      </p>
                      {d.model && <p className="text-xs text-gray-600 truncate">{d.model}</p>}
                    </div>
                    <div className="flex items-center gap-2 ml-3 shrink-0">
                      {d.host_status && (
                        <span className={`h-2 w-2 rounded-full ${
                          d.host_status === "normal" ? "bg-green-400" : "bg-gray-500"
                        }`} title={d.host_status} />
                      )}
                      <span className={`text-xs font-bold ${riskColor(d.risk_score)}`}>{d.risk_score}</span>
                      {d.last_seen_at && (
                        <span className="text-xs text-gray-600">{timeAgo(d.last_seen_at)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {/* Vulnerability summary */}
              {u.total_vulns > 0 && (
                <div className="flex gap-3 mt-2 pt-2 border-t border-gray-800">
                  <span className="text-xs text-gray-500">Vulns:</span>
                  <span className="text-xs text-red-400">{u.critical_vulns} critical</span>
                  <span className="text-xs text-orange-400">{u.high_vulns} high</span>
                  {u.exploitable_vulns > 0 && <span className="text-xs text-yellow-400">{u.exploitable_vulns} exploitable</span>}
                  {u.kev_vulns > 0 && <span className="text-xs text-red-300">{u.kev_vulns} KEV</span>}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  const colors: Record<string, string> = {
    indigo: "text-indigo-400",
    emerald: "text-emerald-400",
    gray: "text-gray-400",
  };
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <p className="text-sm text-gray-400">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent ? colors[accent] || "text-white" : "text-white"}`}>
        {value.toLocaleString()}
      </p>
    </div>
  );
}
