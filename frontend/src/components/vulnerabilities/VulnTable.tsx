"use client";

import { Flame, ShieldAlert } from "lucide-react";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface Props {
  vulnerabilities: VulnerabilitySummary[];
  selectedIds: Set<string>;
  onSelectToggle: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
  onHostClick?: (assetId: string, hostname: string) => void;
}

export default function VulnTable({ vulnerabilities, selectedIds, onSelectToggle, onSelectAll, onHostClick }: Props) {
  const allSelected = vulnerabilities.length > 0 && vulnerabilities.every((v) => selectedIds.has(v.id));

  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-800 bg-gray-900/70">
          <th className="w-10 px-3 py-3">
            <input type="checkbox" checked={allSelected}
              onChange={() => allSelected ? onSelectAll([]) : onSelectAll(vulnerabilities.map((v) => v.id))}
              className="rounded border-gray-600 bg-gray-800 text-indigo-600" />
          </th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">CVE</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Host</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Exploit</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">KEV</th>
          <th className="px-3 py-3 text-left font-medium text-gray-400">Remediation</th>
        </tr></thead>
        <tbody className="divide-y divide-gray-800/50">
          {vulnerabilities.map((v) => (
            <tr key={v.id} className={cn("transition-colors hover:bg-gray-800/30", selectedIds.has(v.id) && "bg-indigo-500/5")}>
              <td className="px-3 py-2.5">
                <input type="checkbox" checked={selectedIds.has(v.id)} onChange={() => onSelectToggle(v.id)}
                  className="rounded border-gray-600 bg-gray-800 text-indigo-600" />
              </td>
              <td className="px-3 py-2.5 font-mono text-sm text-white">{v.cve_id || "N/A"}</td>
              <td className="px-3 py-2.5"><SeverityBadge severity={v.severity} /></td>
              <td className="px-3 py-2.5"><SourceBadge source={v.source} /></td>
              <td className="px-3 py-2.5"><StatusBadge status={v.status} /></td>
              <td className="px-3 py-2.5">
                {v.asset_hostname && v.asset_id && onHostClick ? (
                  <button onClick={() => onHostClick(v.asset_id!, v.asset_hostname!)}
                    className="text-indigo-400 hover:text-indigo-300 text-sm hover:underline">
                    {v.asset_hostname}
                  </button>
                ) : <span className="text-gray-400">{v.asset_hostname || "—"}</span>}
              </td>
              <td className="max-w-[150px] truncate px-3 py-2.5 text-gray-400 text-xs">{v.affected_product || "—"}</td>
              <td className="px-3 py-2.5">
                {v.exploit_available ? (
                  <span className="flex items-center gap-1 text-xs font-medium text-orange-400">
                    <Flame className="h-3.5 w-3.5" />{v.exploit_status_name || "Yes"}
                  </span>
                ) : <span className="text-gray-600 text-xs">—</span>}
              </td>
              <td className="px-3 py-2.5">
                {v.cisa_kev ? <span className="text-red-400 text-xs font-medium">🛡️ KEV</span> : <span className="text-gray-600 text-xs">—</span>}
              </td>
              <td className="max-w-[200px] truncate px-3 py-2.5 text-xs text-gray-400">{v.remediation_action || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {vulnerabilities.length === 0 && <div className="py-12 text-center text-gray-500">No vulnerabilities found</div>}
    </div>
  );
}
