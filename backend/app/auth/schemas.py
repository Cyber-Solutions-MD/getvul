"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr


class CurrentUser(BaseModel):
    """Represents the authenticated user extracted from JWT."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str


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


class RefreshRequest(BaseModel):
    """Request to refresh an access token."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response with a new access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
