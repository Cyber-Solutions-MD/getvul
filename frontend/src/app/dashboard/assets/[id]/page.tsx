"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = "http://localhost:8000";
const TOKEN = "dev-token";
const headers = { Authorization: `Bearer ${TOKEN}` };

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500/20 text-red-400",
  HIGH: "bg-orange-500/20 text-orange-400",
  MEDIUM: "bg-yellow-500/20 text-yellow-400",
  LOW: "bg-green-500/20 text-green-400",
};

const CATEGORY_ICONS: Record<string, string> = {
  WORKSTATION: "🖥️",
  SERVER: "🗄️",
  NETWORK: "🌐",
  MOBILE: "📱",
  OTHER: "❓",
};

function riskColor(score: number) {
  if (score >= 80) return "text-red-400";
  if (score >= 50) return "text-orange-400";
  if (score >= 20) return "text-yellow-400";
  return "text-green-400";
}

export default function AssetDetailPage() {
  const params = useParams();
  const [asset, setAsset] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/v1/assets/${params.id}`, { headers });
        if (r.ok) {
          setAsset(await r.json());
        } else {
          setError("Asset not found");
        }
      } catch {
        setError("Failed to load asset");
      }
    })();
  }, [params.id]);

  if (error) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <p className="text-gray-400">{error}</p>
      </div>
    );
  }

  if (!asset) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  const vc = asset.vuln_counts || {};

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button
        onClick={() => window.location.href = "/dashboard/assets"}
        className="text-sm text-indigo-400 hover:text-indigo-300"
      >
        ← Back to Assets
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {CATEGORY_ICONS[asset.device_category] || "❓"} {asset.hostname}
          </h1>
          <p className="mt-1 text-gray-400">
            {asset.os_name} {asset.os_version}
            {asset.model && <span> · {asset.model}</span>}
            {asset.serial_number && <span> · S/N: {asset.serial_number}</span>}
          </p>
          {asset.assigned_user && (
            <p className="text-sm text-gray-500">
              Assigned to: {asset.assigned_user}
              {asset.department && <span> · {asset.department}</span>}
              {asset.building && <span> · {asset.building}</span>}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-400">Risk Score</p>
          <p className={`text-4xl font-bold ${riskColor(asset.risk_score)}`}>
            {asset.risk_score}
          </p>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4 lg:grid-cols-7">
        {[
          { label: "Total Vulns", value: vc.total, color: "text-white" },
          { label: "Critical", value: vc.critical, color: "text-red-400" },
          { label: "High", value: vc.high, color: "text-orange-400" },
          { label: "Medium", value: vc.medium, color: "text-yellow-400" },
          { label: "Low", value: vc.low, color: "text-green-400" },
          { label: "Exploitable", value: vc.exploitable, color: "text-yellow-300" },
          { label: "CISA KEV", value: vc.kev, color: "text-red-300" },
        ].map((card) => (
          <div key={card.label} className="rounded-lg border border-gray-700 bg-gray-800 p-3">
            <p className="text-xs text-gray-400">{card.label}</p>
            <p className={`text-xl font-bold ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* IP / Scanners / MDM */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-2 text-sm font-medium text-gray-400">IP Addresses</p>
          {(asset.ip_addresses || []).length > 0 ? (
            <div className="space-y-1">
              {asset.ip_addresses.map((ip: string) => (
                <span key={ip} className="mr-2 rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">
                  {ip}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">None recorded</p>
          )}
        </div>
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-2 text-sm font-medium text-gray-400">Seen By Scanners</p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(asset.seen_by_sources || {}).map((s) => (
              <span key={s} className="rounded-full border border-indigo-500/30 bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-400">
                {s.toUpperCase()}
              </span>
            ))}
          </div>
        </div>
        {asset.mdm_details && (
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="mb-2 text-sm font-medium text-gray-400">MDM Security</p>
            <div className="space-y-1 text-sm">
              {Object.entries(asset.mdm_details).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-gray-400">{k}</span>
                  <span className={v ? "text-green-400" : "text-red-400"}>
                    {v ? "✓" : "✗"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Vulnerabilities table */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-white">
          Vulnerabilities ({vc.total})
        </h2>
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
              {(asset.vulnerabilities || []).map((v: any) => (
                <tr key={v.id} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-2 font-mono text-sm text-indigo-400">
                    <a
                      href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline"
                    >
                      {v.cve_id}
                    </a>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_COLORS[v.severity] || ""}`}>
                      {v.severity}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-300">{v.status}</td>
                  <td className="px-4 py-2 text-gray-300">{v.product || "—"}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs max-w-xs truncate">
                    {v.remediation || "—"}
                  </td>
                  <td className="px-4 py-2">
                    {v.is_exploitable && <span className="text-yellow-400">⚡</span>}
                  </td>
                  <td className="px-4 py-2">
                    {v.is_cisa_kev && <span className="text-red-300">🚨</span>}
                  </td>
                  <td className="px-4 py-2">
                    <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">
                      {v.source}
                    </span>
                  </td>
                </tr>
              ))}
              {(asset.vulnerabilities || []).length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                    No vulnerabilities found for this asset
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
