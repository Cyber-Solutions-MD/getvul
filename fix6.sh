#!/bin/bash
cd ~/Desktop/getvul
echo "=== First 40 lines ==="
head -40 backend/app/vulnerabilities/router.py
echo ""
echo "=== Lines with get_current_user ==="
grep -n "get_current_user" backend/app/vulnerabilities/router.py
echo ""
echo "=== Lines with 'import' ==="
grep -n "^from\|^import" backend/app/vulnerabilities/router.py
