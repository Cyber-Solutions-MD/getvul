#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    lines = f.readlines()

# Remove the misplaced imports at lines 147-148 (0-indexed: 146-147)
new_lines = []
for i, line in enumerate(lines):
    # Skip the two misplaced import lines inside the function
    if i == 146 and "from sqlalchemy import select, func, case" in line:
        continue
    if i == 147 and "from app.assets.models import Asset" in line:
        continue
    new_lines.append(line)

# Now ensure these imports exist at the top (after line 14)
content = "".join(new_lines)
if "from sqlalchemy import select, func, case" not in content:
    content = content.replace(
        "from app.vulnerabilities.models import Vulnerability\n",
        "from sqlalchemy import select, func, case\nfrom app.assets.models import Asset\nfrom app.vulnerabilities.models import Vulnerability\n",
    )
elif "from app.assets.models import Asset" not in content:
    content = content.replace(
        "from app.vulnerabilities.models import Vulnerability\n",
        "from app.assets.models import Asset\nfrom app.vulnerabilities.models import Vulnerability\n",
    )

with open("backend/app/vulnerabilities/router.py", "w") as f:
    f.write(content)

print("✓ Fixed: moved imports to top, removed from function body")
PYEOF

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
  docker compose logs backend --tail 5 2>&1 | grep "Error\|error"
fi
