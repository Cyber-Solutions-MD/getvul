"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useToast } from "@/components/ui/ToastProvider";

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
  const { toast } = useToast();
  const [asset, setAsset] = useState<any>(null);
  const [remediations, setRemediations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"remediations" | "vulns">("remediations");
  const [sevFilter, setSevFilter] = useState("");
  const [showTicketConfirm, setShowTicketConfirm] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [a, r] = await Promise.all([
          api(`/api/v1/assets/${params.id}`),
          api(`/api/v1/vulnerabilities/hosts/${params.id}/remediations`).catch(() => []),
        ]);
        setAsset(a);
        setRemediations(r);
      } catch {} finally { setLoading(false); }
    })();
  }, [params.id]);

  if (loading) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">Loading...</p></div>;
  if (!asset) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">Asset not found</p></div>;

  const vc = asset.vuln_counts || {};
  const vulns = asset.vulnerabilities || [];
  const du = asset.directory_user;
  const mdm = asset.mdm_details || {};
  const sources = Array.isArray(asset.seen_by_sources) ? asset.seen_by_sources : Object.keys(asset.seen_by_sources || {});
  const filteredVulns = sevFilter ? vulns.filter((v: any) => v.severity === sevFilter) : vulns;
  const filteredRem = sevFilter ? remediations.filter((r: any) => r.max_severity === sevFilter) : remediations;

  return (
    <div className="space-y-5">
      <button onClick={() => router.push("/dashboard/assets")} className="text-sm text-indigo-400 hover:text-indigo-300">← Assets</button>

      {/* Header — compact */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-lg">{CAT_ICONS[asset.device_category] || "❓"}</span>
            <h1 className="text-xl font-bold text-white truncate">{asset.hostname}</h1>
            {asset.host_status && (
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${asset.host_status === "normal" ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-400"}`}>{asset.host_status}</span>
            )}
            {asset.is_ignored && <span className="rounded bg-orange-500/20 border border-orange-500/30 px-1.5 py-0.5 text-[10px] text-orange-400">IGNORED</span>}
          </div>
          <p className="text-sm text-gray-400 mt-0.5">
            {asset.os_name} {asset.os_version} {asset.model && `· ${asset.model}`} {asset.serial_number && `· ${asset.serial_number}`}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button onClick={() => setShowTicketConfirm(true)} className="rounded-lg bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-500">
            Create Ticket
          </button>
          <ConfirmModal
            open={showTicketConfirm}
            title="Create Ticket"
            message={`Create ticket for ${asset.hostname}?`}
            confirmLabel="Create"
            variant="info"
            onConfirm={async () => {
              setShowTicketConfirm(false);
              try {
                const r = await api("/api/v1/tickets/host", { method: "POST", body: JSON.stringify({ asset_id: asset.id, provider: "ASANA", project_key: "" }) });
                if (r.task_url) { toast({ title: "Ticket Created", message: "Ticket created successfully!", variant: "success" }); window.open(r.task_url, "_blank"); }
                else toast({ title: "Failed", message: r.error || "Failed to create ticket", variant: "error" });
              } catch (e: any) { toast({ title: "Error", message: e.message, variant: "error" }); }
            }}
            onCancel={() => setShowTicketConfirm(false)}
          />
          <div className="text-right">
            <p className="text-[10px] text-gray-500 uppercase">Risk</p>
            <p className={`text-3xl font-bold ${riskColor(asset.risk_score)}`}>{asset.risk_score}</p>
          </div>
        </div>
      </div>

      {/* Vuln count pills — inline */}
      <div className="flex flex-wrap gap-2">
        {([
          { l: "Total", v: vc.total, c: "text-white", s: "" },
          { l: "Critical", v: vc.critical, c: "text-red-400", s: "CRITICAL" },
          { l: "High", v: vc.high, c: "text-orange-400", s: "HIGH" },
          { l: "Medium", v: vc.medium, c: "text-yellow-400", s: "MEDIUM" },
          { l: "Low", v: vc.low, c: "text-green-400", s: "LOW" },
          { l: "Exploit", v: vc.exploitable, c: "text-yellow-300", s: "" },
          { l: "KEV", v: vc.kev, c: "text-red-300", s: "" },
        ]).map(c => (
          <button key={c.l} onClick={() => c.s && setSevFilter(sevFilter === c.s ? "" : c.s)}
            className={`rounded-lg border px-3 py-1.5 text-xs transition ${sevFilter === c.s && c.s ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-800/50"}`}>
            <span className="text-gray-500">{c.l} </span><span className={`font-bold ${c.c}`}>{c.v}</span>
          </button>
        ))}
      </div>

      {/* Info — two columns, compact */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Left: Device + Network */}
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 space-y-3">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
            <R l="Type" v={asset.device_category} />
            <R l="Serial" v={asset.serial_number} />
            <R l="Model" v={asset.model} />
            <R l="Manufacturer" v={asset.system_manufacturer} />
            <R l="Local IP" v={(asset.ip_addresses || []).join(", ")} />
            <R l="External IP" v={asset.external_ip} />
            <R l="MAC" v={(asset.mac_addresses || []).join(", ")} />
            <R l="Managed By" v={asset.managed_by} />
          </div>
          {/* Scanners */}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-800">
            <span className="text-[10px] text-gray-500">Sources:</span>
            {sources.map((s: string) => (
              <span key={s} className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] text-indigo-400">{s}</span>
            ))}
          </div>
          {asset.crowdstrike_aid && <R l="CrowdStrike AID" v={asset.crowdstrike_aid} mono />}
        </div>

        {/* Right: User info — merged from Humaans + Google Workspace */}
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 space-y-3">
          {/* Directory user (Google Workspace / Azure / Okta) */}
          {du && (
            <div className="flex items-center gap-3 pb-2 border-b border-gray-800">
              {du.avatar_url ? (
                <img src={du.avatar_url} alt="" className="h-9 w-9 rounded-full" referrerPolicy="no-referrer" />
              ) : (
                <div className="h-9 w-9 rounded-full bg-indigo-600/50 flex items-center justify-center text-sm text-white font-bold">
                  {(du.display_name || du.email || "?")[0]?.toUpperCase()}
                </div>
              )}
              <div>
                <p className="text-sm font-medium text-white">{du.display_name}</p>
                <p className="text-[11px] text-gray-500">{du.email} · {du.job_title || du.department || du.idp_source}</p>
              </div>
              <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] ${du.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                {du.is_active ? "Active" : "Suspended"}
              </span>
            </div>
          )}
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
            <R l="Assigned User" v={asset.assigned_user} />
            <R l="Department" v={du?.department || asset.department} />
            <R l="Job Title" v={du?.job_title} />
            <R l="Email" v={asset.humaans_email || du?.email} />
            {asset.github_handle && <R l="GitHub" v={`@${asset.github_handle.replace(/^@/, "")}`} link={`https://github.com/${asset.github_handle.replace(/^@/, "")}`} />}
            {asset.element_handle && <R l="Element" v={asset.element_handle} />}
            <R l="Location" v={asset.humaans_location} />
            <R l="Timezone" v={asset.humaans_timezone} />
            {du?.groups?.length > 0 && (
              <div className="col-span-2">
                <span className="text-gray-500">Groups: </span>
                <span className="text-gray-300">{du.groups.slice(0, 5).join(", ")}{du.groups.length > 5 ? ` +${du.groups.length - 5}` : ""}</span>
              </div>
            )}
          </div>
          {/* Activity */}
          <div className="pt-2 border-t border-gray-800 grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
            <R l="Last Login" v={asset.last_login_user} />
            <R l="Last Seen" v={asset.last_seen_at ? timeAgo(asset.last_seen_at) : null} />
            <R l="Login Time" v={asset.last_login_at ? new Date(asset.last_login_at).toLocaleString() : null} />
            <R l="Host Status" v={asset.host_status} badge={asset.host_status === "normal" ? "green" : "gray"} />
            <R l="Containment" v={asset.containment_status} badge={asset.containment_status === "normal" ? "green" : asset.containment_status === "contained" ? "red" : asset.containment_status === "lift_containment_pending" ? "yellow" : "gray"} />
          </div>
          {/* MDM flags — compact single line */}
          {mdm.filevault_enabled !== undefined && (
            <div className="pt-2 border-t border-gray-800 flex gap-3 text-[10px]">
              <Flag l="FileVault" v={mdm.filevault_enabled} />
              <Flag l="SIP" v={mdm.sip_enabled} />
              <Flag l="Gatekeeper" v={mdm.gatekeeper_enabled} />
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        <button onClick={() => setTab("remediations")}
          className={`pb-2 text-sm font-medium transition ${tab === "remediations" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400"}`}>
          Remediations ({remediations.length})
        </button>
        <button onClick={() => setTab("vulns")}
          className={`pb-2 text-sm font-medium transition ${tab === "vulns" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400"}`}>
          Vulnerabilities ({vc.total})
        </button>
      </div>

      {/* Remediations */}
      {tab === "remediations" && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr><th className="px-4 py-2">Remediation</th><th className="px-4 py-2">Product</th><th className="px-4 py-2">Severity</th><th className="px-4 py-2 text-right">Vulns</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredRem.map((r: any, i: number) => (
                <tr key={i} className="hover:bg-gray-800/50">
                  <td className="px-4 py-2 text-gray-200 max-w-md truncate">{r.remediation_action || "—"}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs">{r.product || r.affected_product || "—"}</td>
                  <td className="px-4 py-2"><span className={`rounded-full border px-2 py-0.5 text-xs ${SEV_COLORS[r.max_severity] || ""}`}>{r.max_severity}</span></td>
                  <td className="px-4 py-2 text-right text-gray-300">{r.vuln_count || 1}</td>
                </tr>
              ))}
              {filteredRem.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No remediations</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {/* Vulnerabilities */}
      {tab === "vulns" && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr><th className="px-4 py-2">CVE</th><th className="px-4 py-2">Severity</th><th className="px-4 py-2">Status</th><th className="px-4 py-2">Product</th><th className="px-4 py-2">Source</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredVulns.map((v: any) => (
                <tr key={v.id} className="hover:bg-gray-800/50">
                  <td className="px-4 py-2 font-mono text-xs">
                    <a href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline">{v.cve_id}</a>
                    {v.is_exploitable && <span className="ml-1 text-yellow-400">⚡</span>}
                    {v.is_cisa_kev && <span className="ml-1 text-red-300">KEV</span>}
                  </td>
                  <td className="px-4 py-2"><span className={`rounded-full border px-2 py-0.5 text-xs ${SEV_COLORS[v.severity] || ""}`}>{v.severity}</span></td>
                  <td className="px-4 py-2 text-gray-400 text-xs">{v.status}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs max-w-[200px] truncate">{v.product || "—"}</td>
                  <td className="px-4 py-2"><span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] text-gray-300">{v.source}</span></td>
                </tr>
              ))}
              {filteredVulns.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">No vulnerabilities</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function R({ l, v, mono, badge, link }: { l: string; v: any; mono?: boolean; badge?: "green" | "red" | "gray" | "yellow"; link?: string }) {
  if (!v) return null;
  const badgeC = { green: "bg-green-500/20 text-green-400", red: "bg-red-500/20 text-red-400", yellow: "bg-yellow-500/20 text-yellow-400", gray: "bg-gray-500/20 text-gray-400" };
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500 shrink-0">{l}</span>
      {badge ? <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${badgeC[badge]}`}>{v}</span>
       : link ? <a href={link} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline text-right truncate">{v}</a>
       : <span className={`text-gray-200 text-right truncate ${mono ? "font-mono" : ""}`}>{v}</span>}
    </div>
  );
}

function Flag({ l, v }: { l: string; v: boolean | undefined }) {
  if (v === undefined) return null;
  return <span className={v ? "text-green-400" : "text-red-400"}>{l}: {v ? "✓" : "✗"}</span>;
}

function timeAgo(iso: string): string {
  const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return "now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return `${Math.floor(diffHrs / 24)}d ago`;
}
