"""Phase 6 — Default-admin hardening (force password change on first login).

Wave 0 RED scaffold. These 12 test cases define the automated contract that
Waves 1-3 turn green (Nyquist: every downstream task verifies against a case
here). The node IDs are fixed by 06-VALIDATION.md and MUST match verbatim.

Every test asserts a not-yet-built behavior and MUST fail (RED) until the
implementing wave lands:

  - Wave 1 (Plan 01): `users.must_change_password` column + seed flag.
  - Wave 2 (Plan 02): JWT claim, CurrentUser claim, 403 enforcement gate +
    allowlist, rotation (clear flag + audit + fresh tokens), refresh reads
    the current DB flag.
  - Wave 3 (Plan 03): frontend redirect gate (separate Vitest file).

RED mechanics: where a production symbol does not exist yet (e.g. the
`must_change_password` kwarg on `create_access_token`, the `must_change_password`
attribute on `CurrentUser`, the DB column), the call/assert is written as it
WILL look post-implementation — so it fails now with TypeError / AttributeError /
ProgrammingError / AssertionError. All of those count as RED. These tests are
NOT marked as expected-failures and are NOT bypassed; they fail for real until
implemented.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with
ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update

from app.auth.jwt import create_access_token, decode_token
from app.tenants.models import User

# A non-allowlist authenticated route that depends on get_current_user. The
# vulnerabilities list is mounted at /api/v1/vulnerabilities and requires a
# viewer — it is NOT on the change-password allowlist, so a flagged user must
# be blocked here.
NON_ALLOWLIST_PATH = "/api/v1/vulnerabilities"


async def _seed_password_user(  # nosemgrep: python.lang.security.audit.hardcoded-password-default-argument.hardcoded-password-default-argument
    db_session,
    tenant_id: uuid.UUID,
    *,
    must_change_password: bool,
    role: str = "OWNER",
    password: str = "Admin123!",
):
    """Create a password-login user with the must_change_password flag set.

    Sets the column directly. The keyword does not exist on the model until
    Wave 1 adds it, so this raises TypeError (RED) pre-implementation.

    `password` (Phase 29): defaults to the default install credential so
    every existing Phase 06 caller is unaffected; pass a distinct value to
    seed a user whose current password is NOT "Admin123!".
    """
    from app.auth.password import hash_password

    user = User(
        tenant_id=tenant_id,
        email=f"seed-{uuid.uuid4().hex[:8]}@getvul.local",
        display_name="Seed",
        role=role,
        password_hash=hash_password(password),
        idp_subject=f"local-{uuid.uuid4().hex[:8]}",
        idp_source="local",
        must_change_password=must_change_password,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _reflag(db_session, user_id: uuid.UUID) -> None:
    """Set must_change_password=True in the DB and commit (Phase 29 helper).

    Used between successive rotations in multi-step tests, since a
    successful rotation clears the flag. Uses a Core-style UPDATE (not an
    ORM entity select+mutate) so it always issues a real write — an
    identity-map-cached User object fetched via `select(User)` would not be
    marked dirty by assigning a value it already believes is unchanged
    (e.g. still cached as True from initial seeding), silently no-op'ing a
    plain ORM mutate-and-commit.
    """
    await db_session.execute(update(User).where(User.id == user_id).values(must_change_password=True))
    await db_session.commit()


def _bearer_client(app, token: str) -> AsyncClient:
    """A real httpx client that passes a JWT — NO get_current_user override,
    so the real dependency (and the flag-enforcement gate) actually runs."""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Wave 1: schema + seed ────────────────────────────────────────────────────


async def test_migration_column(db_session, tenant_a):
    """`users.must_change_password` is a boolean NOT NULL, server_default false.

    Insert a user WITHOUT setting the flag; it must read back as False (the
    server default). Pre-Wave-1 the column does not exist → the SELECT errors
    (RED).
    """
    from app.auth.password import hash_password

    u = User(
        tenant_id=tenant_a,
        email=f"nodefault-{uuid.uuid4().hex[:8]}@getvul.local",
        display_name="No Default",
        role="VIEWER",
        password_hash=hash_password("Admin123!"),
        idp_subject=f"local-{uuid.uuid4().hex[:8]}",
        idp_source="local",
    )
    db_session.add(u)
    await db_session.flush()

    row = await db_session.execute(select(User.must_change_password).where(User.id == u.id))
    assert row.scalar_one() is False


async def test_seed_flag(db_session):
    """A user created via the create_admin.py seed path has the flag set True.

    Wave 1 makes create_admin() insert the default admin with
    must_change_password = true so the operator is forced to rotate on first
    login. Pre-Wave-1 either the column is missing or the seed omits it (RED).
    """
    import create_admin

    await create_admin.create_admin()

    result = await db_session.execute(text("SELECT must_change_password FROM users WHERE email = 'admin@getvul.local'"))
    assert result.scalar_one() is True


# ── Wave 2: JWT claim + CurrentUser ──────────────────────────────────────────


def test_jwt_claim_round_trip():
    """`create_access_token(..., must_change_password=True)` round-trips.

    decode_token restores the claim; the default (kwarg omitted) is False.
    The kwarg / decoded attribute do not exist pre-Wave-2 → TypeError /
    AttributeError (RED).
    """
    flagged = create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        email="flag@getvul.local",
        role="OWNER",
        must_change_password=True,
    )
    assert decode_token(flagged).must_change_password is True

    default = create_access_token(
        user_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        email="noflag@getvul.local",
        role="OWNER",
    )
    assert decode_token(default).must_change_password is False


async def test_current_user_claim(db_session, tenant_a):
    """A flagged access token routed through get_current_user yields
    CurrentUser.must_change_password is True.

    Builds a real token with the claim and drives the real dependency
    (constructing the HTTPBearer credentials it expects). The attribute does
    not exist on CurrentUser pre-Wave-2 (RED)."""
    from fastapi.security import HTTPAuthorizationCredentials

    from app.auth.dependencies import get_current_user

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    current = await get_current_user(credentials=creds, db=db_session)
    assert current.must_change_password is True


# ── Wave 2: enforcement gate + allowlist ─────────────────────────────────────


async def test_enforcement_blocks(app_factory, db_session, tenant_a):
    """Flagged user hitting a non-allowlist route → 403 password_change_required.

    The gate raises HTTPException(403, detail={"reason":
    "password_change_required"}), so the body is
    resp.json()["detail"]["reason"]. Pre-Wave-2 there is no gate → the request
    succeeds (or 401/422), so the 403 assertion fails (RED)."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.get(NON_ALLOWLIST_PATH)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason"] == "password_change_required"


