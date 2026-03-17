#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing backend Dockerfile..."

cat > backend/Dockerfile << 'FILEEOF'
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
FILEEOF

echo "🔧 Removing obsolete version from docker-compose.yml..."
sed -i '' '1{/^version:/d;}' docker-compose.yml

echo "🔄 Rebuilding containers..."
docker compose down
docker compose up --build -d

echo "⏳ Waiting for backend to start..."
sleep 10

echo "🔍 Testing endpoints..."
echo ""
echo "Health check:"
curl -s http://localhost:8000/health
echo ""
echo ""
echo "Auth /me (expect 401):"
curl -s http://localhost:8000/auth/me
echo ""
echo ""
echo "Auth login/google:"
curl -s http://localhost:8000/auth/login/google | head -c 200
echo ""
echo ""
echo "✅ Done! Backend running at http://localhost:8000"
echo "   Swagger docs: http://localhost:8000/docs"
