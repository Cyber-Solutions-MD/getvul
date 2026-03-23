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
    """Change current user's password."""
    from app.auth.password import change_password

    result = await change_password(
        db, user.id,
        current_password=body.get("current_password"),
        new_password=body.get("new_password", ""),
    )
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
        tenant = (await db.execute(
            select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True))
        )).scalar_one_or_none()

    if tenant:
        config["tenant_name"] = tenant.name
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
