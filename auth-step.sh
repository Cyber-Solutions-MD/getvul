#!/bin/bash
set -euo pipefail

# ============================================================
# GetVul — Step 4: Auth System
# SSO (Google + Azure Entra ID), JWT, RBAC
#
# Run from the getvul/ root:
#   chmod +x auth-step.sh
#   ./auth-step.sh
# ============================================================

echo "🔐 Building auth system..."

# ══════════════════════════════════════════════
#  backend/app/auth/providers.py — OIDC Providers
# ══════════════════════════════════════════════

cat > backend/app/auth/providers.py << 'FILEEOF'
"""OIDC provider implementations for Google Workspace and Azure Entra ID."""

from __future__ import annotations

import httpx

from app.config import settings


class OIDCTokens:
    """Parsed tokens from an OIDC provider."""

    def __init__(self, id_token: str, access_token: str, refresh_token: str | None = None):
        self.id_token = id_token
        self.access_token = access_token
        self.refresh_token = refresh_token


class OIDCUserInfo:
    """Normalized user info from any OIDC provider."""

    def __init__(
        self,
        subject: str,
        email: str,
        name: str | None = None,
        picture: str | None = None,
        email_verified: bool = False,
        raw: dict | None = None,
    ):
        self.subject = subject
        self.email = email
        self.name = name
        self.picture = picture
        self.email_verified = email_verified
        self.raw = raw or {}


class BaseOIDCProvider:
    """Base class for OIDC providers."""

    authorization_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})}" for k, v in params.items())
        # Use httpx to build clean query string
        return f"{self.authorization_url}?{httpx.QueryParams(params)}"

    async def exchange_code(self, code: str) -> OIDCTokens:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        return OIDCTokens(
            id_token=data["id_token"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
        )

    async def get_userinfo(self, access_token: str) -> OIDCUserInfo:
        """Fetch user info from the provider's userinfo endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_userinfo(data)

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        raise NotImplementedError


class GoogleOIDCProvider(BaseOIDCProvider):
    """Google Workspace OIDC provider."""

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scopes = ["openid", "email", "profile"]

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        return OIDCUserInfo(
            subject=data["sub"],
            email=data["email"],
            name=data.get("name"),
            picture=data.get("picture"),
            email_verified=data.get("email_verified", False),
            raw=data,
        )


class AzureOIDCProvider(BaseOIDCProvider):
    """Azure Entra ID OIDC provider."""

    userinfo_url = "https://graph.microsoft.com/oidc/userinfo"
    scopes = ["openid", "email", "profile", "User.Read"]

    def __init__(self, azure_tenant_id: str = "common"):
        self.azure_tenant_id = azure_tenant_id
        self.authorization_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/authorize"
        self.token_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
        self.client_id = settings.azure_client_id
        self.client_secret = settings.azure_client_secret
        self.redirect_uri = settings.azure_redirect_uri

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        return OIDCUserInfo(
            subject=data.get("sub", ""),
            email=data.get("email", ""),
            name=data.get("name"),
            picture=None,  # Azure userinfo doesn't return picture
            email_verified=True,  # Azure validates email at tenant level
            raw=data,
        )


def get_provider(provider_name: str, azure_tenant_id: str = "common") -> BaseOIDCProvider:
    """Factory to get the right OIDC provider."""
    if provider_name == "google":
        return GoogleOIDCProvider()
    elif provider_name == "azure":
        return AzureOIDCProvider(azure_tenant_id=azure_tenant_id)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/jwt.py — JWT Token Management
# ══════════════════════════════════════════════

cat > backend/app/auth/jwt.py << 'FILEEOF'
"""JWT token creation and verification."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


class TokenPayload:
    """Decoded JWT payload."""

    def __init__(
        self,
        sub: str,
        tenant_id: str,
        email: str,
        role: str,
        token_type: str = "access",
        exp: datetime | None = None,
        jti: str | None = None,
    ):
        self.sub = sub
        self.tenant_id = tenant_id
        self.email = email
        self.role = role
        self.token_type = token_type
        self.exp = exp
        self.jti = jti or str(uuid.uuid4())


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str,
    role: str,
) -> str:
    """Create a short-lived access token (15 min default)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    tenant_id: str,
) -> str:
    """Create a long-lived refresh token (7 days default)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise

    return TokenPayload(
        sub=payload["sub"],
        tenant_id=payload.get("tenant_id", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "VIEWER"),
        token_type=payload.get("type", "access"),
        jti=payload.get("jti"),
    )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/rbac.py — Role-Based Access Control
