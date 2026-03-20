"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN = "dev-token";
const headers: Record<string, string> = { Authorization: `Bearer ${TOKEN}` };

const SEV_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-green-500/20 text-green-400 border-green-500/30",
};
const CAT_ICONS: Record<string, string> = { WORKSTATION: "🖥️", SERVER: "🗄️", NETWORK: "🌐", MOBILE: "📱", OTHER: "❓" };

function riskColor(s: number) {
  if (s >= 80) return "text-red-400";
  if (s >= 50) return "text-orange-400";
  if (s >= 20) return "text-yellow-400";
  return "text-green-400";
}

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [asset, setAsset] = useState<any>(null);
  const [remediations, setRemediations] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sevFilter, setSevFilter] = useState("");
  const [tab, setTab] = useState<"remediations" | "vulns">("remediations");

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/v1/assets/${params.id}`, { headers });
        if (!r.ok) { setError("Asset not found"); return; }
        const data = await r.json();
        setAsset(data);

        // Fetch remediations for this host
        const rr = await fetch(`${API}/api/v1/vulnerabilities/hosts/${params.id}/remediations`, { headers });
        if (rr.ok) setRemediations(await rr.json());
      } catch { setError("Failed to load"); }
      finally { setLoading(false); }
    })();
  }, [params.id]);

  if (loading) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">Loading...</p></div>;
  if (error) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">{error}</p></div>;
  if (!asset) return null;

  const vc = asset.vuln_counts || {};
  const vulns = asset.vulnerabilities || [];
  const filteredVulns = sevFilter ? vulns.filter((v: any) => v.severity === sevFilter) : vulns;
  const filteredRem = sevFilter
    ? remediations.filter((r: any) => r.max_severity === sevFilter || r.severities?.includes(sevFilter))
    : remediations;

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/dashboard/assets")} className="text-sm text-indigo-400 hover:text-indigo-300">← Back to Assets</button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{CAT_ICONS[asset.device_category] || "❓"} {asset.hostname}</h1>
            {asset.host_status && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                asset.host_status === "normal" || asset.host_status === "online"
                  ? "bg-green-500/20 text-green-400 border border-green-500/30"
                  : asset.host_status === "contained" || asset.host_status === "containment_pending"
                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                  : "bg-gray-500/20 text-gray-400 border border-gray-500/30"
              }`}>{asset.host_status}</span>
            )}
          </div>
          <p className="mt-1 text-gray-400">
            {asset.os_name} {asset.os_version}
            {asset.model && <span> · {asset.model}</span>}
            {asset.serial_number && <span> · S/N: {asset.serial_number}</span>}
          </p>
          {(asset.last_login_user || asset.assigned_user) && (
            <p className="text-sm text-gray-500">
              {asset.last_login_user && <span>Last login: {asset.last_login_user}</span>}
              {asset.last_login_user && asset.last_login_at && <span className="text-gray-600"> ({new Date(asset.last_login_at).toLocaleDateString()})</span>}
              {asset.assigned_user && asset.last_login_user && <span> · </span>}
              {asset.assigned_user && <span>Assigned: {asset.assigned_user}</span>}
              {asset.department && <span> · {asset.department}</span>}
            </p>
          )}
        </div>
        <div className="flex items-start gap-4">
          <button
            onClick={async () => {
              if (!confirm(`Create Asana remediation ticket for ${asset.hostname}?`)) return;
              try {
                const resp = await fetch(`${API}/api/v1/tickets/host`, {
                  method: "POST", headers,
                  body: JSON.stringify({ asset_id: asset.id, provider: "ASANA", project_key: "" }),
                });
                const data = await resp.json();
                if (resp.ok && data.task_url) {
                  alert(`Ticket created! ${data.vulns_linked} vulns linked, assigned to ${data.assignee || 'unassigned'}. Due: ${data.due_on}`);
                  window.open(data.task_url, "_blank");
                } else {
                  alert(`Error: ${data.detail || data.error || 'Failed'}`);
                }
              } catch (e: any) { alert(`Error: ${e.message}`); }
            }}
            className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-500 whitespace-nowrap"
          >
            Create Ticket
          </button>
          <div className="text-right">
            <p className="text-sm text-gray-400">Risk Score</p>
            <p className={`text-4xl font-bold ${riskColor(asset.risk_score)}`}>{asset.risk_score}</p>
          </div>
        </div>
      </div>

      {/* Vuln count cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        {([
          { label: "Total", value: vc.total, color: "text-white", sev: "" },
          { label: "Critical", value: vc.critical, color: "text-red-400", sev: "CRITICAL" },
          { label: "High", value: vc.high, color: "text-orange-400", sev: "HIGH" },
          { label: "Medium", value: vc.medium, color: "text-yellow-400", sev: "MEDIUM" },
          { label: "Low", value: vc.low, color: "text-green-400", sev: "LOW" },
          { label: "Exploitable", value: vc.exploitable, color: "text-yellow-300", sev: "" },
          { label: "CISA KEV", value: vc.kev, color: "text-red-300", sev: "" },
        ] as const).map((c) => (
          <button key={c.label}
            onClick={() => c.sev && setSevFilter(sevFilter === c.sev ? "" : c.sev)}
            className={`rounded-lg border p-3 text-left transition ${
              sevFilter === c.sev && c.sev ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-800 hover:border-gray-600"
            }`}>
            <p className="text-xs text-gray-400">{c.label}</p>
            <p className={`text-xl font-bold ${c.color}`}>{c.value}</p>
          </button>
        ))}
      </div>

      {/* Info panels */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Device Info */}
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-3 text-sm font-medium text-gray-400">Device Info</p>
          <div className="space-y-2 text-sm">
            <InfoRow label="Type" value={asset.asset_type || asset.device_category} />
            <InfoRow label="Serial Number" value={asset.serial_number} />
            <InfoRow label="Model" value={asset.model} />
            {asset.crowdstrike_aid && <InfoRow label="CrowdStrike AID" value={asset.crowdstrike_aid} mono />}
          </div>
        </div>

        {/* Network */}
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-3 text-sm font-medium text-gray-400">Network</p>
          <div className="space-y-2 text-sm">
            <InfoRow label="Local IP" value={(asset.ip_addresses || []).join(", ")} />
            <InfoRow label="External IP" value={asset.external_ip} />
            <InfoRow label="MAC Address" value={(asset.mac_addresses || []).join(", ")} />
          </div>
        </div>

        {/* User & Activity */}
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-3 text-sm font-medium text-gray-400">User & Activity</p>
          <div className="space-y-2 text-sm">
            <InfoRow label="Assigned User" value={asset.assigned_user} />
            <InfoRow label="Work Email" value={asset.humaans_email} />
            <InfoRow label="Department" value={asset.department} />
            {asset.github_handle && (
              <div className="flex justify-between gap-4">
                <span className="text-gray-500 shrink-0">GitHub</span>
                <a href={`https://github.com/${asset.github_handle.replace(/^@/, "")}`}
                  target="_blank" rel="noopener noreferrer"
                  className="text-indigo-400 hover:underline text-right truncate">@{asset.github_handle.replace(/^@/, "")}</a>
              </div>
            )}
            {asset.linkedin_handle && (
              <div className="flex justify-between gap-4">
                <span className="text-gray-500 shrink-0">LinkedIn</span>
                <a href={`https://linkedin.com/in/${asset.linkedin_handle}`}
                  target="_blank" rel="noopener noreferrer"
                  className="text-indigo-400 hover:underline text-right truncate">{asset.linkedin_handle}</a>
              </div>
            )}
            {asset.element_handle && <InfoRow label="Element" value={asset.element_handle} />}
            {asset.humaans_location && <InfoRow label="Location" value={asset.humaans_location} />}
            {asset.humaans_timezone && <InfoRow label="Timezone" value={asset.humaans_timezone} />}
            {asset.humaans_teams && asset.humaans_teams.length > 0 && (
              <div className="flex justify-between gap-4">
                <span className="text-gray-500 shrink-0">Teams</span>
                <span className="text-gray-200 text-right text-xs">{asset.humaans_teams.join(", ")}</span>
              </div>
            )}
            <div className="mt-2 border-t border-gray-700 pt-2" />
            <InfoRow label="Last Login User" value={asset.last_login_user} />
            <InfoRow label="Last Login" value={asset.last_login_at ? new Date(asset.last_login_at).toLocaleString() : null} />
            <InfoRow label="Last Seen" value={asset.last_seen_at ? timeAgo(asset.last_seen_at) : null} />
            <InfoRow label="Host Status" value={asset.host_status} badge={
              asset.host_status === "normal" ? "green" : asset.host_status === "contained" ? "red" : "gray"
            } />
          </div>
        </div>

        {/* Scanners */}
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-3 text-sm font-medium text-gray-400">Scanners</p>
          <div className="flex flex-wrap gap-2">
            {(Array.isArray(asset.seen_by_sources) ? asset.seen_by_sources : Object.keys(asset.seen_by_sources || {})).map((s: string) => (
              <span key={s} className="rounded-full border border-indigo-500/30 bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-400">{s}</span>
            ))}
          </div>
        </div>

        {/* MDM Security (if available) */}
        {asset.mdm_details && Object.keys(asset.mdm_details).length > 0 && (
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="mb-3 text-sm font-medium text-gray-400">MDM Security</p>
            {Object.entries(asset.mdm_details).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-gray-400">{k}</span>
                <span className={v ? "text-green-400" : "text-red-400"}>{v ? "✓" : "✗"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        <button onClick={() => setTab("remediations")}
          className={`pb-2 text-sm font-medium transition ${tab === "remediations" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          🔧 Remediations ({remediations.length})
        </button>
        <button onClick={() => setTab("vulns")}
          className={`pb-2 text-sm font-medium transition ${tab === "vulns" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          🛡️ Vulnerabilities ({vc.total})
        </button>
      </div>

      {/* Remediations tab */}
      {tab === "remediations" && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr>
                <th className="px-4 py-3">Remediation</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3 text-right">Vulns</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {(filteredRem.length > 0 ? filteredRem : remediations.length === 0 ? [] : filteredRem).map((r: any, i: number) => (
                <tr key={i} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-3 text-gray-200 max-w-md">{r.remediation_action || r.remediation || "No remediation info"}</td>
                  <td className="px-4 py-3 text-gray-400">{r.product || r.affected_product || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_COLORS[r.max_severity || r.severity] || ""}`}>
                      {r.max_severity || r.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">{r.vuln_count || r.count || 1}</td>
                </tr>
              ))}
              {remediations.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No remediations found — data may not include remediation info</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Vulns tab */}
      {tab === "vulns" && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr>
                <th className="px-4 py-3">CVE</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Remediation</th>
                <th className="px-4 py-3">Exploit</th>
                <th className="px-4 py-3">KEV</th>
                <th className="px-4 py-3">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredVulns.map((v: any) => (
                <tr key={v.id} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-2 font-mono text-sm">
                    <a href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`} target="_blank" rel="noopener noreferrer"
                      className="text-indigo-400 hover:underline">{v.cve_id}</a>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_COLORS[v.severity] || ""}`}>{v.severity}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-300">{v.status}</td>
                  <td className="px-4 py-2 text-gray-300">{v.product || v.affected_product || "—"}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs max-w-xs truncate">{v.remediation || v.remediation_action || "—"}</td>
                  <td className="px-4 py-2">{v.is_exploitable && <span className="text-yellow-400">⚡</span>}</td>
                  <td className="px-4 py-2">{v.is_cisa_kev && <span className="text-red-300">🚨</span>}</td>
                  <td className="px-4 py-2"><span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">{v.source}</span></td>
                </tr>
              ))}
              {filteredVulns.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">No vulnerabilities match your filter</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value, mono, badge }: { label: string; value: string | null | undefined; mono?: boolean; badge?: "green" | "red" | "gray" }) {
  if (!value) return null;
  const badgeColors = { green: "bg-green-500/20 text-green-400", red: "bg-red-500/20 text-red-400", gray: "bg-gray-500/20 text-gray-400" };
  return (
    <div className="flex justify-between gap-4">
      <span className="text-gray-500 shrink-0">{label}</span>
      {badge ? (
        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${badgeColors[badge]}`}>{value}</span>
      ) : (
        <span className={`text-gray-200 text-right truncate ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMin = Math.floor((now - then) / 60000);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(iso).toLocaleDateString();
}
