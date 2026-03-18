#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔑 Generating valid Fernet encryption key..."

# Generate key using Python inside the running container
NEW_KEY=$(docker compose exec -T backend python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Trim any whitespace/carriage returns
NEW_KEY=$(echo "$NEW_KEY" | tr -d '[:space:]')

echo "   Key: ${NEW_KEY}"

echo "🔧 Updating docker-compose.yml..."
sed -i '' "s|ENCRYPTION_KEY:.*|ENCRYPTION_KEY: \"${NEW_KEY}\"|" docker-compose.yml

echo "🔧 Updating .env..."
if grep -q "ENCRYPTION_KEY" .env 2>/dev/null; then
  sed -i '' "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${NEW_KEY}|" .env
else
  echo "ENCRYPTION_KEY=${NEW_KEY}" >> .env
fi

echo "🔄 Restarting backend..."
docker compose restart backend

echo "⏳ Waiting (10s)..."
sleep 10

echo "🔍 Testing health..."
curl -s http://localhost:8000/health
echo ""

echo ""
echo "✅ Fixed! Now go to http://localhost:3000/dashboard/connectors"
echo "   and try saving your CrowdStrike connector again."
