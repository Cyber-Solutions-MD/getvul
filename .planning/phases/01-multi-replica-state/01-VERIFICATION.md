---
phase: 01-multi-replica-state
verified: 2026-05-09T00:00:00Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
requirements:
  PROD-01-01: satisfied
  PROD-01-02: satisfied
  PROD-01-03: satisfied
spot_checks:
  phase_1_suite_passing: 15/15
  full_backend_suite_passing: 47/47
---

# Phase 01: Multi-Replica State Verification Report

**Phase Goal:** Two backend replicas behind a load balancer can complete an OIDC login and share rate-limit budget without race conditions or lost state.
**Verified:** 2026-05-09
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

Both subsystems that previously held state in-process — the OIDC state dict (`_pending_states`) and the per-tenant rate limiter (`_rate_limit_store`) — now persist state in a shared Redis instance. A 4-test cross-replica integration suite (`backend/tests/test_multi_replica.py`) provably exercises the goal: state set on app A is consumed on app B, the second consume fails (one-shot), 100+101 requests across replicas trip the shared 200-req budget on the 201st request, and a simulated Redis outage produces fail-open (limiter) and fail-closed (OIDC) behavior in both replicas. All 15 phase-1 tests and all 47 backend tests pass against live Redis db=1.

### Observable Truths (merged ROADMAP success criteria + per-plan must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_pending_states` dict gone from auth/router.py; state lives in Redis with TTL | ✓ VERIFIED | `grep -c "_pending_states" backend/app/auth/router.py` → 0; `await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)` present at router.py:47 |
| 2 | `_rate_limit_store` defaultdict gone from main.py; counter lives in Redis | ✓ VERIFIED | `grep -c "_rate_limit_store" backend/app/main.py` → 0; `grep -c "defaultdict" backend/app/main.py` → 0; `pipe.zadd(key, {member: now_ms})` at main.py:136 |
| 3 | Integration test boots two backend processes against one Redis and verifies (a) OIDC cross-replica callback (b) shared rate-limit budget | ✓ VERIFIED | `test_multi_replica.py` defines 4 tests using `two_apps` fixture which yields two FastAPI instances against shared db=1; tests pass live |
| 4 | doc/security.md:20 claim "Redis-backed rate limiting" is now true | ✓ VERIFIED | `sed -n '20p' doc/security.md` → `- Per-tenant API rate limiting: 200 requests per 60 seconds (Redis-backed sliding window)` |
| 5 | OIDC login persists state in Redis with 600s TTL keyed `oidc:state:{token}` | ✓ VERIFIED | router.py:47 `await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)`; `test_state_set_with_ttl` asserts TTL ∈ [595, 600] (PASSED live) |
| 6 | OIDC callback consumes state via single atomic GETDEL — replays within TTL fail | ✓ VERIFIED | router.py:70 `await redis_client.getdel(f"oidc:state:{state}")`; `test_state_replay_rejected` asserts second consume returns 400 (PASSED live) |
| 7 | OIDC callback rejects when stored provider does not match URL provider | ✓ VERIFIED | router.py:74 `if stored_provider is None or stored_provider != provider` → 400; `test_state_provider_mismatch` PASSED live |
| 8 | OIDC login + callback return 503 when Redis unreachable (fail-closed CSRF defense) | ✓ VERIFIED | `except RedisError → 503 Auth backend unavailable` in both endpoints (router.py:48-50, 71-73); `test_login_503_on_redis_down` PASSED live |
| 9 | TenantRateLimitMiddleware uses Redis sorted-set sliding window keyed `ratelimit:{tenant_id}` | ✓ VERIFIED | main.py:127 `key = f"ratelimit:{tenant_key}"`; pipeline uses ZREMRANGEBYSCORE → ZADD → ZCARD → EXPIRE |
| 10 | ZADD member is `f"{now_ms}:{uuid.uuid4().hex[:8]}"` (defeats sub-ms duplicate-member undercount) | ✓ VERIFIED | main.py:131 exact pattern present; `test_concurrent_burst_respects_limit` (asyncio.gather of 250 reqs) asserts exactly 200/50 split — PASSED live |
| 11 | Pipeline is `transaction=True` and runs ZREMRANGEBYSCORE/ZADD/ZCARD/EXPIRE in one round trip | ✓ VERIFIED | main.py:134 `async with redis_client.pipeline(transaction=True) as pipe:` followed by 4 commands |
| 12 | When count exceeds 200, middleware returns 429 with `Retry-After: 60` | ✓ VERIFIED | main.py:150 `if count > RATE_LIMIT_REQUESTS:` → 429 + `Retry-After: str(RATE_LIMIT_WINDOW)`; `test_limit_enforced` PASSED live |
| 13 | On RedisError, limiter fails OPEN with structured warning `event=redis_unavailable subsystem=rate_limiter` | ✓ VERIFIED | main.py:140-147 emits structlog warning with subsystem="rate_limiter" then calls call_next; `test_fail_open_on_redis_down` asserts both behaviors (PASSED live) |
| 14 | Tests can spin up TWO independent app instances against ONE shared Redis db=1 | ✓ VERIFIED | conftest.py:78-94 `two_apps` fixture builds two apps via `app_factory()`, both wrapped in `LifespanManager`, both sharing db=1 |
| 15 | Auth router + rate-limit middleware resolve Redis client via app.state.redis without importing app at module scope | ✓ VERIFIED | redis_client.py:13 `def get_redis(request: Request)` returns `request.app.state.redis`; auth router uses `Depends(get_redis)`; middleware reads `request.app.state.redis` directly |
| 16 | All 4 cross-replica integration tests use the existing `two_apps` fixture from conftest.py | ✓ VERIFIED | `grep -cF "two_apps" tests/test_multi_replica.py` → 7 (3 of 4 tests use the fixture; the 4th builds local apps to access app.state.redis for monkeypatching — explicit deviation in 01-03-SUMMARY, plan permits) |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/pyproject.toml` | `asgi-lifespan>=2.1` in dev deps | ✓ VERIFIED | Found in `[project.optional-dependencies].dev` immediately after `httpx>=0.27` (line 32) |
| `backend/app/main.py` | `create_app()` factory + Redis lifespan + sliding-window middleware | ✓ VERIFIED | `def create_app` at line 162; `app = create_app()` at line 539; `app.state.redis = redis.from_url(...)` at line 45 with `socket_timeout=2.0`, `decode_responses=True`; `await app.state.redis.aclose()` at line 74; full sorted-set sliding window middleware lines 107-159 |
| `backend/app/redis_client.py` | `get_redis(request)` FastAPI dependency | ✓ VERIFIED | 15-line file; `def get_redis(request: Request) -> redis.Redis: return request.app.state.redis` |
| `backend/app/auth/router.py` | Redis-backed OIDC state via SET NX EX 600 + GETDEL | ✓ VERIFIED | `await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)` at line 47; `await redis_client.getdel(f"oidc:state:{state}")` at line 70; both wrapped in `except RedisError → 503` |
| `backend/tests/conftest.py` | `redis_test_url`, `flushed_redis`, `app_factory`, `single_app`, `two_apps` fixtures | ✓ VERIFIED | All 5 fixtures present and signed correctly; `flushed_redis` hard-asserts `db == 1` before any FLUSHDB |
| `backend/tests/test_oidc_state.py` | 5 PROD-01-01 unit tests (TTL, replay, mismatch, expiry, 503) | ✓ VERIFIED | 95 lines, 5 named tests matching VALIDATION.md rows 01-01-01 through 01-01-05; all pass live |
| `backend/tests/test_rate_limit.py` | 6 PROD-01-02 tests (enforce, slide, isolate, fail-open, concurrency, doc parity) | ✓ VERIFIED | 255 lines (≥200 min_lines), 6 named tests matching VALIDATION.md rows 01-02-01 through 01-02-06; all pass live |
| `backend/tests/test_multi_replica.py` | 4 PROD-01-03 cross-replica tests | ✓ VERIFIED | 159 lines (≥150 min_lines), 4 named tests matching VALIDATION.md rows 01-03-01 through 01-03-04; all pass live |
| `doc/security.md` | line 20 reads `(Redis-backed sliding window)` | ✓ VERIFIED | `sed -n '20p' doc/security.md` → exact mandated wording present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `lifespan` in main.py | `redis.from_url(settings.redis_url, ...)` | `app.state.redis` assignment | ✓ WIRED | main.py:45-50 — pattern `app\.state\.redis = redis\.from_url` matches; constructor passes `decode_responses=True`, `socket_timeout=2.0`, `socket_connect_timeout=2.0` |
| `auth/router.py login(provider)` | Redis SET `oidc:state:{state}` | `await redis_client.set(..., ex=600, nx=True)` | ✓ WIRED | router.py:47 — exact pattern |
| `auth/router.py callback(provider)` | Redis GETDEL `oidc:state:{state}` | `await redis_client.getdel(...)` | ✓ WIRED | router.py:70 — exact pattern |
| `RedisError catch (auth router)` | HTTP 503 `Auth backend unavailable` | `raise HTTPException(status_code=503, detail=...)` | ✓ WIRED | router.py:48-50, 71-73 — both call sites have the catch + 503 raise |
| `main.py TenantRateLimitMiddleware.dispatch` | Redis ZADD `ratelimit:{tenant_key}` | `pipe.zadd(key, {member: now_ms})` inside `pipeline(transaction=True)` | ✓ WIRED | main.py:134-136 — pattern matches |
| `TenantRateLimitMiddleware RedisError catch` | structlog warning + call_next (fail-open) | `logger.warning(...subsystem="rate_limiter") + return await call_next(request)` | ✓ WIRED | main.py:140-147 — structured warning fields (event/subsystem/error/tenant_id) match D-19 |
| `doc/security.md:20` | code in main.py middleware | verbatim wording match | ✓ WIRED | doc says "Redis-backed sliding window"; main.py uses Redis sorted-set sliding window |
| `tests/conftest.py two_apps fixture` | `asgi_lifespan.LifespanManager(app)` wrapping both | wrap before AsyncClient construction | ✓ WIRED | conftest.py:84-94 builds two apps via `app_factory()`, wraps each in `LifespanManager`, both yielding clients pointing at db=1 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|---|
| auth router OIDC state | `stored_provider` (callback) | `await redis_client.getdel(...)` against shared Redis db=1 | Yes — set by login flow, consumed atomically | ✓ FLOWING |
| rate limiter `count` | `results[2]` from pipeline.execute() | Real Redis ZCARD on `ratelimit:{tenant_key}` after ZADD | Yes — sorted set is the single source of truth | ✓ FLOWING |
| `app.state.redis` | populated in lifespan | `redis.from_url(settings.redis_url, ...)` opened by `lifespan` ASGI startup hook | Yes — verified via the `probe` sanity assertion in test_redis_outage_failure_modes (set on A, get on B) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase-1 tests pass | `pytest tests/test_oidc_state.py tests/test_rate_limit.py tests/test_multi_replica.py -v` | `15 passed in 8.07s` | ✓ PASS |
| Full backend test suite passes (no regressions) | `pytest -q` | `47 passed in 4.92s` | ✓ PASS |
| All target source files compile | `python3 -m py_compile {file}` for main.py, auth/router.py, redis_client.py, conftest.py, all 3 phase-1 test files | All compile | ✓ PASS |
| Live Redis available on port 6379 | `nc -z localhost 6379` | `succeeded` (gsd-redis-01-01 docker container) | ✓ PASS |

Tests were executed live against a fresh venv (Python 3.12.7) with `pip install -e ".[dev]"` against the live `gsd-redis-01-01` Redis container. The temporary venv was deleted after verification.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROD-01-01 | 01-00, 01-01 | OIDC state moves from `_pending_states` dict to Redis with TTL ≤10 min | ✓ SATISFIED | `_pending_states` removed (router.py); SET NX EX 600 + GETDEL implemented; 5 unit tests in test_oidc_state.py covering TTL, replay, mismatch, expiry, 503 — all PASSED |
| PROD-01-02 | 01-00, 01-02 | Per-tenant rate limiter moves from `_rate_limit_store` defaultdict to Redis sorted-set; doc/security.md drift fixed | ✓ SATISFIED | `_rate_limit_store`/defaultdict removed (main.py); 4-command pipeline with uuid-suffixed members and `transaction=True`; 6 tests in test_rate_limit.py including doc parity — all PASSED; doc/security.md:20 updated |
| PROD-01-03 | 01-00, 01-03 | Both implementations have integration tests proving correctness across two backend processes hitting one Redis | ✓ SATISFIED | 4 integration tests in test_multi_replica.py covering D-17 cases (a) cross-replica OIDC, (b) shared rate-limit budget, (c) Redis outage failure modes — all PASSED |

No orphaned requirements. REQUIREMENTS.md maps PROD-01-01/02/03 to Phase 1 and all three appear in the source plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| backend/app/redis_client.py | 13 | No try/except around `request.app.state.redis` | ℹ️ Info — intentional | Per project rule "no defensive validation at non-boundary code" (D-12 / 01-00 plan); missing app.state.redis is a desired loud AttributeError signaling a lifespan regression |
| backend/tests/conftest.py | 41 | `try/except RedisError: pass` in cleanup | ℹ️ Info — intentional with `# noqa: SIM105` | RESEARCH Pitfall 6 — the ONE place defensive try/except is correct (test cleanup may run after test deliberately killed Redis) |