async def test_enforcement_allowlist_me(app_factory, db_session, tenant_a):
    """Flagged user hitting GET /auth/me → 200 (allowlist pass)."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.get("/auth/me")
    assert resp.status_code == 200


async def test_enforcement_allowlist_change(app_factory, db_session, tenant_a):
    """Flagged user hitting POST /auth/change-password is NOT blocked by the
    flag gate. It may 400 on a bad/missing body, but it must never 403 for the
    flag. Pre-Wave-2 there is no allowlist concept; this asserts the
    allowlist-pass invariant that Wave 2 guarantees (RED until then)."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={
                "current_password": "Admin123!",
                "new_password": "NewPassw0rd!x",
            },
        )
    assert resp.status_code != 403


async def test_unflagged_user_unblocked(app_factory, db_session, tenant_a):
    """An UNflagged user hitting the same non-allowlist route is NOT blocked by
    the flag gate (no false-positive interference). Pre-Wave-2 the token has no
    claim to compare against; this asserts the gate Wave 2 adds does not fire
    for unflagged users."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=False, role="VIEWER")
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=False,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.get(NON_ALLOWLIST_PATH)
    assert resp.status_code != 403


# ── Wave 2: rotation (clear flag + audit + fresh tokens) ─────────────────────


async def test_rotation_clears_flag(app_factory, db_session, tenant_a):
    """A flagged user POSTing a valid rotation to /auth/change-password clears
    the DB flag (must_change_password becomes False)."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={
                "current_password": "Admin123!",
                "new_password": "NewPassw0rd!x",
            },
        )
    assert resp.status_code == 200

    row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
    assert row.scalar_one() is False


async def test_rotation_audit_event(app_factory, db_session, tenant_a):
    """A successful flagged rotation writes an audit_logs row with
    action == 'auth.first_login_rotation' for that user."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={
                "current_password": "Admin123!",
                "new_password": "NewPassw0rd!x",
            },
        )
    assert resp.status_code == 200

    count = await db_session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE action = 'auth.first_login_rotation' AND user_id = :uid"),
        {"uid": str(user.id)},
    )
    assert count.scalar_one() == 1


async def test_rotation_fresh_tokens(app_factory, db_session, tenant_a):
    """The /auth/change-password response (when the flag was set) returns a
    fresh access_token whose decoded must_change_password is False."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={
                "current_password": "Admin123!",
                "new_password": "NewPassw0rd!x",
            },
        )
    assert resp.status_code == 200
    fresh = resp.json()["access_token"]
    assert decode_token(fresh).must_change_password is False


