#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

ASSET_ID=$(curl -s "http://localhost:8000/api/v1/assets?page=1&page_size=1" \
  -H "Authorization: Bearer dev-token" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)

echo "Asset ID: $ASSET_ID"
echo ""

echo "=== Asset detail response ==="
curl -s -w "\nHTTP: %{http_code}" "http://localhost:8000/api/v1/assets/$ASSET_ID" \
  -H "Authorization: Bearer dev-token"
echo ""

echo ""
echo "=== Backend error ==="
docker compose logs backend --tail 15 2>&1 | grep -i "error\|attribute\|traceback\|column" || echo "none"

echo ""
echo "=== Asset detail endpoint code ==="
grep -n "def get_asset\|asset_id" backend/app/assets/router.py | head -10
