"""Auth API routes — login, callback, refresh, me, logout."""

from __future__ import annotations

import secrets
from typing import Annotated

import redis.asyncio as redis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.exceptions import RedisError
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
from app.redis_client import get_redis

router = APIRouter()
logger = structlog.get_logger()


@router.get("/login/{provider}", response_model=AuthorizationURL)
async def login(
    provider: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    """Initiate SSO login — returns the authorization URL to redirect the user to."""
    if provider not in ("google", "azure"):
        raise HTTPException(status_code=400, detail="Unsupported provider. Use 'google' or 'azure'.")

    state = secrets.token_urlsafe(32)
    try:
        ok = await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
    if not ok:
        raise HTTPException(status_code=500, detail="State collision — retry")

    oidc = get_provider(provider)
    authorization_url = oidc.get_authorization_url(state=state)

    return AuthorizationURL(authorization_url=authorization_url, state=state)


@router.get("/callback/{provider}", response_model=TokenResponse)
async def callback(
    provider: str,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    """Handle the OIDC callback — exchange code, upsert user, issue JWTs."""
    try:
        stored_provider = await redis_client.getdel(f"oidc:state:{state}")
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
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
    """Logout — client should discard tokens."""
    return {"message": "Logged out. Please discard your tokens."}


# ── Password auth ──


@router.post("/register")
async def register(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user with email/password."""
    from app.auth.password import register_user

    result = await register_user(
        db,
        email=body.get("email", ""),
        password=body.get("password", ""),
        display_name=body.get("display_name", ""),
        tenant_slug=body.get("tenant_slug"),
        tenant_name=body.get("tenant_name"),
    )
    if "error" in result:
        raise HTTPException(400, result["error"])

    user = result["user"]
    tenant = result["tenant"]
    from app.audit import audit
    from app.auth.schemas import CurrentUser

    cu = CurrentUser(id=user.id, tenant_id=tenant.id, email=user.email, role=user.role)
    await audit(db, cu, "auth.register", "user", str(user.id), {"email": user.email})
    await db.commit()
    return issue_tokens(user, tenant)


@router.post("/login")
async def login_password(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login with email/password."""
    from app.auth.password import login_with_password

    result = await login_with_password(db, body.get("email", ""), body.get("password", ""))
    if "error" in result:
        raise HTTPException(401, result["error"])

    user = result["user"]
    tenant = result["tenant"]
    from app.audit import audit
    from app.auth.schemas import CurrentUser

    cu = CurrentUser(id=user.id, tenant_id=tenant.id, email=user.email, role=user.role)
    await audit(db, cu, "auth.login", "user", str(user.id), {"method": "password"})
    await db.commit()
    return issue_tokens(user, tenant)


@router.post("/change-password")
async def change_password_endpoint(
    body: dict,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change current user's password.

    When the caller is a flagged (must_change_password) user, this completes the
    forced first-login rotation (D-09): clear the DB flag, emit an
    auth.first_login_rotation audit row BEFORE commit (AUDIT-01 fail-closed),
    then return fresh flag-free tokens so the client needs no extra round-trip.
    """
    from app.auth.password import change_password

    flag_was_set = user.must_change_password
    new_password = body.get("new_password", "")

    # Belt-and-suspenders (T-06-default-cred-reuse): the default tenant has
    # history_count=0, so password-history reuse-prevention is disabled. A
    # flagged admin could otherwise "rotate" back to the install credential —
    # or a trivial variant of it — and defeat the whole gate (WR-01). Reject:
    #   1. the default install credential, normalized to catch whitespace and
    #      case-fold variants (" Admin123!", "admin123!", "ADMIN123!"); and
    #   2. reuse of the caller's *current* password by hash, which generalizes
    #      the guard beyond a single hardcoded literal.
    # RESIDUAL (backlog): near-but-not-equal variants such as "Admin1234!"
    # still pass. Catching those requires a real complexity/similarity policy,
    # which is a larger design change deliberately out of scope here.
    if flag_was_set:
        from app.auth.password import verify_password

        default_install_credential = "Admin123!"
        if new_password.strip().casefold() == default_install_credential.casefold():
            raise HTTPException(400, "Choose a password other than the default install credential")

        from sqlalchemy import select

        from app.tenants.models import User

        current_hash = (await db.execute(select(User.password_hash).where(User.id == user.id))).scalar_one_or_none()
        if current_hash and verify_password(new_password, current_hash):
            raise HTTPException(400, "Choose a password different from your current one")

    result = await change_password(
        db,
        user.id,
        current_password=body.get("current_password"),
        new_password=new_password,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])

    if not flag_was_set:
        await db.commit()
        return result

    # Flagged rotation completion — strict order: clear flag -> audit -> commit -> issue_tokens.
    from sqlalchemy import select

    from app.audit import audit
    from app.tenants.models import Tenant, User

    user_row = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
    tenant_row = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    user_row.must_change_password = False

    await audit(db, user, "auth.first_login_rotation", "user", str(user.id), {"email": user.email})
    await db.commit()
    await db.refresh(user_row)

    return issue_tokens(user_row, tenant_row)


@router.post("/forgot-password")
async def forgot_password(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Request a password reset email. Public endpoint — no auth required."""
    from app.auth.password import request_password_reset

    email = (body.get("email") or "").strip()
    if not email:
        raise HTTPException(400, "Email is required")

    result = await request_password_reset(db, email)
    await db.commit()
    return result


@router.post("/reset-password")
async def reset_password(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirm password reset with token. Public endpoint — no auth required."""
    from app.auth.password import confirm_password_reset

    token = (body.get("token") or "").strip()
    new_password = body.get("new_password", "")

    if not token:
        raise HTTPException(400, "Reset token is required")
    if not new_password:
        raise HTTPException(400, "New password is required")

    result = await confirm_password_reset(db, token, new_password)
    if "error" in result:
        raise HTTPException(400, result["error"])
    await db.commit()
    return result


@router.get("/config")
async def auth_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_slug: str | None = Query(None),
):
    """Public endpoint — returns auth config for the login page.

    Tells the frontend which login methods are available.
    """
    from sqlalchemy import select

    from app.tenants.models import Tenant

    config = {
        "password_login": True,
        "sso_providers": [],
        "sso_enforced": False,
        "tenant_name": None,
    }

    tenant = None
    if tenant_slug:
        # Sanitize: strip null bytes and control characters that crash PostgreSQL
        safe_slug = tenant_slug.replace("\x00", "").strip()[:63]
        if safe_slug:
            tenant = (
                await db.execute(select(Tenant).where(Tenant.slug == safe_slug, Tenant.is_active.is_(True)))
            ).scalar_one_or_none()

    if tenant:
        config["tenant_found"] = True
        config["sso_enforced"] = tenant.sso_enforced
        if tenant.sso_enforced:
            config["password_login"] = False  # Disabled unless user has override
        if tenant.idp_provider == "GOOGLE":
            config["sso_providers"].append("google")
        elif tenant.idp_provider == "AZURE_ENTRA_ID":
            config["sso_providers"].append("azure")
        elif tenant.idp_provider == "LOCAL":
            pass  # No SSO, password only
        else:
            # Both available
            config["sso_providers"] = ["google", "azure"]

    return config