# ══════════════════════════════════════════════

cat > backend/app/auth/rbac.py << 'FILEEOF'
"""Role-based access control dependencies for FastAPI."""

from __future__ import annotations

from functools import wraps
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.tenants.models import UserRole

# Role hierarchy: Owner > Admin > Analyst > Viewer
ROLE_HIERARCHY: dict[str, int] = {
    UserRole.OWNER.value: 40,
    UserRole.ADMIN.value: 30,
    UserRole.ANALYST.value: 20,
    UserRole.VIEWER.value: 10,
}


def _check_role(user: CurrentUser, minimum_role: str) -> bool:
    user_level = ROLE_HIERARCHY.get(user.role, 0)
    required_level = ROLE_HIERARCHY.get(minimum_role, 100)
    return user_level >= required_level


class RequireRole:
    """FastAPI dependency that enforces a minimum role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: CurrentUser = Depends(RequireRole("ADMIN"))):
            ...
    """

    def __init__(self, minimum_role: str):
        self.minimum_role = minimum_role

    async def __call__(
        self, user: Annotated[CurrentUser, Depends(get_current_user)]
    ) -> CurrentUser:
        if not _check_role(user, self.minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.minimum_role} role or higher",
            )
        return user


# Convenience dependencies
require_viewer = RequireRole(UserRole.VIEWER.value)
require_analyst = RequireRole(UserRole.ANALYST.value)
require_admin = RequireRole(UserRole.ADMIN.value)
require_owner = RequireRole(UserRole.OWNER.value)
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/schemas.py — Auth Pydantic Schemas
# ══════════════════════════════════════════════

cat > backend/app/auth/schemas.py << 'FILEEOF'
"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr


class CurrentUser(BaseModel):
    """Represents the authenticated user extracted from JWT."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str


class AuthorizationURL(BaseModel):
    """Response for the login initiation endpoint."""

    authorization_url: str
    state: str


class TokenResponse(BaseModel):
    """Response after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo


class UserInfo(BaseModel):
    """User info returned after login."""

    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: str
    tenant_id: uuid.UUID
    tenant_name: str


class RefreshRequest(BaseModel):
    """Request to refresh an access token."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response with a new access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/dependencies.py — FastAPI Auth Dependencies
# ══════════════════════════════════════════════

cat > backend/app/auth/dependencies.py << 'FILEEOF'
"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt import decode_token
from app.auth.schemas import CurrentUser

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    """Extract and validate the current user from the JWT bearer token.

    Used as a FastAPI dependency:
        @router.get("/me")
        async def me(user: CurrentUser = Depends(get_current_user)):
            return user
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return CurrentUser(
        id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        email=payload.email,
        role=payload.role,
    )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/service.py — Auth Business Logic
# ══════════════════════════════════════════════

