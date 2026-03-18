#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "=== Current imports in vuln router ==="
head -20 backend/app/vulnerabilities/router.py
echo ""

echo "🔧 Adding missing import..."
python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    content = f.read()

if "get_current_user" not in content.split("import")[0] and "from app.auth.dependencies import get_current_user" not in content:
    # Check what auth import exists
    if "from app.auth" in content:
        # Add get_current_user to existing auth import
        import re
        m = re.search(r'from app\.auth\.\w+ import (.+)', content)
        if m:
            print(f"Existing auth import: {m.group(0)}")
    
    # Safe approach: add the import after other imports
    content = content.replace(
        "from app.vulnerabilities.models import",
        "from app.auth.dependencies import get_current_user\nfrom app.vulnerabilities.models import",
        1,
    )
    
    # Also need get_db if not present
    if "get_db" not in content and "DBSession" not in content:
        content = content.replace(
            "from app.auth.dependencies import get_current_user",
            "from app.auth.dependencies import get_current_user\nfrom app.db.session import get_db",
        )
    
    with open("backend/app/vulnerabilities/router.py", "w") as f:
        f.write(content)
    print("✓ Added get_current_user import")
else:
    print("get_current_user already imported")

# Also check get_db and AsyncSession
if "AsyncSession" not in content:
    content2 = open("backend/app/vulnerabilities/router.py").read()
    content2 = content2.replace(
        "from app.auth.dependencies import get_current_user",
        "from app.auth.dependencies import get_current_user\nfrom sqlalchemy.ext.asyncio import AsyncSession",
    )
    open("backend/app/vulnerabilities/router.py", "w").write(content2)
    print("✓ Added AsyncSession import")

if "get_db" not in open("backend/app/vulnerabilities/router.py").read():
    content3 = open("backend/app/vulnerabilities/router.py").read()
    content3 = content3.replace(
        "from app.auth.dependencies import get_current_user",
        "from app.auth.dependencies import get_current_user\nfrom app.db.session import get_db",
    )
    open("backend/app/vulnerabilities/router.py", "w").write(content3)
    print("✓ Added get_db import")
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
  echo "Testing grouped remediations:"
  curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
    -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'✓ {len(d)} unique remediations')
    for r in d[:5]:
        print(f'  [{r[\"max_severity\"]:8}] {r[\"vuln_count\"]:3} vulns — {r[\"remediation_action\"][:70]}')
except Exception as e:
    print(f'✗ {e}')
" 2>&1
else
  echo "❌ Still down:"
  docker compose logs backend --tail 10 2>&1 | grep -i "error\|name\|import"
fi
