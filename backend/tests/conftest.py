"""Shared async test fixtures for Phase 1 multi-replica state tests.

Phase 1 requires:
  - A real Redis on db=1 (db=0 is the dev/CI app db; D-16).
  - The FastAPI lifespan to actually run so app.state.redis is set
    (httpx.ASGITransport does NOT trigger lifespan — D-15, RESEARCH Pitfall 2).
  - Two independent app instances for the cross-replica integration suite
    (PROD-01-03).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
import redis.asyncio as redis
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

REDIS_TEST_URL = "redis://localhost:6379/1"


@pytest_asyncio.fixture(scope="function")
async def redis_test_url(monkeypatch) -> AsyncIterator[str]:
    monkeypatch.setenv("REDIS_URL", REDIS_TEST_URL)
    # Force pydantic-settings re-read inside create_app() callers.
    from app import config as _config_module

    monkeypatch.setattr(_config_module, "settings", _config_module.Settings())
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

    Yields (client, app). Used by single-replica unit tests in test_oidc_state.py
    and test_rate_limit.py.
    """
    app = app_factory()
    async with LifespanManager(app) as mgr, AsyncClient(
        transport=ASGITransport(app=mgr.app), base_url="http://testserver"
    ) as client:
        yield client, mgr.app


@pytest_asyncio.fixture(scope="function")
async def two_apps(flushed_redis, app_factory):
    """Two independent app instances both pointing at the same db=1.

    Yields (client_a, client_b). Used exclusively by test_multi_replica.py
    to satisfy PROD-01-03 (D-17).
    """
    app_a = app_factory()
    app_b = app_factory()
    async with (
        LifespanManager(app_a) as mgr_a, LifespanManager(app_b) as mgr_b, AsyncClient(
            transport=ASGITransport(app=mgr_a.app), base_url="http://app-a"
        ) as client_a,
        AsyncClient(
            transport=ASGITransport(app=mgr_b.app), base_url="http://app-b"
        ) as client_b,
    ):
        yield client_a, client_b
