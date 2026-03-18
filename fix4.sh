#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔍 Current remediations endpoint:"
grep -n "hosts.*remediations\|def.*remediations_for_host\|def.*host_remediations" backend/app/vulnerabilities/router.py | head -5

echo ""
echo "🔧 Fixing — group remediations by action..."

python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    content = f.read()

# Find the hosts/{asset_id}/remediations endpoint and replace it
# Look for the function that handles this route
import re

# Find pattern: @router.get("/hosts/{asset_id}/remediations") ... function body
pattern = r'(@router\.get\("/hosts/\{asset_id\}/remediations"\).*?\n)((?:async )?def \w+\(.*?\):.*?)(?=\n@router|\n\nasync def |\n\ndef |\Z)'
match = re.search(pattern, content, re.DOTALL)

if match:
    old_func = match.group(0)
    print(f"Found endpoint at position {match.start()}, length {len(old_func)}")
    print(f"First 100 chars: {old_func[:100]}")
    
    new_func = '''@router.get("/hosts/{asset_id}/remediations")
async def remediations_for_host(
    asset_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get remediations for a specific host, grouped by remediation action."""
    from sqlalchemy import func, case
    from app.assets.models import Asset

    # Verify asset belongs to tenant
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    # Group vulns by remediation_action
    query = (
        select(
            Vulnerability.remediation_action,
            Vulnerability.affected_product,
            func.count().label("vuln_count"),
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    (Vulnerability.severity == "LOW", 1),
                    else_=0,
                )
            ).label("max_sev_rank"),
            func.array_agg(Vulnerability.severity.distinct()).label("severities"),
            func.array_agg(Vulnerability.cve_id.distinct()).label("cve_ids"),
        )
        .where(Vulnerability.asset_id == asset_id)
        .group_by(Vulnerability.remediation_action, Vulnerability.affected_product)
        .order_by(
            func.max(
                case(
                    (Vulnerability.severity == "CRITICAL", 4),
                    (Vulnerability.severity == "HIGH", 3),
                    (Vulnerability.severity == "MEDIUM", 2),
                    (Vulnerability.severity == "LOW", 1),
                    else_=0,
                )
            ).desc(),
            func.count().desc(),
        )
    )

    result = await db.execute(query)
    rows = result.fetchall()

    sev_map = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "UNKNOWN"}

    return [
        {
            "remediation_action": row.remediation_action or "No remediation available",
            "product": row.affected_product or "Unknown",
            "max_severity": sev_map.get(row.max_sev_rank, "UNKNOWN"),
            "vuln_count": row.vuln_count,
            "severities": list(set(row.severities)) if row.severities else [],
            "cve_ids": list(set(row.cve_ids))[:10] if row.cve_ids else [],
        }
        for row in rows
    ]
'''
    content = content[:match.start()] + new_func + content[match.end():]
    
    # Make sure we have the right imports
    if "from fastapi import" in content and "HTTPException" not in content.split("from fastapi import")[1].split("\n")[0]:
        content = content.replace("from fastapi import", "from fastapi import HTTPException, ", 1)
    
    with open("backend/app/vulnerabilities/router.py", "w") as f:
        f.write(content)
    print("✓ Replaced endpoint with grouped version")
else:
    print("Could not find endpoint with regex — searching manually...")
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "hosts" in line and "remediations" in line and "router" in line:
            print(f"  Line {i+1}: {line.strip()}")
PYEOF

echo ""
echo "🔄 Rebuilding..."
docker compose up --build -d backend

echo "⏳ Waiting..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is up!"
    break
  fi
  sleep 2
done

ASSET_ID=$(curl -s "http://localhost:8000/api/v1/assets?page=1&page_size=1" \
  -H "Authorization: Bearer dev-token" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)

echo ""
echo "Testing grouped remediations for $ASSET_ID:"
curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'✓ {len(d)} unique remediations (was 42 duplicates)')
    for r in d[:5]:
        print(f'  [{r[\"max_severity\"]:8}] {r[\"vuln_count\"]:3} vulns — {r[\"remediation_action\"][:70]}')
except Exception as e:
    print(f'✗ {e}')
    import subprocess; subprocess.run(['docker','compose','logs','backend','--tail','10'])
" 2>&1

echo ""
echo "Done! Refresh the asset detail page"
