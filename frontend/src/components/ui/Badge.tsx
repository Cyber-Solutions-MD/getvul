import { cn } from "@/lib/utils";

const severityStyles: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  INFO: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

const statusStyles: Record<string, string> = {
  OPEN: "bg-red-500/15 text-red-400 border-red-500/20",
  IN_PROGRESS: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
  REMEDIATED: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  SUPPRESSED: "bg-gray-500/15 text-gray-400 border-gray-500/20",
  FALSE_POSITIVE: "bg-gray-500/15 text-gray-500 border-gray-500/20",
};

const sourceStyles: Record<string, string> = {
  CROWDSTRIKE: "bg-red-500/10 text-red-300 border-red-500/20",
  NESSUS: "bg-green-500/10 text-green-300 border-green-500/20",
  DEFENDER: "bg-blue-500/10 text-blue-300 border-blue-500/20",
  WIZ: "bg-purple-500/10 text-purple-300 border-purple-500/20",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        severityStyles[severity] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        statusStyles[status] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function SourceBadge({ source }: { source: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        sourceStyles[source] || "bg-gray-700 text-gray-300 border-gray-600"
      )}
    >
      {source === "CROWDSTRIKE" ? "CS" : source === "DEFENDER" ? "MDE" : source}
    </span>
  );
}