No `TODO`, `FIXME`, `HACK`, `placeholder`, or stub markers found in any phase-1 source or test files. No empty handlers, no `return null`/`return []` stubs in routes or middleware. The only "fail-soft" pattern (`except Exception: pass`) is in the JWT decode path inside the rate-limit middleware (main.py:123), which is preserved verbatim from the original code per D-04 and is the correct behavior for "anonymous" fallback — not a phase-1 regression.

### Anti-Pattern Spot Checks Across Modified Files

```bash
# Files modified in phase 1 (from SUMMARY key-files):
backend/pyproject.toml         — only adds asgi-lifespan>=2.1 line
backend/app/main.py            — create_app(), Redis lifespan, sliding-window middleware
backend/app/redis_client.py    — 15-line dependency module (new)
backend/app/auth/router.py     — OIDC login/callback bodies updated
backend/tests/conftest.py      — 5 phase-1 fixtures (new)
backend/tests/test_oidc_state.py    — 5 tests (new)
backend/tests/test_rate_limit.py    — 6 tests (new)
backend/tests/test_multi_replica.py — 4 tests (new)
doc/security.md                — line 20 wording change
```

Grep across all of these finds zero `TODO|FIXME|XXX|HACK` markers attributable to phase-1 work. The `# noqa: SIM105` in conftest.py is documented as intentional in 01-00-SUMMARY.

