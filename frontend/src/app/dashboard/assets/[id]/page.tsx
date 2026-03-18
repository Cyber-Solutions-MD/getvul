"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Server, ArrowLeft, Shield, Flame, ShieldAlert, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { SeverityBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

interface AssetDetail {
  id: string; hostname: string | null; ip_addresses: string[];
  os_name: string | null; os_version: string | null;
  asset_type: string | null; cloud_provider: string | null;
  seen_by_sources: string[]; risk_score: number | null;
  vuln_counts: Record<string, number>;
  created_at: string; updated_at: string;
}

interface RemediationForHost {
  remediation_id: string; remediation_action: string | null;
  cve_id: string | null; severity: string; affected_product: string | null;
  exploit_available: boolean; cisa_kev: boolean; exploit_status: string | null;
}

export default function AssetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const assetId = params.id as string;

  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [remediations, setRemediations] = useState<RemediationForHost[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, r] = await Promise.all([
        api<AssetDetail>(`/api/v1/assets/${assetId}`),
        api<RemediationForHost[]>(`/api/v1/vulnerabilities/hosts/${assetId}/remediations`),
      ]);
      setAsset(a);
      setRemediations(r);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [assetId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-indigo-500" /></div>;
  if (!asset) return <div className="py-20 text-center text-gray-500">Asset not found</div>;

  const riskColor = (asset.risk_score ?? 0) >= 80 ? "text-red-400" :
                    (asset.risk_score ?? 0) >= 50 ? "text-orange-400" :
                    (asset.risk_score ?? 0) >= 20 ? "text-yellow-400" : "text-emerald-400";

  const totalVulns = Object.values(asset.vuln_counts || {}).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/dashboard/assets")}
        className="flex items-center gap-1 text-sm text-indigo-400 hover:text-indigo-300">
        <ArrowLeft className="h-4 w-4" />Back to assets
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="rounded-xl bg-gray-800 p-3">
            <Server className="h-6 w-6 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{asset.hostname || "Unknown"}</h1>
            <p className="text-sm text-gray-400">
              {asset.os_name} {asset.os_version} · {asset.asset_type || "Unknown type"}
              {asset.ip_addresses?.length > 0 && ` · ${asset.ip_addresses[0]}`}
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className={cn("text-3xl font-bold", riskColor)}>{asset.risk_score ?? "—"}</div>
          <div className="text-xs text-gray-400">Risk Score</div>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Scanners</div>
          <div className="mt-2 flex gap-1.5 flex-wrap">
            {(asset.seen_by_sources || []).map((s) => <SourceBadge key={s} source={s} />)}
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Total Open Vulns</div>
          <div className="mt-1 text-2xl font-bold text-white">{totalVulns}</div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">By Severity</div>
          <div className="mt-2 flex gap-2 flex-wrap">
            {Object.entries(asset.vuln_counts || {}).sort((a, b) => {
              const order: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
              return (order[a[0]] ?? 4) - (order[b[0]] ?? 4);
            }).map(([sev, cnt]) => (
              <div key={sev} className="flex items-center gap-1">
                <SeverityBadge severity={sev} /><span className="text-xs text-white">{cnt}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-400">Remediations Needed</div>
          <div className="mt-1 text-2xl font-bold text-white">{remediations.length}</div>
        </div>
      </div>

      {/* Remediations table */}
      <div>
        <h2 className="mb-3 text-sm font-medium text-gray-400">Remediations Needed</h2>
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
              {remediations.map((r, i) => (
                <tr key={i} className="hover:bg-gray-800/30">
                  <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{r.cve_id}</td>
                  <td className="px-3 py-2.5"><SeverityBadge severity={r.severity} /></td>
                  <td className="px-3 py-2.5 text-xs text-gray-400 max-w-[150px] truncate">{r.affected_product}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-300 max-w-[300px] truncate">{r.remediation_action || "—"}</td>
                  <td className="px-3 py-2.5">
                    {r.exploit_available ? (
                      <span className="flex items-center gap-1 text-xs text-orange-400"><Flame className="h-3 w-3" />{r.exploit_status || "Yes"}</span>
                    ) : <span className="text-gray-600 text-xs">—</span>}
                  </td>
                  <td className="px-3 py-2.5">
                    {r.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {remediations.length === 0 && <div className="py-12 text-center text-gray-500">No open remediations</div>}
        </div>
      </div>
    </div>
  );
}
