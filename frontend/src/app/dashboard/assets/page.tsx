"use client";

import { useCallback, useEffect, useState } from "react";

const API = "http://localhost:8000";
const TOKEN = "dev-token";
const headers = { Authorization: `Bearer ${TOKEN}` };

const CATEGORY_ICONS: Record<string, string> = {
  WORKSTATION: "🖥️",
  SERVER: "🗄️",
  NETWORK: "🌐",
  MOBILE: "📱",
  OTHER: "❓",
};

const CATEGORY_COLORS: Record<string, string> = {
  WORKSTATION: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  SERVER: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  NETWORK: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  MOBILE: "bg-green-500/20 text-green-400 border-green-500/30",
  OTHER: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

function riskColor(score: number) {
  if (score >= 80) return "text-red-400";
  if (score >= 50) return "text-orange-400";
  if (score >= 20) return "text-yellow-400";
  return "text-green-400";
}

function riskBg(score: number) {
  if (score >= 80) return "bg-red-500";
  if (score >= 50) return "bg-orange-500";
  if (score >= 20) return "bg-yellow-500";
  return "bg-green-500";
}

export default function AssetsPage() {
  const [assets, setAssets] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [minRisk, setMinRisk] = useState(0);
  const [sortBy, setSortBy] = useState("risk_score");
  const [sortDir, setSortDir] = useState("desc");
  const [classifying, setClassifying] = useState(false);
  const pageSize = 25;

  const fetchStats = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/v1/assets/stats`, { headers });
      if (r.ok) setStats(await r.json());
    } catch {}
  }, []);

  const fetchAssets = useCallback(async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    if (search) params.set("search", search);
    if (category) params.set("device_category", category);
    if (minRisk > 0) params.set("min_risk", String(minRisk));

    try {
      const r = await fetch(`${API}/api/v1/assets?${params}`, { headers });
      if (r.ok) {
        const data = await r.json();
        setAssets(data.items || []);
        setTotal(data.total || 0);
        setPages(data.pages || 0);
      }
    } catch {}
  }, [page, search, category, minRisk, sortBy, sortDir]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchAssets(); }, [fetchAssets]);

  const handleClassify = async () => {
    setClassifying(true);
    try {
      const r = await fetch(`${API}/api/v1/assets/classify`, { method: "POST", headers });
      if (r.ok) {
        await fetchStats();
        await fetchAssets();
      }
    } catch {}
    setClassifying(false);
  };

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(d => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const sortArrow = (col: string) => {
    if (sortBy !== col) return "";
    return sortDir === "asc" ? " ↑" : " ↓";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Asset Inventory</h1>
        <button
          onClick={handleClassify}
          disabled={classifying}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {classifying ? "Classifying..." : "🔄 Classify Devices"}
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-6">
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="text-sm text-gray-400">Total Assets</p>
            <p className="text-2xl font-bold text-white">{stats.total?.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="text-sm text-gray-400">Avg Risk Score</p>
            <p className={`text-2xl font-bold ${riskColor(stats.avg_risk_score)}`}>
              {stats.avg_risk_score}
            </p>
          </div>
          {Object.entries(stats.by_device_category || {}).map(([cat, count]) => (
            <div key={cat} className="rounded-lg border border-gray-700 bg-gray-800 p-4">
              <p className="text-sm text-gray-400">
                {CATEGORY_ICONS[cat] || "❓"} {cat}
              </p>
              <p className="text-2xl font-bold text-white">{(count as number).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search hostname or OS..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-400"
        />
        {/* Device category pills */}
        {["WORKSTATION", "SERVER", "NETWORK", "MOBILE", "OTHER"].map((cat) => (
          <button
            key={cat}
            onClick={() => { setCategory(category === cat ? "" : cat); setPage(1); }}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              category === cat
                ? CATEGORY_COLORS[cat]
                : "border-gray-600 text-gray-400 hover:border-gray-500"
            }`}
          >
            {CATEGORY_ICONS[cat]} {cat}
          </button>
        ))}
        {/* Risk filter */}
        <select
          value={minRisk}
          onChange={(e) => { setMinRisk(Number(e.target.value)); setPage(1); }}
          className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white"
        >
          <option value={0}>All Risk</option>
          <option value={80}>Critical (80+)</option>
          <option value={50}>High (50+)</option>
          <option value={20}>Medium (20+)</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="w-full text-sm text-left">
          <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
            <tr>
              <th className="cursor-pointer px-4 py-3" onClick={() => handleSort("hostname")}>
                Hostname{sortArrow("hostname")}
              </th>
              <th className="px-4 py-3">OS</th>
              <th className="cursor-pointer px-4 py-3" onClick={() => handleSort("device_category")}>
                Type{sortArrow("device_category")}
              </th>
              <th className="px-4 py-3">Scanners</th>
              <th className="cursor-pointer px-4 py-3 text-right" onClick={() => handleSort("risk_score")}>
                Risk{sortArrow("risk_score")}
              </th>
              <th className="px-4 py-3 text-right">Vulns</th>
              <th className="px-4 py-3 text-right">Crit</th>
              <th className="px-4 py-3 text-right">High</th>
              <th className="px-4 py-3 text-right">Exploit</th>
              <th className="px-4 py-3 text-right">KEV</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {assets.map((a) => (
              <tr
                key={a.id}
                className="cursor-pointer bg-gray-900 hover:bg-gray-800 transition"
                onClick={() => window.location.href = `/dashboard/assets/${a.id}`}
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{a.hostname}</div>
                  {a.assigned_user && (
                    <div className="text-xs text-gray-500">{a.assigned_user}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-300">
                  {a.os_name} {a.os_version && <span className="text-gray-500">{a.os_version}</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${CATEGORY_COLORS[a.device_category] || CATEGORY_COLORS.OTHER}`}>
                    {CATEGORY_ICONS[a.device_category] || "❓"} {a.device_category}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    {Object.keys(a.seen_by_sources || {}).map((s) => (
                      <span key={s} className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">
                        {s.toUpperCase().slice(0, 3)}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="h-2 w-16 overflow-hidden rounded-full bg-gray-700">
                      <div className={`h-full ${riskBg(a.risk_score)}`} style={{ width: `${a.risk_score}%` }} />
                    </div>
                    <span className={`font-mono font-bold ${riskColor(a.risk_score)}`}>
                      {a.risk_score}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-gray-300">{a.total_vulns}</td>
                <td className="px-4 py-3 text-right">
                  {a.critical > 0 && <span className="font-bold text-red-400">{a.critical}</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  {a.high > 0 && <span className="font-bold text-orange-400">{a.high}</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  {a.exploitable > 0 && <span className="text-yellow-400">{a.exploitable}</span>}
                </td>
                <td className="px-4 py-3 text-right">
                  {a.kev > 0 && <span className="text-red-300">🚨 {a.kev}</span>}
                </td>
              </tr>
            ))}
            {assets.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-gray-500">
                  No assets found matching your filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-400">
            {total.toLocaleString()} assets · Page {page} of {pages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-gray-600 px-3 py-1 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-30"
            >
              ← Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page === pages}
              className="rounded-lg border border-gray-600 px-3 py-1 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
