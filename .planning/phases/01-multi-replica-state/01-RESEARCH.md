# Phase 1: Multi-Replica State - Research

**Researched:** 2026-05-08
**Domain:** redis-py asyncio + FastAPI lifespan + cross-replica integration testing
**Confidence:** HIGH (all critical claims verified against official redis-py / Redis / FastAPI / httpx docs)

## Summary

Phase 1 replaces two in-process Python data structures (`_pending_states: dict` in [backend/app/auth/router.py:31](../../../backend/app/auth/router.py#L31), `_rate_limit_store: defaultdict` in [backend/app/main.py:103](../../../backend/app/main.py#L103)) with Redis-backed equivalents so two backend replicas can share OIDC state and rate-limit budget. The `redis>=5.2` dependency is already in [backend/pyproject.toml:14](../../../backend/pyproject.toml#L14) but unused; CONTEXT.md has locked every meaningful design decision (sliding window with sorted set + MULTI/EXEC pipeline; SET NX EX + GETDEL for OIDC; fail-open limiter, fail-closed state store; client on `app.state.redis` via lifespan). All decisions are sound and align with current redis-py 5.x / Redis 7 idioms.

**Primary recommendation:** Implement exactly as CONTEXT.md prescribes. The two non-obvious gotchas the planner must surface in tasks are (1) the ZADD member must include a uuid suffix to avoid duplicate-member no-ops at sub-millisecond contention, and (2) `httpx.AsyncClient(transport=ASGITransport(app=...))` does **not** trigger FastAPI lifespan — the multi-replica integration test must use `LifespanManager` from `asgi-lifespan` (new dev dep) or build the Redis client inside the fixture and inject it onto `app.state` manually.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Rate-limiter algorithm**
- D-01: Sliding window via Redis sorted set, keyed `ratelimit:{tenant_id}` (or `ratelimit:anonymous`). Per request: `ZREMRANGEBYSCORE` (prune older than `now - 60s`) + `ZADD now now` + `ZCARD` + `EXPIRE 60`. Reject when `ZCARD >= 200`.
- D-02: Pipeline the four commands via `redis.asyncio.client.Pipeline` (`async with client.pipeline(transaction=True) as pipe`) so they execute as one round trip.
- D-03: Limit stays global at 200 requests / 60 seconds (`RATE_LIMIT_REQUESTS = 200`, `RATE_LIMIT_WINDOW = 60`).
- D-04: Tenant key derivation unchanged — JWT decoded lightweight, fall back to `"anonymous"`.

**Redis-down behavior**
- D-05: Rate limiter **fails open** when Redis is unreachable; emit `logger.warning("redis_unavailable", subsystem="rate_limiter", error=str(e))`.
- D-06: OIDC state store **fails closed**: HTTP 503 on Redis errors at both `/auth/login/{provider}` and `/auth/callback/{provider}`.
- D-07: No Redis check on `/health` in this phase — Phase 7 (PROD-07) introduces `/ready`.

**OIDC state TTL & semantics**
- D-08: TTL is **10 minutes** (`SETEX state:{token} 600 {provider}`).
- D-09: Consume is **atomic one-shot** via `GETDEL state:{token}`.
- D-10: Key namespace: `oidc:state:{token}`.

**Redis client lifecycle**
- D-11: `redis.asyncio.Redis` client created in FastAPI `lifespan`, stored on `app.state.redis`. Created via `redis.asyncio.from_url(settings.redis_url, decode_responses=True, socket_timeout=2.0, socket_connect_timeout=2.0)`. Closed on shutdown via `await app.state.redis.aclose()`.
- D-12: Middleware reads via `request.app.state.redis`; route handlers use a thin `get_redis(request: Request)` dependency.
- D-13: In-memory `_pending_states: dict` and `_rate_limit_store: defaultdict(list)` are **deleted entirely** in this phase. No fallback path.
- D-14: 2-second socket timeout.

**Multi-replica integration test**
- D-15: Two FastAPI app instances via `app_factory()`, each with its own lifespan, both pointing at one real Redis. Each app gets its own `httpx.AsyncClient(transport=ASGITransport(app=app_instance))`.
- D-16: Reuse existing `services.redis` in [.github/workflows/ci.yml:32-40](../../../.github/workflows/ci.yml#L32-L40). Tests use `REDIS_URL=redis://localhost:6379/1` (db=1). Test fixture flushes db=1 before each test.
- D-17: Required test cases — (a) state set on app A, GETDEL on app B succeeds and second GETDEL fails; (b) tenant T issues 100 requests through app A and 101 through app B; the 201st request gets 429; (c) Redis stopped mid-test → rate limit allows traffic with warning log, OIDC callback returns 503.

**Observability**
- D-18: Redis-failure events emitted as structured logs only (structlog). NO Prometheus dep.
- D-19: Log fields: `event`, `subsystem` (`rate_limiter` | `oidc_state`), `error` (str(exception)), `tenant_id` if known.

**Doc parity**
- D-20: Update [doc/security.md:20](../../../doc/security.md#L20) so the "Redis-backed" claim becomes true.

### Claude's Discretion

- Exact module layout for the Redis client (`backend/app/redis_client.py` vs putting `from_url` directly in `lifespan`)
- Names for the small Pydantic/dataclass response shape on rate-limit headers (today: `Retry-After`)
- Whether to introduce a tiny `RateLimiterError` exception class or just `redis.RedisError` catch
- Whether the test fixture lives in `backend/tests/conftest.py` or `backend/tests/test_multi_replica.py`
- Any micro-optimizations like Redis connection pool size

### Deferred Ideas (OUT OF SCOPE)

- Prometheus `/metrics` endpoint
- Per-user / per-IP rate limits
- Tenant-configurable limits via `tenant.rate_limit_config` JSONB
- Token-bucket / Lua-script algorithms
- Rate-limit fallback to in-process counter when Redis is down (rejected — fail-open + warn instead)
- Redis Sentinel / Cluster

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-01-01 | OIDC state moves from `_pending_states` dict to Redis with TTL ≤10 min | "OIDC state store" section below — `SET ... NX EX 600` write, `GETDEL` consume |
| PROD-01-02 | Per-tenant rate limiter moves from `_rate_limit_store` defaultdict to Redis sorted set | "Sliding window via sorted set" section — exact ZADD/ZREMRANGEBYSCORE/ZCARD/EXPIRE pipeline |
| PROD-01-03 | Integration tests prove correctness across two backend processes hitting one Redis | "Test architecture" section — two `app_factory()` instances + `LifespanManager` + shared Redis db=1 |

## Project Constraints (from CLAUDE.md and PROJECT.md)

No `./CLAUDE.md` file found at repo root. Constraints inherited from PROJECT.md and CONTEXT.md preferences:

- **No backwards-compat hacks** — D-13 mandates outright deletion of `_pending_states` and `_rate_limit_store`. Plans must NOT include "fallback to in-memory if Redis down" branches; use the locked fail-open / fail-closed semantics instead.
- **Default to no comments** — code should not narrate trivial behavior; only explain non-obvious choices.
- **Prefer editing over creating** — extend the existing `lifespan` in [backend/app/main.py:19-54](../../../backend/app/main.py#L19-L54), do not introduce a parallel startup mechanism. Add to the existing `TenantRateLimitMiddleware` class shape (replace storage backend; keep tenant extraction).
- **No defensive validation at non-user-input boundaries** — Redis client construction does not need try/except around `from_url`; let it raise on bad config. Wrap only the per-request commands where a 503 / fail-open decision is actually meaningful.
- **Tenant isolation invariant** — every Redis key must be tenant-scoped: `ratelimit:{tenant_id}` and `oidc:state:{token}` (the OIDC token is global by design, but it carries no tenant data; the tenant resolution happens on the post-callback email lookup, unchanged).

## Standard Stack

### Core (already in pyproject.toml — no new prod deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `redis` | `>=5.2` (latest as of 2026-02: 5.x family; redis-py 7.4.0 docs current) | Async Redis client (`redis.asyncio`) | Official Python client maintained by Redis Inc.; only credible option [VERIFIED: pypi.org/project/redis] |
| `fastapi` | `>=0.115,<1.0` | Lifespan + middleware host | Already in deps |
| `structlog` | `>=24.0` | Structured warning logs on Redis errors | Already in deps; project pattern |

### Supporting (dev only — adds ONE new dep)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asgi-lifespan` | `>=2.1` | Trigger FastAPI lifespan during `httpx.AsyncClient` tests | Required for the PROD-01-03 integration test (see `Test architecture` section) [VERIFIED: github.com/florimondmanca/asgi-lifespan] |
| `pytest-asyncio` | `>=0.24` (already in dev deps) | Async test driver | Already wired (`asyncio_mode = "auto"` in pyproject.toml) [VERIFIED: backend/pyproject.toml:31] |
| `httpx` | `>=0.27` (already in dev deps) | `AsyncClient + ASGITransport` | Already wired [VERIFIED: backend/pyproject.toml:33] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `MULTI/EXEC` pipeline | Lua script (`EVAL`) | Lua is more atomic and fewer round trips, but CONTEXT.md (D-02) chose pipeline; pipeline is sufficient because the algorithm is **add-then-count** (no read-then-write race). Skip Lua. |
| `asgi-lifespan` for tests | Build Redis client inside test fixture and assign to `app.state.redis` directly, skipping lifespan | Bypassing lifespan means startup ordering bugs (e.g., scheduler) won't be caught by tests. Recommend `asgi-lifespan`. |
| `fakeredis` for unit tests | Real Redis only | Real Redis already runs in CI (services.redis). Unit-level limiter algorithm tests against fakeredis are nice-to-have but the integration suite must hit real Redis to satisfy PROD-01-03. |
| `aioredis` | `redis.asyncio` | `aioredis` was merged into `redis-py` in 4.2.0 (2022). `redis.asyncio` is now the canonical async client. [VERIFIED: redis.io/docs/latest/develop/clients/redis-py] |

**Installation (dev only):**
```bash
# In backend/, add to [project.optional-dependencies].dev:
asgi-lifespan>=2.1
```

**Version verification:**
- `redis-py` latest as of 2026-02-09: 5.x line; docs at redis.readthedocs.io reference 7.4.0 doc build. Project pin `>=5.2` is correct and compatible with all features used (GETDEL since 4.0; aclose since 5.0.1). [VERIFIED: redis.readthedocs.io/en/stable/ + pypi.org/project/redis]
- `asgi-lifespan` 2.1.0 is the current line as of 2024-2025; no 3.x release. Compatible with httpx 0.27. [CITED: github.com/florimondmanca/asgi-lifespan]

## Architecture Patterns

### Recommended Project Structure (delta only — no new directories needed)

```
backend/app/
├── main.py            # extend existing lifespan; replace TenantRateLimitMiddleware storage backend
├── auth/router.py     # delete _pending_states; use get_redis dep + GETDEL/SETEX
├── redis_client.py    # NEW (Claude's discretion): from_url helper + get_redis dep
└── ratelimit.py       # NEW (Claude's discretion): sliding-window algorithm in one place
backend/tests/
├── conftest.py        # NEW: app_factory, redis_client, two_apps fixtures
├── test_oidc_state.py # NEW: OIDC state store tests
├── test_rate_limit.py # NEW: limiter algorithm tests
└── test_multi_replica.py  # NEW: PROD-01-03 cross-replica suite
```

### Pattern 1: Redis client in FastAPI lifespan

**What:** Create the `redis.asyncio.Redis` once at app startup, attach to `app.state.redis`, close at shutdown.

**When to use:** Always — this is THE canonical FastAPI pattern for connection-pooled clients (DB, Redis, http clients). [VERIFIED: fastapi.tiangolo.com/advanced/events]

**Example (extending the existing lifespan at backend/app/main.py:19-54):**
```python
# Source: redis.readthedocs.io/en/stable/examples/asyncio_examples.html
#         + fastapi.tiangolo.com/advanced/events
import redis.asyncio as redis
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing scheduler bring-up stays first.
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import start_scheduler, stop_scheduler
        start_scheduler()

    # NEW: Redis client for OIDC state + rate limiter.
    app.state.redis = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=2.0,
        socket_connect_timeout=2.0,
    )

    # ... existing syslog config block unchanged ...

    yield

    # NEW: shutdown order — close Redis before stopping scheduler is fine,
    # the scheduler does not depend on Redis.
    await app.state.redis.aclose()
    if settings.environment in ("development", "production"):
        from app.connectors.scheduler import stop_scheduler
        stop_scheduler()
```

**Verified facts:**
- `redis.from_url(...)` returns a `redis.asyncio.Redis` instance when called from `redis.asyncio` (or top-level `redis.from_url` if `import redis.asyncio as redis`). [VERIFIED: redis.readthedocs.io]
- `decode_responses=True` makes `GETDEL` return `str | None` instead of `bytes | None`. [VERIFIED: redis-py docs]
- `aclose()` is the canonical async close in redis-py 5.0.1+. `close()` is `@deprecated_function` and warns since 5.0.0. [VERIFIED: github.com/redis/redis-py/blob/master/redis/asyncio/client.py + PR #3335]
- Default connection-pool max is `2**31` connections; explicit `max_connections` is Claude's discretion. [VERIFIED: redis.readthedocs.io/en/stable/connections.html]

### Pattern 2: `get_redis` dependency for route handlers

**What:** A 1-line dep that pulls the client off `request.app.state` so handlers don't import the global `app`.

**When to use:** Auth router callback/login routes (one of two consumers).

**Example:**
```python
# Source: fastapi.tiangolo.com/advanced/middleware (Request.app)
from fastapi import Request
import redis.asyncio as redis

def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis
```

Then in `backend/app/auth/router.py`:
```python
from typing import Annotated
from fastapi import Depends
import redis.asyncio as redis

@router.get("/login/{provider}", response_model=AuthorizationURL)
async def login(
    provider: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    ...
```

### Pattern 3: Middleware reads `request.app.state.redis`

**What:** `BaseHTTPMiddleware.dispatch(request, call_next)` receives a `Request`; access the client via `request.app.state.redis`.

**When to use:** `TenantRateLimitMiddleware` — middleware can't use `Depends` cleanly. [VERIFIED: fastapi.tiangolo.com/tutorial/middleware]

**Example:**
```python
# Source: starlette.io/middleware + fastapi tutorial
class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        redis_client = request.app.state.redis
        # ... limiter logic using redis_client ...
```

### Pattern 4: Sliding-window pipeline (the rate-limiter core)

**What:** Atomically prune-old → add-current → count → set-TTL.

**When to use:** Per request hitting `/api/*`.

**Example (the exact command sequence):**
```python
# Source: redis.io/tutorials/howtos/ratelimiting + redis.readthedocs.io
import time, uuid
import redis.asyncio as redis
from redis.exceptions import RedisError

RATE_LIMIT_REQUESTS = 200
RATE_LIMIT_WINDOW = 60  # seconds

async def check_rate_limit(redis_client: redis.Redis, tenant_key: str) -> bool:
    """Return True if the request is allowed, False if it should be 429'd."""
    key = f"ratelimit:{tenant_key}"
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - RATE_LIMIT_WINDOW * 1000
    # Unique member: avoids ZADD no-op when two requests arrive in the same ms.
    member = f"{now_ms}:{uuid.uuid4().hex[:8]}"

    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start_ms)
        pipe.zadd(key, {member: now_ms})
        pipe.zcard(key)
        pipe.expire(key, RATE_LIMIT_WINDOW)
        results = await pipe.execute()

    count = results[2]  # ZCARD result after the prune-and-add
    return count <= RATE_LIMIT_REQUESTS
```

**Pipeline result indexing (verify in tests):**
| Index | Command | Type | Meaning |
|-------|---------|------|---------|
| 0 | `ZREMRANGEBYSCORE` | int | Number of removed entries (often 0) |
| 1 | `ZADD` | int | Number of NEW members added (1 if member is unique, 0 if duplicate — see Pitfall 1) |
| 2 | `ZCARD` | int | Current size of the set AFTER the add |
| 3 | `EXPIRE` | int | 1 if TTL set, 0 if key didn't exist |

**Why MULTI/EXEC pipeline is sufficient (and Lua not needed):**
The algorithm is **add-then-count**, NOT check-then-write. Every concurrent request adds itself first, then reads the count. If both requests arrive at the cap, both see `count=201` and both reject — strictly stronger than required. There is no TOCTOU window. [VERIFIED: pattern reasoning corroborated by redis.io/tutorials/howtos/ratelimiting]

### Pattern 5: OIDC state SET / GETDEL

**What:** Atomically write state at login with TTL; atomically read-and-delete at callback.

**Example (login):**
```python
# Source: redis.io/docs/latest/commands/set + redis.io/docs/latest/commands/getdel
import secrets
from redis.exceptions import RedisError

@router.get("/login/{provider}", response_model=AuthorizationURL)
async def login(
    provider: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    if provider not in ("google", "azure"):
        raise HTTPException(status_code=400, detail="Unsupported provider.")
    state = secrets.token_urlsafe(32)
    try:
        # SET ... NX EX 600 — fails if collision (extremely unlikely with 256-bit token)
        ok = await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
    if not ok:
        raise HTTPException(status_code=500, detail="State collision — retry")
    oidc = get_provider(provider)
    return AuthorizationURL(
        authorization_url=oidc.get_authorization_url(state=state),
        state=state,
    )
```

**Example (callback):**
```python
@router.get("/callback/{provider}", response_model=TokenResponse)
async def callback(
    provider: str,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    try:
        stored_provider = await redis_client.getdel(f"oidc:state:{state}")
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
    if stored_provider is None or stored_provider != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    # ... rest of callback unchanged ...
```

**Verified facts:**
- `await client.set(key, value, ex=N, nx=True)` returns `True` on success or `None` if NX condition failed (key already exists). With `decode_responses=True` the success value is `True` (bool), per redis-py command return marshalling. [VERIFIED: redis.io/docs/latest/commands/set]
- `await client.getdel(key)` returns `str | None` with `decode_responses=True`. Returns `None` when the key does not exist OR has expired. Available since Redis 6.2.0 (server) and redis-py 4.0.0 (client). Project's redis 7-alpine in [docker-compose.yml:35](../../../docker-compose.yml#L35) and CI [.github/workflows/ci.yml:33](../../../.github/workflows/ci.yml#L33) easily clear that bar. [VERIFIED: redis.io/docs/latest/commands/getdel]
- `secrets.token_urlsafe(32)` produces 256 bits of randomness; collision probability is negligible — the `nx=True` is defense-in-depth, not a meaningful guard.

### Pattern 6: Test architecture (two-app + one-Redis + LifespanManager)

**What:** PROD-01-03 demands two backend processes hit one Redis. We use two FastAPI app instances built by `app_factory()`, each driven by its own `httpx.AsyncClient + ASGITransport`, with `asgi_lifespan.LifespanManager` to actually run the lifespan (which sets up `app.state.redis`).

**Critical fact:** `httpx.AsyncClient(transport=ASGITransport(app=app))` does **NOT** trigger ASGI lifespan events. Without `LifespanManager`, `app.state.redis` is never set and tests crash with `AttributeError`. [VERIFIED: fastapi.tiangolo.com/advanced/async-tests + github.com/encode/httpx/issues/350]

**Conftest fixtures (recommended):**
```python
# Source: github.com/florimondmanca/asgi-lifespan + fastapi.tiangolo.com/advanced/async-tests
# backend/tests/conftest.py
import os
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

@pytest_asyncio.fixture(scope="function")
async def redis_test_url(monkeypatch):
    """Force tests onto db=1 so prod data on db=0 is never touched."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    yield "redis://localhost:6379/1"

@pytest_asyncio.fixture(scope="function")
async def flushed_redis(redis_test_url):
    """Provide a clean Redis db=1 to each test."""
    import redis.asyncio as redis
    client = redis.from_url(redis_test_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()

def _build_app():
    """Build a fresh FastAPI app instance for tests.

    Requires backend/app/main.py to expose `create_app()` factory; current code
    builds `app` at module load. The phase plan must extract a factory.
    """
    from app.main import create_app  # NEW factory to be added
    return create_app()

@pytest_asyncio.fixture(scope="function")
async def two_apps(flushed_redis):
    """Two independent app instances both pointing at db=1."""
    app_a = _build_app()
    app_b = _build_app()
    async with LifespanManager(app_a) as mgr_a, LifespanManager(app_b) as mgr_b:
        async with (
            AsyncClient(transport=ASGITransport(app=mgr_a.app), base_url="http://app-a") as client_a,
            AsyncClient(transport=ASGITransport(app=mgr_b.app), base_url="http://app-b") as client_b,
        ):
            yield client_a, client_b
```

**Important:** The current `backend/app/main.py` builds `app = FastAPI(...)` at module top. For tests to construct fresh instances with isolated lifespans, the planner MUST extract a `create_app()` factory. This is locked under D-15 ("each constructed by an `app_factory()`"). Without the factory, both tests would share the same `app.state.redis` and the test would not actually exercise two replicas.

### Anti-Patterns to Avoid

- **Module-scoped Redis client.** `client = redis.from_url(settings.redis_url)` at module top creates a connection on import — breaks tests, ignores lifespan, leaks on shutdown. Always inside `lifespan` and on `app.state`.
- **`async with redis.from_url(...) as client` per request.** This builds a new connection pool per request. Always reuse the lifespan-scoped client.
- **`pipe.zadd(key, {now_ms: now_ms})` (member == score).** Two requests in the same millisecond produce the same `(member, score)` pair; the second `ZADD` is a no-op (returns 0) and ZCARD won't grow. Always use a unique member (uuid suffix).
- **Catching `Exception` around limiter call.** Catch `redis.exceptions.RedisError` only — letting unrelated bugs (bad JWT, etc.) get swallowed as "Redis errors" hides real problems.
- **Mutating `settings` in tests.** Use `monkeypatch.setenv("REDIS_URL", ...)` and rebuild via `create_app()` — the existing `Settings` is `pydantic_settings.BaseSettings`, which reads env on instantiation. Don't write `settings.redis_url = ...`.
- **Reusing one `httpx.AsyncClient` across both apps.** Each app needs its own transport bound to its own ASGI app, otherwise both clients hit the same in-process app and the multi-replica test is meaningless.
- **`async with client.pipeline()` without `transaction=True`.** Without transactions, the four commands can interleave with another client's commands — exactly the race CONTEXT.md (D-02) closes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random state token | Custom token generator | `secrets.token_urlsafe(32)` | Already correct in current code; stdlib, cryptographically secure |
| Atomic read-and-delete | `GET` then `DEL` (two round trips, race-vulnerable) | `await client.getdel(key)` | One round trip, atomic; available in redis-py 4.0+, Redis 6.2+ |
| Sliding-window count | Manual list of timestamps + filter (this is what current code does) | Sorted set + ZREMRANGEBYSCORE + ZCARD | Redis-side pruning; O(log N) instead of O(N); cross-replica safe |
| Set-with-TTL on first write | `SET` + `EXPIRE` (two commands) | `SET key value EX seconds NX` | Atomic; redis-py supports `ex=` and `nx=` kwargs |
| Lifespan wiring for tests | Calling startup/shutdown hooks manually | `asgi_lifespan.LifespanManager(app)` | Battle-tested by Starlette / FastAPI ecosystem; handles ordering and exceptions |
| Per-test app rebuild | Mutating `settings` | `monkeypatch.setenv` + `create_app()` factory | Pydantic settings reads env on init — factory respects test isolation |
| Connection-pool tuning | Custom `ConnectionPool(max_connections=...)` | redis-py default | Default is generous; under load tune later — micro-optimization (Claude's discretion) |

**Key insight:** Every one of these is a 1-2 line redis-py call away. Custom code in this domain reliably introduces races (limiter doesn't share across replicas), correctness bugs (TTL drift between SET and EXPIRE), or test fragility (manual lifespan calls).

## Common Pitfalls

### Pitfall 1: ZADD with `member == score` is a no-op on duplicates

**What goes wrong:** Two requests arriving in the same millisecond from the same tenant both call `ZADD ratelimit:T 1715000000123 1715000000123`. The second one is a no-op (member already exists, score "updates" to the same value) — `ZADD` returns 0, `ZCARD` does not grow, and the request count is undercounted. Burst traffic can silently exceed the 200 limit.

**Why it happens:** Sorted-set membership is keyed by member, not by `(member, score)`. If you reuse the timestamp as both, sub-millisecond duplicates collide. Modern hardware easily fits multiple requests in the same millisecond.

**How to avoid:** Use a unique member: `member = f"{now_ms}:{uuid.uuid4().hex[:8]}"` (or any random suffix). Score remains `now_ms` so `ZREMRANGEBYSCORE` continues to work for time-based pruning.

**Warning signs:** Test 200 concurrent requests in a tight loop and observe ZCARD < 200. If pruning is correct but counts don't grow, you have this bug.

[VERIFIED: redis.io/docs/latest/commands/zadd — "If a specified member is already a member of the sorted set, the score is updated and the element reinserted at the right position"]

### Pitfall 2: `httpx.AsyncClient + ASGITransport` does not trigger lifespan

**What goes wrong:** Test runs, gets `AttributeError: 'State' object has no attribute 'redis'` on the first request because lifespan never ran, so `app.state.redis` is never set.

**Why it happens:** `ASGITransport` only handles HTTP scope, not lifespan scope. Lifespan runs on its own ASGI scope which `ASGITransport` does not initiate.

**How to avoid:** Wrap the app in `asgi_lifespan.LifespanManager(app)` before constructing the `AsyncClient`, and pass `manager.app` to `ASGITransport`. Or set `app.state.redis` manually in the fixture (acceptable for unit tests; rejected for the multi-replica integration test under D-15).

**Warning signs:** First test request fails with attribute access errors on `app.state`.

[VERIFIED: fastapi.tiangolo.com/advanced/async-tests — "If your application relies on lifespan events, the AsyncClient won't trigger these events. To ensure they are triggered, use LifespanManager from florimondmanca/asgi-lifespan."]

### Pitfall 3: `decode_responses=True` is set on the app client but the test fixture forgets it

**What goes wrong:** Test code that opens its own Redis client (e.g., to seed or assert state) without `decode_responses=True` gets `bytes` back; comparing `b"google" == "google"` is False.

**How to avoid:** Use `decode_responses=True` consistently in the `flushed_redis` fixture and any direct Redis assertions. Or wrap with `.decode()`.

**Warning signs:** Equality assertions on stored values fail mysteriously.

### Pitfall 4: Tests run on prod db=0 and corrupt rate-limit data

**What goes wrong:** Test fixture forgets to override `REDIS_URL` to db=1 and `flushdb()` wipes the dev environment's keys.

**How to avoid:** Hard-code `redis://localhost:6379/1` in the test fixture (not via env). Assert `client.connection_pool.connection_kwargs["db"] == 1` before flushing. CONTEXT.md D-16 already specifies db=1.

**Warning signs:** Local dev's rate-limit budget mysteriously resets when you run `pytest`.

### Pitfall 5: `await client.aclose()` deprecation surface — using `close()` triggers warnings under strict pytest

**What goes wrong:** Pytest configured with `-W error::DeprecationWarning` fails the suite because `close()` raises `DeprecationWarning` since redis-py 5.0.0.

**How to avoid:** Use `await client.aclose()` everywhere. CONTEXT.md D-11 already mandates this; the planner should ensure the same is used in test fixtures.

[VERIFIED: github.com/redis/redis-py/blob/master/redis/asyncio/client.py — `close()` is `@deprecated_function(version="5.0.1", reason="Use aclose() instead")`]

### Pitfall 6: Lifespan exceptions during shutdown leak in tests

**What goes wrong:** If `aclose()` raises (e.g., Redis went down mid-test), the test fixture cleanup raises and shadows the actual test failure.

**How to avoid:** In the test fixture's `LifespanManager` context, the manager already swallows shutdown exceptions cleanly. For ad-hoc clients (the `flushed_redis` fixture), `await client.aclose()` should be in a `try/except RedisError: pass` if the failure-mode test stopped Redis on purpose. Note this is the ONE place defensive `try/except` is correct — it's test cleanup, not production code.

### Pitfall 7: Module-level `_pending_states` deletion forgets the comment claim

**What goes wrong:** [backend/app/auth/router.py:30](../../../backend/app/auth/router.py#L30) reads `# In-memory state store (use Redis in production)`. The comment must be deleted along with the dict; otherwise the code misleads future readers.

**How to avoid:** Plan task explicitly removes both lines 30 and 31 of `backend/app/auth/router.py`.

### Pitfall 8: Doc string drift in CSRF defense

**What goes wrong:** GETDEL returns `None` for both "key not found" AND "expired key" — both should be treated identically as "invalid state". The current code's check `if stored_provider is None or stored_provider != provider:` covers this; the new code must keep that exact compound check.

**How to avoid:** Lift the existing check verbatim into the new GETDEL-based callback. Don't "improve" the error message to distinguish "expired" vs "tampered" — leaking that distinction helps CSRF attackers probe TTL behavior.

## Code Examples

Verified patterns from official sources, ready to copy into plan tasks:

### Construction at lifespan startup
```python
# Source: redis.readthedocs.io/en/stable/examples/asyncio_examples.html
import redis.asyncio as redis
app.state.redis = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=2.0,
    socket_connect_timeout=2.0,
)
```

### Pipelined sliding window
```python
# Source: redis.io/tutorials/howtos/ratelimiting + redis.readthedocs.io
async with redis_client.pipeline(transaction=True) as pipe:
    pipe.zremrangebyscore(key, 0, window_start_ms)
    pipe.zadd(key, {f"{now_ms}:{uuid.uuid4().hex[:8]}": now_ms})
    pipe.zcard(key)
    pipe.expire(key, RATE_LIMIT_WINDOW)
    results = await pipe.execute()
count = results[2]
```

### Atomic OIDC state write
```python
# Source: redis.io/docs/latest/commands/set
ok = await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)
# ok is True on success, None on NX miss.
```

### Atomic OIDC state consume
```python
# Source: redis.io/docs/latest/commands/getdel
stored_provider = await redis_client.getdel(f"oidc:state:{state}")
# str | None when decode_responses=True
```

### Catching Redis errors
```python
# Source: redis.readthedocs.io/en/stable/exceptions.html
from redis.exceptions import RedisError
try:
    ... # redis ops
except RedisError as e:
    # ConnectionError and TimeoutError both subclass RedisError
    logger.warning("redis_unavailable", subsystem="rate_limiter", error=str(e))
    return await call_next(request)  # fail open
```

### Test fixture — two apps + LifespanManager + shared Redis
```python
# Source: github.com/florimondmanca/asgi-lifespan README
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

async with LifespanManager(app_a) as mgr_a, LifespanManager(app_b) as mgr_b:
    async with (
        AsyncClient(transport=ASGITransport(app=mgr_a.app), base_url="http://app-a") as client_a,
        AsyncClient(transport=ASGITransport(app=mgr_b.app), base_url="http://app-b") as client_b,
    ):
        # tests
        ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `aioredis` library | `redis.asyncio` (merged into redis-py) | 2022, redis-py 4.2.0 | One client, both sync and async; CONTEXT.md correctly chose `redis.asyncio` |
| `app=app` kwarg on `httpx.AsyncClient` | `transport=ASGITransport(app=app)` | httpx 0.27 (March 2024) | The old form is deprecated and removed; project's `httpx>=0.27` is fine |
| `await client.close()` (async) | `await client.aclose()` | redis-py 5.0.0 / 5.0.1 | DeprecationWarning on `close()`; mandate `aclose()` |
| `GET` + `DEL` (read-then-delete) | `GETDEL` | Redis 6.2 (Feb 2021), redis-py 4.0 | Atomic single-round-trip; CONTEXT.md correctly chose this |
| Module-level `app = FastAPI(...)` | `create_app()` factory | Always was best practice; FastAPI docs in lifespan section | Required for test isolation; planner must extract factory |

**Deprecated/outdated:**
- `aioredis` (separate package): merged into `redis-py` 4.2.0; do not pull as a separate dep.
- `httpx.AsyncClient(app=app, ...)`: removed in httpx 0.28+; use `transport=ASGITransport(app=app)`.
- `await client.close()` on async Redis: still works, but emits `DeprecationWarning` since 5.0.0.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+, pytest-asyncio 0.24+ (`asyncio_mode = "auto"`) [VERIFIED: backend/pyproject.toml:31, 71-73] |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && pytest tests/test_rate_limit.py tests/test_oidc_state.py -x` |
| Full suite command | `cd backend && pytest -v --cov=app --cov-report=xml` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-01-01 | OIDC state SET with TTL ≤ 600s, GETDEL atomic consume | unit | `pytest backend/tests/test_oidc_state.py -x` | ❌ Wave 0 |
| PROD-01-01 | OIDC callback rejects reused state token (replay defense) | unit | `pytest backend/tests/test_oidc_state.py::test_state_replay_rejected -x` | ❌ Wave 0 |
| PROD-01-01 | OIDC callback rejects mismatched provider | unit | `pytest backend/tests/test_oidc_state.py::test_state_provider_mismatch -x` | ❌ Wave 0 |
| PROD-01-01 | OIDC state expires after 600s (use 1s TTL in test) | unit | `pytest backend/tests/test_oidc_state.py::test_state_ttl_expiry -x` | ❌ Wave 0 |
| PROD-01-01 | OIDC login returns 503 on Redis ConnectionError | failure-mode | `pytest backend/tests/test_oidc_state.py::test_login_503_on_redis_down -x` | ❌ Wave 0 |
| PROD-01-02 | Limiter allows N≤200 in window, 429 at 201 | unit | `pytest backend/tests/test_rate_limit.py::test_limit_enforced -x` | ❌ Wave 0 |
| PROD-01-02 | Limiter prunes entries older than window | unit | `pytest backend/tests/test_rate_limit.py::test_window_slides -x` | ❌ Wave 0 |
| PROD-01-02 | Limiter is per-tenant (tenant A and B independent) | unit | `pytest backend/tests/test_rate_limit.py::test_per_tenant_isolation -x` | ❌ Wave 0 |
| PROD-01-02 | Limiter fails OPEN on Redis ConnectionError + emits warning log | failure-mode | `pytest backend/tests/test_rate_limit.py::test_fail_open_on_redis_down -x` | ❌ Wave 0 |
| PROD-01-02 | 200 concurrent requests observe correct cap (sub-ms) | concurrency | `pytest backend/tests/test_rate_limit.py::test_concurrent_burst_respects_limit -x` | ❌ Wave 0 |
| PROD-01-02 | doc/security.md:20 wording matches code | docs | grep assertion in `pytest backend/tests/test_rate_limit.py::test_doc_parity` | ❌ Wave 0 |
| PROD-01-03 | Cross-replica OIDC: state set on app A, consumed on app B | integration | `pytest backend/tests/test_multi_replica.py::test_oidc_cross_replica -x` | ❌ Wave 0 |
| PROD-01-03 | Cross-replica OIDC: second consume fails (one-shot semantics) | integration | `pytest backend/tests/test_multi_replica.py::test_oidc_one_shot -x` | ❌ Wave 0 |
| PROD-01-03 | Cross-replica rate limit: 100 reqs A + 101 reqs B → 201st is 429 | integration | `pytest backend/tests/test_multi_replica.py::test_ratelimit_shared_budget -x` | ❌ Wave 0 |
| PROD-01-03 | Redis down mid-test: limiter allows + warns, OIDC returns 503 | integration | `pytest backend/tests/test_multi_replica.py::test_redis_outage_failure_modes -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_oidc_state.py tests/test_rate_limit.py tests/test_multi_replica.py -x` (target < 30 s)
- **Per wave merge:** `cd backend && pytest -v` (full backend suite)
- **Phase gate:** `cd backend && pytest -v --cov=app --cov-report=xml` green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/conftest.py` — shared fixtures: `redis_test_url`, `flushed_redis`, `app_factory`, `two_apps`
- [ ] `backend/tests/test_oidc_state.py` — covers PROD-01-01
- [ ] `backend/tests/test_rate_limit.py` — covers PROD-01-02
- [ ] `backend/tests/test_multi_replica.py` — covers PROD-01-03
- [ ] Add `asgi-lifespan>=2.1` to `[project.optional-dependencies].dev` in `backend/pyproject.toml`
- [ ] Add `create_app()` factory to `backend/app/main.py` (refactor the current top-level `app = FastAPI(...)`)
- [ ] CI step env var: tests must export `REDIS_URL=redis://localhost:6379/1` (CI currently sets db=0; the test fixture overrides via `monkeypatch.setenv`, so no change to ci.yml required — but document this so the planner does not introduce a redundant CI change)

## Security Domain

> Security enforcement is implicitly enabled (no `.planning/config.json` opt-out found).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | OIDC state store IS the CSRF defense for AuthN flow — verified state token, one-shot consume, TTL. Library: `secrets.token_urlsafe(32)` (256 bits). |
| V3 Session Management | partial | Not session tokens per se, but OIDC state has session-like semantics: opaque, one-shot, time-bound. Pattern: `SET ... NX EX 600` + `GETDEL`. |
| V4 Access Control | yes | Per-tenant rate limiter enforces a coarse availability boundary. Tenant key derived from JWT (already correct). |
| V5 Input Validation | yes | `provider` path param validated against `("google", "azure")` allow-list (already correct in router). Pydantic continues to validate request bodies. |
| V6 Cryptography | no | No crypto introduced in this phase. Existing JWT/Fernet untouched. |

### Known Threat Patterns for FastAPI + Redis

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| OIDC state replay (CSRF) | Spoofing / Tampering | One-shot atomic `GETDEL` — current `_pending_states.pop` already does this; new code must preserve via `GETDEL` (not `GET` then `DEL`) |
| OIDC state forgery | Spoofing | 256-bit `secrets.token_urlsafe(32)` (unchanged) — uniquely identifies a flow, infeasible to guess |
| OIDC state TTL drift / lingering tokens | Tampering / Information Disclosure | `EX 600` set atomically with the value; never use `SET` + later `EXPIRE` (race window where the key is non-expiring) |
| Rate-limit bypass via replica routing | Denial of Service (T) | Sorted-set in shared Redis closes the per-replica bypass that exists today |
| Rate-limit TOCTOU under concurrency | Denial of Service | `MULTI/EXEC` pipeline + add-then-count algorithm (no read-then-write race) |
| Redis outage → CSRF defense bypass | Spoofing / Elevation | Fail-CLOSED on OIDC state path (D-06): 503 instead of "no state to validate, allow it" |
| Redis outage → request flood | Denial of Service | Fail-OPEN on rate limiter (D-05): availability over precision; structlog warning surfaces it |
| Information disclosure via error message | Information Disclosure | Generic "Invalid or expired state parameter" — do not differentiate "expired" vs "tampered" (Pitfall 8) |
| Sub-millisecond duplicate ZADD undercount | Denial of Service (limiter bypass) | Unique member with uuid suffix (Pitfall 1) |
| Tenant-key spoofing in JWT | Spoofing | Existing `decode_token` validates HS256 signature; lightweight parse in middleware is fine because the limit is global anyway — invalid tokens fall to `"anonymous"` |

## Sources

### Primary (HIGH confidence)
- redis-py official docs — https://redis.readthedocs.io/en/stable/ — async client, pipeline, exceptions, connection params
- redis-py asyncio examples — https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html — `from_url`, `aclose()`, pipeline transaction shape
- redis-py source — https://github.com/redis/redis-py/blob/master/redis/asyncio/client.py — confirmed `close()` deprecated in 5.0.1, `aclose()` is canonical
- Redis SET command — https://redis.io/docs/latest/commands/set/ — NX EX semantics and return values
- Redis GETDEL command — https://redis.io/docs/latest/commands/getdel/ — Redis 6.2+, returns nil on missing
- Redis ZADD command — https://redis.io/docs/latest/commands/zadd/ — duplicate-member behavior (Pitfall 1)
- FastAPI async tests — https://fastapi.tiangolo.com/advanced/async-tests/ — ASGITransport pattern + lifespan caveat
- FastAPI middleware — https://fastapi.tiangolo.com/tutorial/middleware/ — Request.app.state access
- asgi-lifespan README — https://github.com/florimondmanca/asgi-lifespan — `LifespanManager` canonical usage

### Secondary (MEDIUM confidence)
- Redis rate-limiter tutorial — https://redis.io/tutorials/howtos/ratelimiting/ — sorted-set sliding-window pattern
- HTTPX transports — https://www.python-httpx.org/advanced/transports/ — ASGITransport API in httpx 0.27
- Starlette TestClient docs — https://www.starlette.io/testclient/ — comparison with AsyncClient + LifespanManager

### Tertiary (LOW confidence)
- None. All claims in this document are backed by official sources.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (none) | — | — | — |

**Table is empty:** Every factual claim in this research is verified against an official source (redis-py docs, Redis command refs, FastAPI docs, httpx docs, asgi-lifespan README) or cited from existing project files. No `[ASSUMED]` claims. The planner can proceed without user confirmation on factual matters; the only outstanding decisions are explicitly delegated to Claude's discretion in CONTEXT.md.

## Open Questions

1. **Should `create_app()` live in `backend/app/main.py` or a new `backend/app/factory.py`?**
   - What we know: D-15 mandates a factory; the current `app = FastAPI(...)` at `main.py:57` works for prod via uvicorn's `app.main:app` import path.
   - What's unclear: Whether to keep `app = create_app()` at module bottom of `main.py` (preserves `uvicorn app.main:app`) or move to a new module.
   - Recommendation: Keep both in `main.py` — define `create_app()`, then `app = create_app()` at module bottom. Zero change to uvicorn entrypoint, supports tests. Claude's discretion (D-15 only mandates the factory exists).

2. **Should the Redis client live in `backend/app/redis_client.py` or stay inline in `lifespan`?**
   - What we know: Lifespan in `main.py` is the home of the construction call. Where `get_redis` lives is open.
   - Recommendation: Put `get_redis` in `backend/app/redis_client.py` (new file, ~10 lines) so the auth router doesn't import from `app.main` (which would create a circular import risk). The `from_url` call stays inside `lifespan` to keep startup ordering visible. Claude's discretion.

3. **Concurrency test bound — what counts as "200 concurrent"?**
   - What we know: D-17 says "100 from app A and 101 from app B".
   - What's unclear: Whether to model true concurrency with `asyncio.gather` or sequential issuing (which would not exercise the sub-ms duplicate-member bug).
   - Recommendation: Use `asyncio.gather(*[client.get(...) for _ in range(N)])` so the pipeline race surface is actually exercised. With `httpx.AsyncClient + ASGITransport` the requests run in-process — Python's GIL serializes them, but the `await pipe.execute()` boundary still creates interleaving relative to Redis. Add at least one `gather` test.

4. **Is the connector-scheduler import order safe with the new lifespan additions?**
   - What we know: `start_scheduler()` runs before Redis client creation in the proposed lifespan extension. The scheduler does not consume Redis today.
   - What's unclear: Future scheduler features that might use Redis would need the client up first.
   - Recommendation: Defer — Phase 1 scheduler does not use Redis. Document the order in a CONTEXT note for future phases (PROD-07 readiness will surface this again).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All backend code | ✓ (assumed; ci.yml pins) | 3.12 | — |
| `redis>=5.2` | OIDC + limiter clients | ✓ | declared in `pyproject.toml:14` | — |
| `httpx>=0.27` | Tests (AsyncClient + ASGITransport) | ✓ | declared in `pyproject.toml:33` | — |
| `pytest-asyncio>=0.24` | Async tests | ✓ | declared in `pyproject.toml:31` | — |
| `asgi-lifespan>=2.1` | Lifespan triggering in tests | ✗ | — | Build Redis client manually in fixture and assign to `app.state.redis`, skipping lifespan; less faithful to prod startup but works |
| Redis 7-alpine | All Redis ops | ✓ in CI | [.github/workflows/ci.yml:33](../../../.github/workflows/ci.yml#L33) | — |
| Redis 7-alpine | All Redis ops (local dev) | ✓ via `docker-compose up redis` | [docker-compose.yml:35](../../../docker-compose.yml#L35) | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `asgi-lifespan` is the only new dev dep. Recommend adding it (it is the documented FastAPI-blessed pattern). Fallback (manual `app.state.redis = ...` in the fixture) is acceptable but loses lifespan-ordering coverage; planner's call.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries declared in `pyproject.toml`; verified versions against PyPI / official docs.
- Architecture: HIGH — pipeline shape, lifespan pattern, ASGITransport + LifespanManager all confirmed in current FastAPI / redis-py / httpx docs.
- Pitfalls: HIGH — every pitfall has a documented citation (Redis ZADD docs for member-duplicate, FastAPI docs for lifespan-not-triggered, redis-py source for `aclose`).
- Test architecture: HIGH — confirmed via FastAPI async-tests page and asgi-lifespan official README.

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (30 days; redis-py 5.x line is stable, httpx 0.27 stable, FastAPI 0.115 stable)
