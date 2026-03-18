#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "=== Full file around the problem ==="
wc -l backend/app/vulnerabilities/router.py

echo ""
echo "🔧 Rewriting the remediations endpoint cleanly..."

# Extract everything BEFORE the broken endpoint, then append clean version
python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    content = f.read()

# Find where the remediations endpoint starts
marker = '@router.get("/hosts/{asset_id}/remediations")'
idx = content.find(marker)

if idx == -1:
    print("Could not find remediations endpoint marker!")
    exit(1)

# Keep everything before it
before = content[:idx]

# Check imports in `before`
needs = []
if "from sqlalchemy import" not in before or "select" not in before:
    needs.append("from sqlalchemy import select, func, case")
if "from app.vulnerabilities.models import Vulnerability" not in before:
    needs.append("from app.vulnerabilities.models import Vulnerability")
if "from app.assets.models import Asset" not in before:
    needs.append("from app.assets.models import Asset")

# Add missing imports after the last existing import line
if needs:
    lines = before.split("\n")
    last_import = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("from ") or line.strip().startswith("import "):
            last_import = i
    for j, imp in enumerate(needs):
        lines.insert(last_import + 1 + j, imp)
    before = "\n".join(lines)
    print(f"Added {len(needs)} imports")

# Write clean file: everything before + clean endpoint
clean_endpoint = '''@router.get("/hosts/{asset_id}/remediations")
async def remediations_for_host(
    asset_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
):
    """Get remediations for a specific host, grouped by remediation action."""
    # Verify asset belongs to tenant
    asset = (await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")

    # Group vulns by remediation_action + product
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
        }
        for row in rows
    ]
'''

with open("backend/app/vulnerabilities/router.py", "w") as f:
    f.write(before + clean_endpoint)

print("✓ Wrote clean file")
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

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
  ASSET_ID=$(curl -s "http://localhost:8000/api/v1/assets?page=1&page_size=1" \
    -H "Authorization: Bearer dev-token" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)
  echo ""
  curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
    -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'✓ {len(d)} grouped remediations')
    for r in d[:5]:
        print(f'  [{r[\"max_severity\"]:8}] {r[\"vuln_count\"]:3} vulns — {r[\"remediation_action\"][:70]}')
except Exception as e:
    print(f'✗ {e}')
    import subprocess; subprocess.run(['docker','compose','logs','backend','--tail','5'])
"
else
  echo "❌ Still down:"
  docker compose logs backend --tail 10 2>&1 | grep "Error\|error"
fi
