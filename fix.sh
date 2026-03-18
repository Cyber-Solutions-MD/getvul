#!/bin/bash
set -euo pipefail

cd ~/Desktop/getvul

echo "🔧 Fixing enum types in tenant model..."

cat > backend/app/tenants/models.py << 'FILEEOF'
"""Tenant and User SQLAlchemy models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdPProvider(str, enum.Enum):
    GOOGLE = "GOOGLE"
    AZURE_ENTRA_ID = "AZURE_ENTRA_ID"


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    idp_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    idp_tenant_id: Mapped[str | None] = mapped_column(String(255))
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="VIEWER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    idp_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
FILEEOF

echo "🔧 Fixing seed.py to use string values instead of enums..."

sed -i '' 's/idp_provider=IdPProvider.GOOGLE/idp_provider="GOOGLE"/' backend/app/seed.py
sed -i '' 's/role=UserRole.OWNER/role="OWNER"/' backend/app/seed.py

echo "🔧 Resetting database (fresh migration)..."
docker compose down -v
docker compose up -d

echo "⏳ Waiting for services (30s)..."
sleep 30

echo "🔍 Seeding..."
curl -s -X POST http://localhost:8000/dev/seed
echo ""
echo ""

echo "🔍 Testing vuln list..."
curl -s "http://localhost:8000/api/v1/vulnerabilities?page_size=2" -H "Authorization: Bearer dev-token" | head -c 300
echo ""
echo ""

echo "🔍 Testing stats..."
curl -s "http://localhost:8000/api/v1/vulnerabilities/stats" -H "Authorization: Bearer dev-token"
echo ""

echo ""
echo "✅ Fixed! Commit and push:"
echo "   git add -A && git commit -m 'fix: use String columns instead of PG enum types' && git push"
