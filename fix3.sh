#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "=== Finding exact lines with 'v.remediation' ==="
grep -n 'v\.remediation' backend/app/assets/router.py
echo ""

echo "=== Fix with Python (reliable) ==="
python3 << 'PYEOF'
with open("backend/app/assets/router.py", "r") as f:
    lines = f.readlines()

fixed = 0
for i, line in enumerate(lines):
    # Fix v.remediation that is NOT already v.remediation_action or v.remediation_id or v.remediation_info
    if "v.remediation" in line and "v.remediation_action" not in line and "v.remediation_id" not in line and "v.remediation_info" not in line:
        old = line.rstrip()
        line = line.replace("v.remediation", "v.remediation_action")
        print(f"  Line {i+1}: {old.strip()} → {line.strip()}")
        lines[i] = line
        fixed += 1
    # Also fix v.product that is NOT v.affected_product
    if "v.product" in line and "v.affected_product" not in line:
        old = line.rstrip()
        line = line.replace("v.product", "v.affected_product")
        print(f"  Line {i+1}: {old.strip()} → {line.strip()}")
        lines[i] = line
        fixed += 1

with open("backend/app/assets/router.py", "w") as f:
    f.writelines(lines)

print(f"\nFixed {fixed} lines")
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
curl -s "http://localhost:8000/api/v1/assets/$ASSET_ID" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'✓ {d[\"hostname\"]} — {d[\"vuln_counts\"][\"total\"]} vulns, {len(d.get(\"vulnerabilities\",[]))} details')
except Exception as e:
    print(f'✗ {e}')
    import subprocess; subprocess.run(['docker','compose','logs','backend','--tail','5'])
" 2>&1

echo ""
echo "Done!"
