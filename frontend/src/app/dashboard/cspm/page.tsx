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
  TrendingUp,
  Server,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import Pagination from "@/components/ui/Pagination";
import { cn } from "@/lib/utils";
import type { MisconfigSummary, CSPMDashboardStats } from "@/types/cspm";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PaginatedFindings {
  items: MisconfigSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface ComplianceFramework {
  framework: string;
  total_controls: number;
  passed: number;
  failed: number;
  suppressed: number;
  pass_rate: number;
}

interface ResourceRow {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  region: string;
  cloud_provider: string;
  total_findings: number;
  critical_findings: number;
  open_findings: number;
  worst_severity: string;
  frameworks: string[];
  last_seen: string;
}

interface PaginatedResources {
  items: ResourceRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface TrendDay {
  date: string;
  new_findings: number;
  resolved: number;
}

interface TrendsData {
  days: TrendDay[];
  summary: {
    new_findings: number;
    resolved: number;
    currently_open: number;
  };
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const CATEGORIES = ["IAM", "NETWORK", "ENCRYPTION", "LOGGING", "STORAGE", "COMPUTE", "DATABASE", "CONTAINER", "SECRETS"];
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SOURCES = ["CROWDSTRIKE", "WIZ", "DEFENDER"];
const CLOUDS = ["AWS", "AZURE", "GCP"];

const categoryIcons: Record<string, string> = {
  IAM: "\u{1F464}", NETWORK: "\u{1F310}", ENCRYPTION: "\u{1F510}", LOGGING: "\u{1F4CB}",
  STORAGE: "\u{1F4BE}", COMPUTE: "\u{1F5A5}\uFE0F", DATABASE: "\u{1F5C4}\uFE0F", CONTAINER: "\u{1F4E6}", SECRETS: "\u{1F511}",
};

const sevColors: Record<string, string> = {
  CRITICAL: "border-red-500/40 bg-red-500/10 text-red-400",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-400",
  MEDIUM: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400",
  LOW: "border-blue-500/40 bg-blue-500/10 text-blue-400",
};

const TABS = ["Findings", "Compliance", "Resources", "Trends"] as const;
type Tab = (typeof TABS)[number];

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function CSPMPage() {
  const [tab, setTab] = useState<Tab>("Findings");

  /* ---- Findings state ---- */
  const [stats, setStats] = useState<CSPMDashboardStats | null>(null);
  const [data, setData] = useState<PaginatedFindings | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selSeverity, setSelSeverity] = useState<string[]>([]);
  const [selCategory, setSelCategory] = useState<string[]>([]);
  const [selSource, setSelSource] = useState<string[]>([]);
  const [selCloud, setSelCloud] = useState<string | null>(null);

  /* ---- Compliance state ---- */
  const [compliance, setCompliance] = useState<ComplianceFramework[] | null>(null);
  const [compLoading, setCompLoading] = useState(false);

  /* ---- Resources state ---- */
  const [resources, setResources] = useState<PaginatedResources | null>(null);
  const [resLoading, setResLoading] = useState(false);
  const [resPage, setResPage] = useState(1);
  const [resSearch, setResSearch] = useState("");
  const [resCloud, setResCloud] = useState<string | null>(null);

  /* ---- Trends state ---- */
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [trendsLoading, setTrendsLoading] = useState(false);
  const [trendDays, setTrendDays] = useState(30);

  const toggle = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];

  /* ---- Findings fetchers ---- */
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

  /* ---- Compliance fetcher ---- */
  const loadCompliance = useCallback(async () => {
    setCompLoading(true);
    try {
      const c = await api<ComplianceFramework[]>("/api/v1/cspm/compliance");
      c.sort((a, b) => a.pass_rate - b.pass_rate);
      setCompliance(c);
    } catch (e) {
      console.error(e);
    } finally {
      setCompLoading(false);
    }
  }, []);

  /* ---- Resources fetcher ---- */
  const loadResources = useCallback(async () => {
    setResLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(resPage));
      params.set("page_size", "25");
      if (resSearch) params.set("search", resSearch);
      if (resCloud) params.set("cloud_provider", resCloud);
      const r = await api<PaginatedResources>(`/api/v1/cspm/resources?${params.toString()}`);
      setResources(r);
    } catch (e) {
      console.error(e);
    } finally {
      setResLoading(false);
    }
  }, [resPage, resSearch, resCloud]);

  /* ---- Trends fetcher ---- */
  const loadTrends = useCallback(async () => {
    setTrendsLoading(true);
    try {
      const t = await api<TrendsData>(`/api/v1/cspm/trends?days=${trendDays}`);
      setTrends(t);
    } catch (e) {
      console.error(e);
    } finally {
      setTrendsLoading(false);
    }
  }, [trendDays]);

  /* ---- Effects for Findings ---- */
  useEffect(() => { loadStats(); }, [loadStats]);

  useEffect(() => {
    const t = setTimeout(loadFindings, 300);
    return () => clearTimeout(t);
  }, [loadFindings]);

  useEffect(() => { setPage(1); }, [search, selSeverity, selCategory, selSource, selCloud]);

  /* ---- Effects for other tabs (load on first visit) ---- */
  useEffect(() => {
    if (tab === "Compliance" && compliance === null && !compLoading) loadCompliance();
  }, [tab, compliance, compLoading, loadCompliance]);

  useEffect(() => {
    if (tab === "Resources" && resources === null && !resLoading) loadResources();
  }, [tab, resources, resLoading, loadResources]);

  useEffect(() => {
    if (tab === "Trends" && trends === null && !trendsLoading) loadTrends();
  }, [tab, trends, trendsLoading, loadTrends]);

  /* ---- Resources: reload on filter change ---- */
  useEffect(() => {
    if (tab === "Resources") {
      const t = setTimeout(loadResources, 300);
      return () => clearTimeout(t);
    }
  }, [resPage, resSearch, resCloud, tab, loadResources]);

  useEffect(() => { setResPage(1); }, [resSearch, resCloud]);

  /* ---- Trends: reload on days change ---- */
  useEffect(() => {
    if (tab === "Trends") loadTrends();
  }, [trendDays, tab, loadTrends]);

  /* ---- Navigate from Resources row to filtered Findings ---- */
  const goToResourceFindings = (resourceName: string) => {
    setSearch(resourceName);
    setTab("Findings");
  };

  const handleRefresh = () => {
    if (tab === "Findings") { loadStats(); loadFindings(); }
    if (tab === "Compliance") loadCompliance();
    if (tab === "Resources") loadResources();
    if (tab === "Trends") loadTrends();
  };

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
        <button onClick={handleRefresh} className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-sm font-medium transition ${
              tab === t
                ? "border-b-2 border-indigo-500 text-white"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "Findings" && (
        <FindingsTab
          stats={stats}
          data={data}
          loading={loading}
          page={page}
          setPage={setPage}
          search={search}
          setSearch={setSearch}
          selSeverity={selSeverity}
          setSelSeverity={setSelSeverity}
          selCategory={selCategory}
          setSelCategory={setSelCategory}
          selSource={selSource}
          setSelSource={setSelSource}
          selCloud={selCloud}
          setSelCloud={setSelCloud}
          toggle={toggle}
        />
      )}
      {tab === "Compliance" && (
        <ComplianceTab data={compliance} loading={compLoading} />
      )}
      {tab === "Resources" && (
        <ResourcesTab
          data={resources}
          loading={resLoading}
          search={resSearch}
          setSearch={setResSearch}
          cloud={resCloud}
          setCloud={setResCloud}
          page={resPage}
          setPage={setResPage}
          onRowClick={goToResourceFindings}
        />
      )}
      {tab === "Trends" && (
        <TrendsTab data={trends} loading={trendsLoading} days={trendDays} setDays={setTrendDays} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  StatCard (unchanged)                                               */
/* ------------------------------------------------------------------ */

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">{icon}<span className="text-sm text-gray-400">{label}</span></div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Findings Tab                                                       */
/* ------------------------------------------------------------------ */

function FindingsTab({
  stats, data, loading, page, setPage,
  search, setSearch, selSeverity, setSelSeverity,
  selCategory, setSelCategory, selSource, setSelSource,
  selCloud, setSelCloud, toggle,
}: {
  stats: CSPMDashboardStats | null;
  data: PaginatedFindings | null;
  loading: boolean;
  page: number;
  setPage: (p: number) => void;
  search: string;
  setSearch: (s: string) => void;
  selSeverity: string[];
  setSelSeverity: (v: string[]) => void;
  selCategory: string[];
  setSelCategory: (v: string[]) => void;
  selSource: string[];
  setSelSource: (v: string[]) => void;
  selCloud: string | null;
  setSelCloud: (v: string | null) => void;
  toggle: (arr: string[], val: string) => string[];
}) {
  return (
    <div className="space-y-6">
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
                      <span>{categoryIcons[c.category] || "\u{1F4CC}"}</span>
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
                        {categoryIcons[m.category] || "\u{1F4CC}"} {m.category}
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

/* ------------------------------------------------------------------ */
/*  Compliance Tab                                                     */
/* ------------------------------------------------------------------ */

function passRateColor(rate: number): string {
  if (rate > 80) return "text-emerald-400";
  if (rate >= 50) return "text-yellow-400";
  return "text-red-400";
}

function passRateBorderColor(rate: number): string {
  if (rate > 80) return "border-emerald-500/30";
  if (rate >= 50) return "border-yellow-500/30";
  return "border-red-500/30";
}

function passRateBarColor(rate: number): string {
  if (rate > 80) return "bg-emerald-500";
  if (rate >= 50) return "bg-yellow-500";
  return "bg-red-500";
}

function ComplianceTab({ data, loading }: { data: ComplianceFramework[] | null; loading: boolean }) {
  if (loading || !data) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (data.length === 0) {
    return <div className="py-12 text-center text-gray-500">No compliance data available</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((fw) => (
        <div
          key={fw.framework}
          className={cn(
            "rounded-xl border bg-gray-900/50 p-5 transition-colors hover:bg-gray-800/40",
            passRateBorderColor(fw.pass_rate)
          )}
        >
          {/* Framework name & pass rate */}
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">{fw.framework}</h3>
              <p className="mt-0.5 text-xs text-gray-500">{fw.total_controls} controls</p>
            </div>
            <div className="flex flex-col items-center">
              {/* Circular progress indicator */}
              <div className="relative h-14 w-14">
                <svg className="h-14 w-14 -rotate-90" viewBox="0 0 56 56">
                  <circle cx="28" cy="28" r="24" fill="none" stroke="currentColor" strokeWidth="4" className="text-gray-800" />
                  <circle
                    cx="28"
                    cy="28"
                    r="24"
                    fill="none"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${(fw.pass_rate / 100) * 150.8} 150.8`}
                    className={passRateColor(fw.pass_rate)}
                    stroke="currentColor"
                  />
                </svg>
                <span className={cn("absolute inset-0 flex items-center justify-center text-xs font-bold", passRateColor(fw.pass_rate))}>
                  {Math.round(fw.pass_rate)}%
                </span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-gray-800">
            <div className={cn("h-full rounded-full transition-all", passRateBarColor(fw.pass_rate))} style={{ width: `${fw.pass_rate}%` }} />
          </div>

          {/* Breakdown */}
          <div className="mt-4 flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1 text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" /> {fw.passed} Passed
            </span>
            <span className="flex items-center gap-1 text-red-400">
              <XCircle className="h-3.5 w-3.5" /> {fw.failed} Failed
            </span>
            <span className="flex items-center gap-1 text-gray-500">
              <MinusCircle className="h-3.5 w-3.5" /> {fw.suppressed} Suppressed
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Resources Tab                                                      */
/* ------------------------------------------------------------------ */

function ResourcesTab({
  data, loading, search, setSearch, cloud, setCloud, page, setPage, onRowClick,
}: {
  data: PaginatedResources | null;
  loading: boolean;
  search: string;
  setSearch: (s: string) => void;
  cloud: string | null;
  setCloud: (c: string | null) => void;
  page: number;
  setPage: (p: number) => void;
  onRowClick: (name: string) => void;
}) {
  return (
    <div className="space-y-4">
      {/* Search + cloud filter */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search resources..."
            className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="flex gap-1.5">
          {CLOUDS.map((c) => (
            <button
              key={c}
              onClick={() => setCloud(cloud === c ? null : c)}
              className={cn(
                "rounded-md border px-2.5 py-1.5 text-xs font-medium transition-all",
                cloud === c
                  ? "border-purple-500/40 bg-purple-500/15 text-purple-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {loading && !data ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/70">
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Resource Name</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Type</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Region</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Cloud</th>
                  <th className="px-3 py-3 text-right font-medium text-gray-400">Findings</th>
                  <th className="px-3 py-3 text-right font-medium text-gray-400">Critical</th>
                  <th className="px-3 py-3 text-right font-medium text-gray-400">Open</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Worst Severity</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Frameworks</th>
                  <th className="px-3 py-3 text-left font-medium text-gray-400">Last Seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {(data?.items || []).map((r) => (
                  <tr
                    key={r.resource_id}
                    onClick={() => onRowClick(r.resource_name || r.resource_id)}
                    className="cursor-pointer transition-colors hover:bg-gray-800/30"
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <Server className="h-3.5 w-3.5 shrink-0 text-gray-500" />
                        <span className="max-w-[200px] truncate text-sm text-white">{r.resource_name || r.resource_id}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{r.resource_type}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{r.region}</td>
                    <td className="px-3 py-2.5">
                      <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] font-medium text-gray-300">{r.cloud_provider}</span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm text-white">{r.total_findings}</td>
                    <td className="px-3 py-2.5 text-right">
                      <span className={cn("text-sm font-medium", r.critical_findings > 0 ? "text-red-400" : "text-gray-500")}>
                        {r.critical_findings}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right text-sm text-orange-400">{r.open_findings}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={r.worst_severity} /></td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {r.frameworks.slice(0, 3).map((f) => (
                          <span key={f} className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">{f}</span>
                        ))}
                        {r.frameworks.length > 3 && (
                          <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">+{r.frameworks.length - 3}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-500">{new Date(r.last_seen).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && <div className="py-12 text-center text-gray-500">No resources match your filters</div>}
          </div>
          {data && data.total_pages > 1 && (
            <Pagination page={data.page} totalPages={data.total_pages} total={data.total} pageSize={data.page_size} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Trends Tab                                                         */
/* ------------------------------------------------------------------ */

function TrendsTab({
  data, loading, days, setDays,
}: {
  data: TrendsData | null;
  loading: boolean;
  days: number;
  setDays: (d: number) => void;
}) {
  if (loading || !data) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  const maxVal = Math.max(...data.days.map((d) => Math.max(d.new_findings, d.resolved)), 1);

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-gray-500" />
        <span className="text-xs text-gray-500">Period:</span>
        {[7, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs font-medium transition-all",
              days === d
                ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-400"
                : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
            )}
          >
            {d}d
          </button>
        ))}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          icon={<AlertTriangle className="h-5 w-5 text-red-400" />}
          label={`New Findings (${days}d)`}
          value={data.summary.new_findings.toLocaleString()}
        />
        <StatCard
          icon={<CheckCircle2 className="h-5 w-5 text-emerald-400" />}
          label={`Resolved (${days}d)`}
          value={data.summary.resolved.toLocaleString()}
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5 text-orange-400" />}
          label="Currently Open"
          value={data.summary.currently_open.toLocaleString()}
        />
      </div>

      {/* Timeline chart */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-400">Daily Activity</h2>
          <div className="flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-red-500" /> New
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Resolved
            </span>
          </div>
        </div>

        {/* Chart area */}
        <div className="flex items-end gap-px" style={{ height: 180 }}>
          {data.days.map((day, i) => {
            const newH = (day.new_findings / maxVal) * 160;
            const resH = (day.resolved / maxVal) * 160;
            const dateObj = new Date(day.date);
            const label = `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;
            const showLabel = data.days.length <= 14 || i % Math.ceil(data.days.length / 14) === 0;

            return (
              <div key={day.date} className="group relative flex flex-1 flex-col items-center justify-end">
                {/* Tooltip */}
                <div className="pointer-events-none absolute -top-10 z-10 hidden rounded bg-gray-800 px-2 py-1 text-[10px] text-gray-200 shadow-lg group-hover:block whitespace-nowrap">
                  {label}: {day.new_findings} new, {day.resolved} resolved
                </div>

                {/* Stacked bars side by side */}
                <div className="flex w-full items-end justify-center gap-px">
                  <div
                    className="rounded-t bg-red-500/80 transition-all hover:bg-red-500"
                    style={{ height: Math.max(newH, day.new_findings > 0 ? 2 : 0), width: "45%" }}
                  />
                  <div
                    className="rounded-t bg-emerald-500/80 transition-all hover:bg-emerald-500"
                    style={{ height: Math.max(resH, day.resolved > 0 ? 2 : 0), width: "45%" }}
                  />
                </div>

                {/* Date label */}
                {showLabel && (
                  <span className="mt-1.5 text-[9px] text-gray-600">{label}</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Data table below chart */}
      <div className="overflow-hidden rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900/70">
              <th className="px-3 py-3 text-left font-medium text-gray-400">Date</th>
              <th className="px-3 py-3 text-right font-medium text-gray-400">New Findings</th>
              <th className="px-3 py-3 text-right font-medium text-gray-400">Resolved</th>
              <th className="px-3 py-3 text-left font-medium text-gray-400">Net Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {data.days.slice().reverse().slice(0, 14).map((day) => {
              const net = day.new_findings - day.resolved;
              return (
                <tr key={day.date} className="transition-colors hover:bg-gray-800/30">
                  <td className="px-3 py-2.5 text-xs text-gray-300">{new Date(day.date).toLocaleDateString()}</td>
                  <td className="px-3 py-2.5 text-right text-sm text-red-400">{day.new_findings}</td>
                  <td className="px-3 py-2.5 text-right text-sm text-emerald-400">{day.resolved}</td>
                  <td className="px-3 py-2.5">
                    <span className={cn("flex items-center gap-1 text-sm font-medium", net > 0 ? "text-red-400" : net < 0 ? "text-emerald-400" : "text-gray-500")}>
                      {net > 0 ? "+" : ""}{net}
                      {net !== 0 && <ArrowRight className={cn("h-3 w-3", net > 0 ? "rotate-[-45deg]" : "rotate-[45deg]")} />}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
