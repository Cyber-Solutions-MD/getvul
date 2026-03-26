"use client";

import { useCallback, useEffect, useState } from "react";
import { Bug, RefreshCw, Loader2, Pill, Monitor } from "lucide-react";
import ExportButton from "@/components/ui/ExportButton";
import { api } from "@/lib/api";
import VulnFilters, { type VulnFilterState } from "@/components/vulnerabilities/VulnFilters";
import VulnTable from "@/components/vulnerabilities/VulnTable";
import BulkActions from "@/components/vulnerabilities/BulkActions";
import Pagination from "@/components/ui/Pagination";
import { SeverityBadge } from "@/components/ui/Badge";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useToast } from "@/components/ui/ToastProvider";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface PaginatedVulns {
  items: VulnerabilitySummary[];
  total: number; page: number; page_size: number; total_pages: number;
}

interface RemediationGrouped {
  remediation_id: string; remediation_action: string | null;
  affected_product: string | null; affected_hosts: number;
  vuln_count: number; max_severity: string;
  is_suppressed?: boolean; suppressed_count?: number;
}

interface PaginatedRemediations {
  items: RemediationGrouped[];
  total: number; page: number; page_size: number; total_pages: number;
}

interface HostForRemediation {
  asset_id: string; hostname: string; os_name: string | null;
  os_version: string | null; cve_id: string | null; severity: string;
  exploit_available: boolean; cisa_kev: boolean; exploit_status: string | null;
}

interface RemediationForHost {
  remediation_id: string; remediation_action: string | null;
  cve_id: string | null; severity: string; affected_product: string | null;
  exploit_available: boolean; cisa_kev: boolean;
  exploit_status: string | null; exploit_status_id: number | null;
}

const DEFAULT_FILTERS: VulnFilterState = {
  search: "", severity: [], source: [], status: [],
  device_type: null, exploit_available: null, cisa_kev: null,
};

type Tab = "vulnerabilities" | "remediations";

function buildFilterParams(filters: VulnFilterState): URLSearchParams {
  const p = new URLSearchParams();
  filters.severity.forEach((s) => p.append("severity", s));
  filters.source.forEach((s) => p.append("source", s));
  filters.status.forEach((s) => p.append("status", s));
  if (filters.search) p.set("search", filters.search);
  if (filters.device_type) p.set("device_type", filters.device_type);
  if (filters.exploit_available === true) p.set("exploit_only", "true");
  if (filters.cisa_kev === true) p.set("kev_only", "true");
  return p;
}

