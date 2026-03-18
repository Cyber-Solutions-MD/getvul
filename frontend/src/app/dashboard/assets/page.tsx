"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Server, Search, X, Filter, RefreshCw, Loader2,
  Shield, AlertTriangle, Flame, ShieldAlert, ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, SourceBadge } from "@/components/ui/Badge";
import Pagination from "@/components/ui/Pagination";
import { cn } from "@/lib/utils";
import type { AssetSummary, AssetStats } from "@/types/asset";

interface PaginatedAssets {
  items: AssetSummary[];
  total: number; page: number; page_size: number; total_pages: number;
}

const SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"];

function riskColor(score: number | null): string {
  if (score === null) return "text-gray-500";
  if (score >= 80) return "text-red-400";
  if (score >= 50) return "text-orange-400";
  if (score >= 20) return "text-yellow-400";
  return "text-emerald-400";
}

function riskBg(score: number | null): string {
  if (score === null) return "bg-gray-800";
  if (score >= 80) return "bg-red-500";
  if (score >= 50) return "bg-orange-500";
  if (score >= 20) return "bg-yellow-500";
  return "bg-emerald-500";
}

export default function AssetsPage() {
  const [stats, setStats] = useState<AssetStats | null>(null);
  const [data, setData] = useState<PaginatedAssets | null>(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [page, setPage] = useState(1);

  // Filters
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [riskMin, setRiskMin] = useState<number | null>(null);

  const loadStats = useCallback(async () => {
    try { setStats(await api<AssetStats>("/api/v1/assets/stats")); } catch (e) { console.error(e); }
  }, []);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "30");
      if (search) p.set("search", search);
      if (sourceFilter) p.set("source", sourceFilter);
      if (riskMin !== null) p.set("risk_score_min", String(riskMin));
      setData(await api<PaginatedAssets>(`/api/v1/assets?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, search, sourceFilter, riskMin]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => {
    const t = setTimeout(loadAssets, 300);
    return () => clearTimeout(t);
  }, [loadAssets]);
  useEffect(() => { setPage(1); }, [search, sourceFilter, riskMin]);

  async function handleRecompute() {
    setRecomputing(true);
    try {
      await api("/api/v1/assets/recompute-risk-scores", { method: "POST" });
      await loadStats();
      await loadAssets();
    } catch (e) { console.error(e); }
    finally { setRecomputing(false); }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="h-6 w-6 text-emerald-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Asset Inventory</h1>
            {stats && <p className="text-sm text-gray-400">{stats.total_assets.toLocaleString()} assets discovered</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleRecompute} disabled={recomputing}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
            {recomputing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
            Recompute Risk
          </button>
          <button onClick={() => { loadStats(); loadAssets(); }}
            className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
            <RefreshCw className="h-4 w-4" />Refresh
          </button>
        </div>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={<Server className="h-5 w-5 text-emerald-400" />} label="Total Assets" value={stats.total_assets.toLocaleString()} />
          <StatCard icon={<Shield className="h-5 w-5 text-indigo-400" />} label="Avg Risk Score"
            value={stats.average_risk_score.toString()} extra={<RiskBar score={stats.average_risk_score} />} />

          {/* Scanner coverage */}
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
            <div className="flex items-center gap-3"><Server className="h-5 w-5 text-sky-400" /><span className="text-sm text-gray-400">Scanner Coverage</span></div>
            <div className="mt-3 space-y-1.5">
              {Object.entries(stats.scanner_coverage).map(([src, cnt]) => (
                <div key={src} className="flex items-center justify-between">
                  <SourceBadge source={src} />
                  <span className="text-sm font-medium text-white">{cnt.toLocaleString()}</span>
                </div>
              ))}
              {Object.keys(stats.scanner_coverage).length === 0 && <span className="text-xs text-gray-500">No scanners connected</span>}
            </div>
          </div>

          {/* Risk distribution */}
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
            <div className="flex items-center gap-3"><AlertTriangle className="h-5 w-5 text-orange-400" /><span className="text-sm text-gray-400">Risk Distribution</span></div>
            <div className="mt-3 space-y-1.5">
              {stats.by_risk_range.map((r) => (
                <div key={r.range} className="flex items-center justify-between">
                  <span className="text-xs text-gray-300">{r.range}</span>
                  <span className="text-sm font-medium text-white">{r.count}</span>
                </div>
              ))}
              {stats.by_risk_range.length === 0 && <span className="text-xs text-gray-500">Run "Recompute Risk" first</span>}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search hostname, OS..."
            className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"><X className="h-4 w-4" /></button>}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500"><Filter className="h-3.5 w-3.5" />Filters</div>

          {/* Source filter */}
          <div className="flex gap-1.5">
            {SOURCES.map((s) => (
              <button key={s} onClick={() => setSourceFilter(sourceFilter === s ? null : s)}
                className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                  sourceFilter === s
                    ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {s === "CROWDSTRIKE" ? "CS" : s === "DEFENDER" ? "MDE" : s}
              </button>
            ))}
          </div>

          <div className="h-4 w-px bg-gray-700" />

          {/* Risk score filter */}
          <div className="flex gap-1.5">
            {[
              { label: "Critical 80+", min: 80 },
              { label: "High 50+", min: 50 },
              { label: "Medium 20+", min: 20 },
            ].map((r) => (
              <button key={r.min} onClick={() => setRiskMin(riskMin === r.min ? null : r.min)}
                className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                  riskMin === r.min
                    ? "border-red-500/40 bg-red-500/15 text-red-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {r.label}
              </button>
            ))}
          </div>

          {(sourceFilter || riskMin !== null) && (
            <button onClick={() => { setSourceFilter(null); setRiskMin(null); }}
              className="text-xs text-gray-500 hover:text-gray-300">Clear filters</button>
          )}
        </div>
      </div>

      {/* Table */}
      {loading && !data ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Hostname</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">OS</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Scanners</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Risk</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Vulns</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Critical</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">High</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploitable</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
                <th className="w-8 px-3 py-3"></th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(data?.items || []).map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-800/30 cursor-pointer"
                    onClick={() => window.location.href = `/dashboard/assets/${asset.id}`}>
                    <td className="px-3 py-2.5 text-white font-medium">{asset.hostname || "—"}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{asset.os_name} {asset.os_version}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex gap-1">
                        {(asset.seen_by_sources || []).map((s) => <SourceBadge key={s} source={s} />)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className={cn("text-sm font-bold", riskColor(asset.risk_score))}>{asset.risk_score ?? "—"}</span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-800">
                          <div className={cn("h-full rounded-full", riskBg(asset.risk_score))}
                            style={{ width: `${Math.min(100, asset.risk_score || 0)}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-white">{asset.open_vuln_count}</td>
                    <td className="px-3 py-2.5">
                      {asset.critical_count > 0 ? (
                        <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs font-medium text-red-400">{asset.critical_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.high_count > 0 ? (
                        <span className="rounded bg-orange-500/20 px-1.5 py-0.5 text-xs font-medium text-orange-400">{asset.high_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.exploitable_count > 0 ? (
                        <span className="flex items-center gap-1 text-xs font-medium text-orange-400">
                          <Flame className="h-3 w-3" />{asset.exploitable_count}
                        </span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {asset.kev_count > 0 ? (
                        <span className="text-xs font-medium text-red-400">🛡️ {asset.kev_count}</span>
                      ) : <span className="text-gray-600">0</span>}
                    </td>
                    <td className="px-3 py-2.5"><ChevronRight className="h-4 w-4 text-gray-600" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && <div className="py-12 text-center text-gray-500">No assets match your filters</div>}
          </div>
          {data && data.total_pages > 1 && (
            <Pagination page={data.page} totalPages={data.total_pages} total={data.total} pageSize={data.page_size} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, extra }: { icon: React.ReactNode; label: string; value: string; extra?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">{icon}<span className="text-sm text-gray-400">{label}</span></div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
      {extra}
    </div>
  );
}

function RiskBar({ score }: { score: number }) {
  return (
    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-800">
      <div className={cn("h-full rounded-full transition-all", riskBg(score))}
        style={{ width: `${Math.min(100, score)}%` }} />
    </div>
  );
}
