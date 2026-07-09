"""Phase 06 — default-admin hardening (PROD-06-01..04) test suite.

Node IDs are contractually fixed by 06-VALIDATION.md and must match
character-for-character; Waves 1-3 turn these green in order:

  Wave 1 (Plan 01): test_migration_column, test_seed_flag
  Wave 2 (Plan 02): test_jwt_claim_round_trip, test_current_user_claim,
    test_enforcement_blocks, test_enforcement_allowlist_me,
    test_enforcement_allowlist_change, test_unflagged_user_unblocked,
    test_rotation_clears_flag, test_rotation_audit_event,
    test_rotation_fresh_tokens, test_refresh_reads_current_flag
  Wave 3 (Plan 03): frontend change-password.test.tsx (separate file)

NOTE: This file is the Wave-0 dependency (Plan 00). It was created here as a
Rule-3 blocking-issue fix because Plan 00 had not been merged onto this
executor's base at spawn time (parallel-worktree stale-base). The two Wave-1
cases (test_migration_column, test_seed_flag) are implemented GREEN by Plan 01;
the remaining ten are honest RED stubs (no skip/xfail) that assert the real
Wave 2/3 behaviour and fail until those waves land.

Env (MEMORY.md getvul-backend-pytest-env): ENCRYPTION_KEY + JWT_SECRET_KEY must
be set; run this file on its own, not the whole tests/ dir.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


# ── Wave 1 (Plan 01) — GREEN ────────────────────────────────────────────────


async def test_migration_column(db_session) -> None:
    """users.must_change_password is boolean, NOT NULL, server_default false.

    Verified two ways: information_schema metadata, and a row inserted WITHOUT
    the column reads back as False (proving the server_default false applies —
    T-06-01-02, no NULL-bypass of the enforcement gate).
    """
    meta = await db_session.execute(
        text(
            "SELECT data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'must_change_password'"
        )
    )
    row = meta.first()
    assert row is not None, "users.must_change_password column is missing"
    data_type, is_nullable, column_default = row
    assert data_type == "boolean"
    assert is_nullable == "NO"  # NOT NULL
    assert column_default is not None and "false" in column_default.lower()

    # A tenant + user inserted without setting the flag must default to False.
    tenant_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO tenants (id, name, slug, domain, idp_provider, is_active) "
            "VALUES (:id, :name, :slug, :domain, 'GOOGLE', true)"
        ),
        {
            "id": str(tenant_id),
            "name": f"mig-{tenant_id.hex[:8]}",
            "slug": f"mig-{tenant_id.hex[:8]}",
            "domain": f"mig-{tenant_id.hex[:8]}.test",
        },
    )
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, display_name, role, is_active, idp_subject) "
            "VALUES (:id, :tid, :email, 'Mig User', 'VIEWER', true, :sub)"
        ),
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": f"mig-{user_id.hex[:8]}@test.local",
            "sub": f"mig-{user_id.hex[:8]}",
        },
    )
    flag = await db_session.execute(
        text("SELECT must_change_password FROM users WHERE id = :id"),
        {"id": str(user_id)},
    )
    assert flag.scalar() is False


async def test_seed_flag(db_session) -> None:
    """A user seeded by create_admin.py has must_change_password = True (D-02).

    Runs the real seed path against a clean users table and asserts the OWNER
    admin row carries the flag (T-06-01-01).
    """
    import create_admin

    # create_admin() short-circuits if any password user already exists, so
    # clear the table first to guarantee the seed actually runs.
    await db_session.execute(text("TRUNCATE TABLE users, tenants RESTART IDENTITY CASCADE"))
    await db_session.commit()

    await create_admin.create_admin()

    result = await db_session.execute(
        text(
            "SELECT must_change_password FROM users "
            "WHERE email = 'admin@getvul.local' AND role = 'OWNER'"
        )
    )
    assert result.scalar() is True


# ── Wave 2 (Plan 02) — RED until enforcement/rotation land ──────────────────


async def test_jwt_claim_round_trip() -> None:
    from app.auth.jwt import create_access_token, decode_token

    token = create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        email="claim@test.local",
        role="OWNER",
        must_change_password=True,
    )
    assert decode_token(token).must_change_password is True

    default = create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        email="claim2@test.local",
        role="OWNER",
    )
    assert decode_token(default).must_change_password is False


async def test_current_user_claim(client_factory) -> None:
    pytest.fail("Wave 2: get_current_user must expose must_change_password (not yet implemented)")


async def test_enforcement_blocks(client_factory) -> None:
    pytest.fail("Wave 2: flagged user on non-allowlist route must 403 password_change_required")


async def test_enforcement_allowlist_me(client_factory) -> None:
    pytest.fail("Wave 2: flagged user must reach GET /auth/me (200)")


async def test_enforcement_allowlist_change(client_factory) -> None:
    pytest.fail("Wave 2: flagged user must reach POST /auth/change-password (not 403)")


async def test_unflagged_user_unblocked(client_factory) -> None:
    pytest.fail("Wave 2: unflagged user must not be blocked by the enforcement gate")


async def test_rotation_clears_flag(client_factory) -> None:
    pytest.fail("Wave 2: successful rotation must set must_change_password=False")


async def test_rotation_audit_event(client_factory) -> None:
    pytest.fail("Wave 2: rotation must emit auth.first_login_rotation audit row")


async def test_rotation_fresh_tokens(client_factory) -> None:
    pytest.fail("Wave 2: rotation response tokens must not carry the flag")


async def test_refresh_reads_current_flag(client_factory) -> None:
    pytest.fail("Wave 2: /auth/refresh must reflect the current DB flag (false) after rotation")
