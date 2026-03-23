"""FastAPI dependencies for authentication."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.auth.schemas import CurrentUser
from app.config import settings
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Extract and validate the current user from the JWT bearer token."""

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
            return CurrentUser(
                id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                role=user.role.value if hasattr(user.role, "value") else user.role,
            )
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

    return CurrentUser(
        id=uuid.UUID(payload.sub),
        tenant_id=uuid.UUID(payload.tenant_id),
        email=payload.email,
        role=payload.role,
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
