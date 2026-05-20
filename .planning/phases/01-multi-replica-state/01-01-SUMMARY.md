---
phase: 01-multi-replica-state
plan: 01
subsystem: auth
tags: [oidc, redis, csrf-defense, fail-closed, getdel, structlog, pytest-asyncio]

# Dependency graph
requires:
  - "01-00 — get_redis dep, app.state.redis lifespan, conftest fixtures"
provides:
  - "Redis-backed OIDC state store at backend/app/auth/router.py — SET NX EX 600 + GETDEL"
  - "Fail-closed CSRF defense — HTTP 503 + structlog warning on RedisError (D-06, D-19)"
  - "PROD-01-01 unit-test surface at backend/tests/test_oidc_state.py (5 tests)"
affects: [01-03-multi-replica-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Redis SET key value EX seconds NX — atomic write-with-TTL (no SET+EXPIRE race)"
    - "Atomic one-shot consume via GETDEL (Redis 6.2+, redis-py 4.0+)"
    - "RedisError catch surface (parent of ConnectionError/TimeoutError) → structlog warn → HTTP 503"
    - "Compound 'is None or != provider' check preserves info-leak defense (Pitfall 8)"

key-files:
  created:
    - "backend/tests/test_oidc_state.py (102 lines, 5 tests)"
  modified:
    - "backend/app/auth/router.py (login + callback bodies, imports, dict deletion)"
    - "backend/tests/conftest.py (single_app fixture: yield FastAPI app, not mgr.app — Rule 1 deviation)"

key-decisions:
  - "Followed plan exactly for router edits — imports placed per plan §1, body shape verbatim from plan §3 and §4"
  - "Conftest single_app fixture changed (Rule 1 deviation): yields the original FastAPI instance instead of LifespanManager's wrapped state-middleware closure. The wrapped closure has no .state attribute, so test 5 (Redis-down monkeypatch) crashed with AttributeError. 01-00 SUMMARY documented '(client, app)' contract; the fixture now matches that contract."
  - "Dropped unused 'import redis.asyncio as redis_pkg' from test file (ruff F401, Rule 1 minor)"

requirements-completed:
  - PROD-01-01

# Metrics
duration: 3min (auto-mode TDD-style execution; ~214s wall)
completed: 2026-05-09
---

# Phase 01 Plan 01: OIDC State on Redis Summary

**OIDC state moves from in-process `_pending_states: dict` to Redis via atomic `SET ... EX 600 NX` at login and `GETDEL oidc:state:{token}` at callback; CSRF defense fails closed (HTTP 503) when Redis is unreachable.**

## Performance

- **Duration:** ~214 s (~3.5 min)
- **Started:** 2026-05-09T09:56:27Z
- **Completed:** 2026-05-09T10:00:01Z
- **Tasks:** 2 / 2
- **Files modified:** 3 (1 new test file, 1 router edit, 1 conftest fixture fix)

## Accomplishments

- Replaced the in-process `_pending_states: dict[str, str]` (and the misleading `# In-memory state store (use Redis in production)` comment) with a Redis-backed flow:
  - `/auth/login/{provider}` writes `oidc:state:{token} = {provider}` via `await redis_client.set(..., ex=600, nx=True)`. The `nx=True` is defense-in-depth against the negligible 256-bit `secrets.token_urlsafe(32)` collision; collision returns HTTP 500 ("State collision — retry").
  - `/auth/callback/{provider}` consumes the state in one round trip via `await redis_client.getdel(f"oidc:state:{state}")`. The compound `if stored_provider is None or stored_provider != provider:` check is preserved verbatim per Pitfall 8 (no info-leak distinguishing "expired" from "tampered").
- Both routes catch `redis.exceptions.RedisError` (parent of `ConnectionError` and `TimeoutError`), emit `logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))` per D-19, and raise `HTTPException(503, "Auth backend unavailable")` per D-06 (CSRF defense fails CLOSED).
- Added `backend/tests/test_oidc_state.py` with the 5 PROD-01-01 unit tests demanded by VALIDATION.md rows 01-01-01 through 01-01-05. All 5 pass against real Redis db=1.
- Full backend test suite: **37 / 37 passing** (32 pre-existing + 5 new). No regressions.

## Task Commits

Each task committed atomically with `--no-verify` per the parallel-executor protocol:

1. **Task 1 — feat(01-01): replace `_pending_states` dict with Redis SET NX EX + GETDEL** — `c7c2e3b`
2. **Task 2 — test(01-01): add 5 PROD-01-01 OIDC state unit tests** — `c7a8a1c`

## Files Created/Modified

### Created

- **`backend/tests/test_oidc_state.py`** (102 lines, 5 tests)
  - `test_state_set_with_ttl` — `GET /auth/login/google` → key `oidc:state:{state}` exists with value `"google"` and TTL ∈ [595, 600] (VALIDATION row 01-01-01).
  - `test_state_replay_rejected` — Seed `oidc:state:STATE = "google"`; first `/auth/callback/google` consumes it (status ∈ {400, 401, 502, 503} since the IdP token exchange is unmocked); the key is deleted (GETDEL semantic); replay returns 400 with `"Invalid or expired state parameter"` (VALIDATION row 01-01-02).
  - `test_state_provider_mismatch` — Seed `oidc:state:STATE = "google"`; `/auth/callback/azure?state=STATE` returns 400; the key is deleted by GETDEL even on mismatch — preventing later replay against `google` (VALIDATION row 01-01-03).
  - `test_state_ttl_expiry` — Seed with `ex=1`; sleep 1.2 s; callback returns 400 (VALIDATION row 01-01-04).
  - `test_login_503_on_redis_down` — Monkeypatch `app.state.redis.set` and `.getdel` to raise `redis.exceptions.ConnectionError`; both `/auth/login/google` and `/auth/callback/google` return 503 with detail `"Auth backend unavailable"` (VALIDATION row 01-01-05).

### Modified

- **`backend/app/auth/router.py`** — diff summary:
  - Added imports: `import redis.asyncio as redis`, `import structlog`, `from redis.exceptions import RedisError`, `from app.redis_client import get_redis`.
  - Added `logger = structlog.get_logger()` immediately after `router = APIRouter()`.
  - Deleted both line 30 (`# In-memory state store (use Redis in production)`) and line 31 (`_pending_states: dict[str, str] = {}`).
  - `login(provider)` → `login(provider, redis_client: Annotated[redis.Redis, Depends(get_redis)])`. Body now:
    ```python
    state = secrets.token_urlsafe(32)
    try:
        ok = await redis_client.set(f"oidc:state:{state}", provider, ex=600, nx=True)
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
    if not ok:
        raise HTTPException(status_code=500, detail="State collision — retry")
    ```
  - `callback(provider, code, state, db)` → `callback(provider, code, state, db, redis_client: Annotated[redis.Redis, Depends(get_redis)])`. State validation block now:
    ```python
    try:
        stored_provider = await redis_client.getdel(f"oidc:state:{state}")
    except RedisError as e:
        logger.warning("redis_unavailable", subsystem="oidc_state", error=str(e))
        raise HTTPException(status_code=503, detail="Auth backend unavailable")
    if stored_provider is None or stored_provider != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    ```
  - The remaining callback body (token exchange, userinfo fetch, tenant resolve, upsert_user, issue_tokens) is byte-identical to the previous version.

- **`backend/tests/conftest.py`** — `single_app` fixture: was `yield client, mgr.app`; now `yield client, app`. The original FastAPI instance has the lifespan-populated `.state.redis`; the LifespanManager's wrapped ASGI callable does not. Tests still route HTTP requests through `mgr.app` via `ASGITransport`; only the second yielded element changed.

## Decisions Made

- Followed the plan's router edits verbatim (imports, body shape, error message string, log fields).
- Did **not** modify the password-auth routes below, the `/me` route, or the `/refresh` route — outside the plan's scope.
- Removed the unused `import redis.asyncio as redis_pkg` from the test file (ruff F401 — Rule 1 micro-fix). The plan specified this import but never referenced `redis_pkg` in any test body.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `single_app` conftest fixture yielded the wrong app object**

- **Found during:** Task 2 (`test_login_503_on_redis_down` raised `AttributeError: 'function' object has no attribute 'state'`).
- **Issue:** `backend/tests/conftest.py` shipped by 01-00 yielded `(client, mgr.app)` from the `single_app` fixture, where `mgr.app` is `LifespanManager`'s wrapped state-middleware closure (`state_middleware.<locals>.app_with_state`). That closure has no `.state` attribute, so `monkeypatch.setattr(app.state.redis, "set", ...)` crashed before the test could even start. The 01-00 SUMMARY explicitly claimed `single_app` yields `(client, app)`, so this was an unambiguous contract violation rather than a design choice.
- **Fix:** Changed `yield client, mgr.app` → `yield client, app` (the original `FastAPI` instance returned by `app_factory()`). HTTP requests still flow through `mgr.app` via `ASGITransport`; the test's monkeypatch now hits the same `app.state.redis` that the lifespan populated.
- **Files modified:** `backend/tests/conftest.py` (1 line change + clarifying docstring)
- **Commit:** `c7a8a1c` (rolled into the Task 2 commit since the fix is what enables Task 2's last test to run)
- **Risk to parallel waves:** Low. `two_apps` (used only by 01-03) is unchanged. 01-02's rate-limiter tests will likely also need `app.state.redis` access for the fail-open Redis-down test, so this fix is forward-compatible.

**2. [Rule 1 - Lint] Removed unused import in test file**

- **Found during:** Task 2 ruff post-check.
- **Issue:** Plan specified `import redis.asyncio as redis_pkg` in the test file, but no test body references `redis_pkg`. ruff F401 fired.
- **Fix:** Dropped that single import line. `RedisConnectionError` is the only redis import the tests actually need.
- **Files modified:** `backend/tests/test_oidc_state.py`
- **Commit:** `c7a8a1c`

## Authentication Gates

None — Phase 1 has no external service auth (Redis is local infra).

## Issues Encountered

- **Worktree base mismatch (resolved before any task started):** The worktree branch was based on `8cede77` (main) instead of `47d9cc2` (the 01-00 final commit). Resolved via `git reset --hard 47d9cc2`. After the reset, `.planning/phases/01-multi-replica-state/` only contained 01-00 + 01-02 plan files — 01-01 and 01-03 plan files exist as untracked in the parent repo. Copied the four needed planning files (PROJECT.md, REQUIREMENTS.md, config.json, 01-01-PLAN.md, 01-00-PLAN.md, 01-03-PLAN.md) into the worktree's untracked tree purely for read access; they are NOT included in any of this plan's commits (the orchestrator owns those writes).
- **No local Python venv or Redis:** Created `backend/.venv` (Python 3.12.7) via `pyenv local 3.12.7 && python3.12 -m venv .venv && pip install -e ".[dev]"`. Started a Redis 7-alpine container via `docker run -d --rm --name gsd-redis-01-01 -p 6379:6379 redis:7-alpine` so tests have a live db=1. `.venv/` and `gsd-redis-01-01` are environmental setup, not plan deliverables; `backend/.python-version` is also untracked.

## User Setup Required

None — Phase 1 is purely backend infra. The deployment has already documented `REDIS_URL` in `.env.example` and provides the redis service in `docker-compose.yml`. Production deploys will hit the existing Redis without configuration changes.

## Next Phase Readiness

This plan unblocks:

- **01-03 (multi-replica integration suite)** — can now seed state on app A's Redis and consume it on app B via the production code paths (no longer the in-memory dict). The `test_oidc_cross_replica` and `test_oidc_one_shot` tests in 01-03 should pass against this implementation.

This plan does NOT block:

- **01-02 (rate limiter on Redis)** — independent surface (`backend/app/main.py::TenantRateLimitMiddleware`); both plans run in parallel under wave 1.

No blockers to phase-1 completion.

## Self-Check: PASSED

Verification (run from worktree root):

| Claim | Check | Result |
|---|---|---|
| `backend/app/auth/router.py` modified | `[ -f backend/app/auth/router.py ]` | FOUND |
| `backend/tests/test_oidc_state.py` created | `[ -f backend/tests/test_oidc_state.py ]` | FOUND |
| `backend/tests/conftest.py` modified | `[ -f backend/tests/conftest.py ]` | FOUND |
| `_pending_states` removed | `grep -c "_pending_states" backend/app/auth/router.py` | `0` |
| In-memory comment removed | `grep -c "In-memory state store" backend/app/auth/router.py` | `0` |
| SET NX EX 600 line | `grep -F 'ex=600, nx=True' backend/app/auth/router.py` | hit |
| GETDEL line | `grep -F 'await redis_client.getdel(f"oidc:state:' backend/app/auth/router.py` | hit |
| 503 fail-closed (≥2 hits) | `grep -c 'status_code=503' backend/app/auth/router.py` | `2` |
| structlog subsystem (≥2 hits) | `grep -cF 'subsystem="oidc_state"' backend/app/auth/router.py` | `2` |
| All 5 unit tests green | `pytest tests/test_oidc_state.py -v` | `5 passed` |
| Full backend suite green | `pytest -q` | `37 passed` |
| Commit `c7c2e3b` exists | `git log --oneline | grep c7c2e3b` | FOUND |
| Commit `c7a8a1c` exists | `git log --oneline | grep c7a8a1c` | FOUND |
| Lint clean on changed files | `ruff check app/auth/router.py tests/test_oidc_state.py tests/conftest.py` | `All checks passed!` |

---
*Phase: 01-multi-replica-state, Plan: 01*
*Completed: 2026-05-09*