cat > backend/app/auth/service.py << 'FILEEOF'
"""Auth service — handles SSO callback, user upsert, token issuance."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.providers import OIDCUserInfo
from app.auth.schemas import RefreshResponse, TokenResponse, UserInfo
from app.config import settings
from app.tenants.models import Tenant, User, UserRole


async def resolve_tenant_by_email(db: AsyncSession, email: str) -> Tenant | None:
    """Find the tenant by matching the user's email domain."""
    domain = email.split("@")[1].lower()
    result = await db.execute(
        select(Tenant).where(Tenant.domain == domain, Tenant.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def upsert_user(
    db: AsyncSession,
    tenant: Tenant,
    userinfo: OIDCUserInfo,
) -> User:
    """Create or update a user from SSO login."""
    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant.id,
            User.email == userinfo.email.lower(),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        # First user in a tenant becomes OWNER, rest are VIEWER
        existing_users = await db.execute(
            select(User).where(User.tenant_id == tenant.id).limit(1)
        )
        is_first_user = existing_users.scalar_one_or_none() is None

        user = User(
            tenant_id=tenant.id,
            email=userinfo.email.lower(),
            display_name=userinfo.name,
            avatar_url=userinfo.picture,
            role=UserRole.OWNER if is_first_user else UserRole.VIEWER,
            idp_subject=userinfo.subject,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        # Update existing user
        user.display_name = userinfo.name or user.display_name
        user.avatar_url = userinfo.picture or user.avatar_url
        user.idp_subject = userinfo.subject
        user.last_login_at = datetime.now(timezone.utc)

    await db.flush()
    return user


def issue_tokens(user: User, tenant: Tenant) -> TokenResponse:
    """Issue JWT access + refresh tokens for an authenticated user."""
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserInfo(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
        ),
    )


async def refresh_access_token(db: AsyncSession, refresh_token_str: str) -> RefreshResponse:
    """Validate a refresh token and issue a new access token."""
    from jose import JWTError

    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise ValueError("Invalid refresh token")

    if payload.token_type != "refresh":
        raise ValueError("Not a refresh token")

    # Look up the user to get current role (may have changed)
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload.sub), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found or deactivated")

    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
    )

    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/auth/router.py — Auth API Routes
# ══════════════════════════════════════════════

cat > backend/app/auth/router.py << 'FILEEOF'
"""Auth API routes — login, callback, refresh, me, logout."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.providers import get_provider
from app.auth.schemas import (
    AuthorizationURL,
    CurrentUser,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
)
from app.auth.service import (
    issue_tokens,
    refresh_access_token,
    resolve_tenant_by_email,
    upsert_user,
)
from app.db.session import get_db

router = APIRouter()

# In-memory state store (use Redis in production)
_pending_states: dict[str, str] = {}


@router.get("/login/{provider}", response_model=AuthorizationURL)
async def login(provider: str):
    """Initiate SSO login — returns the authorization URL to redirect the user to."""
    if provider not in ("google", "azure"):
        raise HTTPException(status_code=400, detail="Unsupported provider. Use 'google' or 'azure'.")

    state = secrets.token_urlsafe(32)
    _pending_states[state] = provider

    oidc = get_provider(provider)
    authorization_url = oidc.get_authorization_url(state=state)

    return AuthorizationURL(authorization_url=authorization_url, state=state)


@router.get("/callback/{provider}", response_model=TokenResponse)
async def callback(
    provider: str,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Handle the OIDC callback — exchange code, upsert user, issue JWTs."""
    # Validate state
    stored_provider = _pending_states.pop(state, None)
    if stored_provider is None or stored_provider != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    # Exchange authorization code for tokens
    oidc = get_provider(provider)
    try:
        tokens = await oidc.exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    # Fetch user info
    try:
        userinfo = await oidc.get_userinfo(tokens.access_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {e}")

    if not userinfo.email:
        raise HTTPException(status_code=400, detail="No email in user info")

    # Resolve tenant
    tenant = await resolve_tenant_by_email(db, userinfo.email)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tenant configured for domain '{userinfo.email.split('@')[1]}'",
        )

    # Upsert user
    user = await upsert_user(db, tenant, userinfo)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Issue GetVul JWTs
    return issue_tokens(user, tenant)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh an access token using a valid refresh token."""
    try:
        return await refresh_access_token(db, body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=CurrentUser)
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    """Return the currently authenticated user."""
    return user


@router.post("/logout")
async def logout():
    """Logout — client should discard tokens.

    Server-side token revocation can be added with a Redis blocklist.
    """
    return {"message": "Logged out. Please discard your tokens."}
FILEEOF

# ══════════════════════════════════════════════
#  backend/app/dependencies.py — Shared Dependencies
# ══════════════════════════════════════════════

cat > backend/app/dependencies.py << 'FILEEOF'
"""Shared FastAPI dependencies used across routers."""

from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.db.session import AsyncSession, get_db

# Type aliases for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]
AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
FILEEOF

# ══════════════════════════════════════════════
#  Update backend/app/main.py — Register auth router
# ══════════════════════════════════════════════

cat > backend/app/main.py << 'FILEEOF'
"""GetVul API — entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import settings

