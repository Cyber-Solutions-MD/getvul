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
