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
    sso_enforced: bool = False
    timezone: str = "UTC"

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    allow_password_login: bool = True
    groups: list | None = None
    department: str | None = None
    job_title: str | None = None
    idp_source: str | None = None
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: str
