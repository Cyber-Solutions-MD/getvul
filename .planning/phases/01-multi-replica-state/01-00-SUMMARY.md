---
phase: 01-multi-replica-state
plan: 00
subsystem: infra
tags: [redis, fastapi, asgi-lifespan, pytest-asyncio, httpx, lifespan, multi-replica]

# Dependency graph
requires: []
provides:
  - "create_app() factory in backend/app/main.py — each call yields an isolated FastAPI instance"
  - "app.state.redis populated by lifespan via redis.asyncio.from_url with 2s socket timeouts (D-11, D-14)"
  - "from app.redis_client import get_redis — FastAPI dependency for route handlers"
  - "Test fixtures in backend/tests/conftest.py: redis_test_url, flushed_redis, app_factory, single_app, two_apps"
  - "asgi-lifespan>=2.1 in [project.optional-dependencies].dev"
affects: [01-01-oidc-state, 01-02-rate-limiter, 01-03-multi-replica-integration]

# Tech tracking
tech-stack:
  added: ["asgi-lifespan>=2.1 (dev only)"]
  patterns:
    - "FastAPI app-factory pattern (create_app() returns a fresh instance each call)"
    - "Redis client lifecycle owned by lifespan (one client per app on app.state.redis)"
    - "get_redis(request) dependency for route handlers (avoids importing main at module scope)"
    - "Test fixtures use real Redis on db=1 + LifespanManager so app.state.redis is populated"

key-files:
  created:
    - "backend/app/redis_client.py"
    - "backend/tests/conftest.py"
  modified:
    - "backend/pyproject.toml"
    - "backend/app/main.py"

key-decisions:
  - "Imports consolidated to top of main.py (ruff I rules); previous file had scattered conditional imports"
  - "Middleware classes (SecurityHeaders, TenantRateLimit) stay at module scope; only the .add_middleware() calls move into create_app()"
  - "SIM105 suppressed with noqa on the conftest cleanup try/except — the plan explicitly mandates this pattern (RESEARCH Pitfall 6)"

patterns-established:
  - "Pattern 1: every FastAPI instance is built via create_app(); module-level `app = create_app()` is the uvicorn entrypoint"
  - "Pattern 2: long-lived clients (Redis, DB) attach to app.state inside lifespan and close on shutdown"
  - "Pattern 3: route handlers fetch shared state via FastAPI Depends; middleware reads request.app.state directly"

requirements-completed:
  - PROD-01-01
  - PROD-01-02
  - PROD-01-03

# Metrics
duration: 12min
completed: 2026-05-09
---

# Phase 01 Plan 00: Wave-0 Foundation Summary

**FastAPI app-factory + Redis-on-lifespan plumbing and shared async test fixtures, so plans 01-01 / 01-02 / 01-03 can land their behavior changes against a stable substrate.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-09T12:42Z (worktree branch verification)
- **Completed:** 2026-05-09T12:48Z (last task commit)
- **Tasks:** 4 / 4
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Added `asgi-lifespan>=2.1` as a dev-only dep so `httpx.AsyncClient(transport=ASGITransport(app=app))` triggers FastAPI lifespan in tests (the integration suite cannot pass without this).
- Refactored `backend/app/main.py` so every `app.add_middleware`, `app.include_router`, and `@app.<verb>` decorator now lives inside a single `def create_app() -> FastAPI` function. Module-level `app = create_app()` preserves the `uvicorn app.main:app` entrypoint and every `from app.main import app` callsite (audit log, etc.).
- Extended the existing `lifespan()` to open a `redis.asyncio` client (`decode_responses=True`, `socket_timeout=2.0`, `socket_connect_timeout=2.0`) on `app.state.redis` and close it via `await app.state.redis.aclose()` on shutdown.
- Created `backend/app/redis_client.py` exposing the canonical `get_redis(request) -> redis.Redis` FastAPI dependency. No defensive try/except — missing `app.state.redis` is a loud `AttributeError` by design.
- Created `backend/tests/conftest.py` with the full Phase-1 fixture stack (`redis_test_url`, `flushed_redis`, `app_factory`, `single_app`, `two_apps`). `flushed_redis` hard-asserts `db == 1` before any FLUSHDB to prevent prod-data tampering.
- All 32 existing tests still pass; `pytest --collect-only` succeeds.

## Task Commits

Each task was committed atomically (with `--no-verify` per the parallel-executor protocol):

1. **Task 1: Add asgi-lifespan dev dep** — `6b0570d` (chore)
2. **Task 2: Extract create_app() factory + add Redis lifespan** — `08539f2` (refactor)
3. **Task 3: New get_redis dependency module** — `e6f2f6b` (feat)
4. **Task 4: Shared test fixtures (conftest.py)** — `8e1c78a` (test)

## Files Created/Modified