### Human Verification Required

None. All must-have truths are programmatically verifiable and have been verified by:

1. Static structural checks (grep, file existence, code shape)
2. Live test execution against real Redis db=1 (15/15 phase-1 tests + 47/47 full suite)
3. Inspection of structlog event capture in `test_fail_open_on_redis_down` and `test_redis_outage_failure_modes` (the structured-log shape D-19 demands is asserted by `.get("event") == "redis_unavailable"`, `.get("subsystem") == "rate_limiter"`, `.get("error")` containing the simulated message)
4. Manual `sed -n '20p' doc/security.md` confirms the exact mandated wording

The VALIDATION.md "Manual-Only Verifications" section listed two items:
- "Visual confirmation of structlog `redis_unavailable` warning shape" — **already covered programmatically** by `structlog.testing.capture_logs()` assertions in `test_fail_open_on_redis_down` and `test_redis_outage_failure_modes` (which verify event/subsystem/error fields exactly).
- "Production-like behavior under sustained 1000 req/min" — **explicitly out of scope for this milestone** ("Out of CI scope; requires soak test infra not in this milestone"). Not a phase-1 gate.

Therefore no human verification is required to mark this phase passed.

### Gaps Summary

No gaps. Every must-have from PLAN frontmatter and ROADMAP success criteria is verified, every requirement (PROD-01-01/02/03) is satisfied, and the goal — "Two backend replicas behind a load balancer can complete an OIDC login and share rate-limit budget without race conditions or lost state" — is observable and tested by `tests/test_multi_replica.py::{test_oidc_cross_replica, test_oidc_one_shot, test_ratelimit_shared_budget, test_redis_outage_failure_modes}`, all of which pass live against a real Redis on db=1.

The phase is complete and unblocks Phase 2 (CI Gating).

---

*Verified: 2026-05-09*
*Verifier: Claude (gsd-verifier)*
