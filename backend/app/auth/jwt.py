"""JWT token creation and verification."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


class TokenPayload:
    """Decoded JWT payload."""

    def __init__(
        self,
        sub: str,
        tenant_id: str,
        email: str,
        role: str,
        token_type: str = "access",
        exp: datetime | None = None,
        jti: str | None = None,
    ):
        self.sub = sub
        self.tenant_id = tenant_id
        self.email = email
        self.role = role
        self.token_type = token_type
        self.exp = exp
        self.jti = jti or str(uuid.uuid4())


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str,
    role: str,
) -> str:
    """Create a short-lived access token (15 min default)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    tenant_id: str,
) -> str:
    """Create a long-lived refresh token (7 days default)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise

    return TokenPayload(
        sub=payload["sub"],
        tenant_id=payload.get("tenant_id", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "VIEWER"),
        token_type=payload.get("type", "access"),
        jti=payload.get("jti"),
    )
