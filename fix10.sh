#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "=== Current top imports ==="
head -30 backend/app/vulnerabilities/router.py
echo ""

echo "🔧 Forcing all needed imports at top of file..."

python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    lines = f.readlines()

# Build the required imports block
required_imports = [
    "from sqlalchemy import select, func, case\n",
    "from app.vulnerabilities.models import Vulnerability\n",
    "from app.assets.models import Asset\n",
]

# Find the line after 'from __future__ import annotations'
insert_after = None
existing = set()
for i, line in enumerate(lines):
    stripped = line.strip()
    # Track what's already imported
    if "from sqlalchemy import" in stripped and "select" in stripped:
        existing.add("sqlalchemy")
    if "from app.vulnerabilities.models import Vulnerability" in stripped:
        existing.add("vuln_model")
    if "from app.assets.models import Asset" in stripped:
        existing.add("asset_model")
    # Find last import line
    if stripped.startswith("from ") or stripped.startswith("import "):
        insert_after = i

# Add missing imports right after the last import
to_add = []
if "sqlalchemy" not in existing:
    to_add.append(required_imports[0])
if "vuln_model" not in existing:
    to_add.append(required_imports[1])
if "asset_model" not in existing:
    to_add.append(required_imports[2])

if to_add and insert_after is not None:
    for j, imp in enumerate(to_add):
        lines.insert(insert_after + 1 + j, imp)
    print(f"Added {len(to_add)} imports after line {insert_after + 1}")
else:
    print(f"All imports present (sqlalchemy={'✓' if 'sqlalchemy' in existing else '✗'}, Vulnerability={'✓' if 'vuln_model' in existing else '✗'}, Asset={'✓' if 'asset_model' in existing else '✗'})")

with open("backend/app/vulnerabilities/router.py", "w") as f:
    f.writelines(lines)
PYEOF

echo ""
echo "=== Verify imports ==="
grep -n "from sqlalchemy\|from app.vulnerabilities.models\|from app.assets.models" backend/app/vulnerabilities/router.py

echo ""
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
