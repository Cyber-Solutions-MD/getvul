"""PROD-01-03: Cross-replica integration tests.

Two independent FastAPI app instances against one shared Redis db=1.
Targets each row in .planning/phases/01-multi-replica-state/01-VALIDATION.md
under "Per-Task Verification Map" tasks 01-03-01 through 01-03-04.

The two_apps fixture in conftest.py yields (client_a, client_b). For tests
that need to monkeypatch the underlying app.state.redis, we derive the apps
locally via LifespanManager so we have direct handles to mgr_a.app /
mgr_b.app.
"""

from __future__ import annotations

import pytest
import structlog
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

TEST_API_ENDPOINT = "/api/v1/reports"


@pytest.mark.asyncio
async def test_oidc_cross_replica(two_apps, flushed_redis):
    client_a, client_b = two_apps

    # Replica A initiates login.
    login_resp = await client_a.get("/auth/login/google")
    assert login_resp.status_code == 200, login_resp.text
    state = login_resp.json()["state"]

    # The state lives in shared Redis db=1, visible to BOTH replicas.
    stored = await flushed_redis.get(f"oidc:state:{state}")
    assert stored == "google", f"state not visible in shared Redis; got {stored!r}"

    # Replica B (different process — simulated by a different app instance)
    # consumes the state. Token exchange will fail because the IdP is fake,
    # but the GETDEL must have removed the key.
    callback_resp = await client_b.get(f"/auth/callback/google?state={state}&code=fake")
    assert callback_resp.status_code in (400, 401, 502, 503)

    # The state key MUST be gone (consumed atomically across replicas).
    assert await flushed_redis.exists(f"oidc:state:{state}") == 0


@pytest.mark.asyncio
async def test_oidc_one_shot(two_apps, flushed_redis):
    client_a, client_b = two_apps

    login_resp = await client_a.get("/auth/login/google")
    state = login_resp.json()["state"]

    # First consume on replica B — succeeds at the state-validation level.
    first = await client_b.get(f"/auth/callback/google?state={state}&code=fake")
    assert first.status_code in (400, 401, 502, 503)

    # Second consume of the same state — replay defense.
    second = await client_b.get(f"/auth/callback/google?state={state}&code=fake")
    assert second.status_code == 400
    assert second.json()["detail"] == "Invalid or expired state parameter"


@pytest.mark.asyncio
async def test_ratelimit_shared_budget(two_apps, flushed_redis):
    client_a, client_b = two_apps

    # 100 anonymous requests through replica A.
    for _ in range(100):
        await client_a.get(TEST_API_ENDPOINT)

    # 100 anonymous requests through replica B.
    for _ in range(100):
        await client_b.get(TEST_API_ENDPOINT)

    # The next request — anywhere — must be 429.
    blocked = await client_b.get(TEST_API_ENDPOINT)
    assert blocked.status_code == 429, (
        f"replica B should hit shared cap on the 201st request; got {blocked.status_code}"
    )
    assert blocked.headers.get("Retry-After") == "60"

    # And replica A is also out of budget.
    blocked_a = await client_a.get(TEST_API_ENDPOINT)
    assert blocked_a.status_code == 429


@pytest.mark.asyncio
async def test_redis_outage_failure_modes(flushed_redis, app_factory, monkeypatch):
    """Build the two apps locally so we can reach `app.state.redis` to mock it.

    LifespanManager's `.app` attribute is a wrapped state-middleware closure
    (a `function`), not the original FastAPI instance — so `mgr.app.state`
    does not exist. We keep direct references to `app_a` / `app_b` and access
    `app_a.state.redis` (populated by lifespan). HTTP requests still flow
    through `mgr_*.app` via ASGITransport.
    """
    app_a = app_factory()
    app_b = app_factory()

    async with (
        LifespanManager(app_a) as mgr_a,
        LifespanManager(app_b) as mgr_b,
        AsyncClient(transport=ASGITransport(app=mgr_a.app), base_url="http://app-a") as client_a,
        AsyncClient(transport=ASGITransport(app=mgr_b.app), base_url="http://app-b") as client_b,
    ):
        # Sanity: both apps see the same Redis db.
        await app_a.state.redis.set("probe", "1")
        assert await app_b.state.redis.get("probe") == "1"

        # Kill both apps' Redis client surfaces.
        def boom_pipeline(*args, **kwargs):
            raise RedisConnectionError("simulated outage")

        async def boom_set(*args, **kwargs):
            raise RedisConnectionError("simulated outage")

        async def boom_getdel(*args, **kwargs):
            raise RedisConnectionError("simulated outage")

        monkeypatch.setattr(app_a.state.redis, "pipeline", boom_pipeline)
        monkeypatch.setattr(app_a.state.redis, "set", boom_set)
        monkeypatch.setattr(app_a.state.redis, "getdel", boom_getdel)
        monkeypatch.setattr(app_b.state.redis, "pipeline", boom_pipeline)
        monkeypatch.setattr(app_b.state.redis, "set", boom_set)
        monkeypatch.setattr(app_b.state.redis, "getdel", boom_getdel)

        # Limiter: fail OPEN with structured warning.
        with structlog.testing.capture_logs() as captured:
            resp = await client_a.get(TEST_API_ENDPOINT)
        assert resp.status_code != 429, "limiter must fail open during Redis outage"
        limiter_events = [
            e for e in captured if e.get("event") == "redis_unavailable" and e.get("subsystem") == "rate_limiter"
        ]
        assert limiter_events, f"expected a rate_limiter redis_unavailable warning; got {captured}"

        # OIDC: fail CLOSED with 503.
        login_resp = await client_a.get("/auth/login/google")
        assert login_resp.status_code == 503
        assert login_resp.json()["detail"] == "Auth backend unavailable"

        callback_resp = await client_b.get("/auth/callback/google?state=anything&code=fake")
        assert callback_resp.status_code == 503
        assert callback_resp.json()["detail"] == "Auth backend unavailable"
