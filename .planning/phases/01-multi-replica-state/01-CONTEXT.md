# Phase 1: Multi-Replica State - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the in-process OIDC state dict ([backend/app/auth/router.py:31](../../../backend/app/auth/router.py#L31)) and the in-process per-tenant rate-limit dict ([backend/app/main.py:103-104](../../../backend/app/main.py#L103-L104)) with Redis-backed equivalents so two backend replicas behind a load balancer share both pieces of state.

In scope:
- Add a `redis.asyncio.Redis` client to the app and use it for OIDC state + rate limiting
- Delete the in-memory `_pending_states` dict and `_rate_limit_store` defaultdict
- Multi-process integration test proving correctness

Out of scope (other phases):
- Per-user / per-IP rate limits (new capability)
- Per-tenant configurable limits (new capability)
- Health endpoint Redis check (Phase 7 — PROD-07)
- Prometheus / `/metrics` endpoint (deferred — see deferred ideas)
- Background scheduler extraction to a separate worker (v1.1+ SCALE-01)

</domain>

<decisions>
## Implementation Decisions

### Rate-limiter algorithm
- **D-01:** Sliding window via Redis sorted set, keyed `ratelimit:{tenant_id}` (or `ratelimit:anonymous`). Per request: `ZREMRANGEBYSCORE` (prune older than `now - 60s`) + `ZADD now now` + `ZCARD` + `EXPIRE 60`. Reject when `ZCARD >= 200`.
- **D-02:** Pipeline the four commands via `redis.asyncio.client.Pipeline` (`async with client.pipeline(transaction=True) as pipe`) so they execute as one round trip. Atomicity matters when multiple concurrent requests from the same tenant race on the same window.
- **D-03:** Limit stays global at 200 requests / 60 seconds (`RATE_LIMIT_REQUESTS = 200`, `RATE_LIMIT_WINDOW = 60`). No per-tenant configurability in this phase.
- **D-04:** Tenant key derivation is unchanged — JWT decoded lightweight, fall back to `"anonymous"`.

### Redis-down behavior
- **D-05:** Rate limiter **fails open** when Redis is unreachable: allow the request through, emit `logger.warning("redis_unavailable", subsystem="rate_limiter", error=str(e))`. Treat the limiter as a safety valve, not a security boundary.
- **D-06:** OIDC state store **fails closed**: if Redis is unreachable on `GET /auth/login/{provider}` we cannot persist state, so return 503; on `GET /auth/callback/{provider}` if state read fails, return 503 with `{"detail": "Auth backend unavailable"}`. Bypassing state validation is a CSRF defect — never elide it.
- **D-07:** No Redis check on `/health` in this phase — Phase 7 (PROD-07) will introduce `/ready` for that. Keep `/health` unchanged.

### OIDC state TTL & semantics
- **D-08:** TTL is **10 minutes** (`SETEX state:{token} 600 {provider}`). Matches the PROD-01-01 ceiling. Comfortable margin for slow IdP redirects, MFA, and proxy retries.
- **D-09:** Consume is **atomic one-shot**: callback uses `GETDEL state:{token}` to read and delete in one operation. A replayed callback within the TTL window must fail. Matches current `_pending_states.pop(state, None)` semantics.
- **D-10:** Key namespace: `oidc:state:{token}` (under a single `oidc:` prefix so future OIDC-related keys can colocate).

