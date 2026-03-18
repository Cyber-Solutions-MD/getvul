#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    content = f.read()

# Replace get_current_user with require_viewer (already imported)
# Replace get_db with DBSession (already imported)
content = content.replace(
    "user=Depends(get_current_user)",
    "user: Annotated[CurrentUser, Depends(require_viewer)]"
)
content = content.replace(
    "db: AsyncSession = Depends(get_db)",
    "db: DBSession"
)

# Remove any added imports that aren't needed
content = content.replace("from app.auth.dependencies import get_current_user\n", "")
content = content.replace("from app.db.session import get_db\n", "")
content = content.replace("from sqlalchemy.ext.asyncio import AsyncSession\n", "")

with open("backend/app/vulnerabilities/router.py", "w") as f:
    f.write(content)

print("✓ Fixed: get_current_user → require_viewer, get_db → DBSession")
PYEOF

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
  curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
    -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'✓ {len(d)} grouped remediations')
for r in d[:5]:
    print(f'  [{r[\"max_severity\"]:8}] {r[\"vuln_count\"]:3} vulns — {r[\"remediation_action\"][:70]}')
" 2>&1
else
  echo "❌ Still down:"
  docker compose logs backend --tail 5 2>&1 | grep -i "error\|name"
fi
