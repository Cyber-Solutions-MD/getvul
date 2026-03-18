#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

python3 << 'PYEOF'
with open("backend/app/vulnerabilities/router.py", "r") as f:
    c = f.read()

# Add select, func, case to top-level imports if not there
if "from sqlalchemy import" not in c:
    c = c.replace(
        "from fastapi import APIRouter",
        "from sqlalchemy import select, func, case\nfrom fastapi import APIRouter",
    )
else:
    # Check which are missing
    for name in ["select", "func", "case"]:
        if f"import {name}" not in c and f", {name}" not in c:
            # Add to existing sqlalchemy import
            c = c.replace("from sqlalchemy import", f"from sqlalchemy import {name}, ", 1)

# Remove local imports that are now top-level
c = c.replace("    from sqlalchemy import func, case, select\n", "")
c = c.replace("    from sqlalchemy import func, case\n", "")

with open("backend/app/vulnerabilities/router.py", "w") as f:
    f.write(c)

print("done")
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

ASSET_ID=$(curl -s "http://localhost:8000/api/v1/assets?page=1&page_size=1" \
  -H "Authorization: Bearer dev-token" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>/dev/null)

curl -s "http://localhost:8000/api/v1/vulnerabilities/hosts/$ASSET_ID/remediations" \
  -H "Authorization: Bearer dev-token" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(f'{len(d)} grouped remediations')
    for r in d[:5]:
        print(f'  [{r[\"max_severity\"]:8}] {r[\"vuln_count\"]:3} vulns — {r[\"remediation_action\"][:70]}')
except Exception as e:
    print(f'Error: {e}')
    import subprocess; subprocess.run(['docker','compose','logs','backend','--tail','5'])
"
