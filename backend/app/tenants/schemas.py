"""Pydantic schemas for tenant and user management."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    domain: str | None
    idp_provider: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: str
