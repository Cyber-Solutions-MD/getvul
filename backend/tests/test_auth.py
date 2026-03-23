"""Tests for the auth system — JWT, RBAC, endpoints."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.rbac import ROLE_HIERARCHY, _check_role
from app.auth.schemas import CurrentUser
from app.config import settings

# ── JWT Tests ──


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            email="test@example.com",
            role="ADMIN",
        )
        assert isinstance(token, str)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "ADMIN"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id=user_id, tenant_id=str(uuid.uuid4()))
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_decode_valid_token(self):
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        token = create_access_token(
            user_id=user_id, tenant_id=tenant_id, email="a@b.com", role="VIEWER",
        )
        decoded = decode_token(token)
        assert decoded.sub == user_id
        assert decoded.tenant_id == tenant_id
        assert decoded.role == "VIEWER"

    def test_decode_expired_token(self):
        from jose import JWTError

        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "email": "a@b.com",
            "role": "VIEWER",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_invalid_secret(self):
        from jose import JWTError

        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            email="a@b.com",
            role="VIEWER",
        )
        # Tamper: decode with wrong secret
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])  # nosemgrep: python-pyjwt-hardcoded-secret


# ── RBAC Tests ──


class TestRBAC:
    def _make_user(self, role: str) -> CurrentUser:
        return CurrentUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="test@example.com",
            role=role,
        )

    def test_owner_can_access_everything(self):
        user = self._make_user("OWNER")
        assert _check_role(user, "OWNER") is True
        assert _check_role(user, "ADMIN") is True
        assert _check_role(user, "ANALYST") is True
        assert _check_role(user, "VIEWER") is True

    def test_viewer_cannot_access_admin(self):
        user = self._make_user("VIEWER")
        assert _check_role(user, "VIEWER") is True
        assert _check_role(user, "ANALYST") is False
        assert _check_role(user, "ADMIN") is False
        assert _check_role(user, "OWNER") is False

    def test_analyst_can_access_analyst_and_below(self):
        user = self._make_user("ANALYST")
        assert _check_role(user, "ANALYST") is True
        assert _check_role(user, "VIEWER") is True
        assert _check_role(user, "ADMIN") is False

    def test_role_hierarchy_ordering(self):
        assert ROLE_HIERARCHY["OWNER"] > ROLE_HIERARCHY["ADMIN"]
        assert ROLE_HIERARCHY["ADMIN"] > ROLE_HIERARCHY["ANALYST"]
        assert ROLE_HIERARCHY["ANALYST"] > ROLE_HIERARCHY["VIEWER"]
