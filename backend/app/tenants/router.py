"""Tenant and user management routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import require_admin, require_owner
from app.auth.schemas import CurrentUser
from app.dependencies import AuthenticatedUser, DBSession
from app.tenants.models import Tenant, User
from app.tenants.schemas import TenantResponse, UserResponse, UserRoleUpdate

router = APIRouter()


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(db: DBSession, user: AuthenticatedUser):
    """Get the current user's tenant info."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_admin)],
):
    """List all users in the tenant. Requires Admin role."""
    result = await db.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.email)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Update a user's role. Requires Owner role."""
    if body.role not in ("OWNER", "ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = body.role
    await db.flush()
    return target_user


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_owner)],
):
    """Deactivate a user. Requires Owner role."""
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.tenant_id == user.tenant_id)
        .values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deactivated"}
