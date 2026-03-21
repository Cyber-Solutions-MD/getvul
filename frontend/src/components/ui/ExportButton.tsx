"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  resource: string;
  label?: string;
  filters?: Record<string, string | string[] | boolean>;
}

export default function ExportButton({ resource, label, filters }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleExport() {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("getvul_token") || "dev-token" : "dev-token";
      const params = new URLSearchParams();
      if (filters) {
        for (const [k, v] of Object.entries(filters)) {
          if (v === true) params.set(k, "true");
          else if (Array.isArray(v)) v.forEach(item => params.append(k, item));
          else if (v) params.set(k, String(v));
        }
      }

      let resp = await fetch(`${API}/api/v1/export/${resource}?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Auto-refresh on 401
      if (resp.status === 401) {
        const refresh = typeof window !== "undefined" ? localStorage.getItem("getvul_refresh") : null;
        if (refresh) {
          const rr = await fetch(`${API}/auth/refresh`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refresh }),
          });
          if (rr.ok) {
            const data = await rr.json();
            localStorage.setItem("getvul_token", data.access_token);
            resp = await fetch(`${API}/api/v1/export/${resource}?${params}`, {
              headers: { Authorization: `Bearer ${data.access_token}` },
            });
          } else {
            window.location.href = "/login";
            return;
          }
        } else {
          window.location.href = "/login";
          return;
        }
      }

      if (!resp.ok) return;

      const blob = await resp.blob();
      const disposition = resp.headers.get("Content-Disposition") || "";
      const filename = disposition.match(/filename=(.+)/)?.[1] || `getvul_${resource}.csv`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {} finally {
      setLoading(false);
    }
  }

  return (
    <button onClick={handleExport} disabled={loading}
      className="flex items-center gap-1.5 rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 disabled:opacity-50">
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      {loading ? "Exporting..." : label || "Export CSV"}
    </button>
  );
}
