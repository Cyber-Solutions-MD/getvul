"use client";

import {
  Bug,
  AlertTriangle,
  ShieldAlert,
  Flame,
  Link2,
  Clock,
} from "lucide-react";

// Placeholder data — will be replaced with API calls
const stats = {
  total_vulnerabilities: 2847,
  open_vulnerabilities: 1923,
  by_severity: [
    { severity: "CRITICAL", count: 142 },
    { severity: "HIGH", count: 567 },
    { severity: "MEDIUM", count: 834 },
    { severity: "LOW", count: 1304 },
  ],
  by_source: [
    { source: "CROWDSTRIKE", count: 1200 },
    { source: "DEFENDER", count: 890 },
    { source: "NESSUS", count: 502 },
    { source: "WIZ", count: 255 },
  ],
  exploitable_count: 89,
  cisa_kev_count: 34,
  correlated_cves: 142,
  mttr_days: 12.5,
};

const severityColors: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
  HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      {/* Top stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Bug className="h-5 w-5 text-indigo-400" />}
          label="Total Vulnerabilities"
          value={stats.total_vulnerabilities.toLocaleString()}
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5 text-orange-400" />}
          label="Open"
          value={stats.open_vulnerabilities.toLocaleString()}
        />
        <StatCard
          icon={<Flame className="h-5 w-5 text-red-400" />}
          label="Exploitable"
          value={stats.exploitable_count.toLocaleString()}
        />
        <StatCard
          icon={<ShieldAlert className="h-5 w-5 text-red-400" />}
          label="CISA KEV"
          value={stats.cisa_kev_count.toLocaleString()}
        />
      </div>

      {/* Severity breakdown + Source breakdown */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Severity */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">By Severity</h2>
          <div className="space-y-3">
            {stats.by_severity.map((s) => (
              <div key={s.severity} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
                      severityColors[s.severity] || "bg-gray-700 text-gray-300"
                    }`}
                  >
                    {s.severity}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{
                        width: `${(s.count / stats.total_vulnerabilities) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="w-16 text-right text-sm font-medium text-white">
                    {s.count.toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sources */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">By Source</h2>
          <div className="space-y-3">
            {stats.by_source.map((s) => (
              <div key={s.source} className="flex items-center justify-between">
                <span className="text-sm text-gray-300">{s.source}</span>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{
                        width: `${(s.count / stats.total_vulnerabilities) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="w-16 text-right text-sm font-medium text-white">
                    {s.count.toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard
          icon={<Link2 className="h-5 w-5 text-emerald-400" />}
          label="Correlated CVEs (2+ sources)"
          value={stats.correlated_cves.toLocaleString()}
        />
        <StatCard
          icon={<Clock className="h-5 w-5 text-blue-400" />}
          label="Mean Time to Remediate"
          value={stats.mttr_days ? `${stats.mttr_days} days` : "N/A"}
        />
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
