"""Auth service — handles SSO callback, user upsert, token issuance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
    result = await db.execute(select(Tenant).where(Tenant.domain == domain, Tenant.is_active.is_(True)))
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
        existing_users = await db.execute(select(User).where(User.tenant_id == tenant.id).limit(1))
        is_first_user = existing_users.scalar_one_or_none() is None

        user = User(
            tenant_id=tenant.id,
            email=userinfo.email.lower(),
            display_name=userinfo.name,
            avatar_url=userinfo.picture,
            role=UserRole.OWNER if is_first_user else UserRole.VIEWER,
            idp_subject=userinfo.subject,
            last_login_at=datetime.now(UTC),
        )
        db.add(user)
    else:
        # Update existing user
        user.display_name = userinfo.name or user.display_name
        user.avatar_url = userinfo.picture or user.avatar_url
        user.idp_subject = userinfo.subject
        user.last_login_at = datetime.now(UTC)

    await db.flush()
    return user


def issue_tokens(user: User, tenant: Tenant) -> TokenResponse:
    """Issue JWT access + refresh tokens for an authenticated user."""
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        must_change_password=user.must_change_password,
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
            must_change_password=user.must_change_password,
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
    result = await db.execute(select(User).where(User.id == uuid.UUID(payload.sub), User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found or deactivated")

    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        must_change_password=user.must_change_password,
    )

    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
