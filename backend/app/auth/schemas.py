"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Represents the authenticated user extracted from JWT."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    must_change_password: bool = False


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
    # PROD-06-03 / SC#4: the login response must carry the forced-rotation flag
    # so the SPA can gate a flagged user onto /change-password immediately after
    # login — without waiting for a hard reload to hit /auth/me. Defaults false
    # so pre-flag callers stay valid.
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    """Request to refresh an access token."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response with a new access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
