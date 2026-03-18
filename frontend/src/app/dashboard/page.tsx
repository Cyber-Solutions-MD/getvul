"use client";

import { useEffect, useState } from "react";
import {
  Bug,
  AlertTriangle,
  ShieldAlert,
  Flame,
  Link2,
  Clock,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types/vulnerability";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const data = await api<DashboardStats>("/api/v1/vulnerabilities/stats");
      setStats(data);
    } catch (e) {
      console.error("Failed to load stats:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      await api("/dev/seed", { method: "POST" });
      await loadStats();
    } catch (e) {
      console.error("Seed failed:", e);
    } finally {
      setSeeding(false);
    }
  }

  const severityColors: Record<string, string> = {
    CRITICAL: "bg-red-500/20 text-red-400 border-red-500/30",
    HIGH: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    MEDIUM: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LOW: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  // Show seed button if no data
  if (!stats || stats.total_vulnerabilities === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Bug className="h-12 w-12 text-gray-600" />
        <h2 className="mt-4 text-lg font-medium text-white">No vulnerability data yet</h2>
        <p className="mt-2 text-sm text-gray-400">
          Seed the database with sample data to explore the dashboard
        </p>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="mt-6 flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {seeding && <Loader2 className="h-4 w-4 animate-spin" />}
          {seeding ? "Seeding..." : "Seed Sample Data"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <h2 className="mb-4 text-sm font-medium text-gray-400">By Severity</h2>
          <div className="space-y-3">
            {stats.by_severity.map((s) => (
              <div key={s.severity} className="flex items-center justify-between">
                <span
                  className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
                    severityColors[s.severity] || "bg-gray-700 text-gray-300"
                  }`}
                >
                  {s.severity}
                </span>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{
                        width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%`,
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
                        width: `${Math.max(2, (s.count / stats.total_vulnerabilities) * 100)}%`,
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
