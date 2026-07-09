"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.auth.schemas import CurrentUser
from app.config import settings
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)

# D-07: the ONLY routes a flagged (must_change_password) user may reach until
# they rotate. Exact-match against request.url.path — no prefix/suffix/case
# tricks (T-06-allowlist-bypass). FastAPI normalizes router-matched paths and
# 307-redirects trailing-slash forms to these canonical values.
MUST_CHANGE_PASSWORD_ALLOWLIST = frozenset(
    {
        "/auth/change-password",
        "/auth/me",
        "/auth/logout",
        "/auth/refresh",
    }
)


async def get_current_user(
    request: Request = None,  # FastAPI injects Request positionally; default lets unit tests call directly
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> CurrentUser:
    """Extract and validate the current user from the JWT bearer token.

    Also enforces the forced-rotation gate (PROD-06-02): a flagged user is
    blocked with 403 password_change_required on every path NOT in
    MUST_CHANGE_PASSWORD_ALLOWLIST. The gate runs on both the JWT and dev-token
    paths so dev-token cannot bypass it (T-06-enforcement-completeness).
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Dev mode: accept "dev-token" and return the first owner user
    if settings.environment == "development" and token == "dev-token":
        from app.tenants.models import User

        result = await db.execute(select(User).where(User.role == "OWNER", User.is_active.is_(True)).limit(1))
        user = result.scalar_one_or_none()
        if user:
            current_user = CurrentUser(
                id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role.value if hasattr(user.role, "value") else user.role,
                must_change_password=user.must_change_password,
            )
            _enforce_password_change_gate(current_user, request)
            return current_user
        raise HTTPException(status_code=401, detail="No dev user found. Run POST /dev/seed first.")

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    current_user = CurrentUser(
        id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        email=payload.email,
        role=payload.role,
        must_change_password=payload.must_change_password,
    )
    _enforce_password_change_gate(current_user, request)
    return current_user


def _enforce_password_change_gate(current_user: CurrentUser, request: Request | None) -> None:
    """Raise 403 password_change_required if a flagged user hits a non-allowlist path.

    When request is None (a direct in-process call outside the ASGI stack, e.g. a
    unit test invoking the dependency without FastAPI wiring) the path cannot be
    resolved; the gate is a no-op in that case. In production every route reaches
    this dependency through the ASGI stack, so request is always populated.
    """
    if request is None:
        return
    if current_user.must_change_password and request.url.path not in MUST_CHANGE_PASSWORD_ALLOWLIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "password_change_required"},
        )


# ── Role-based access helpers ──

ROLE_HIERARCHY = {"owner": 4, "admin": 3, "analyst": 2, "viewer": 1}


def require_role(minimum_role: str):
    """Dependency that checks the user has at least the given role.

    Usage:
        @router.post("/classify")
        async def classify(user=Depends(require_role("admin"))):
    """
    from fastapi import Depends, HTTPException

    async def _check(user=Depends(get_current_user)):
        user_level = ROLE_HIERARCHY.get(user.role.lower() if hasattr(user.role, "lower") else str(user.role).lower(), 0)
        required_level = ROLE_HIERARCHY.get(minimum_role.lower(), 0)
        if user_level < required_level:
            raise HTTPException(403, f"Requires {minimum_role} role or higher")
        return user

    return _check
