#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fix 1: Asset detail page — show remediations for host..."

mkdir -p frontend/src/app/dashboard/assets/\[id\]

cat > frontend/src/app/dashboard/assets/\[id\]/page.tsx << 'TSXEOF'
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TOKEN = "dev-token";
const headers: Record<string, string> = { Authorization: `Bearer ${TOKEN}` };

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
  const [asset, setAsset] = useState<any>(null);
  const [remediations, setRemediations] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sevFilter, setSevFilter] = useState("");
  const [tab, setTab] = useState<"remediations" | "vulns">("remediations");

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/api/v1/assets/${params.id}`, { headers });
        if (!r.ok) { setError("Asset not found"); return; }
        const data = await r.json();
        setAsset(data);

        // Fetch remediations for this host
        const rr = await fetch(`${API}/api/v1/vulnerabilities/hosts/${params.id}/remediations`, { headers });
        if (rr.ok) setRemediations(await rr.json());
      } catch { setError("Failed to load"); }
      finally { setLoading(false); }
    })();
  }, [params.id]);

  if (loading) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">Loading...</p></div>;
  if (error) return <div className="flex min-h-[400px] items-center justify-center"><p className="text-gray-400">{error}</p></div>;
  if (!asset) return null;

  const vc = asset.vuln_counts || {};
  const vulns = asset.vulnerabilities || [];
  const filteredVulns = sevFilter ? vulns.filter((v: any) => v.severity === sevFilter) : vulns;
  const filteredRem = sevFilter
    ? remediations.filter((r: any) => r.max_severity === sevFilter || r.severities?.includes(sevFilter))
    : remediations;

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/dashboard/assets")} className="text-sm text-indigo-400 hover:text-indigo-300">← Back to Assets</button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{CAT_ICONS[asset.device_category] || "❓"} {asset.hostname}</h1>
          <p className="mt-1 text-gray-400">
            {asset.os_name} {asset.os_version}
            {asset.model && <span> · {asset.model}</span>}
            {asset.serial_number && <span> · S/N: {asset.serial_number}</span>}
          </p>
          {asset.assigned_user && (
            <p className="text-sm text-gray-500">
              Assigned: {asset.assigned_user}
              {asset.department && <span> · {asset.department}</span>}
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-400">Risk Score</p>
          <p className={`text-4xl font-bold ${riskColor(asset.risk_score)}`}>{asset.risk_score}</p>
        </div>
      </div>

      {/* Vuln count cards */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        {([
          { label: "Total", value: vc.total, color: "text-white", sev: "" },
          { label: "Critical", value: vc.critical, color: "text-red-400", sev: "CRITICAL" },
          { label: "High", value: vc.high, color: "text-orange-400", sev: "HIGH" },
          { label: "Medium", value: vc.medium, color: "text-yellow-400", sev: "MEDIUM" },
          { label: "Low", value: vc.low, color: "text-green-400", sev: "LOW" },
          { label: "Exploitable", value: vc.exploitable, color: "text-yellow-300", sev: "" },
          { label: "CISA KEV", value: vc.kev, color: "text-red-300", sev: "" },
        ] as const).map((c) => (
          <button key={c.label}
            onClick={() => c.sev && setSevFilter(sevFilter === c.sev ? "" : c.sev)}
            className={`rounded-lg border p-3 text-left transition ${
              sevFilter === c.sev && c.sev ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 bg-gray-800 hover:border-gray-600"
            }`}>
            <p className="text-xs text-gray-400">{c.label}</p>
            <p className={`text-xl font-bold ${c.color}`}>{c.value}</p>
          </button>
        ))}
      </div>

      {/* Info row */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-2 text-sm font-medium text-gray-400">IP Addresses</p>
          {(asset.ip_addresses || []).length > 0
            ? asset.ip_addresses.map((ip: string) => <span key={ip} className="mr-2 rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">{ip}</span>)
            : <p className="text-sm text-gray-500">None</p>}
        </div>
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <p className="mb-2 text-sm font-medium text-gray-400">Scanners</p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(asset.seen_by_sources || {}).map((s: string) => (
              <span key={s} className="rounded-full border border-indigo-500/30 bg-indigo-500/20 px-2 py-0.5 text-xs text-indigo-400">{s}</span>
            ))}
          </div>
        </div>
        {asset.mdm_details && (
          <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
            <p className="mb-2 text-sm font-medium text-gray-400">MDM Security</p>
            {Object.entries(asset.mdm_details).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm">
                <span className="text-gray-400">{k}</span>
                <span className={v ? "text-green-400" : "text-red-400"}>{v ? "✓" : "✗"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-700">
        <button onClick={() => setTab("remediations")}
          className={`pb-2 text-sm font-medium transition ${tab === "remediations" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          🔧 Remediations ({remediations.length})
        </button>
        <button onClick={() => setTab("vulns")}
          className={`pb-2 text-sm font-medium transition ${tab === "vulns" ? "border-b-2 border-indigo-500 text-white" : "text-gray-400 hover:text-gray-300"}`}>
          🛡️ Vulnerabilities ({vc.total})
        </button>
      </div>

      {/* Remediations tab */}
      {tab === "remediations" && (
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="border-b border-gray-700 bg-gray-800 text-gray-400">
              <tr>
                <th className="px-4 py-3">Remediation</th>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3 text-right">Vulns</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {(filteredRem.length > 0 ? filteredRem : remediations.length === 0 ? [] : filteredRem).map((r: any, i: number) => (
                <tr key={i} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-3 text-gray-200 max-w-md">{r.remediation_action || r.remediation || "No remediation info"}</td>
                  <td className="px-4 py-3 text-gray-400">{r.product || r.affected_product || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_COLORS[r.max_severity || r.severity] || ""}`}>
                      {r.max_severity || r.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">{r.vuln_count || r.count || 1}</td>
                </tr>
              ))}
              {remediations.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-500">No remediations found — data may not include remediation info</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Vulns tab */}
      {tab === "vulns" && (
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
              {filteredVulns.map((v: any) => (
                <tr key={v.id} className="bg-gray-900 hover:bg-gray-800">
                  <td className="px-4 py-2 font-mono text-sm">
                    <a href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`} target="_blank" rel="noopener noreferrer"
                      className="text-indigo-400 hover:underline">{v.cve_id}</a>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEV_COLORS[v.severity] || ""}`}>{v.severity}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-300">{v.status}</td>
                  <td className="px-4 py-2 text-gray-300">{v.product || v.affected_product || "—"}</td>
                  <td className="px-4 py-2 text-gray-400 text-xs max-w-xs truncate">{v.remediation || v.remediation_action || "—"}</td>
                  <td className="px-4 py-2">{v.is_exploitable && <span className="text-yellow-400">⚡</span>}</td>
                  <td className="px-4 py-2">{v.is_cisa_kev && <span className="text-red-300">🚨</span>}</td>
                  <td className="px-4 py-2"><span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-300">{v.source}</span></td>
                </tr>
              ))}
              {filteredVulns.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">No vulnerabilities match your filter</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
TSXEOF


echo "🔧 Fix 2: Add host filter to vulnerability dashboard..."

# Check what the current vuln page looks like
VULN_PAGE="frontend/src/app/dashboard/vulnerabilities/page.tsx"

# Add hostname filter to the backend vulnerabilities list endpoint
# Check if it already supports asset_hostname param
grep -c "hostname\|asset_id\|host" backend/app/vulnerabilities/router.py | head -1

# Add hostname search to the vuln list endpoint
python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    content = f.read()

# Check if hostname filter already exists
if "hostname" in content and "asset_hostname" in content:
    print("Hostname filter already exists in vuln router")
else:
    # Find the list endpoint and add hostname filter param
    # Add after existing Query params
    if "def list_vulnerabilities" in content or "async def list_" in content:
        # Add import for Asset if not present
        if "from app.assets.models import Asset" not in content:
            content = content.replace(
                "from app.vulnerabilities.models import",
                "from app.assets.models import Asset\nfrom app.vulnerabilities.models import",
            )
        
        # Add hostname param to the list function
        # Find the pattern: search: str = Query("" and add after it
        if 'asset_hostname: str = Query("")' not in content:
            content = content.replace(
                'search: str = Query("",',
                'search: str = Query("",\n    asset_hostname: str = Query("", description="Filter by hostname"),',
                1,
            )
            # If that didn't work try alternate patterns
            if 'asset_hostname' not in content:
                content = content.replace(
                    'search: str = Query("")',
                    'search: str = Query("")\n    asset_hostname: str = Query("", description="Filter by hostname"),',
                    1,
                )

        # Add the filter logic — join with Asset table
        if "asset_hostname" in content and "Asset.hostname" not in content:
            # Add filter after existing filters
            content = content.replace(
                "if search:",
                'if asset_hostname:\n        query = query.join(Asset, Vulnerability.asset_id == Asset.id).where(Asset.hostname.ilike(f"%{asset_hostname}%"))\n    if search:',
                1,
            )
        
        with open("backend/app/vulnerabilities/router.py", "w") as f:
            f.write(content)
        print("Added hostname filter to vuln router")
    else:
        print("Could not find list endpoint — manual fix needed")
PYEOF

# Now add the host filter UI to the frontend vulnerabilities page
# We need to add a hostname search input
python3 << 'PYEOF'
with open("frontend/src/app/dashboard/vulnerabilities/page.tsx", "r") as f:
    content = f.read()

# Check if hostname filter already exists
if "asset_hostname" in content or "hostFilter" in content:
    print("Host filter already in frontend vuln page")
else:
    # Add state for hostname filter
    content = content.replace(
        'const [search, setSearch] = useState("");',
        'const [search, setSearch] = useState("");\n  const [hostFilter, setHostFilter] = useState("");',
        1,
    )
    
    # Add hostname to API params
    content = content.replace(
        'if (search) params.set("search", search);',
        'if (search) params.set("search", search);\n    if (hostFilter) params.set("asset_hostname", hostFilter);',
        1,
    )
    
    # Add hostFilter to useCallback/useEffect dependency if present
    content = content.replace(
        'search, ',
        'search, hostFilter, ',
        1,
    )
    
    # Add hostname input to the filter UI — find the search input and add after it
    # Look for the search input pattern
    search_input_end = content.find('Search CVE')
    if search_input_end == -1:
        search_input_end = content.find('search')
    
    # Simpler: add the host filter input after the search input
    # Find the pattern: onChange={(e) => { setSearch(
    old_search = 'onChange={(e) => { setSearch(e.target.value); setPage(1); }}'
    if old_search in content:
        # Find the closing of the search input tag and add host filter after
        # Add before the filter pills
        content = content.replace(
            old_search,
            old_search + '''
          />
          <input
            type="text"
            placeholder="Filter by hostname..."
            value={hostFilter}
            onChange={(e) => { setHostFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-400 focus:border-indigo-500 focus:outline-none"''',
            1,
        )
        print("Added host filter input to frontend")
    else:
        # Try alternate approach — just add after search state setter
        print("Could not find exact search input pattern — trying alternate")
        # Find the Filters section and add hostname input
        if "Filters" in content:
            content = content.replace(
                '>Filters</span>',
                '''>Filters</span>
              <input type="text" placeholder="Filter by hostname..." value={hostFilter}
                onChange={(e) => { setHostFilter(e.target.value); setPage(1); }}
                className="rounded-lg border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs text-white placeholder-gray-400" />''',
                1,
            )
            print("Added host filter via Filters label")
    
    with open("frontend/src/app/dashboard/vulnerabilities/page.tsx", "w") as f:
        f.write(content)
PYEOF


echo ""
echo "🔄 Rebuilding..."
docker compose up --build -d

echo "⏳ Waiting..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is up!"
    break
  fi
  sleep 2
done

echo ""
echo "Testing asset detail:"
# Get first asset ID
ASSET_ID=$(curl -s "http://localhost:8000/api/v1/assets?page=1&page_size=1" \
  -H "Authorization: Bearer dev-token" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)

if [ -n "$ASSET_ID" ]; then
  echo "Asset ID: $ASSET_ID"
  curl -s "http://localhost:8000/api/v1/assets/$ASSET_ID" \
    -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Host: {d[\"hostname\"]}')
print(f'Vulns: {d[\"vuln_counts\"][\"total\"]}')
print(f'Vuln details returned: {len(d.get(\"vulnerabilities\",[]))}')
" 2>&1

  echo ""
  echo "Testing remediations for host:"
  curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
    -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if isinstance(d, list):
    print(f'{len(d)} remediations found')
    for r in d[:3]:
        print(f'  {r.get(\"remediation_action\",r.get(\"remediation\",\"?\"))[:60]}')
else:
    print(f'Response: {str(d)[:200]}')
" 2>&1
fi

echo ""
echo "Testing hostname filter on vulns:"
curl -s "http://localhost:8000/api/v1/vulnerabilities?asset_hostname=par03642&page_size=3" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'Vulns for par03642: {d.get(\"total\",len(d.get(\"items\",[])))}')
except: print('hostname filter not working yet')
" 2>&1

echo ""
echo "Done! Test:"
echo "  1. Click any asset row → should show remediations"
echo "  2. Vulnerabilities page → hostname filter input"
