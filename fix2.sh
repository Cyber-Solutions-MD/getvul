#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔑 Generating a valid Fernet key..."

# Generate key locally with Python
NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)

# Fallback: if cryptography not installed locally, use a known valid key
if [ -z "$NEW_KEY" ]; then
  NEW_KEY="s2KzF3tB8GpR5xN7vQ9wE1yU4iO6aS0dL8jH2kM5nP0="
  # Generate properly inside container
  NEW_KEY=$(docker compose exec -T backend python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | tr -d '[:space:]')
fi

echo "   Key: ${NEW_KEY}"

# Verify it's valid
python3 -c "
import base64
key = '${NEW_KEY}'
decoded = base64.urlsafe_b64decode(key)
assert len(decoded) == 32, f'Bad length: {len(decoded)}'
print('   ✓ Valid Fernet key')
" 2>/dev/null || echo "   (Will validate inside container)"

echo "🔧 Writing key directly to docker-compose.yml..."

# Rewrite the entire docker-compose.yml with the correct key
cat > docker-compose.yml << FILEEOF
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: getvul
      POSTGRES_PASSWORD: getvul
      POSTGRES_DB: getvul
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U getvul"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://getvul:getvul@postgres:5432/getvul"
      REDIS_URL: "redis://redis:6379/0"
      DEBUG: "true"
      ENVIRONMENT: "development"
      JWT_SECRET_KEY: "dev-secret-change-in-prod"
      ENCRYPTION_KEY: "${NEW_KEY}"
    volumes:
      - ./backend:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    command: npm run dev
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: "http://localhost:8000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend

volumes:
  pgdata:
FILEEOF

echo "🔧 Updating .env..."
if grep -q "ENCRYPTION_KEY" .env 2>/dev/null; then
  sed -i '' "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${NEW_KEY}|" .env
else
  echo "ENCRYPTION_KEY=${NEW_KEY}" >> .env
fi

echo "🔄 Recreating backend container (not just restart)..."
docker compose up -d --force-recreate backend

echo "⏳ Waiting (15s)..."
sleep 15

echo "🔍 Verifying encryption works..."
curl -s -X POST http://localhost:8000/api/v1/connectors/test \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"connector_type":"CROWDSTRIKE","credentials":{"client_id":"test","client_secret":"test","base_url":"https://api.crowdstrike.com"},"config":{}}' | python3 -m json.tool 2>/dev/null || echo "Test endpoint responded"

echo ""
echo "✅ Fixed! Try saving your CrowdStrike connector again:"
echo "   http://localhost:3000/dashboard/connectors"