async def test_rotation_rejects_default_variant(app_factory, db_session, tenant_a):
    """WR-01 hardening: a flagged user cannot rotate to the default install
    credential or a trivial variant of it. Whitespace-padded (" Admin123!"),
    case-folded ("admin123!" / "ADMIN123!"), and exact reuse ("Admin123!") are
    all rejected 400, and the must_change_password flag stays True so the gate
    is not defeated. (Near-but-not-equal variants like "Admin1234!" are the
    documented residual, out of scope for this minimal hardening.)"""
    from asgi_lifespan import LifespanManager

    for variant in (" Admin123!", "Admin123! ", "admin123!", "ADMIN123!", "Admin123!"):
        user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
            must_change_password=True,
        )
        app = app_factory()
        async with LifespanManager(app), _bearer_client(app, token) as ac:
            resp = await ac.post(
                "/auth/change-password",
                json={"current_password": "Admin123!", "new_password": variant},
            )
        assert resp.status_code == 400, f"variant {variant!r} should be rejected"

        row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
        assert row.scalar_one() is True, f"flag must remain set after rejecting {variant!r}"


async def test_refresh_reads_current_flag(app_factory, db_session, tenant_a):
    """After rotation (flag now False in DB), /auth/refresh yields an access
    token whose decoded must_change_password is False — refresh reads the
    current DB flag, not a stale claim."""
    from asgi_lifespan import LifespanManager

    from app.auth.jwt import create_refresh_token

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    access = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    refresh = create_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    app = app_factory()
    async with LifespanManager(app):
        async with _bearer_client(app, access) as ac:
            rot = await ac.post(
                "/auth/change-password",
                json={
                    "current_password": "Admin123!",
                    "new_password": "NewPassw0rd!x",
                },
            )
            assert rot.status_code == 200

        # Refresh with no bearer flag interference — the endpoint is public.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as public:
            resp = await public.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_access = resp.json()["access_token"]
    assert decode_token(new_access).must_change_password is False


# ── Phase 29: forced-rotation password policy (complexity/history/similarity) ──


def test_password_similarity_helpers():
    """Pure-function unit tests for the new similarity primitives (no DB).

    RED pre-Task-2: `password_similarity_ratio` / `is_too_similar` do not
    exist yet, so this fails with ImportError.
    """
    from app.auth.password import is_too_similar, password_similarity_ratio

    assert password_similarity_ratio("Admin1234!Xy", "Admin123!") >= 0.7
    assert password_similarity_ratio("Zephyr!Quokka42", "Admin123!") < 0.7

    assert is_too_similar("Admin1234!Xy", ["Admin123!"]) is not None
    assert is_too_similar("Zephyr!Quokka42", ["Admin123!"]) is None

    # DoS-truncation (Warning 2 fix): a 10k-char input must ratio-compare
    # identically to its 128-char-truncated form (normalize THEN truncate).
    long_input = "Admin123!" + "x" * 10000
    assert password_similarity_ratio(long_input, "Admin123!") == password_similarity_ratio(
        long_input[:128], "Admin123!"
    )

    # Make the 128-char cap itself observable: an input built from exactly
    # 128 casefolded chars (9 + 119 = 128) must yield the same ratio as the
    # 10k-char input above — proving truncation actually happens at 128, not
    # some other length.
    assert password_similarity_ratio(long_input, "Admin123!") == password_similarity_ratio(
        "admin123!" + "x" * 119, "admin123!"
    )


async def test_rotation_rejects_weak_complexity(app_factory, db_session, tenant_a):
    """A flagged rotation to a password that fails ONE complexity rule of
    FORCED_ROTATION_POLICY (min_length=12 + all 4 char classes) is rejected
    400, and the flag stays True. Each candidate is dissimilar to
    "Admin123!" so the rejection isolates the complexity guard, not the
    similarity guard."""
    from asgi_lifespan import LifespanManager

    candidates = (
        "Sh0rt!Aa",  # too short (8 chars)
        "alllower123!x",  # no uppercase
        "ALLUPPER123!X",  # no lowercase
        "NoDigitsHere!X",  # no digit
        "NoSymbol1234Xy",  # no symbol
    )
    for candidate in candidates:
        user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
            must_change_password=True,
        )
        app = app_factory()
        async with LifespanManager(app), _bearer_client(app, token) as ac:
            resp = await ac.post(
                "/auth/change-password",
                json={"current_password": "Admin123!", "new_password": candidate},
            )
        assert resp.status_code == 400, f"candidate {candidate!r} should be rejected"

        row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
        assert row.scalar_one() is True, f"flag must remain set after rejecting {candidate!r}"


