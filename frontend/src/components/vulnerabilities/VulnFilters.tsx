"use client";

import { Search, X, Filter } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VulnFilterState {
  search: string;
  severity: string[];
  source: string[];
  status: string[];
  device_type: string | null;
  exploit_available: boolean | null;
  cisa_kev: boolean | null;
}

const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SOURCES = ["CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ"];
const STATUSES = ["OPEN", "IN_PROGRESS", "REMEDIATED", "SUPPRESSED", "FALSE_POSITIVE"];
const DEVICE_TYPES = ["SERVER", "WORKSTATION", "OTHER"];

const sevColors: Record<string, string> = {
  CRITICAL: "border-red-500/40 bg-red-500/10 text-red-400 data-[active=true]:bg-red-500/25",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-400 data-[active=true]:bg-orange-500/25",
  MEDIUM: "border-yellow-500/40 bg-yellow-500/10 text-yellow-400 data-[active=true]:bg-yellow-500/25",
  LOW: "border-blue-500/40 bg-blue-500/10 text-blue-400 data-[active=true]:bg-blue-500/25",
};

interface Props {
  filters: VulnFilterState;
  onChange: (filters: VulnFilterState) => void;
}

export default function VulnFilters({ filters, onChange }: Props) {
  const toggleArray = (arr: string[], value: string) =>
    arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];

  const activeCount =
    filters.severity.length +
    filters.source.length +
    filters.status.length +
    (filters.device_type !== null ? 1 : 0) +
    (filters.exploit_available !== null ? 1 : 0) +
    (filters.cisa_kev !== null ? 1 : 0);

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search CVE ID, product name..."
          className="w-full rounded-lg border border-gray-700 bg-gray-900 py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        {filters.search && (
          <button
            onClick={() => onChange({ ...filters, search: "" })}
            className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Filter className="h-3.5 w-3.5" />
          Filters{activeCount > 0 && ` (${activeCount})`}
        </div>

        {/* Severity */}
        <div className="flex gap-1.5">
          {SEVERITIES.map((sev) => (
            <button
              key={sev}
              data-active={filters.severity.includes(sev)}
              onClick={() =>
                onChange({ ...filters, severity: toggleArray(filters.severity, sev) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.severity.includes(sev)
                  ? sevColors[sev]
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {sev}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Source */}
        <div className="flex gap-1.5">
          {SOURCES.map((src) => (
            <button
              key={src}
              onClick={() =>
                onChange({ ...filters, source: toggleArray(filters.source, src) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.source.includes(src)
                  ? "border-indigo-500/40 bg-indigo-500/15 text-indigo-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {src === "CROWDSTRIKE" ? "CS" : src === "DEFENDER" ? "MDE" : src}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Status */}
        <div className="flex gap-1.5">
          {STATUSES.map((st) => (
            <button
              key={st}
              onClick={() =>
                onChange({ ...filters, status: toggleArray(filters.status, st) })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.status.includes(st)
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {st.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Device Type */}
        <div className="flex gap-1.5">
          {DEVICE_TYPES.map((dt) => (
            <button
              key={dt}
              onClick={() =>
                onChange({ ...filters, device_type: filters.device_type === dt ? null : dt })
              }
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
                filters.device_type === dt
                  ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-400"
                  : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
              )}
            >
              {dt}
            </button>
          ))}
        </div>

        <div className="h-4 w-px bg-gray-700" />

        {/* Toggles */}
        <button
          onClick={() =>
            onChange({
              ...filters,
              exploit_available: filters.exploit_available === true ? null : true,
            })
          }
          className={cn(
            "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
            filters.exploit_available === true
              ? "border-red-500/40 bg-red-500/15 text-red-400"
              : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
          )}
        >
          🔥 Exploitable
        </button>

        <button
          onClick={() =>
            onChange({
              ...filters,
              cisa_kev: filters.cisa_kev === true ? null : true,
            })
          }
          className={cn(
            "rounded-md border px-2 py-0.5 text-xs font-medium transition-all",
            filters.cisa_kev === true
              ? "border-red-500/40 bg-red-500/15 text-red-400"
              : "border-gray-700 bg-gray-900 text-gray-500 hover:text-gray-300"
          )}
        >
          🛡️ CISA KEV
        </button>

        {/* Clear all */}
        {activeCount > 0 && (
          <button
            onClick={() =>
              onChange({
                search: filters.search,
                severity: [],
                source: [],
                status: [],
                device_type: null,
                exploit_available: null,
                cisa_kev: null,
              })
            }
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
