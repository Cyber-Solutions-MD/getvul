"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Bug, AlertTriangle, ShieldAlert, Flame, Link2, Clock,
  Loader2, Server, Ticket, Users, Plug, TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import ExportButton from "@/components/ui/ExportButton";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useToast } from "@/components/ui/ToastProvider";
import type { DashboardStats } from "@/types/vulnerability";

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "report">("overview");
  const [trendDays, setTrendDays] = useState(30);

  useEffect(() => {
    Promise.all([
      api<DashboardStats>("/api/v1/vulnerabilities/stats").catch(() => null),
      api("/api/v1/vulnerabilities/overview").catch(() => null),
      api(`/api/v1/vulnerabilities/trends?days=${trendDays}`).catch(() => null),
    ]).then(([s, o, t]) => {
      setStats(s);
      setOverview(o);
      setTrends(t);
    }).finally(() => setLoading(false));
  }, [trendDays]);

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>;

  const sevColors: Record<string, string> = {
    CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
    HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };

  const riskColor = (s: number) => s >= 80 ? "text-red-400" : s >= 50 ? "text-orange-400" : s >= 20 ? "text-yellow-400" : "text-green-400";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      <div className="flex gap-4 border-b border-gray-700">
        <button onClick={() => setTab("overview")}
          className={`pb-2 text-sm font-medium transition ${tab === "overview" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          Overview
        </button>
        <button onClick={() => setTab("report")}
          className={`pb-2 text-sm font-medium transition ${tab === "report" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          Executive Report
        </button>
      </div>

      {tab === "report" && <ReportBuilder />}

      {tab === "overview" && <>

      {/* Top stat cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={<Bug className="h-5 w-5 text-indigo-400" />} label="Total Vulnerabilities" value={stats.total_vulnerabilities} />
          <StatCard icon={<AlertTriangle className="h-5 w-5 text-orange-400" />} label="Open" value={stats.open_vulnerabilities} />
          <StatCard icon={<Flame className="h-5 w-5 text-red-400" />} label="Exploitable" value={stats.exploitable_count} />
          <StatCard icon={<ShieldAlert className="h-5 w-5 text-red-400" />} label="CISA KEV" value={stats.cisa_kev_count} />
        </div>
      )}

      {/* Second row — tickets + risk + MTTR */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {overview?.tickets && (
          <>
            <StatCard icon={<Ticket className="h-5 w-5 text-orange-400" />} label="Open Tickets" value={overview.tickets.open}
              sub={overview.tickets.overdue > 0 ? `${overview.tickets.overdue} overdue` : undefined} subColor="text-red-400" />
            <StatCard icon={<Ticket className="h-5 w-5 text-emerald-400" />} label="Resolved Tickets" value={overview.tickets.resolved} />
          </>
        )}
        {stats && (
          <>
            <StatCard icon={<Link2 className="h-5 w-5 text-emerald-400" />} label="Correlated CVEs" value={stats.correlated_cves} />
            <StatCard icon={<Clock className="h-5 w-5 text-blue-400" />} label="MTTR" value={stats.mttr_days ? `${stats.mttr_days}d` : "N/A"} text />
          </>
        )}
      </div>

      {/* SLA Compliance */}
      {overview?.sla && overview.sla.open_with_sla > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-400">SLA Compliance</h2>
            <span className={`text-2xl font-bold ${
              overview.sla.compliance_pct >= 90 ? "text-emerald-400" :
              overview.sla.compliance_pct >= 70 ? "text-yellow-400" : "text-red-400"
            }`}>
              {overview.sla.compliance_pct}%
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3">
              <p className="text-xs text-gray-500">SLA Breached</p>
              <p className="text-xl font-bold text-red-400">{overview.sla.breached}</p>
            </div>
            <div className="rounded-lg border border-orange-500/20 bg-orange-500/5 p-3">
              <p className="text-xs text-gray-500">At Risk (72h)</p>
              <p className="text-xl font-bold text-orange-400">{overview.sla.at_risk}</p>
            </div>
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
              <p className="text-xs text-gray-500">Within SLA</p>
              <p className="text-xl font-bold text-emerald-400">{overview.sla.within_sla}</p>
            </div>
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-3">
              <p className="text-xs text-gray-500">Avg Days Left</p>
              <p className="text-xl font-bold text-blue-400">{overview.sla.avg_days_remaining ?? "—"}</p>
            </div>
          </div>
          {/* Breach by severity */}
          {overview.sla.breached > 0 && overview.sla.breach_by_severity && (
            <div className="mt-3 flex items-center gap-3 text-xs">
              <span className="text-gray-500">Breached by severity:</span>
              {Object.entries(overview.sla.breach_by_severity as Record<string, number>).map(([sev, count]) => (
                <span key={sev} className={`rounded px-1.5 py-0.5 ${
                  sev === "CRITICAL" ? "bg-red-500/20 text-red-400" :
                  sev === "HIGH" ? "bg-orange-500/20 text-orange-400" :
                  "bg-yellow-500/20 text-yellow-400"
                }`}>{sev}: {count}</span>
              ))}
            </div>
          )}
          {/* SLA policy */}
          <div className="mt-3 flex items-center gap-2 text-[10px] text-gray-600">
            <span>SLA Policy:</span>
            {Object.entries(overview.sla.sla_config as Record<string, number>).map(([sev, days]) => (
              <span key={sev}>{sev}={days}d</span>
            ))}
          </div>
        </div>
      )}

      {/* Trend Analytics */}
      {trends?.vuln_trends?.timeline?.length > 0 && (
        <div className="space-y-6">
          {/* Period selector */}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-400">Vulnerability Trends</h2>
            <div className="flex items-center gap-1 rounded-lg border border-gray-700 bg-gray-800 p-0.5">
              {[7, 30, 90].map(d => (
                <button key={d} onClick={() => setTrendDays(d)}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition ${trendDays === d ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}>
                  {d}d
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* New vs Resolved chart */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-400">New vs Resolved</h3>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" />New: {trends.vuln_trends.totals.new.toLocaleString()}</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-400" />Resolved: {trends.vuln_trends.totals.resolved.toLocaleString()}</span>
                </div>
              </div>
              <BarChart data={trends.vuln_trends.timeline} />
            </div>

            {/* Severity trend */}
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h3 className="text-sm font-medium text-gray-400 mb-4">New Vulns by Severity</h3>
              <SeverityChart data={trends.vuln_trends.timeline} />
            </div>
          </div>

          {/* MTTR Trend */}
          {trends.mttr_trend?.length > 1 && (
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
              <h3 className="text-sm font-medium text-gray-400 mb-4">Mean Time to Remediate (Weekly)</h3>
              <MttrChart data={trends.mttr_trend} />
            </div>
          )}

          {/* Snapshot trend (if available) */}
          {trends.risk_trend?.length > 1 && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
                <h3 className="text-sm font-medium text-gray-400 mb-4">Open Vulnerabilities Over Time</h3>
                <LineChart data={trends.risk_trend} dataKey="open_vulns" color="text-orange-400" />
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
                <h3 className="text-sm font-medium text-gray-400 mb-4">Average Risk Score</h3>
                <LineChart data={trends.risk_trend} dataKey="avg_risk" color="text-red-400" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

        {/* Severity breakdown */}
        {stats && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Vulnerabilities by Severity</h2>
            <div className="space-y-3">
              {stats.by_severity.map(s => (
                <div key={s.severity} className="flex items-center justify-between">
                  <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${sevColors[s.severity] || "bg-gray-700 text-gray-300"}`}>
                    {s.severity}
                  </span>
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                      <div className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%` }} />
                    </div>
                    <span className="w-16 text-right text-sm font-medium text-white">{s.count.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk distribution */}
        {overview?.risk_distribution && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Asset Risk Distribution</h2>
            <div className="space-y-3">
              {[
                { label: "Critical (80+)", count: overview.risk_distribution.critical, color: "bg-red-500" },
                { label: "High (50-79)", count: overview.risk_distribution.high, color: "bg-orange-500" },
                { label: "Medium (20-49)", count: overview.risk_distribution.medium, color: "bg-yellow-500" },
                { label: "Low (<20)", count: overview.risk_distribution.low, color: "bg-green-500" },
              ].map(r => {
                const total = Object.values(overview.risk_distribution as Record<string, number>).reduce((a: number, b: number) => a + b, 0);
                return (
                  <div key={r.label} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{r.label}</span>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                        <div className={`h-full rounded-full ${r.color}`}
                          style={{ width: `${Math.max(2, total ? (r.count / total) * 100 : 0)}%` }} />
                      </div>
                      <span className="w-16 text-right text-sm font-medium text-white">{r.count.toLocaleString()}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Top 10 Riskiest Hosts */}
        {overview?.top_risky_hosts?.length > 0 && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6 lg:col-span-2">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Top 10 Riskiest Hosts</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-500">
                  <tr>
                    <th className="pb-2">Host</th>
                    <th className="pb-2">Type</th>
                    <th className="pb-2">User</th>
                    <th className="pb-2 text-center">Risk</th>
                    <th className="pb-2 text-center">Vulns</th>
                    <th className="pb-2 text-center">Critical</th>
                    <th className="pb-2 text-center">Exploitable</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {overview.top_risky_hosts.map((h: any) => (
                    <tr key={h.id} className="hover:bg-gray-800/30 cursor-pointer" onClick={() => router.push(`/dashboard/assets/${h.id}`)}>
                      <td className="py-2 text-white font-medium">{h.hostname}</td>
                      <td className="py-2 text-gray-400 text-xs">{h.device_category || "—"}</td>
                      <td className="py-2 text-gray-400 text-xs truncate max-w-[120px]">{h.assigned_user || "—"}</td>
                      <td className="py-2 text-center">
                        <span className={`font-bold ${riskColor(h.risk_score)}`}>{h.risk_score}</span>
                      </td>
                      <td className="py-2 text-center text-gray-300">{h.vuln_count}</td>
                      <td className="py-2 text-center text-red-400">{h.critical}</td>
                      <td className="py-2 text-center text-yellow-400">{h.exploitable}</td>
                      <td className="py-2">
                        {h.host_status && (
                          <span className={`inline-block h-2 w-2 rounded-full ${h.host_status === "normal" ? "bg-green-400" : "bg-gray-500"}`} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Vulnerability Status Breakdown */}
        {overview?.by_status && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Vulnerability Status</h2>
            <div className="space-y-2">
              {[
                { key: "OPEN", label: "Open", color: "bg-orange-500" },
                { key: "IN_PROGRESS", label: "In Progress", color: "bg-blue-500" },
                { key: "REMEDIATED", label: "Remediated", color: "bg-emerald-500" },
                { key: "SUPPRESSED", label: "Suppressed", color: "bg-gray-500" },
              ].map(s => {
                const count = overview.by_status[s.key] || 0;
                const total = Object.values(overview.by_status as Record<string, number>).reduce((a: number, b: number) => a + b, 0);
                return (
                  <div key={s.key} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{s.label}</span>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                        <div className={`h-full rounded-full ${s.color}`}
                          style={{ width: `${Math.max(1, total ? (count / total) * 100 : 0)}%` }} />
                      </div>
                      <span className="w-16 text-right text-sm font-medium text-white">{count.toLocaleString()}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Connector Health */}
        {overview?.connectors?.length > 0 && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Connector Health</h2>
            <div className="space-y-2">
              {overview.connectors.map((c: any) => (
                <div key={c.type} className="flex items-center justify-between rounded-lg bg-gray-800/30 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${c.status === "SUCCESS" ? "bg-emerald-400" : c.status === "FAILED" ? "bg-red-400" : "bg-gray-500"}`} />
                    <span className="text-sm text-white">{c.type}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {c.records && <span>{c.records.toLocaleString()} records</span>}
                    {c.last_sync && <span>{timeAgo(c.last_sync)}</span>}
                    {!c.enabled && <span className="text-gray-600">disabled</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Source breakdown */}
        {stats && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
            <h2 className="mb-4 text-sm font-medium text-gray-400">Vulnerabilities by Source</h2>
            <div className="space-y-3">
              {stats.by_source.map(s => (
                <div key={s.source} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">{s.source}</span>
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                      <div className="h-full rounded-full bg-emerald-500"
                        style={{ width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%` }} />
                    </div>
                    <span className="w-16 text-right text-sm font-medium text-white">{s.count.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick stats row */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">Quick Stats</h2>
          <div className="grid grid-cols-2 gap-4">
            <MiniStat label="Total Assets" value={(overview?.risk_distribution ? Object.values(overview.risk_distribution as Record<string,number>).reduce((a:number,b:number)=>a+b,0) : 0).toLocaleString()} icon={<Server className="h-4 w-4 text-gray-500" />} />
            <MiniStat label="Active Users" value={(overview?.total_users || 0).toLocaleString()} icon={<Users className="h-4 w-4 text-gray-500" />} />
            <MiniStat label="Connectors" value={(overview?.connectors?.length || 0).toString()} icon={<Plug className="h-4 w-4 text-gray-500" />} />
            <MiniStat label="Automation Rules" value="—" icon={<TrendingUp className="h-4 w-4 text-gray-500" />} />
          </div>
        </div>
      </div>
      </>}
    </div>
  );
}

function ReportBuilder() {
  const { toast } = useToast();
  // Saved/scheduled reports
  const [reports, setReports] = useState<any[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);

  const loadReports = useCallback(async () => {
    try { setReports(await api("/api/v1/reports")); } catch {} finally { setLoadingReports(false); }
  }, []);
  useEffect(() => { loadReports(); }, [loadReports]);
  // Sections
  const [sections, setSections] = useState({
    vulns: true, assets: true, risk: true, top_hosts: true, top_remediations: true, tickets: true,
  });
  // Filters
  const [severities, setSeverities] = useState<string[]>(["CRITICAL", "HIGH", "MEDIUM", "LOW"]);
  const [deviceTypes, setDeviceTypes] = useState<string[]>(["WORKSTATION", "SERVER", "NETWORK", "MOBILE"]);
  const [exploitOnly, setExploitOnly] = useState(false);
  const [kevOnly, setKevOnly] = useState(false);
  const [topCount, setTopCount] = useState(5);
  const [minRisk, setMinRisk] = useState(0);
  // Output
  const [format, setFormat] = useState("pdf");
  const [generating, setGenerating] = useState(false);

  const toggleArr = (arr: string[], item: string, setter: (v: string[]) => void) =>
    setter(arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item]);
  const toggle = (key: string) => setSections(s => ({ ...s, [key]: !s[key as keyof typeof s] }));

  async function handleGenerate() {
    setGenerating(true);
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("getvul_token") || "dev-token" : "dev-token";
      const params = new URLSearchParams({ format });
      severities.forEach(s => params.append("severity", s));
      deviceTypes.forEach(d => params.append("device_type", d));
      if (exploitOnly) params.set("exploit_available", "true");
      if (kevOnly) params.set("cisa_kev", "true");
      params.set("top_count", String(topCount));
      params.set("min_risk", String(minRisk));
      // Pass sections
      Object.entries(sections).forEach(([k, v]) => { if (v) params.append("section", k); });

      let resp = await fetch(`${API}/api/v1/export/summary?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Auto-refresh on 401
      if (resp.status === 401) {
        const refresh = localStorage.getItem("getvul_refresh");
        if (refresh) {
          const rr = await fetch(`${API}/auth/refresh`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refresh }),
          });
          if (rr.ok) {
            const data = await rr.json();
            localStorage.setItem("getvul_token", data.access_token);
            resp = await fetch(`${API}/api/v1/export/summary?${params}`, {
              headers: { Authorization: `Bearer ${data.access_token}` },
            });
          } else {
            window.location.href = "/login";
            return;
          }
        } else {
          window.location.href = "/login";
          return;
        }
      }

      if (!resp.ok) {
        const err = await resp.text().catch(() => "Unknown error");
        toast({ title: "Export Failed", message: err, variant: "error" });
        return;
      }

      const blob = await resp.blob();
      const ext = format === "pdf" ? "pdf" : format === "csv" ? "csv" : "txt";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `getvul_executive_report.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast({ title: "Export Error", message: e.message, variant: "error" });
    } finally { setGenerating(false); }
  }

  return (
    <div className="space-y-6">
      {/* Sections */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-medium text-white mb-1">Report Sections</h2>
        <p className="text-sm text-gray-400 mb-4">Select what to include in the report</p>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {[
            { key: "vulns", label: "Vulnerability Overview" },
            { key: "assets", label: "Assets by Type" },
            { key: "risk", label: "Risk Distribution" },
            { key: "top_hosts", label: "Top Riskiest Hosts" },
            { key: "top_remediations", label: "Top Remediations" },
            { key: "tickets", label: "Ticket Status" },
          ].map(s => (
            <label key={s.key} className={`flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition ${
              sections[s.key as keyof typeof sections] ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-800"}`}>
              <input type="checkbox" checked={sections[s.key as keyof typeof sections]}
                onChange={() => toggle(s.key)} className="rounded border-gray-600" />
              <span className="text-sm text-white">{s.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-medium text-white mb-1">Filters</h2>
        <p className="text-sm text-gray-400 mb-4">Narrow down what data the report covers</p>

        <div className="space-y-4">
          {/* Severity */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-300">Vulnerability Severities</label>
            <div className="flex flex-wrap gap-2">
              {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(s => (
                <button key={s} onClick={() => toggleArr(severities, s, setSeverities)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                    severities.includes(s) ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-500"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Device types */}
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-300">Device Types</label>
            <div className="flex flex-wrap gap-2">
              {["WORKSTATION", "SERVER", "NETWORK", "MOBILE"].map(d => (
                <button key={d} onClick={() => toggleArr(deviceTypes, d, setDeviceTypes)}
                  className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                    deviceTypes.includes(d) ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-500"}`}>
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {/* Exploit / KEV */}
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" checked={exploitOnly} onChange={e => setExploitOnly(e.target.checked)} className="rounded border-gray-600" />
              Exploitable only
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input type="checkbox" checked={kevOnly} onChange={e => setKevOnly(e.target.checked)} className="rounded border-gray-600" />
              CISA KEV only
            </label>

            {/* Top N */}
            <div>
              <label className="mb-1 block text-xs text-gray-400">Top hosts/remediations</label>
              <div className="flex gap-2">
                {[3, 5, 10, 20].map(n => (
                  <button key={n} onClick={() => setTopCount(n)}
                    className={`rounded-md border px-2 py-1 text-xs ${topCount === n ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-500"}`}>
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {/* Min risk */}
            <div>
              <label className="mb-1 block text-xs text-gray-400">Min risk score</label>
              <div className="flex gap-2">
                {[0, 20, 50, 80].map(r => (
                  <button key={r} onClick={() => setMinRisk(r)}
                    className={`rounded-md border px-2 py-1 text-xs ${minRisk === r ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-500"}`}>
                    {r === 0 ? "Any" : `${r}+`}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Format + Generate */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">Format:</span>
            {[
              { id: "pdf", label: "PDF", icon: "📄" },
              { id: "csv", label: "CSV", icon: "📊" },
              { id: "txt", label: "Text", icon: "📝" },
            ].map(f => (
              <button key={f.id} onClick={() => setFormat(f.id)}
                className={`rounded-lg border px-4 py-2 text-sm transition ${
                  format === f.id ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-800 text-gray-400"}`}>
                {f.icon} {f.label}
              </button>
            ))}
          </div>

          <button onClick={handleGenerate} disabled={generating || Object.values(sections).every(v => !v)}
            className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {generating ? "Generating..." : "Generate Report"}
          </button>
        </div>

        {/* Summary */}
        <div className="mt-4 rounded-lg bg-gray-800/50 p-3 text-xs text-gray-500">
          Report will include: {Object.entries(sections).filter(([,v]) => v).map(([k]) => k).join(", ")} |
          Severities: {severities.join(", ") || "all"} |
          Devices: {deviceTypes.join(", ") || "all"} |
          {exploitOnly ? " Exploitable only |" : ""}{kevOnly ? " CISA KEV only |" : ""}
          Top {topCount} | Min risk {minRisk}+ | Format: {format.toUpperCase()}
        </div>
      </div>

      {/* Save as Scheduled Report */}
      <ScheduleReportSection
        currentConfig={{
          sections: Object.entries(sections).filter(([,v]) => v).map(([k]) => k),
          filters: {
            severity: severities, device_type: deviceTypes,
            ...(exploitOnly ? { exploit_available: true } : {}),
            ...(kevOnly ? { cisa_kev: true } : {}),
            top_count: topCount, min_risk: minRisk,
          },
          format,
        }}
        reports={reports}
        onReload={loadReports}
      />
    </div>
  );
}

function ScheduleReportSection({ currentConfig, reports, onReload }: {
  currentConfig: { sections: string[]; filters: any; format: string };
  reports: any[];
  onReload: () => void;
}) {
  const [showSave, setShowSave] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<any>(null);
  const [saveSchedule, setSaveSchedule] = useState("weekly");
  const [saveRecipients, setSaveRecipients] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSaveSchedule() {
    if (!saveName.trim() || !saveRecipients.trim()) return;
    setSaving(true);
    try {
      await api("/api/v1/reports", {
        method: "POST",
        body: JSON.stringify({
          name: saveName,
          schedule: saveSchedule,
          format: currentConfig.format,
          recipients: saveRecipients.split(",").map((e: string) => e.trim()).filter(Boolean),
          sections: currentConfig.sections,
          filters: currentConfig.filters,
        }),
      });
      setSaveName(""); setSaveRecipients(""); setShowSave(false);
      onReload();
    } catch {} finally { setSaving(false); }
  }

  return (
    <div className="space-y-4">
      {/* Save as scheduled */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-medium text-white">Schedule This Report</h3>
            <p className="text-xs text-gray-500">Save the current configuration as a recurring scheduled report</p>
          </div>
          {!showSave && (
            <button onClick={() => setShowSave(true)}
              className="rounded-lg border border-indigo-500/50 bg-indigo-500/10 px-4 py-2 text-sm text-indigo-400 hover:bg-indigo-500/20">
              + Schedule
            </button>
          )}
        </div>

        {showSave && (
          <div className="space-y-3 border-t border-gray-700 pt-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-gray-400">Report Name</label>
                <input value={saveName} onChange={e => setSaveName(e.target.value)} placeholder="Weekly Security Summary"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">Recipients (comma-separated)</label>
                <input value={saveRecipients} onChange={e => setSaveRecipients(e.target.value)} placeholder="ciso@company.com"
                  className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-indigo-500 focus:outline-none" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">Frequency:</span>
              {["daily", "weekly", "monthly"].map(s => (
                <button key={s} onClick={() => setSaveSchedule(s)}
                  className={`rounded-md border px-3 py-1 text-xs capitalize ${saveSchedule === s ? "border-indigo-500 bg-indigo-500/15 text-indigo-400" : "border-gray-700 bg-gray-900 text-gray-500"}`}>
                  {s}
                </button>
              ))}
              <div className="ml-auto flex gap-2">
                <button onClick={handleSaveSchedule} disabled={saving || !saveName.trim() || !saveRecipients.trim()}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">
                  {saving ? "Saving..." : "Save Schedule"}
                </button>
                <button onClick={() => setShowSave(false)} className="text-xs text-gray-500">Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Existing scheduled reports */}
      {reports.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h3 className="text-sm font-medium text-white mb-3">Scheduled Reports ({reports.length})</h3>
          <div className="space-y-2">
            {reports.map((r: any) => (
              <div key={r.id} className={`flex items-center justify-between rounded-lg border px-4 py-3 ${r.is_enabled ? "border-gray-700 bg-gray-800/50" : "border-gray-800 opacity-50"}`}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${r.is_enabled ? "bg-emerald-400" : "bg-gray-500"}`} />
                    <span className="text-sm text-white">{r.name}</span>
                    <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">{r.schedule}</span>
                    <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">{r.format?.toUpperCase()}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500 ml-4">
                    {(r.recipients || []).join(", ")}
                    {r.last_sent_at && <span> · Last: {new Date(r.last_sent_at).toLocaleDateString()}</span>}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={async () => { await api(`/api/v1/reports/${r.id}/send`, { method: "POST" }); onReload(); }}
                    className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:text-white">Send</button>
                  <button onClick={async () => { await api(`/api/v1/reports/${r.id}`, { method: "PATCH", body: JSON.stringify({ is_enabled: !r.is_enabled }) }); onReload(); }}
                    className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:text-white">{r.is_enabled ? "Pause" : "Enable"}</button>
                  <button onClick={() => setDeleteTarget(r)}
                    className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-500 hover:text-red-400">Delete</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmModal
        open={!!deleteTarget}
        title="Delete Report"
        message={deleteTarget ? `Delete "${deleteTarget.name}"?` : ""}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={async () => {
          if (deleteTarget) {
            await api(`/api/v1/reports/${deleteTarget.id}`, { method: "DELETE" });
            onReload();
          }
          setDeleteTarget(null);
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

function StatCard({ icon, label, value, sub, subColor, text }: {
  icon: React.ReactNode; label: string; value: number | string; sub?: string; subColor?: string; text?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <p className={`mt-3 ${text ? "text-lg" : "text-2xl"} font-bold text-white`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {sub && <p className={`mt-1 text-xs ${subColor || "text-gray-500"}`}>{sub}</p>}
    </div>
  );
}

function MiniStat({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      {icon}
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-sm font-medium text-white">{value}</p>
      </div>
    </div>
  );
}

// ── Trend Chart Components (pure CSS, no chart library) ──

function BarChart({ data }: { data: { date: string; new: number; resolved: number }[] }) {
  const maxVal = Math.max(...data.map(d => Math.max(d.new, d.resolved)), 1);
  const showEvery = data.length > 14 ? Math.ceil(data.length / 7) : 1;

  return (
    <div className="flex items-end gap-px h-32">
      {data.map((d, i) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-px group relative" title={`${d.date}: +${d.new} new, -${d.resolved} resolved`}>
          <div className="w-full flex flex-col-reverse gap-px">
            <div className="w-full rounded-t bg-red-400/80" style={{ height: `${Math.max(1, (d.new / maxVal) * 100)}px` }} />
          </div>
          <div className="w-full flex flex-col gap-px">
            <div className="w-full rounded-b bg-emerald-400/80" style={{ height: `${Math.max(0, (d.resolved / maxVal) * 100)}px` }} />
          </div>
          {i % showEvery === 0 && (
            <span className="text-[8px] text-gray-600 mt-1 whitespace-nowrap">{d.date.slice(5)}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function SeverityChart({ data }: { data: { date: string; by_severity: Record<string, number> }[] }) {
  const maxVal = Math.max(...data.map(d => Object.values(d.by_severity).reduce((a, b) => a + b, 0)), 1);
  const colors = { CRITICAL: "bg-red-500", HIGH: "bg-orange-500", MEDIUM: "bg-yellow-500", LOW: "bg-blue-500" };
  const showEvery = data.length > 14 ? Math.ceil(data.length / 7) : 1;

  return (
    <div>
      <div className="flex items-center gap-4 mb-2 text-[10px]">
        {Object.entries(colors).map(([sev, color]) => (
          <span key={sev} className="flex items-center gap-1"><span className={`h-2 w-2 rounded-full ${color}`} />{sev}</span>
        ))}
      </div>
      <div className="flex items-end gap-px h-28">
        {data.map((d, i) => {
          const total = Object.values(d.by_severity).reduce((a, b) => a + b, 0);
          return (
            <div key={d.date} className="flex-1 flex flex-col justify-end" title={`${d.date}: ${JSON.stringify(d.by_severity)}`}>
              <div className="flex flex-col-reverse">
                {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map(sev => {
                  const val = d.by_severity[sev] || 0;
                  if (val === 0) return null;
                  return <div key={sev} className={`w-full ${colors[sev]}`} style={{ height: `${Math.max(1, (val / maxVal) * 100)}px` }} />;
                })}
              </div>
              {i % showEvery === 0 && (
                <span className="text-[8px] text-gray-600 mt-1 text-center">{d.date.slice(5)}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MttrChart({ data }: { data: { week: string; mttr_days: number | null; count: number }[] }) {
  const values = data.filter(d => d.mttr_days != null).map(d => d.mttr_days!);
  const maxVal = Math.max(...values, 1);

  return (
    <div className="flex items-end gap-2 h-24">
      {data.map(d => (
        <div key={d.week} className="flex-1 flex flex-col items-center gap-1 group" title={`Week of ${d.week}: ${d.mttr_days ?? "—"}d avg (${d.count} vulns)`}>
          <span className="text-[9px] text-gray-500 opacity-0 group-hover:opacity-100">{d.mttr_days != null ? `${d.mttr_days}d` : ""}</span>
          <div className="w-full rounded-t bg-blue-400/70" style={{ height: `${d.mttr_days != null ? Math.max(2, (d.mttr_days / maxVal) * 80) : 0}px` }} />
          <span className="text-[8px] text-gray-600">{d.week?.slice(5) || ""}</span>
        </div>
      ))}
    </div>
  );
}

function LineChart({ data, dataKey, color }: { data: { date: string; [key: string]: any }[]; dataKey: string; color: string }) {
  const values = data.map(d => Number(d[dataKey]) || 0);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values);
  const range = maxVal - minVal || 1;
  const showEvery = data.length > 30 ? Math.ceil(data.length / 10) : data.length > 14 ? 3 : 1;

  // Build SVG path
  const h = 80;
  const w = data.length > 0 ? 100 : 0;
  const points = values.map((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * w;
    const y = h - ((v - minVal) / range) * (h - 10) - 5;
    return `${x},${y}`;
  });
  const pathD = points.length > 0 ? `M ${points.join(" L ")}` : "";

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className={`text-lg font-bold ${color}`}>{values.length > 0 ? values[values.length - 1] : "—"}</span>
        {values.length >= 2 && (
          <span className={`text-xs ${values[values.length - 1] > values[0] ? "text-red-400" : "text-emerald-400"}`}>
            {values[values.length - 1] > values[0] ? "↑" : "↓"} {Math.abs(values[values.length - 1] - values[0])} vs {data.length}d ago
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-20" preserveAspectRatio="none">
        <path d={pathD} fill="none" stroke="currentColor" strokeWidth="1.5" className={color} />
      </svg>
      <div className="flex justify-between text-[8px] text-gray-600 mt-1">
        {data.filter((_, i) => i % showEvery === 0 || i === data.length - 1).map(d => (
          <span key={d.date}>{d.date.slice(5)}</span>
        ))}
      </div>
    </div>
  );
}

function timeAgo(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d ago`;
}
