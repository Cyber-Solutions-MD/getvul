"use client";

import { useCallback, useEffect, useState } from "react";
import { Bug, RefreshCw, Loader2, Pill, Monitor } from "lucide-react";
import { api } from "@/lib/api";
import VulnFilters, { type VulnFilterState } from "@/components/vulnerabilities/VulnFilters";
import VulnTable from "@/components/vulnerabilities/VulnTable";
import BulkActions from "@/components/vulnerabilities/BulkActions";
import Pagination from "@/components/ui/Pagination";
import { SeverityBadge } from "@/components/ui/Badge";
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
  exploit_available: null, cisa_kev: null,
};

type Tab = "vulnerabilities" | "remediations";

export default function VulnerabilitiesPage() {
  const [tab, setTab] = useState<Tab>("vulnerabilities");
  const [vulnData, setVulnData] = useState<PaginatedVulns | null>(null);
  const [remData, setRemData] = useState<PaginatedRemediations | null>(null);
  const [filters, setFilters] = useState<VulnFilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Drill-down states
  const [selectedRemediation, setSelectedRemediation] = useState<RemediationGrouped | null>(null);
  const [remHosts, setRemHosts] = useState<HostForRemediation[] | null>(null);
  const [selectedHostId, setSelectedHostId] = useState<string | null>(null);
  const [selectedHostName, setSelectedHostName] = useState<string>("");
  const [hostRemediations, setHostRemediations] = useState<RemediationForHost[] | null>(null);

  const fetchVulns = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "25");
      if (filters.search) p.set("search", filters.search);
      filters.severity.forEach((s) => p.append("severity", s));
      filters.source.forEach((s) => p.append("source", s));
      filters.status.forEach((s) => p.append("status", s));
      if (filters.exploit_available !== null) p.set("exploit_available", String(filters.exploit_available));
      if (filters.cisa_kev !== null) p.set("cisa_kev", String(filters.cisa_kev));
      setVulnData(await api<PaginatedVulns>(`/api/v1/vulnerabilities?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters]);

  const fetchRemediations = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      p.set("page", String(page)); p.set("page_size", "25");
      if (filters.search) p.set("search", filters.search);
      filters.severity.forEach((s) => p.append("severity", s));
      if (filters.exploit_available === true) p.set("exploit_only", "true");
      if (filters.cisa_kev === true) p.set("kev_only", "true");
      setRemData(await api<PaginatedRemediations>(`/api/v1/vulnerabilities/remediations/grouped?${p}`));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, filters]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (tab === "vulnerabilities") fetchVulns();
      else fetchRemediations();
    }, 300);
    return () => clearTimeout(t);
  }, [tab, fetchVulns, fetchRemediations]);

  useEffect(() => { setPage(1); setSelectedIds(new Set()); }, [filters, tab]);

  async function drillRemediation(rem: RemediationGrouped) {
    setSelectedRemediation(rem);
    try {
      const hosts = await api<HostForRemediation[]>(`/api/v1/vulnerabilities/remediations/${encodeURIComponent(rem.remediation_id)}/hosts`);
      setRemHosts(hosts);
    } catch (e) { console.error(e); }
  }

  async function drillHost(assetId: string, hostname: string) {
    setSelectedHostId(assetId); setSelectedHostName(hostname);
    try {
      const rems = await api<RemediationForHost[]>(`/api/v1/vulnerabilities/hosts/${assetId}/remediations`);
      setHostRemediations(rems);
    } catch (e) { console.error(e); }
  }

  const data = tab === "vulnerabilities" ? vulnData : remData;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bug className="h-6 w-6 text-indigo-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Vulnerabilities</h1>
            {data && <p className="text-sm text-gray-400">{data.total.toLocaleString()} {tab === "vulnerabilities" ? "vulnerabilities" : "remediations"}</p>}
          </div>
        </div>
        <button onClick={() => tab === "vulnerabilities" ? fetchVulns() : fetchRemediations()} disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-900 p-1 w-fit">
        <button onClick={() => { setTab("vulnerabilities"); setSelectedRemediation(null); setSelectedHostId(null); }}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "vulnerabilities" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Bug className="h-4 w-4" />Vulnerabilities
        </button>
        <button onClick={() => { setTab("remediations"); setSelectedRemediation(null); setSelectedHostId(null); }}
          className={cn("flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
            tab === "remediations" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white")}>
          <Pill className="h-4 w-4" />Remediations
        </button>
      </div>

      <VulnFilters filters={filters} onChange={setFilters} />

      {selectedIds.size > 0 && (
        <BulkActions selectedCount={selectedIds.size} selectedIds={Array.from(selectedIds)}
          onComplete={() => { setSelectedIds(new Set()); fetchVulns(); }} />
      )}

      {loading && !data ? (
        <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>
      ) : tab === "vulnerabilities" ? (
        <>
          <VulnTable vulnerabilities={vulnData?.items || []} selectedIds={selectedIds}
            onSelectToggle={(id) => setSelectedIds(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; })}
            onSelectAll={(ids) => setSelectedIds(ids.length ? new Set(ids) : new Set())}
            onHostClick={(assetId, hostname) => { setTab("remediations"); drillHost(assetId, hostname); }} />
          {vulnData && vulnData.total_pages > 1 && (
            <Pagination page={vulnData.page} totalPages={vulnData.total_pages} total={vulnData.total} pageSize={vulnData.page_size} onPageChange={setPage} />
          )}
        </>
      ) : selectedRemediation && remHosts ? (
        /* Drill-down: hosts affected by a remediation */
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <button onClick={() => { setSelectedRemediation(null); setRemHosts(null); }} className="text-xs text-indigo-400 hover:text-indigo-300">← Back to remediations</button>
              <h2 className="mt-1 text-lg font-medium text-white">{selectedRemediation.remediation_action || "Unknown remediation"}</h2>
              <p className="text-sm text-gray-400">{selectedRemediation.affected_product} · {remHosts.length} affected hosts</p>
            </div>
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
                    <td className="px-3 py-2.5 text-white">{h.hostname}</td>
                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{h.cve_id}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={h.severity} /></td>
                    <td className="px-3 py-2.5"><ExploitBadge status={h.exploit_status} available={h.exploit_available} /></td>
                    <td className="px-3 py-2.5">{h.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400">{h.os_name} {h.os_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : selectedHostId && hostRemediations ? (
        /* Drill-down: remediations needed for a host */
        <div className="space-y-4">
          <div>
            <button onClick={() => { setSelectedHostId(null); setHostRemediations(null); }} className="text-xs text-indigo-400 hover:text-indigo-300">← Back</button>
            <h2 className="mt-1 text-lg font-medium text-white flex items-center gap-2"><Monitor className="h-5 w-5 text-gray-400" />{selectedHostName}</h2>
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
          </div>
        </div>
      ) : (
        /* Remediations grouped table */
        <>
          <div className="overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-800 bg-gray-900/70">
                <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Max Severity</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Affected Hosts</th>
                <th className="px-3 py-3 text-left font-medium text-gray-400">Vuln Count</th>
              </tr></thead>
              <tbody className="divide-y divide-gray-800/50">
                {(remData?.items || []).map((rem) => (
                  <tr key={rem.remediation_id} className="hover:bg-gray-800/30 cursor-pointer" onClick={() => drillRemediation(rem)}>
                    <td className="px-3 py-2.5 text-white max-w-[400px] truncate">{rem.remediation_action || rem.remediation_id}</td>
                    <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[200px] truncate">{rem.affected_product}</td>
                    <td className="px-3 py-2.5"><SeverityBadge severity={rem.max_severity} /></td>
                    <td className="px-3 py-2.5 text-white font-medium">{rem.affected_hosts}</td>
                    <td className="px-3 py-2.5 text-gray-400">{rem.vuln_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {remData?.items.length === 0 && <div className="py-12 text-center text-gray-500">No remediations found</div>}
          </div>
          {remData && remData.total_pages > 1 && (
            <Pagination page={remData.page} totalPages={remData.total_pages} total={remData.total} pageSize={remData.page_size} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

function ExploitBadge({ status, available }: { status: string | null; available: boolean }) {
  if (!available && !status) return <span className="text-gray-600 text-xs">—</span>;
  const color = status === "Used in the Wild" ? "text-red-400" :
                status === "Used in Malware" ? "text-red-400" :
                status === "Functional" ? "text-orange-400" :
                status === "Proof of Concept" ? "text-yellow-400" : "text-gray-400";
  return <span className={cn("text-xs font-medium", color)}>🔥 {status || (available ? "Yes" : "No")}</span>;
}