app = FastAPI(
    title="GetVul API",
    description="Unified Vulnerability Aggregation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if settings.debug else ["https://*.getvul.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "getvul-api"}
FILEEOF

# ══════════════════════════════════════════════
#  backend/tests/test_auth.py — Auth Tests
# ══════════════════════════════════════════════

cat > backend/tests/test_auth.py << 'FILEEOF'
"""Tests for the auth system — JWT, RBAC, endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.rbac import ROLE_HIERARCHY, _check_role
from app.auth.schemas import CurrentUser
from app.config import settings


# ── JWT Tests ──


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            email="test@example.com",
            role="ADMIN",
        )
        assert isinstance(token, str)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "ADMIN"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id=user_id, tenant_id=str(uuid.uuid4()))
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_decode_valid_token(self):
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        token = create_access_token(
            user_id=user_id, tenant_id=tenant_id, email="a@b.com", role="VIEWER",
        )
        decoded = decode_token(token)
        assert decoded.sub == user_id
        assert decoded.tenant_id == tenant_id
        assert decoded.role == "VIEWER"

    def test_decode_expired_token(self):
        from jose import JWTError

        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "email": "a@b.com",
            "role": "VIEWER",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_invalid_secret(self):
        from jose import JWTError

        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            email="a@b.com",
            role="VIEWER",
        )
        # Tamper: decode with wrong secret
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])


# ── RBAC Tests ──


class TestRBAC:
    def _make_user(self, role: str) -> CurrentUser:
        return CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="test@example.com",
            role=role,
        )

    def test_owner_can_access_everything(self):
        user = self._make_user("OWNER")
        assert _check_role(user, "OWNER") is True
        assert _check_role(user, "ADMIN") is True
        assert _check_role(user, "ANALYST") is True
        assert _check_role(user, "VIEWER") is True

    def test_viewer_cannot_access_admin(self):
        user = self._make_user("VIEWER")
        assert _check_role(user, "VIEWER") is True
        assert _check_role(user, "ANALYST") is False
        assert _check_role(user, "ADMIN") is False
        assert _check_role(user, "OWNER") is False

    def test_analyst_can_access_analyst_and_below(self):
        user = self._make_user("ANALYST")
        assert _check_role(user, "ANALYST") is True
        assert _check_role(user, "VIEWER") is True
        assert _check_role(user, "ADMIN") is False

    def test_role_hierarchy_ordering(self):
        assert ROLE_HIERARCHY["OWNER"] > ROLE_HIERARCHY["ADMIN"]
        assert ROLE_HIERARCHY["ADMIN"] > ROLE_HIERARCHY["ANALYST"]
        assert ROLE_HIERARCHY["ANALYST"] > ROLE_HIERARCHY["VIEWER"]
FILEEOF

# ══════════════════════════════════════════════
#  COMMIT & PUSH
# ══════════════════════════════════════════════

echo "📝 Committing auth system..."

git add -A
git commit -m "feat: auth system — SSO, JWT, RBAC

- OIDC providers: Google Workspace + Azure Entra ID
- JWT: access tokens (15 min) + refresh tokens (7 days)
- RBAC: Owner > Admin > Analyst > Viewer hierarchy
- Auth router: /auth/login, /auth/callback, /auth/refresh, /auth/me
- Auth service: tenant resolution by email domain, user upsert
- FastAPI dependencies: get_current_user, RequireRole
- Tests: JWT creation/decode/expiry, RBAC role hierarchy"

git push

echo ""
echo "✅ Auth system committed and pushed!"
echo ""
echo "🔍 Verify:"
echo "   make dev"
echo "   open http://localhost:8000/docs"
echo "   → Try GET /auth/login/google"
echo "   → Try GET /auth/me (will return 401 — expected)"
echo ""
echo "📋 Auth endpoints:"
echo "   GET  /auth/login/{provider}    → Get SSO authorization URL"
echo "   GET  /auth/callback/{provider} → Handle SSO callback → returns JWT"
echo "   POST /auth/refresh             → Refresh access token"
echo "   GET  /auth/me                  → Current user info (requires JWT)"
echo "   POST /auth/logout              → Logout"
FILEEOF

echo ""
echo "✅ Auth system built!"
