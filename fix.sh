#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing pyproject.toml — exclude alembic from package discovery..."

cat > backend/pyproject.toml << 'FILEEOF'
[project]
name = "getvul-backend"
version = "0.1.0"
description = "GetVul — Unified Vulnerability Aggregation Platform"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "python-jose[cryptography]>=3.3",
    "httpx>=0.27",
    "boto3>=1.35",
    "orjson>=3.10",
    "tenacity>=9.0",
    "croniter>=3.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.27",
    "ruff>=0.8",
    "mypy>=1.13",
    "factory-boy>=3.3",
]

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["alembic*", "tests*"]

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
strict = true
FILEEOF

echo "🔧 Removing obsolete version from docker-compose.yml..."
sed -i '' '/^version:/d' docker-compose.yml

echo "🔄 Rebuilding (no cache)..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "⏳ Waiting for services to start..."
sleep 15

echo "🔍 Checking containers..."
docker compose ps

echo ""
echo "🔍 Testing endpoints..."
echo "Health:"
curl -s http://localhost:8000/health || echo "  ⚠️  Backend not responding yet"
echo ""
echo "Auth /me:"
curl -s http://localhost:8000/auth/me || echo "  ⚠️  Backend not responding yet"
echo ""

echo ""
echo "If backend isn't up yet, check logs:"
echo "  docker compose logs backend --tail 30"