### Redis client lifecycle
- **D-11:** `redis.asyncio.Redis` client is created in the FastAPI `lifespan` context manager and stored on `app.state.redis`. Created once via `redis.asyncio.from_url(settings.redis_url, decode_responses=True, socket_timeout=2.0, socket_connect_timeout=2.0)`. Closed on shutdown via `await app.state.redis.aclose()`.
- **D-12:** Middleware reads the client via `request.app.state.redis`. No `Depends` injection in middleware (FastAPI middleware doesn't support `Depends` cleanly). For route handlers (auth router), use a thin `get_redis(request: Request)` dependency that returns `request.app.state.redis`.
- **D-13:** Existing in-memory `_pending_states: dict` and `_rate_limit_store: defaultdict(list)` are **deleted entirely** in this phase. No fallback path. Redis is now a hard runtime dependency (it already is — docker-compose starts it, `.env.example` documents `REDIS_URL`).
- **D-14:** Use a 2-second socket timeout so a slow/unreachable Redis fails fast rather than holding the request thread.

### Multi-replica integration test
- **D-15:** Test uses **two FastAPI app instances** (each constructed by an `app_factory()` that returns a fresh `FastAPI` with its own `lifespan`), both pointing at one real Redis. Each app gets its own `httpx.AsyncClient` (transport=`ASGITransport(app=app_instance)`). Closer to production semantics than fakeredis; the cost is acceptable since CI already runs Redis.
- **D-16:** Reuse the existing `services.redis` in [.github/workflows/ci.yml:32-40](../../../.github/workflows/ci.yml#L32-L40). Tests use `REDIS_URL=redis://localhost:6379/1` (db=1 to isolate from any app data on db=0). Test fixture flushes db=1 before each test.
- **D-17:** Required test cases: (a) state set on app A, GETDEL on app B succeeds and second GETDEL fails — proves cross-replica OIDC; (b) tenant T issues 100 requests through app A and 101 through app B; the 201st request gets HTTP 429 — proves cross-replica rate limit; (c) Redis stopped mid-test → rate limit allows traffic with warning log, OIDC callback returns 503.

### Observability
- **D-18:** Redis-failure events emitted as structured logs only (structlog), not Prometheus metrics. Phase 7 may add a `/metrics` endpoint on top; this phase doesn't introduce a new metrics dep.
- **D-19:** Log fields: `event`, `subsystem` (`rate_limiter` | `oidc_state`), `error` (str(exception)), `tenant_id` if known.

### Doc parity
- **D-20:** Update [doc/security.md:20](../../../doc/security.md#L20) (`"Per-tenant API rate limiting: 200 requests per 60 seconds (Redis-backed)"`) so it is finally accurate. PROD-04 (Phase 4) covers other doc/code drift; this single line is in scope here because it directly references the code Phase 1 changes.

### Claude's Discretion
- Exact module layout for the Redis client (`backend/app/redis_client.py` vs putting `from_url` directly in `lifespan`)
- Names for the small Pydantic/dataclass response shape on rate-limit headers (today: `Retry-After`)
- Whether to introduce a tiny `RateLimiterError` exception class or just `redis.RedisError` catch
- Whether the test fixture lives in `backend/tests/conftest.py` or `backend/tests/test_multi_replica.py`
- Any micro-optimizations like Redis connection pool size

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — Multi-tenant invariant, "no backwards-compatibility hacks" preference, in-process scheduler decision (informs why Redis is the right shared substrate)
- `.planning/REQUIREMENTS.md` §"Multi-Replica State (PROD-01)" — PROD-01-01, PROD-01-02, PROD-01-03 acceptance criteria
- `.planning/ROADMAP.md` §"Phase 1: Multi-Replica State" — success criteria 1–4

### Code being replaced (mandatory reads)
- `backend/app/auth/router.py:31-46` — current OIDC state init + use in `/auth/login/{provider}`
- `backend/app/auth/router.py:55-67` — current state consume in `/auth/callback/{provider}`
- `backend/app/main.py:99-144` — current `TenantRateLimitMiddleware`, `_rate_limit_store`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`
- `backend/app/main.py:19-54` — current `lifespan` (where Redis client construction will be added)
- `backend/app/config.py:13` — `redis_url` setting (already exists, no change needed)

### Test plumbing
- `.github/workflows/ci.yml:32-40` — existing `services.redis: redis:7-alpine` available to backend job at `redis://localhost:6379/0`
- `backend/tests/test_auth.py` — existing JWT/auth test file; new multi-replica tests live alongside it
- `docker-compose.yml:34-42` — local Redis service, used by developers running tests outside CI

### Dependency surface
- `backend/pyproject.toml:14` — `redis>=5.2` already in production deps; no new deps for Phase 1
- `backend/pyproject.toml:19` — `tenacity>=9.0` available if a retry wrapper is wanted (Claude's discretion; not required)

### Doc to update
- `doc/security.md:20` — "Per-tenant API rate limiting: 200 requests per 60 seconds (Redis-backed)" line becomes accurate after this phase

### No external ADRs
- This project does not maintain a formal `docs/decisions/` ADR directory. The Implementation Decisions above ARE the ADR for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`structlog` logger pattern** — established across the codebase ([backend/app/connectors/scheduler.py:15](../../../backend/app/connectors/scheduler.py#L15) etc.). New `redis_unavailable` warnings should use `structlog.get_logger()` with the same shape.
- **FastAPI `lifespan` async context manager** — already exists at [backend/app/main.py:19-54](../../../backend/app/main.py#L19-L54). Add Redis client startup/shutdown there; matches how the connector scheduler is started/stopped.
- **`async_session_factory` pattern** — DB session factory in [backend/app/db/session.py](../../../backend/app/db/session.py) gives a model for "module-level factory, called from middleware/handlers" — but client lifecycle decision (D-11) keeps Redis on `app.state` instead, since the client is a single connection-pool object, not a per-request factory.

### Established Patterns
- **JWT decode in middleware without DB** — [backend/app/main.py:118-125](../../../backend/app/main.py#L118-L125) parses the Bearer token in `TenantRateLimitMiddleware` for the tenant key. New Redis-backed limiter keeps this verbatim — only the storage backend changes.
- **`ENVIRONMENT == "development"` gating** — [backend/app/main.py:23](../../../backend/app/main.py#L23) is the canonical env check; reuse the same pattern if any debug-only Redis behavior emerges.
- **No global exception handlers** — handlers raise `HTTPException` directly. New code should do the same.

### Integration Points
- **Middleware add order matters**: `SecurityHeadersMiddleware` then `TenantRateLimitMiddleware` are added in that order at [backend/app/main.py:96, 147](../../../backend/app/main.py#L96). Replacement limiter goes in the same slot — don't re-order.
- **Auth router state init at module load** — [backend/app/auth/router.py:31](../../../backend/app/auth/router.py#L31) is at module level. Move state writes/reads to use `request.app.state.redis` via a `get_redis` dep so the auth router doesn't import the client at module scope.
- **Tests run with `app` instance** — [backend/tests/test_auth.py](../../../backend/tests/test_auth.py) already uses real settings; the new multi-replica test harness must NOT mutate global `settings` (use a `pytest` fixture that builds a fresh `app` per replica with `REDIS_URL` overrides via env).

</code_context>

<specifics>
## Specific Ideas

- The current `_pending_states.pop(state, None)` is a one-shot consume — preserve that semantic with `GETDEL`. Don't weaken it to `GET` + late `DEL`.
- The current limiter's `Retry-After` header value (`str(RATE_LIMIT_WINDOW)`) is fine; carry it through.
- Use Redis db=1 in CI/tests to isolate from db=0 (the app default). This makes test cleanup `FLUSHDB` safe.

</specifics>

<deferred>
## Deferred Ideas

- **Prometheus `/metrics` endpoint** — would require `prometheus_client` dep + auth/network-policy thinking. Belongs in Phase 7 (Health & Observability) at the earliest, or its own phase.
- **Per-user / per-IP rate limits** — new capability; not in Phase 1 scope. Add to backlog if needed.
- **Tenant-configurable limits via `tenant.rate_limit_config` JSONB** — new capability + new admin UI. Backlog candidate.
- **Token-bucket / Lua-script algorithms** — sliding-window sorted set is the chosen algorithm; revisit only if measured latency or burst behavior is a problem.
- **Rate-limit fallback to in-process counter when Redis is down** — rejected in favor of fail-open + warn (D-05). Re-evaluate only if Redis outages become a recurring incident.
- **Redis Sentinel / Cluster** — single-node Redis is fine for the single-VM topology. HA Redis is a v1.1+ concern (SCALE bucket).

</deferred>

---

*Phase: 01-multi-replica-state*
*Context gathered: 2026-05-08*
