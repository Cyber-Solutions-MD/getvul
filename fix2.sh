#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing attribute names in assets/router.py..."

# Fix v.remediation → v.remediation_action
# Fix v.product → v.affected_product (if still there)
# Show all Vulnerability attribute accesses to catch everything
echo "Current vuln attribute accesses:"
grep -n "v\.\(remediation\|product\|exploit\|cisa\|source\|cve\|status\|severity\)" backend/app/assets/router.py | grep -v "^#"

echo ""

# Fix them
sed -i '' 's/v\.remediation\b/v.remediation_action/g' backend/app/assets/router.py
sed -i '' 's/v\.product\b/v.affected_product/g' backend/app/assets/router.py

echo "After fix:"
grep -n "v\.\(remediation\|product\|exploit\|cisa\|source\|cve\|status\|severity\)" backend/app/assets/router.py | grep -v "^#"

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
echo "Testing asset detail:"
curl -s "http://localhost:8000/api/v1/assets/$ASSET_ID" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'✓ {d[\"hostname\"]} — {d[\"vuln_counts\"][\"total\"]} vulns, {len(d.get(\"vulnerabilities\",[]))} returned')
except Exception as e:
    print(f'✗ {e}')
" 2>&1

echo ""
echo "Backend errors:"
docker compose logs backend --tail 5 2>&1 | grep -i "error\|attribute" || echo "No errors"

echo ""
echo "Done! Click an asset row to test"