async def test_rotation_rejects_superseded_password_history(app_factory, db_session, tenant_a):
    """A flagged rotation cannot cycle back to a SUPERSEDED (past, non-current)
    password. A 3-rotation cycle isolates check_password_history from the
    WR-01 current-password guard: the reused password (FirstRotate1!Xy) is a
    past history entry, never the live current password, when the reuse
    attempt happens."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)

    # Rotation 1: Admin123! -> FirstRotate1!Xy (succeeds; flag clears).
    token1 = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token1) as ac:
        resp1 = await ac.post(
            "/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "FirstRotate1!Xy"},
        )
    assert resp1.status_code == 200

    # Rotation 2: FirstRotate1!Xy -> SecondRotate2!Zz (succeeds; flag clears).
    await _reflag(db_session, user.id)
    token2 = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token2) as ac:
        resp2 = await ac.post(
            "/auth/change-password",
            json={"current_password": "FirstRotate1!Xy", "new_password": "SecondRotate2!Zz"},
        )
    assert resp2.status_code == 200

    # Rotation 3 (the assertion): current_password is the correct LIVE
    # current (SecondRotate2!Zz), so verify_password passes and the WR-01
    # current-hash guard does NOT fire. new_password reuses the now-
    # SUPERSEDED FirstRotate1!Xy — rejected by check_password_history alone.
    await _reflag(db_session, user.id)
    token3 = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token3) as ac:
        resp3 = await ac.post(
            "/auth/change-password",
            json={"current_password": "SecondRotate2!Zz", "new_password": "FirstRotate1!Xy"},
        )
    assert resp3.status_code == 400
    detail = resp3.json()["detail"]
    assert "reuse" in detail.lower() or "last" in detail.lower()

    row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
    assert row.scalar_one() is True


async def test_rotation_rejects_near_default_variant(app_factory, db_session, tenant_a):
    """The core WR-01 residual closure: both the ROADMAP example
    "Admin1234!" and the complexity-passing near-variant "Admin1234!Xy" are
    rejected 400 by the similarity guard, and the flag stays True."""
    from asgi_lifespan import LifespanManager

    for candidate in ("Admin1234!", "Admin1234!Xy"):
        user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
        token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            role=user.role,
            must_change_password=True,
        )
        app = app_factory()
        async with LifespanManager(app), _bearer_client(app, token) as ac:
            resp = await ac.post(
                "/auth/change-password",
                json={"current_password": "Admin123!", "new_password": candidate},
            )
        assert resp.status_code == 400, f"candidate {candidate!r} should be rejected"

        row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
        assert row.scalar_one() is True, f"flag must remain set after rejecting {candidate!r}"


async def test_rotation_rejects_similar_to_current(app_factory, db_session, tenant_a):
    """A new password too similar to the user's submitted current password
    (when that current password is NOT the default install credential) is
    rejected 400 by the similarity guard's current-password branch — the
    response detail names "current password" specifically, proving this is
    distinct from the default-credential branch."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True, password="Meadow7!Lantern")
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={"current_password": "Meadow7!Lantern", "new_password": "Meadow7!LanternXz"},
        )
    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()

    row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
    assert row.scalar_one() is True


async def test_rotation_accepts_strong_distinct_password(app_factory, db_session, tenant_a):
    """Positive control: a flagged user rotating to a strong password that is
    dissimilar to both the default install credential and their current
    password succeeds 200 and clears the flag. Guards must not be
    over-broad."""
    from asgi_lifespan import LifespanManager

    user = await _seed_password_user(db_session, tenant_a, must_change_password=True)
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        role=user.role,
        must_change_password=True,
    )
    app = app_factory()
    async with LifespanManager(app), _bearer_client(app, token) as ac:
        resp = await ac.post(
            "/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "Zephyr!Quokka42"},
        )
    assert resp.status_code == 200

    row = await db_session.execute(select(User.must_change_password).where(User.id == user.id))
    assert row.scalar_one() is False