export default function VulnerabilitiesPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("vulnerabilities");
  const [vulnData, setVulnData] = useState<PaginatedVulns | null>(null);
  const [remData, setRemData] = useState<PaginatedRemediations | null>(null);
  const [filters, setFilters] = useState<VulnFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showSuppressed, setShowSuppressed] = useState<"active" | "ignored" | "all">("active");
  const [showIgnoredVulns, setShowIgnoredVulns] = useState<"active" | "ignored" | "all">("active");
  const [savedFilters, setSavedFilters] = useState<any[]>([]);
  const [showSaveFilter, setShowSaveFilter] = useState(false);
  const [saveFilterName, setSaveFilterName] = useState("");
  const [confirmModal, setConfirmModal] = useState<{ title: string; message: string; variant?: "danger" | "warning" | "info"; onConfirm: () => void } | null>(null);

  // Drill-down states
  const [selectedRemediation, setSelectedRemediation] = useState<RemediationGrouped | null>(null);
  const [remHosts, setRemHosts] = useState<HostForRemediation[] | null>(null);
  const [selectedHostId, setSelectedHostId] = useState<string | null>(null);
  const [selectedHostName, setSelectedHostName] = useState<string>("");
  const [hostRemediations, setHostRemediations] = useState<RemediationForHost[] | null>(null);

  // ── Data fetching ──

  const fetchVulns = useCallback(async () => {
    setLoading(true);
    try {
      const p = buildFilterParams(filters);
      p.set("page", String(page));
      p.set("page_size", "25");
      // Vulns endpoint uses different param names
      p.delete("exploit_only");
      p.delete("kev_only");
      if (filters.exploit_available !== null) p.set("exploit_available", String(filters.exploit_available));
      if (filters.cisa_kev !== null) p.set("cisa_kev", String(filters.cisa_kev));
      // Apply ignored filter via status
      if (showIgnoredVulns === "ignored") {
        p.delete("status");
        p.append("status", "SUPPRESSED");
      } else if (showIgnoredVulns === "active") {
        if (!filters.status.length) {
          p.append("status", "OPEN");
          p.append("status", "IN_PROGRESS");
        }
      }
      // "all" leaves status as-is from filters
      setVulnData(await api<PaginatedVulns>(`/api/v1/vulnerabilities?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters, showIgnoredVulns]);

  const fetchRemediations = useCallback(async () => {
    setLoading(true);
    setRemData(null);  // Clear stale data immediately
    try {
      const p = buildFilterParams(filters);
      p.set("page", String(page));
      p.set("page_size", "25");
      p.set("show_suppressed", showSuppressed);
      setRemData(await api<PaginatedRemediations>(`/api/v1/vulnerabilities/remediations/grouped?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters, showSuppressed]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (tab === "vulnerabilities") fetchVulns();
      else if (!selectedRemediation && !selectedHostId) fetchRemediations();
    }, 300);
    return () => clearTimeout(t);
  }, [tab, fetchVulns, fetchRemediations, selectedRemediation, selectedHostId]);

  // Reset on filter/tab/suppressed change
  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
    setSelectedRemediation(null);
    setRemHosts(null);
    setSelectedHostId(null);
    setHostRemediations(null);
  }, [filters, tab, showSuppressed, showIgnoredVulns]);

  // ── Drill-downs (always pass current filters) ──

  async function drillRemediation(rem: RemediationGrouped) {
    setSelectedRemediation(rem);
    setSelectedHostId(null);
    setHostRemediations(null);
    try {
      const p = buildFilterParams(filters);
      const url = `/api/v1/vulnerabilities/remediations/${encodeURIComponent(rem.remediation_id)}/hosts?${p}`;
      const hosts = await api<HostForRemediation[]>(url);
      setRemHosts(hosts);
    } catch (e) {
      console.error("Failed to fetch hosts for remediation:", e);
      setRemHosts([]);
    }
  }

  async function drillHost(assetId: string, hostname: string) {
    setSelectedHostId(assetId);
    setSelectedHostName(hostname);
    try {
      const p = buildFilterParams(filters);
      const url = `/api/v1/vulnerabilities/hosts/${assetId}/remediations?${p}`;
      const rems = await api<RemediationForHost[]>(url);
      setHostRemediations(rems);
    } catch (e) {
      console.error("Failed to fetch remediations for host:", e);
      setHostRemediations([]);
    }
  }

  // ── Saved filters ──
  const loadSavedFilters = useCallback(async () => {
    try {
      const data = await api<any[]>(`/api/v1/vulnerabilities/saved-filters?filter_type=${tab === "vulnerabilities" ? "vulnerability" : "remediation"}`);
      setSavedFilters(data);
    } catch {}
  }, [tab]);

  useEffect(() => { loadSavedFilters(); }, [loadSavedFilters]);

  async function handleSaveFilter() {
    if (!saveFilterName.trim()) return;
    const filterData: any = { ...filters };
    if (tab === "remediations") filterData.show_suppressed = showSuppressed;
    await api("/api/v1/vulnerabilities/saved-filters", {
      method: "POST",
      body: JSON.stringify({ name: saveFilterName, filter_type: tab === "vulnerabilities" ? "vulnerability" : "remediation", filters: filterData }),
    });
    setSaveFilterName("");
    setShowSaveFilter(false);
    loadSavedFilters();
  }

  function applySavedFilter(sf: any) {
    const f = sf.filters;
    setFilters({
      search: f.search || "",
      severity: f.severity || [],
      source: f.source || [],
      status: f.status || [],
      exploit_available: f.exploit_available ?? null,
      cisa_kev: f.cisa_kev ?? null,
    });
    if (f.show_suppressed) setShowSuppressed(f.show_suppressed);
    setPage(1);
  }

  async function updateSavedFilter(sf: any) {
    setConfirmModal({
      title: "Update Saved Filter",
      message: `Update "${sf.name}" with the current filter settings? This will also update any linked automation rules.`,
      variant: "warning",
      onConfirm: async () => {
        setConfirmModal(null);
        const filterData: any = { ...filters };
        if (tab === "remediations") filterData.show_suppressed = showSuppressed;
        try {
          const result = await api<any>(`/api/v1/vulnerabilities/saved-filters/${sf.id}`, {
            method: "PATCH",
            body: JSON.stringify({ filters: filterData }),
          });
          loadSavedFilters();
          const rulesUpdated = result.rules_updated || 0;
          if (rulesUpdated > 0) toast({ title: "Filter Updated", message: `${rulesUpdated} linked automation rule(s) also updated.`, variant: "success" });
        } catch (e: any) { toast({ title: "Error", message: e.message, variant: "error" }); }
      },
    });
  }

  async function deleteSavedFilter(id: string) {
    await api(`/api/v1/vulnerabilities/saved-filters/${id}`, { method: "DELETE" });
    loadSavedFilters();
  }

  async function createRuleFromFilter(sf: any) {
    const ruleName = prompt("Rule name:", `Rule: ${sf.name}`);
    if (!ruleName) return;
    try {
      const result = await api<any>(`/api/v1/vulnerabilities/saved-filters/${sf.id}/create-rule`, {
        method: "POST",
        body: JSON.stringify({ name: ruleName }),
      });
      toast({ title: "Rule Created", message: `Automation rule "${result.rule_name}" created! Go to Tickets → Automation Rules to configure it.`, variant: "success" });
    } catch (e: any) {
      toast({ title: "Error", message: e.message, variant: "error" });
    }
  }

  async function handleBulkIgnoreCve(action: "ignore" | "unignore") {
    if (selectedIds.size === 0) return;
    const cveIds = [...new Set((vulnData?.items || []).filter(v => selectedIds.has(v.id) && v.cve_id).map(v => v.cve_id!))];
    if (!cveIds.length) return;
    const msg = action === "ignore"
      ? `Ignore ${cveIds.length} CVE(s)? All instances across all hosts will be suppressed.`
      : `Restore ${cveIds.length} CVE(s)? All suppressed instances will be reopened.`;
    setConfirmModal({
      title: action === "ignore" ? "Ignore CVEs" : "Restore CVEs",
      message: msg,
      variant: action === "ignore" ? "warning" : "info",
      onConfirm: async () => {
        setConfirmModal(null);
        try {
          await api("/api/v1/vulnerabilities/bulk-ignore-cve", {
            method: "POST",
            body: JSON.stringify({ cve_ids: cveIds, action }),
          });
          setSelectedIds(new Set());
          fetchVulns();
        } catch (e: any) { toast({ title: "Error", message: e.message, variant: "error" }); }
      },
    });
  }

  function goBackToRemediations() {
    setSelectedRemediation(null);
    setRemHosts(null);
    setSelectedHostId(null);
    setHostRemediations(null);
  }

  function goBackFromHost() {
    setSelectedHostId(null);
    setHostRemediations(null);
  }

  // ── Render ──

  const data = tab === "vulnerabilities" ? vulnData : remData;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="h-6 w-6 text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Vulnerabilities</h1>
            {data && <p className="text-sm text-gray-400">
              {data.total.toLocaleString()} {tab === "vulnerabilities" ? "vulnerabilities" : "remediations"}
            </p>}
          </div>
        </div>
        <button onClick={() => tab === "vulnerabilities" ? fetchVulns() : fetchRemediations()} disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </button>
        <ExportButton resource={tab === "vulnerabilities" ? "vulnerabilities" : "remediations"} />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-900 p-1 w-fit">
        <button onClick={() => setTab("vulnerabilities")}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "vulnerabilities" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Bug className="h-4 w-4" />Vulnerabilities
        </button>
        <button onClick={() => setTab("remediations")}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "remediations" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Pill className="h-4 w-4" />Remediations
        </button>
      </div>

      {/* Filters */}
      <VulnFilters filters={filters} onChange={setFilters} />

      {/* Saved filters bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {savedFilters.map(sf => (
          <div key={sf.id} className="flex items-center gap-1 rounded-lg border border-gray-700 bg-gray-900 pl-3 pr-1 py-1">
            <button onClick={() => applySavedFilter(sf)} className="text-xs text-indigo-400 hover:text-indigo-300 font-medium">{sf.name}</button>
            <button onClick={() => updateSavedFilter(sf)} title="Update filter with current settings"
              className="rounded p-1 text-gray-500 hover:text-emerald-400 text-xs">↑</button>
            <button onClick={() => createRuleFromFilter(sf)} title="Create automation rule"
              className="rounded p-1 text-gray-500 hover:text-orange-400 text-xs">→R</button>
            <button onClick={() => deleteSavedFilter(sf.id)} className="rounded p-1 text-gray-600 hover:text-red-400 text-xs">×</button>
          </div>
        ))}
        {showSaveFilter ? (
          <div className="flex items-center gap-2">
            <input value={saveFilterName} onChange={e => setSaveFilterName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSaveFilter()}
              placeholder="Filter name..." autoFocus
              className="w-40 rounded-lg border border-indigo-500 bg-gray-900 px-2 py-1 text-xs text-white placeholder-gray-600 focus:outline-none" />
            <button onClick={handleSaveFilter} disabled={!saveFilterName.trim()}
              className="rounded bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-500 disabled:opacity-50">Save</button>
            <button onClick={() => { setShowSaveFilter(false); setSaveFilterName(""); }}
              className="text-xs text-gray-500 hover:text-gray-300">Cancel</button>
          </div>
        ) : (
          <button onClick={() => setShowSaveFilter(true)}
            className="rounded-lg border border-dashed border-gray-700 px-3 py-1 text-xs text-gray-500 hover:text-gray-300 hover:border-gray-500">
            + Save current filter
          </button>
        )}
      </div>

      {/* Bulk actions */}
      {selectedIds.size > 0 && tab === "vulnerabilities" && (
        <div className="flex items-center gap-3 rounded-lg border border-gray-700 bg-gray-900 px-4 py-2">
          <span className="text-sm text-gray-400">{selectedIds.size} selected</span>
          {showIgnoredVulns === "ignored" ? (
            <button onClick={() => handleBulkIgnoreCve("unignore")}
              className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20">
              Restore Selected CVEs
            </button>
          ) : (
            <button onClick={() => handleBulkIgnoreCve("ignore")}
              className="rounded-lg border border-orange-500/50 bg-orange-500/10 px-3 py-1.5 text-xs text-orange-400 hover:bg-orange-500/20">
              Ignore Selected CVEs
            </button>
          )}
          <BulkActions selectedCount={selectedIds.size} selectedIds={Array.from(selectedIds)}
            onComplete={() => { setSelectedIds(new Set()); fetchVulns(); }} />
        </div>
      )}
      {selectedIds.size > 0 && tab === "remediations" && (
        <BulkActions selectedCount={selectedIds.size} selectedIds={Array.from(selectedIds)}
          onComplete={() => { setSelectedIds(new Set()); fetchVulns(); }} />
      )}

      {/* Content */}
      {loading && !data ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : tab === "vulnerabilities" ? (
        /* ── Vulnerabilities tab ── */
        <>
          <div className="flex items-center gap-2 mb-3">
            {(["active", "ignored", "all"] as const).map(mode => (
              <button key={mode} onClick={() => { setShowIgnoredVulns(mode); setPage(1); setSelectedIds(new Set()); }}
                className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                  showIgnoredVulns === mode
                    ? "border-indigo-500 bg-indigo-500/15 text-indigo-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {mode === "active" ? "Active" : mode === "ignored" ? "Ignored" : "All"}
              </button>
            ))}
          </div>
          <VulnTable
            vulnerabilities={vulnData?.items || []}
            selectedIds={selectedIds}
            onSelectToggle={(id) => setSelectedIds((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; })}
            onSelectAll={(ids) => setSelectedIds(ids.length ? new Set(ids) : new Set())}
            onHostClick={(assetId, hostname) => { setTab("remediations"); drillHost(assetId, hostname); }}
            onRefresh={fetchVulns}
            showIgnored={showIgnoredVulns}
          />
          {vulnData && vulnData.total_pages > 1 && (
            <Pagination page={vulnData.page} totalPages={vulnData.total_pages}
              total={vulnData.total} pageSize={vulnData.page_size} onPageChange={setPage} />
          )}
        </>
      ) : selectedHostId && hostRemediations ? (
        /* ── Drill-down: remediations for a host ── */
        <div className="space-y-4">
          <div>
            <button onClick={goBackFromHost} className="text-xs text-indigo-400 hover:text-indigo-300">
              ← {selectedRemediation ? "Back to affected hosts" : "Back to remediations"}
            </button>
            <h2 className="mt-1 text-lg font-medium text-white flex items-center gap-2">
              <Monitor className="h-5 w-5 text-gray-400" />{selectedHostName}
            </h2>
            <p className="text-sm text-gray-400">{hostRemediations.length} remediations needed</p>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {hostRemediations.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-800/30">
                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{r.cve_id}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={r.severity} /></td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[150px] truncate">{r.affected_product}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-300 max-w-[300px] truncate">{r.remediation_action || "—"}</td>
                    <td className="px-3 py-2.5"><ExploitBadge status={r.exploit_status} available={r.exploit_available} /></td>
                    <td className="px-3 py-2.5">{r.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hostRemediations.length === 0 && <div className="py-12 text-center text-gray-500">No remediations match your filters for this host</div>}
          </div>
        </div>
      ) : selectedRemediation && remHosts ? (
        /* ── Drill-down: hosts affected by a remediation ── */
        <div className="space-y-4">
          <div>
            <button onClick={goBackToRemediations} className="text-xs text-indigo-400 hover:text-indigo-300">← Back to remediations</button>
            <h2 className="mt-1 text-lg font-medium text-white">{selectedRemediation.remediation_action || "Unknown remediation"}</h2>
            <p className="text-sm text-gray-400">{selectedRemediation.affected_product} · {remHosts.length} matching entries</p>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Hostname</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit Status</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">CISA KEV</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">OS</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {remHosts.map((h, i) => (
                  <tr key={i} className="hover:bg-gray-800/30 cursor-pointer" onClick={() => drillHost(h.asset_id, h.hostname)}>
                    <td className="px-3 py-2.5 text-indigo-400 hover:text-indigo-300">{h.hostname}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{h.cve_id}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={h.severity} /></td>
                    <td className="px-3 py-2.5"><ExploitBadge status={h.exploit_status} available={h.exploit_available} /></td>
                    <td className="px-3 py-2.5">{h.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{h.os_name} {h.os_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {remHosts.length === 0 && <div className="py-12 text-center text-gray-500">No hosts match your filters for this remediation</div>}
          </div>
        </div>
      ) : (
        /* ── Remediations grouped table ── */
        <>
          <div className="flex items-center gap-2 mb-3">
            {(["active", "ignored", "all"] as const).map(mode => (
              <button key={mode} onClick={() => { setShowSuppressed(mode); setPage(1); }}
                className={cn("rounded-md border px-3 py-1.5 text-xs font-medium transition-all",
                  showSuppressed === mode
                    ? "border-indigo-500 bg-indigo-500/15 text-indigo-400"
                    : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
                )}>
                {mode === "active" ? "Active" : mode === "ignored" ? "Ignored" : "All"}
              </button>
            ))}
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Max Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Affected Hosts</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Vuln Count</th>
                <th className="px-3 py-3 text-right font-medium text-gray-400">Actions</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(remData?.items || []).map((rem, idx) => (
                  <tr key={`${rem.remediation_id}-${rem.affected_product}-${idx}`} className={cn(
                    "hover:bg-gray-800/30 cursor-pointer group",
                    rem.is_suppressed && "opacity-50"
                  )}>
                    <td className="px-3 py-2.5 max-w-[400px] truncate" onClick={() => drillRemediation(rem)}>
                      <span className={rem.is_suppressed ? "text-gray-500 line-through" : "text-white"}>
                        {rem.remediation_action || rem.remediation_id}
                      </span>
                      {rem.is_suppressed && <span className="ml-2 rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">ignored</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[200px] truncate" onClick={() => drillRemediation(rem)}>{rem.affected_product}</td>
                    <td className="px-3 py-2.5" onClick={() => drillRemediation(rem)}><SeverityBadge severity={rem.max_severity} /></td>
                    <td className="px-3 py-2.5 text-white font-medium" onClick={() => drillRemediation(rem)}>{rem.affected_hosts}</td>
                    <td className="px-3 py-2.5 text-gray-400" onClick={() => drillRemediation(rem)}>{rem.vuln_count}</td>
                    <td className="px-3 py-2.5 text-right">
                      {rem.is_suppressed ? (
                        <UnsuppressButton remediationId={rem.remediation_id} vulnCount={rem.vuln_count} onDone={fetchRemediations} />
                      ) : (
                        <SuppressButton remediationId={rem.remediation_id} vulnCount={rem.vuln_count} onDone={fetchRemediations} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {remData?.items.length === 0 && <div className="py-12 text-center text-gray-500">No remediations match your filters</div>}
          </div>
          {remData && remData.total_pages > 1 && (
            <Pagination page={remData.page} totalPages={remData.total_pages}
              total={remData.total} pageSize={remData.page_size} onPageChange={setPage} />
          )}
        </>
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

function ExploitBadge({ status, available }: { status: string | null; available: boolean }) {
  if (!available && !status) return <span className="text-gray-600 text-xs">—</span>;
  const color = (status === "Used in the Wild" || status === "Used in Malware") ? "text-red-400" :
                status === "Functional" ? "text-orange-400" :
                status === "Proof of Concept" ? "text-yellow-400" : "text-gray-400";
  return <span className={cn("text-xs font-medium", color)}>🔥 {status || (available ? "Yes" : "No")}</span>;
}

function UnsuppressButton({ remediationId, vulnCount, onDone }: { remediationId: string; vulnCount: number; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    setShowConfirm(true);
  }

  async function doUnsuppress() {
    setShowConfirm(false);
    setLoading(true);
    try {
      await api<any>(`/api/v1/vulnerabilities/remediations/${encodeURIComponent(remediationId)}/unsuppress`, { method: "POST" });
      onDone();
    } catch {} finally { setLoading(false); }
  }

  return (
    <>
      <button onClick={handleClick} disabled={loading}
        className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50">
        {loading ? "..." : "Restore"}
      </button>
      <ConfirmModal
        open={showConfirm}
        title="Restore Remediation"
        message={`Restore this remediation? ${vulnCount} vulnerabilities will be reopened and risk scores recalculated.`}
        confirmLabel="Restore"
        variant="info"
        onConfirm={doUnsuppress}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}

function SuppressButton({ remediationId, vulnCount, onDone }: { remediationId: string; vulnCount: number; onDone: () => void }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    setShowConfirm(true);
  }

  async function doSuppress() {
    setShowConfirm(false);
    setLoading(true);
    try {
      const resp = await api<any>(`/api/v1/vulnerabilities/remediations/${encodeURIComponent(remediationId)}/suppress`, { method: "POST" });
      setResult(`${resp.suppressed} suppressed`);
      setTimeout(() => { setResult(null); onDone(); }, 1500);
    } catch (e: any) {
      setResult(`Error: ${e.message}`);
      setTimeout(() => setResult(null), 3000);
    } finally { setLoading(false); }
  }

  if (result) return <span className="text-xs text-emerald-400">{result}</span>;

  return (
    <>
      <button onClick={handleClick} disabled={loading}
        className="opacity-0 group-hover:opacity-100 transition-opacity rounded border border-gray-700 px-2 py-1 text-xs text-gray-500 hover:text-orange-400 hover:border-orange-500/30 disabled:opacity-50"
      >
        {loading ? "..." : "Ignore"}
      </button>
      <ConfirmModal
        open={showConfirm}
        title="Ignore Remediation"
        message={`Ignore this remediation? This will suppress ${vulnCount} vulnerabilities and recalculate risk scores.`}
        confirmLabel="Ignore"
        variant="warning"
        onConfirm={doSuppress}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}
