#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing docker-compose.yml..."

cat > docker-compose.yml << 'FILEEOF'
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
      ENCRYPTION_KEY: "dGhpcy1pcy1hLXRlc3Qta2V5LXBsZWFzZS1jaGFuZ2U="
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

echo "🔧 Generating a real Fernet key..."

# Generate proper Fernet key and update docker-compose
FERNET_KEY=$(docker run --rm python:3.12-slim python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "ZHVtbXkta2V5LXBsZWFzZS1yZXBsYWNlLW1l")

sed -i '' "s|ENCRYPTION_KEY:.*|ENCRYPTION_KEY: \"${FERNET_KEY}\"|" docker-compose.yml

# Also update .env
grep -q "ENCRYPTION_KEY" .env 2>/dev/null && sed -i '' "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${FERNET_KEY}|" .env || echo "ENCRYPTION_KEY=${FERNET_KEY}" >> .env

echo "🔄 Rebuilding..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "⏳ Waiting for services (30s)..."
sleep 30

echo "🔍 Testing..."
echo "Health:"
curl -s http://localhost:8000/health
echo ""
echo ""
echo "Connector types:"
curl -s http://localhost:8000/api/v1/connectors/types | head -c 300
echo ""
echo ""
echo "✅ Done!"
echo "   Frontend: http://localhost:3000/dashboard"
echo "   API docs: http://localhost:8000/docs"
