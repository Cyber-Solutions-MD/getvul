"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Cloud,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Search,
  X,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import Pagination from "@/components/ui/Pagination";
import { cn } from "@/lib/utils";
import type { MisconfigSummary, CSPMDashboardStats } from "@/types/cspm";

interface PaginatedFindings {
  items: MisconfigSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const CATEGORIES = ["IAM", "NETWORK", "ENCRYPTION", "LOGGING", "STORAGE", "COMPUTE", "DATABASE", "CONTAINER", "SECRETS"];
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SOURCES = ["CROWDSTRIKE", "WIZ", "DEFENDER"];
const CLOUDS = ["AWS", "AZURE", "GCP"];

const categoryIcons: Record<string, string> = {
  IAM: "👤", NETWORK: "🌐", ENCRYPTION: "🔐", LOGGING: "📋",
  STORAGE: "💾", COMPUTE: "🖥️", DATABASE: "🗄️", CONTAINER: "📦", SECRETS: "🔑",
};

const sevColors: Record<string, string> = {
  CRITICAL: "border-red-500/40 bg-red-500/10 text-red-400",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-400",
  MEDIUM: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400",
  LOW: "border-blue-500/40 bg-blue-500/10 text-blue-400",
};

export default function CSPMPage() {
  const [stats, setStats] = useState<CSPMDashboardStats | null>(null);
  const [data, setData] = useState<PaginatedFindings | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Filters
  const [search, setSearch] = useState("");
  const [selSeverity, setSelSeverity] = useState<string[]>([]);
  const [selCategory, setSelCategory] = useState<string[]>([]);
  const [selSource, setSelSource] = useState<string[]>([]);
  const [selCloud, setSelCloud] = useState<string | null>(null);

  const toggle = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];

  const loadStats = useCallback(async () => {
    try {
      const s = await api<CSPMDashboardStats>("/api/v1/cspm/stats");
      setStats(s);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadFindings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "25");
      if (search) params.set("search", search);
      selSeverity.forEach((s) => params.append("severity", s));
      selCategory.forEach((s) => params.append("category", s));
      selSource.forEach((s) => params.append("source", s));
      if (selCloud) params.set("cloud_provider", selCloud);

      const d = await api<PaginatedFindings>(`/api/v1/cspm?${params.toString()}`);
      setData(d);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, search, selSeverity, selCategory, selSource, selCloud]);

  useEffect(() => { loadStats(); }, [loadStats]);

  useEffect(() => {
    const t = setTimeout(loadFindings, 300);
    return () => clearTimeout(t);
  }, [loadFindings]);

  useEffect(() => { setPage(1); }, [search, selSeverity, selCategory, selSource, selCloud]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cloud className="h-6 w-6 text-sky-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Cloud Security Posture</h1>
            <p className="text-sm text-gray-400">Misconfigurations across cloud environments</p>
          </div>
        </div>
        <button onClick={() => { loadStats(); loadFindings(); }} className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={<Cloud className="h-5 w-5 text-sky-400" />} label="Total Findings" value={stats.total_findings.toLocaleString()} />
            <StatCard icon={<AlertTriangle className="h-5 w-5 text-orange-400" />} label="Open" value={stats.open_findings.toLocaleString()} />
            <StatCard icon={<ShieldCheck className="h-5 w-5 text-emerald-400" />} label="Compliance Pass Rate" value={stats.compliance_pass_rate !== null ? `${stats.compliance_pass_rate}%` : "N/A"} />
            <StatCard
              icon={<Cloud className="h-5 w-5 text-purple-400" />}
              label="Cloud Providers"
              value={stats.by_cloud_provider.length.toString()}
            />
          </div>

          {/* Category breakdown */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h2 className="mb-4 text-sm font-medium text-gray-400">By Category</h2>
              <div className="space-y-2.5">
                {stats.by_category.sort((a, b) => b.count - a.count).map((c) => (
                  <div key={c.category} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-gray-300">
                      <span>{categoryIcons[c.category] || "📌"}</span>
                      {c.category}
                    </span>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-28 overflow-hidden rounded-full bg-gray-800">
                        <div className="h-full rounded-full bg-sky-500" style={{ width: `${Math.max(3, (c.count / stats.total_findings) * 100)}%` }} />
                      </div>
                      <span className="w-12 text-right text-sm font-medium text-white">{c.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h2 className="mb-4 text-sm font-medium text-gray-400">By Severity</h2>
              <div className="space-y-2.5">
                {stats.by_severity.map((s) => (
                  <div key={s.severity} className="flex items-center justify-between">
                    <SeverityBadge severity={s.severity} />
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-28 overflow-hidden rounded-full bg-gray-800">
                        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(3, (s.count / stats.total_findings) * 100)}%` }} />
                      </div>
                      <span className="w-12 text-right text-sm font-medium text-white">{s.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search rule, resource..." className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"><X className="h-4 w-4" /></button>}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500"><Filter className="h-3.5 w-3.5" />Filters</div>

          <div className="flex gap-1.5">
            {SEVERITIES.map((s) => (
              <button key={s} onClick={() => setSelSeverity(toggle(selSeverity, s))} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selSeverity.includes(s) ? sevColors[s] : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{s}</button>
            ))}
          </div>
          <div className="h-4 w-px bg-gray-700" />
          <div className="flex gap-1.5">
            {CATEGORIES.map((c) => (
              <button key={c} onClick={() => setSelCategory(toggle(selCategory, c))} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selCategory.includes(c) ? "border-sky-500/40 bg-sky-500/15 text-sky-400" : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{categoryIcons[c] || ""} {c}</button>
            ))}
          </div>
          <div className="h-4 w-px bg-gray-700" />
          <div className="flex gap-1.5">
            {CLOUDS.map((c) => (
              <button key={c} onClick={() => setSelCloud(selCloud === c ? null : c)} className={cn("rounded-md border px-2 py-0.5 text-xs font-medium transition-all", selCloud === c ? "border-purple-500/40 bg-purple-500/15 text-purple-400" : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300")}>{c}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      {loading && !data ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Rule</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Category</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Resource</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Cloud</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Detected</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(data?.items || []).map((m) => (
                  <tr key={m.id} className="transition-colors hover:bg-gray-800/30">
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-xs text-gray-400">{m.rule_id}</div>
                      <div className="max-w-[250px] truncate text-sm text-white">{m.rule_name}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1 text-xs text-gray-300">
                        {categoryIcons[m.category] || "📌"} {m.category}
                      </span>
                    </td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={m.severity} /></td>
                    <td className="px-3 py-2.5"><SourceBadge source={m.source} /></td>
                    <td className="px-3 py-2.5"><StatusBadge status={m.status} /></td>
                    <td className="max-w-[200px] truncate px-3 py-2.5 text-xs text-gray-400">{m.resource_name || m.resource_id}</td>
                    <td className="px-3 py-2.5">
                      {m.cloud_provider && (
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-300">{m.cloud_provider}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-500">{new Date(m.first_detected_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && <div className="py-12 text-center text-gray-500">No findings match your filters</div>}
          </div>
          {data && data.total_pages > 1 && <Pagination page={data.page} totalPages={data.total_pages} total={data.total} pageSize={data.page_size} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">{icon}<span className="text-sm text-gray-400">{label}</span></div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
