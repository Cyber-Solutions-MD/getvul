"use client";

import { useState } from "react";
import { ExternalLink, Flame, ShieldAlert, ChevronDown } from "lucide-react";
import { SeverityBadge, StatusBadge, SourceBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import type { VulnerabilitySummary } from "@/types/vulnerability";

interface Props {
  vulnerabilities: VulnerabilitySummary[];
  selectedIds: Set<string>;
  onSelectToggle: (id: string) => void;
  onSelectAll: (ids: string[]) => void;
}

export default function VulnTable({
  vulnerabilities,
  selectedIds,
  onSelectToggle,
  onSelectAll,
}: Props) {
  const allSelected =
    vulnerabilities.length > 0 &&
    vulnerabilities.every((v) => selectedIds.has(v.id));

  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 bg-gray-900/70">
            <th className="w-10 px-3 py-3">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => {
                  if (allSelected) {
                    onSelectAll([]);
                  } else {
                    onSelectAll(vulnerabilities.map((v) => v.id));
                  }
                }}
                className="rounded border-gray-600 bg-gray-800 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-0"
              />
            </th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">CVE / Name</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Severity</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Source</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Status</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Asset</th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Product</th>
            <th className="w-10 px-3 py-3 text-left font-medium text-gray-400"></th>
            <th className="px-3 py-3 text-left font-medium text-gray-400">Detected</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {vulnerabilities.map((vuln) => (
            <tr
              key={vuln.id}
              className={cn(
                "transition-colors hover:bg-gray-800/30",
                selectedIds.has(vuln.id) && "bg-indigo-500/5"
              )}
            >
              <td className="px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={selectedIds.has(vuln.id)}
                  onChange={() => onSelectToggle(vuln.id)}
                  className="rounded border-gray-600 bg-gray-800 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-0"
                />
              </td>
              <td className="px-3 py-2.5">
                <span className="font-mono text-sm text-white">
                  {vuln.cve_id || "N/A"}
                </span>
              </td>
              <td className="px-3 py-2.5">
                <SeverityBadge severity={vuln.severity} />
              </td>
              <td className="px-3 py-2.5">
                <SourceBadge source={vuln.source} />
              </td>
              <td className="px-3 py-2.5">
                <StatusBadge status={vuln.status} />
              </td>
              <td className="px-3 py-2.5">
                <span className="text-gray-300">
                  {vuln.asset_hostname || "—"}
                </span>
              </td>
              <td className="max-w-[180px] truncate px-3 py-2.5 text-gray-400">
                {vuln.affected_product || "—"}
              </td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-1">
                  {vuln.exploit_available && (
                    <Flame className="h-3.5 w-3.5 text-red-400" title="Exploit available" />
                  )}
                  {vuln.cisa_kev && (
                    <ShieldAlert className="h-3.5 w-3.5 text-orange-400" title="CISA KEV" />
                  )}
                </div>
              </td>
              <td className="px-3 py-2.5 text-gray-500">
                {new Date(vuln.first_detected_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {vulnerabilities.length === 0 && (
        <div className="py-12 text-center text-gray-500">
          No vulnerabilities match your filters
        </div>
      )}
    </div>
  );
}
