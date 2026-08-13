"""Shared async test fixtures for Phase 1 multi-replica state tests.

Phase 1 requires:
  - A real Redis on db=1 (db=0 is the dev/CI app db; D-16).
  - The FastAPI lifespan to actually run so app.state.redis is set
    (httpx.ASGITransport does NOT trigger lifespan — D-15, RESEARCH Pitfall 2).
  - Two independent app instances for the cross-replica integration suite
    (PROD-01-03).

Phase 10 adds (Plan 10-01):
  - A small fixture surface for backend behavioural tests against the live
    SQLAlchemy session: `db_session`, `tenant_a` / `tenant_b`, role-scoped
    users (`analyst_user`, `viewer_user`, `analyst_user_b`), and an
    authenticated `client` that injects each role's JWT and bypasses
    `get_current_user` via FastAPI dependency_overrides (so we do NOT have
    to spin up the OIDC flow or seed an IdP per test).
  - All fixtures skip cleanly with `pytest.skip(reason=...)` if Postgres is
    not reachable so the suite does not error during collection on
    environments without a running database (CI provides one; sandboxed
    dev environments may not).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
import redis.asyncio as redis
from asgi_lifespan import LifespanManager
from fastapi import Request
from httpx import ASGITransport, AsyncClient

REDIS_TEST_URL = "redis://localhost:6379/1"

# Import all SQLAlchemy models with cross-table relationships at conftest load
# time so the Vulnerability ↔ Asset (and similar) string-resolved relationships
# can be initialised regardless of which individual test file is collected.
# Without this, running e.g. `pytest tests/test_snooze.py` in isolation fails
# at mapper init with `InvalidRequestError: failed to locate a name ('Asset')`
# because the snooze tests only import Vulnerability.
from app.assets import models as _assets_models  # noqa: F401, E402
from app.audit import AuditLog as _AuditLog  # noqa: F401, E402
from app.notifications import models as _notifications_models  # noqa: F401, E402
from app.tenants import models as _tenants_models  # noqa: F401, E402
from app.vulnerabilities import models as _vulnerabilities_models  # noqa: F401, E402
from app.vulnerabilities import trends as _vulnerabilities_trends  # noqa: F401, E402


@pytest_asyncio.fixture(scope="function")
async def redis_test_url(monkeypatch) -> AsyncIterator[str]:
    monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
    from app import config as _config_module

    # Mutate the EXISTING settings object in place — do NOT replace
    # `_config_module.settings` with a new instance. Other modules (app.main,
    # etc.) did `from app.config import settings` at import time and hold a
    # reference to the original object; rebinding app.config.settings leaves
    # those stale. If CI sets REDIS_URL=db=0, the app's rate limiter would keep
    # using db=0 while tests flush db=1 → the rate-limit counter is never reset
    # → 429 cascade. Mutating redis_url on the shared object fixes it everywhere.
    monkeypatch.setattr(_config_module.settings, "redis_url", REDIS_TEST_URL)
    yield REDIS_TEST_URL


@pytest_asyncio.fixture(scope="function")
async def flushed_redis(redis_test_url) -> AsyncIterator[redis.Redis]:
    client = redis.from_url(redis_test_url, decode_responses=True)
    assert client.connection_pool.connection_kwargs.get("db") == 1, "tests must use db=1"
    await client.flushdb()
    try:
        yield client
    finally:
        try:  # noqa: SIM105 — defensive cleanup; test may have killed Redis (RESEARCH Pitfall 6)
            await client.flushdb()
        except redis.RedisError:
            pass
        await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def app_factory(redis_test_url):
    """Returns a callable that builds a fresh FastAPI instance bound to db=1."""
    from app.main import create_app

    def _factory():
        return create_app()

    return _factory


@pytest_asyncio.fixture(scope="function")
async def single_app(flushed_redis, app_factory):
    """One app instance with lifespan running and an httpx client.

    Yields (client, app) where `app` is the original FastAPI instance — so
    tests can access `app.state.redis` (set by lifespan) and other FastAPI
    attributes. The httpx client routes through `LifespanManager`'s wrapped
    ASGI callable so requests still execute against the lifespan-managed app.
    Used by single-replica unit tests in test_oidc_state.py and
    test_rate_limit.py.
    """
    app = app_factory()
    async with (
        LifespanManager(app) as mgr,
        AsyncClient(transport=ASGITransport(app=mgr.app), base_url="http://testserver") as client,
    ):
        yield client, app


@pytest_asyncio.fixture(scope="function")
async def two_apps(flushed_redis, app_factory):
    """Two independent app instances both pointing at the same db=1.

    Yields (client_a, client_b). Used exclusively by test_multi_replica.py
    to satisfy PROD-01-03 (D-17).
    """
    app_a = app_factory()
    app_b = app_factory()
    async with (
        LifespanManager(app_a) as mgr_a,
        LifespanManager(app_b) as mgr_b,
        AsyncClient(transport=ASGITransport(app=mgr_a.app), base_url="http://app-a") as client_a,
        AsyncClient(transport=ASGITransport(app=mgr_b.app), base_url="http://app-b") as client_b,
    ):
        yield client_a, client_b


# ── Phase 10 fixtures (Plan 10-01) ──────────────────────────────────────────
#
# These fixtures provide a behavioural-test surface against a real Postgres.
# They are intentionally narrow (only the keys called out in the plan's
# <interfaces> block) so existing Phase 1 / Phase 9 fixtures stay untouched.
#
# Skip semantics: if Postgres is unreachable (no DATABASE_URL or connection
# fails) each fixture skips with a clear reason so pytest can still collect
# files cleanly in sandboxed environments.
# ────────────────────────────────────────────────────────────────────────────


async def _db_reachable() -> bool:
    """Return True iff the configured DATABASE_URL accepts a connection."""
    try:
        from sqlalchemy import text

        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="function")
async def db_session(redis_test_url) -> AsyncIterator[Any]:
    """Yield an AsyncSession; skip the test if Postgres is unreachable.

    Used by behavioural tests that need direct DB access (seeding, asserting
    audit rows, etc). Phase 10-01 tests reference this fixture by name.

    WR-13: tests routinely call `db_session.commit()` to make seed rows
    visible to the dependency-overridden FastAPI client (which opens its
    own session via async_session_factory and is independent from this
    one). Committed rows are NOT rolled back at fixture teardown — the
    rollback path only discards uncommitted state. Run a TRUNCATE pass
    over the test-mutated tables after each test to guarantee isolation
    regardless of test ordering. Use RESTART IDENTITY + CASCADE so
    sequences reset and FK chains are honoured.

    Tables in deletion order (most dependent first → upstream parents):
      audit_logs → vulnerabilities → assets → notifications → users →
      tenants. The list is conservative — extra tables here cost a few
      ms per test but eliminate order-dependent flakes that today only
      hide because tests happen to run in a specific order.
    """
    if not await _db_reachable():
        pytest.skip("Postgres not reachable — set DATABASE_URL to a live instance")
    from sqlalchemy import text

    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()

    # Post-test cleanup runs in a fresh session so it can't see any
    # uncommitted state from the test's session.
    async with async_session_factory() as cleanup:
        try:
            # CASCADE handles any other tables that reference these via FK
            # without us having to enumerate them here. RESTART IDENTITY
            # avoids cross-test PK collisions on tables that use serial
            # IDs (vulnerabilities + audit_logs are UUID-keyed so this is
            # primarily a safety net for future tables).
            await cleanup.execute(
                text(
                    "TRUNCATE TABLE audit_logs, vulnerabilities, assets, "
                    "notifications, users, tenants, daily_snapshots "
                    "RESTART IDENTITY CASCADE"
                )
            )
            await cleanup.commit()
        except Exception:
            # Defensive: a TRUNCATE failure must not mask the test's own
            # outcome. Roll back the cleanup session and move on — the
            # next test will start with whatever state survived.
            await cleanup.rollback()


@pytest_asyncio.fixture(scope="function")
async def tenant_a(db_session) -> AsyncIterator[uuid.UUID]:
    """Create an isolated tenant for the test; cleaned up afterwards."""
    from app.tenants.models import Tenant

    tenant = Tenant(
        name=f"Tenant A {uuid.uuid4().hex[:8]}",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        domain=f"tenant-a-{uuid.uuid4().hex[:8]}.test",
        idp_provider="GOOGLE",
        idp_tenant_id="test-a",
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant.id
    # cleanup is implicit via rollback in db_session fixture


@pytest_asyncio.fixture(scope="function")
async def tenant_b(db_session) -> AsyncIterator[uuid.UUID]:
    """Create a second tenant for cross-tenant (IDOR) tests."""
    from app.tenants.models import Tenant

    tenant = Tenant(
        name=f"Tenant B {uuid.uuid4().hex[:8]}",
        slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
        domain=f"tenant-b-{uuid.uuid4().hex[:8]}.test",
        idp_provider="GOOGLE",
        idp_tenant_id="test-b",
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant.id


# Convenience alias — most Phase-10 tests use a single tenant and ask for
# `tenant_id`. This is the same as `tenant_a` so test code can read naturally.
@pytest_asyncio.fixture(scope="function")
async def tenant_id(tenant_a) -> uuid.UUID:
    return tenant_a


async def _make_user(db_session, tenant_id: uuid.UUID, role: str, email_prefix: str):
    from app.auth.schemas import CurrentUser
    from app.tenants.models import User

    u = User(
        tenant_id=tenant_id,
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@test.local",
        display_name=f"{role} test",
        role=role,
        idp_subject=f"test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(u)
    await db_session.flush()
    return CurrentUser(id=u.id, tenant_id=u.tenant_id, email=u.email, role=u.role)


@pytest_asyncio.fixture(scope="function")
async def analyst_user(db_session, tenant_a):
    """ANALYST role user in tenant_a."""
    return await _make_user(db_session, tenant_a, "ANALYST", "analyst-a")


@pytest_asyncio.fixture(scope="function")
async def viewer_user(db_session, tenant_a):
    """VIEWER role user in tenant_a."""
    return await _make_user(db_session, tenant_a, "VIEWER", "viewer-a")


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session, tenant_a):
    """ADMIN role user in tenant_a."""
    return await _make_user(db_session, tenant_a, "ADMIN", "admin-a")


@pytest_asyncio.fixture(scope="function")
async def owner_user(db_session, tenant_a):
    """OWNER role user in tenant_a (top of the role hierarchy — require_owner-gated routes)."""
    return await _make_user(db_session, tenant_a, "OWNER", "owner-a")


@pytest_asyncio.fixture(scope="function")
async def analyst_user_b(db_session, tenant_b):
    """ANALYST role user in tenant_b — used for IDOR / cross-tenant tests."""
    return await _make_user(db_session, tenant_b, "ANALYST", "analyst-b")


_TEST_USER_HEADER = "x-test-user-id"


def _make_authed_client(app, user, registry: dict | None = None) -> AsyncClient:
    """Build an httpx client whose every request is authed as `user`.

    Each client tags its requests with an `X-Test-User-Id` header and the
    `get_current_user` override resolves that header against a shared
    `registry`. Multiple clients on the same FastAPI app stay isolated —
    previously the override was a closure over `user`, so calling
    `_make_authed_client(app, viewer)` then `_make_authed_client(app, analyst)`
    left both clients authed as analyst (last write wins), masking RBAC
    failures like a viewer successfully snoozing a vulnerability.

    Note: `Request` must be importable from this module's top-level
    namespace (not inside this function) so FastAPI's `get_type_hints()`
    can resolve the override's annotation under `from __future__ import
    annotations`. Otherwise FastAPI parses `request` as a query param
    and every request fails with a 422 "missing query.request".
    """
    from app.auth.dependencies import get_current_user

    if registry is None:
        registry = {}
    registry[str(user.id)] = user

    async def _override(request: Request):
        uid = request.headers.get(_TEST_USER_HEADER)
        if uid and uid in registry:
            return registry[uid]
        return user

    app.dependency_overrides[get_current_user] = _override

    # raise_app_exceptions=False so an unhandled route exception surfaces as a
    # 500 *response* (as it would in production via ServerErrorMiddleware) rather
    # than propagating out of the client call. Fail-closed tests (e.g. audit
    # write failure → no commit) assert on that error response; the default
    # (True) re-raises and the test never sees the 500. No test wraps a client
    # call in pytest.raises, so this is safe.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={_TEST_USER_HEADER: str(user.id)},
    )


@pytest_asyncio.fixture(scope="function")
async def client(flushed_redis, redis_test_url, db_session, analyst_user) -> AsyncIterator[AsyncClient]:
    """An authenticated httpx client wired as the analyst user in tenant A.

    Depends on `flushed_redis` so the per-tenant rate-limit counter (Redis db=1)
    is reset before each test. Without it, the shared analyst/tenant-A counter
    accumulates across the whole suite and trips the 200-req/60s limit, cascading
    429s into unrelated tests (WR: test-isolation).

    Default for Phase 10 behavioural tests; if a test needs a different
    role (e.g. viewer for RBAC checks) it should use `client_for(user)`
    via the `client_factory` fixture.
    """
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app), _make_authed_client(app, analyst_user) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def client_factory(flushed_redis, redis_test_url, db_session) -> AsyncIterator:
    """Return a callable `(user) -> AsyncClient` so a single test can
    switch identities (e.g. seed as analyst, attack as viewer).

    Depends on `flushed_redis` (see `client`) to reset the rate-limit counter
    per test and avoid cross-test 429 cascades.
    """
    from app.main import create_app

    app = create_app()
    clients: list[AsyncClient] = []
    registry: dict = {}
    async with LifespanManager(app):

        def _factory(user):
            ac = _make_authed_client(app, user, registry)
            clients.append(ac)
            return ac

        yield _factory
        for ac in clients:
            await ac.aclose()


# WR-14 (Phase 12 code review): pre-existing test-infra issue —
# pytest-asyncio uses a function-scoped event loop, but
# `app.db.session.engine` is a module-level async engine whose asyncpg
# connection pool is bound to whichever loop made the first connection.
# After test #1's loop closes, subsequent tests find the cached pool full of
# "Event loop is closed" connections and `_db_reachable()` returns False
# (→ pytest.skip), or the next `session.flush()` trips a RuntimeError before
# any user code runs.
#
# Disposing the engine before each test gives every test a fresh pool bound
# to the current loop. Previously copied into three Phase 12 test files;
# centralised here so the next test author doesn't copy it a fourth time.
# Follow-up: migrate to a function-scoped engine (or session-scoped event
# loop) so this workaround can be removed entirely.
@pytest_asyncio.fixture(autouse=True)
async def _reset_engine_pool():
    from app.db.session import engine

    await engine.dispose()
    yield
