#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Step 1: Show raw Spotlight JSON to find correct field names..."

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
        creds = get_decrypted_credentials(conn)
        base_url = (conn.config or {}).get("base_url", creds.get("base_url", "https://api.crowdstrike.com"))

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{base_url}/oauth2/token", data={"client_id": creds["client_id"], "client_secret": creds["client_secret"]})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        # Get one CRITICAL vuln with filter (required!)
        print("=== ONE CRITICAL VULN (FULL RAW JSON) ===")
        resp = await client.get(
            f"{base_url}/spotlight/combined/vulnerabilities/v1",
            headers=headers,
            params={"limit": 1, "filter": "status:'open'+cve.severity:'CRITICAL'"},
        )
        if resp.status_code == 200:
            resources = resp.json().get("resources", [])
            if resources:
                print(json.dumps(resources[0], indent=2, default=str))
        else:
            print(f"Status: {resp.status_code}")
            print(resp.text[:1000])

        print("\n=== ONE HIGH VULN (FULL RAW JSON) ===")
        resp = await client.get(
            f"{base_url}/spotlight/combined/vulnerabilities/v1",
            headers=headers,
            params={"limit": 1, "filter": "status:'open'+cve.severity:'HIGH'"},
        )
        if resp.status_code == 200:
            resources = resp.json().get("resources", [])
            if resources:
                print(json.dumps(resources[0], indent=2, default=str))
        else:
            print(f"Status: {resp.status_code}")

asyncio.run(check())
PYEOF

echo ""
echo "══════════════════════════════════════════════════"
echo "Copy EVERYTHING above and paste it back to me."
echo "I need the raw JSON to see the exact field names"
echo "for severity, hostname, CVE, etc."
echo "══════════════════════════════════════════════════"
