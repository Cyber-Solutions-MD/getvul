#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔍 Diagnosing CrowdStrike API responses..."
echo ""

echo "══════════════════════════════════════"
echo "1. Current GetVul stats"
echo "══════════════════════════════════════"
echo "Vuln stats:"
curl -s "http://localhost:8000/api/v1/vulnerabilities/stats" \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Failed"
echo ""
echo "CSPM stats:"
curl -s "http://localhost:8000/api/v1/cspm/stats" \
  -H "Authorization: Bearer dev-token" | python3 -m json.tool 2>/dev/null || echo "Failed"
echo ""

echo "══════════════════════════════════════"
echo "2. Raw CrowdStrike API responses"
echo "══════════════════════════════════════"

docker compose exec -T backend python3 << 'PYEOF'
import asyncio, httpx, json

async def check():
    from app.connectors.service import get_decrypted_credentials
    from app.ticketing.models import ConnectorConfig
    from app.db.session import async_session_factory
    from sqlalchemy import select

    async with async_session_factory() as db:
        r = await db.execute(select(ConnectorConfig).where(ConnectorConfig.connector_type == "CROWDSTRIKE"))
        conn = r.scalar_one_or_none()
        if not conn:
            print("ERROR: No CrowdStrike connector found")
            return
        creds = get_decrypted_credentials(conn)
        base_url = (conn.config or {}).get("base_url", creds.get("base_url", "https://api.crowdstrike.com"))
        print(f"Base URL: {base_url}")

    async with httpx.AsyncClient(timeout=30) as client:
        # Auth
        resp = await client.post(f"{base_url}/oauth2/token", data={"client_id": creds["client_id"], "client_secret": creds["client_secret"]})
        if resp.status_code != 201:
            print(f"AUTH FAILED: {resp.status_code} - {resp.text[:500]}")
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        print(f"Auth: OK (token expires in {resp.json().get('expires_in')}s)")
        print()

        # ── Spotlight: raw vuln data ──
        print("=" * 50)
        print("SPOTLIGHT - Raw vulnerability (3 items)")
        print("=" * 50)
        resp = await client.get(
            f"{base_url}/spotlight/combined/vulnerabilities/v1",
            headers=headers,
            params={"limit": 3},
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("meta", {}).get("pagination", {}).get("total", "?")
            print(f"Total available: {total}")
            print()
            for i, item in enumerate(data.get("resources", [])[:3]):
                print(f"--- Vuln {i+1} ---")
                # Print key fields only
                print(f"  id: {item.get('id')}")
                print(f"  status: {item.get('status')}")
                
                cve = item.get("cve", {})
                if isinstance(cve, dict):
                    print(f"  cve.id: {cve.get('id')}")
                    print(f"  cve.base_score: {cve.get('base_score')}")
                    print(f"  cve.base_score_severity: {cve.get('base_score_severity')}")
                    print(f"  cve.exploit_status: {cve.get('exploit_status')}")
                    print(f"  cve.description: {str(cve.get('description', ''))[:100]}")
                elif isinstance(cve, str):
                    print(f"  cve (string): {cve}")
                else:
                    print(f"  cve (type={type(cve).__name__}): {str(cve)[:200]}")

                host = item.get("host_info", {})
                print(f"  host_info.hostname: {host.get('hostname') if isinstance(host, dict) else host}")
                print(f"  host_info.local_ip: {host.get('local_ip') if isinstance(host, dict) else 'N/A'}")
                print(f"  host_info.os_version: {host.get('os_version') if isinstance(host, dict) else 'N/A'}")
                print(f"  host_info.platform_name: {host.get('platform_name') if isinstance(host, dict) else 'N/A'}")

                aid = item.get("aid", host.get("aid") if isinstance(host, dict) else None)
                print(f"  aid: {aid}")

                app = item.get("app", {})
                print(f"  app.product_name_version: {app.get('product_name_version') if isinstance(app, dict) else app}")

                remediation = item.get("remediation", {})
                print(f"  remediation.action: {str(remediation.get('action', '') if isinstance(remediation, dict) else '')[:100]}")

                # Print ALL top-level keys so we can see what's available
                print(f"  ALL TOP-LEVEL KEYS: {list(item.keys())}")
                print()
            
            # Print one full raw item for debugging
            if data.get("resources"):
                print("--- FULL RAW JSON of first item ---")
                print(json.dumps(data["resources"][0], indent=2, default=str)[:5000])
                print()
        else:
            print(f"Response: {resp.text[:1000]}")
        print()

        # ── Spotlight with severity filter ──
        print("=" * 50)
        print("SPOTLIGHT - Critical+High only")
        print("=" * 50)
        for sev_filter in ["status:'open'+cve.severity:'CRITICAL'", "status:'open'+cve.severity:'HIGH'"]:
            resp = await client.get(
                f"{base_url}/spotlight/combined/vulnerabilities/v1",
                headers=headers,
                params={"limit": 1, "filter": sev_filter},
            )
            total = resp.json().get("meta", {}).get("pagination", {}).get("total", "?") if resp.status_code == 200 else f"Error {resp.status_code}"
            print(f"  Filter '{sev_filter}': {total} results")
        
        # Also try without severity filter
        resp = await client.get(
            f"{base_url}/spotlight/combined/vulnerabilities/v1",
            headers=headers,
            params={"limit": 1, "filter": "status:'open'"},
        )
        total = resp.json().get("meta", {}).get("pagination", {}).get("total", "?") if resp.status_code == 200 else f"Error {resp.status_code}"
        print(f"  Filter 'status:open' (all severities): {total} results")
        
        resp = await client.get(
            f"{base_url}/spotlight/combined/vulnerabilities/v1",
            headers=headers,
            params={"limit": 1},
        )
        total = resp.json().get("meta", {}).get("pagination", {}).get("total", "?") if resp.status_code == 200 else f"Error {resp.status_code}"
        print(f"  No filter (all): {total} results")
        print()

        # ── Hosts endpoint ──
        print("=" * 50)
        print("HOSTS - Device query")
        print("=" * 50)
        resp = await client.get(
            f"{base_url}/devices/queries/devices/v1",
            headers=headers,
            params={"limit": 1},
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("meta", {}).get("pagination", {}).get("total", "?")
            print(f"Total devices: {total}")
            device_ids = data.get("resources", [])
            if device_ids:
                # Get first device details
                resp2 = await client.get(
                    f"{base_url}/devices/entities/devices/v2",
                    headers=headers,
                    params={"ids": device_ids[0]},
                )
                if resp2.status_code == 200:
                    dev = resp2.json().get("resources", [{}])[0]
                    print(f"  Sample device hostname: {dev.get('hostname')}")
                    print(f"  Sample device local_ip: {dev.get('local_ip')}")
                    print(f"  Sample device os_version: {dev.get('os_version')}")
                    print(f"  Sample device platform_name: {dev.get('platform_name')}")
        else:
            print(f"Response: {resp.text[:500]}")
        print()

        # ── CSPM: Configuration Assessment ──
        print("=" * 50)
        print("CSPM - Configuration Assessment")
        print("=" * 50)
        resp = await client.get(
            f"{base_url}/configuration-assessment/combined/assessments/v1",
            headers=headers,
            params={"limit": 2},
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("meta", {}).get("pagination", {}).get("total", "?")
            print(f"Total assessments: {total}")
            for i, item in enumerate(data.get("resources", [])[:2]):
                print(f"--- Assessment {i+1} ---")
                print(json.dumps(item, indent=2, default=str)[:2000])
                print()
        elif resp.status_code == 403:
            print("ACCESS DENIED — 'Configuration Assessment' scope not enabled on API client")
        elif resp.status_code == 404:
            print("NOT FOUND — endpoint may not be available in your cloud region")
        else:
            print(f"Response: {resp.text[:1000]}")
        print()

        # ── CSPM: Fallback endpoints ──
        print("=" * 50)
        print("CSPM - Fallback endpoints")
        print("=" * 50)
        fallbacks = [
            "/cloud-connect-cspm-aws/entities/iom/v2",
            "/detects/entities/iom/v2",
            "/cspm/entities/iom/v2",
            "/cloud-connect-cspm-aws/entities/account/v1",
            "/cspm/entities/policy-settings/v1",
        ]
        for ep in fallbacks:
            try:
                resp = await client.get(f"{base_url}{ep}", headers=headers, params={"limit": 2})
                status = resp.status_code
                count = "N/A"
                if status == 200:
                    data = resp.json()
                    resources = data.get("resources", [])
                    count = len(resources)
                    if resources:
                        print(f"  {ep}: {status} ({count} items)")
                        print(f"    First item keys: {list(resources[0].keys()) if resources else 'empty'}")
                        print(f"    Sample: {json.dumps(resources[0], indent=2, default=str)[:500]}")
                    else:
                        print(f"  {ep}: {status} (0 items)")
                else:
                    print(f"  {ep}: {status}")
            except Exception as e:
                print(f"  {ep}: ERROR - {e}")
        print()

        # ── Summary ──
        print("=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print("Check the output above for:")
        print("  1. Spotlight: Are 'hostname' and 'cve.base_score_severity' populated?")
        print("  2. Spotlight: How many total vulns across different severity filters?")
        print("  3. Hosts: Can we resolve device details?")
        print("  4. CSPM: Which endpoint returns data (200 + non-empty resources)?")

asyncio.run(check())
PYEOF

echo ""
echo "✅ Done. Paste the output above and I'll fix the connector."
