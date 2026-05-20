"""PROD-01-01: Redis-backed OIDC state store unit tests.

Targets each row in .planning/phases/01-multi-replica-state/01-VALIDATION.md
under "Per-Task Verification Map" tasks 01-01-01 through 01-01-05.
"""

from __future__ import annotations

import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError


@pytest.mark.asyncio
async def test_state_set_with_ttl(single_app, flushed_redis):
    client, app = single_app
    resp = await client.get("/auth/login/google")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    state = body["state"]

    stored = await flushed_redis.get(f"oidc:state:{state}")
    assert stored == "google"

    ttl = await flushed_redis.ttl(f"oidc:state:{state}")
    assert 595 <= ttl <= 600, f"TTL {ttl} not within 595–600s window"


@pytest.mark.asyncio
async def test_state_replay_rejected(single_app, flushed_redis):
    client, app = single_app
    state = "fixed-state-token-for-replay-test"
    await flushed_redis.set(f"oidc:state:{state}", "google", ex=600)

    # First callback consumes the state. It will still 4xx (token exchange against
    # a mock IdP fails), but the state must have been DELETED.
    first = await client.get(f"/auth/callback/google?state={state}&code=fake")
    assert first.status_code in (400, 401, 502, 503)

    # The state key must be gone after the first callback (GETDEL semantic).
    assert await flushed_redis.exists(f"oidc:state:{state}") == 0

    # Replay must fail with "Invalid or expired state parameter" (400).
    second = await client.get(f"/auth/callback/google?state={state}&code=fake")
    assert second.status_code == 400
    assert second.json()["detail"] == "Invalid or expired state parameter"


@pytest.mark.asyncio
async def test_state_provider_mismatch(single_app, flushed_redis):
    client, app = single_app
    state = "mismatch-state-token"
    await flushed_redis.set(f"oidc:state:{state}", "google", ex=600)

    resp = await client.get(f"/auth/callback/azure?state={state}&code=fake")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired state parameter"

    # Important: GETDEL was called even though provider mismatched, so the key
    # is deleted — preventing replay against the correct provider.
    assert await flushed_redis.exists(f"oidc:state:{state}") == 0


@pytest.mark.asyncio
async def test_state_ttl_expiry(single_app, flushed_redis):
    client, app = single_app
    state = "ttl-expiry-token"
    await flushed_redis.set(f"oidc:state:{state}", "google", ex=1)
    await asyncio.sleep(1.2)
    resp = await client.get(f"/auth/callback/google?state={state}&code=fake")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid or expired state parameter"


@pytest.mark.asyncio
async def test_login_503_on_redis_down(single_app, monkeypatch):
    client, app = single_app

    async def boom_set(*args, **kwargs):
        raise RedisConnectionError("simulated outage")

    async def boom_getdel(*args, **kwargs):
        raise RedisConnectionError("simulated outage")

    monkeypatch.setattr(app.state.redis, "set", boom_set)
    monkeypatch.setattr(app.state.redis, "getdel", boom_getdel)

    login_resp = await client.get("/auth/login/google")
    assert login_resp.status_code == 503
    assert login_resp.json()["detail"] == "Auth backend unavailable"

    callback_resp = await client.get("/auth/callback/google?state=anything&code=fake")
    assert callback_resp.status_code == 503
    assert callback_resp.json()["detail"] == "Auth backend unavailable"