- `backend/pyproject.toml` — added `"asgi-lifespan>=2.1",` inside `[project.optional-dependencies].dev` immediately after `"httpx>=0.27",`.
- `backend/app/main.py` — fully reorganized:
  - All imports consolidated at the top (FastAPI, redis.asyncio, all routers, get_db, get_current_user, etc.).
  - `lifespan()` keeps its original responsibilities (scheduler bring-up/teardown, syslog config) and now also opens/closes `app.state.redis`.
  - `SecurityHeadersMiddleware`, `TenantRateLimitMiddleware`, `_rate_limit_store`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW` remain at module scope (their *bodies* are unchanged in this plan; 01-02 will replace `TenantRateLimitMiddleware.dispatch`).
  - `create_app()` body holds, in this order: `FastAPI(...)` → CORS → SecurityHeaders → TenantRateLimit → 10 `include_router` calls → `/health` → 1 export route → 4 reports routes → 2 SMTP routes → 4 certificate routes → dev-router conditional → `return app`.
  - Module bottom: `app = create_app()`.
- `backend/app/redis_client.py` — NEW. 4 lines of code (after docstring): a single `get_redis(request: Request) -> redis.Redis` dependency that returns `request.app.state.redis`.
- `backend/tests/conftest.py` — NEW. Five `pytest_asyncio` fixtures:
  - `redis_test_url(monkeypatch)` — sets `REDIS_URL=redis://localhost:6379/1` AND replaces the cached `app.config.settings` singleton so `create_app()` picks up the new URL.
  - `flushed_redis(redis_test_url)` — real `redis.asyncio` client; asserts `db == 1`; `try/finally` cleanup.
  - `app_factory(redis_test_url)` — returns a callable that calls `create_app()`.
  - `single_app(flushed_redis, app_factory)` — yields `(client, app)` with lifespan running.
  - `two_apps(flushed_redis, app_factory)` — yields `(client_a, client_b)` against two independent apps both pointing at db=1 (PROD-01-03 substrate).

## Downstream Import Paths

For plans 01-01, 01-02, 01-03 to consume:

```python
# Route handler dependency:
from app.redis_client import get_redis

# Middleware (cannot use Depends):
client = request.app.state.redis

# Test fixtures (autodiscovered from backend/tests/conftest.py):
async def test_something(single_app):
    client, app = single_app
    # ...

async def test_cross_replica(two_apps):
    client_a, client_b = two_apps
    # ...
```

## Decisions Made

- Followed the plan as written; no architectural deviations.
- Linter-driven micro-adjustments (none of which affect plan acceptance criteria):
  - `from typing import AsyncIterator` → `from collections.abc import AsyncIterator` (UP035 via `ruff --fix`).
  - Nested `async with` statements combined into single statements (SIM117 via `ruff --fix`).
  - `# noqa: SIM105` added to the conftest cleanup `try/except redis.RedisError: pass` because the plan explicitly mandates this pattern (the "ONE place defensive try/except is correct" — RESEARCH Pitfall 6).

## Deviations from Plan

None - plan executed exactly as written. Linter-driven syntax adjustments above are within the plan's "Claude's discretion" surface and do not change behavior or fixture API.

## Issues Encountered

- **Worktree base mismatch (resolved before any task started):** The worktree branch was based on `8cede776` (older than the expected `b9ad4bb`). Resolved via `git reset --soft b9ad4bb...` and `git checkout HEAD -- .planning/...` to restore phase-1 planning files. After reset, working tree was clean and matched the expected base.
- **Planning files needed local copy:** The orchestrator's `.planning/PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `config.json`, and `01-00-PLAN.md` exist in the parent repo but were never committed (still untracked). They were copied into the worktree's untracked tree purely for read access; they are NOT included in any of this plan's commits (the orchestrator owns those writes).
- **No local Python venv existed:** Created `backend/.venv` (Python 3.12.13) and ran `pip install -e ".[dev]"` so verifications could run. `.venv/` is already in the project's `.gitignore`.

## User Setup Required

None - no external service configuration required. Phase 1 needs Redis available at `REDIS_URL` (already documented in `.env.example` and provided by the existing `docker-compose.yml` redis service).

## Next Phase Readiness

The substrate is in place. Downstream waves can proceed:

- **01-01 (OIDC state on Redis)** — can `from app.redis_client import get_redis`; `app.state.redis` is already populated.
- **01-02 (rate limiter on Redis)** — middleware can read `request.app.state.redis` directly inside `TenantRateLimitMiddleware.dispatch`; `_rate_limit_store` and the in-memory pruning loop will be deleted in that plan.
- **01-03 (multi-replica integration suite)** — can use the `two_apps` fixture as-is. `flushed_redis` guarantees a clean db=1 between tests.

No blockers.

## Self-Check: PASSED

Verification:

- `backend/pyproject.toml` — FOUND, contains `asgi-lifespan>=2.1`
- `backend/app/main.py` — FOUND, contains `def create_app`, `app = create_app()`, `app.state.redis = redis.from_url`, `await app.state.redis.aclose()`
- `backend/app/redis_client.py` — FOUND, contains `def get_redis`
- `backend/tests/conftest.py` — FOUND, contains `redis_test_url`, `flushed_redis`, `app_factory`, `single_app`, `two_apps`
- Commits: `6b0570d`, `08539f2`, `e6f2f6b`, `8e1c78a` — all FOUND in `git log`
- `pytest -x` — 32 tests pass (no regressions from refactor)
- `ruff check` — clean on all created/modified files

---
*Phase: 01-multi-replica-state, Plan: 00*
*Completed: 2026-05-09*
