---
phase: 01-multi-replica-state
plan: 03
subsystem: tests
tags: [integration, multi-replica, redis, oidc, rate-limiter, structlog, pytest-asyncio, asgi-lifespan]

# Dependency graph
requires:
  - "01-00 — create_app() factory, app_factory + flushed_redis + two_apps fixtures, asgi-lifespan dev dep"
  - "01-01 — Redis-backed OIDC state at /auth/login + /auth/callback (provides cross-replica OIDC behavior under test)"
  - "01-02 — Redis-backed rate limiter middleware (provides cross-replica rate-limit behavior under test)"
provides:
  - "PROD-01-03 cross-replica integration test surface at backend/tests/test_multi_replica.py (4 tests, 159 lines)"
  - "Regression test for 'in-memory state silently re-introduced' — guards against future contributors wiring up local caches"
  - "Proof artifact for v1.0 production-readiness audit on PROD-01"
affects: [02-ci-gating]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-app local construction via app_factory() + LifespanManager + ASGITransport for tests that need direct app.state.redis access"
    - "structlog.testing.capture_logs() to assert structured warning emission across both replicas during a simulated Redis outage"
    - "GETDEL atomicity verified across replicas: state set on app A → consumed on app B → second consume returns 400"
    - "Cross-replica rate-limit budget verified: 100 reqs A + 100 reqs B + 1 = 429 (shared sorted-set in Redis db=1)"

key-files:
  created:
    - "backend/tests/test_multi_replica.py (159 lines, 4 tests)"
  modified: []

key-decisions:
  - "Followed the plan's test bodies verbatim except for the LifespanManager `mgr_*.app.state` access pattern, which is incorrect (mgr.app is the wrapped state-middleware closure, not the original FastAPI instance — same bug 01-01 fixed in conftest.py). Changed to keep direct `app_a` / `app_b` references and access `app_a.state.redis` (Rule 1 deviation, see Deviations section)."
  - "Removed unused `import asyncio` (the plan recommended asyncio.gather for the rate-limit warm-up but the plan's own action body uses sequential GETs — the import was never referenced; ruff F401)"
  - "Combined nested `async with` statements into a single statement (ruff SIM117 auto-fix) — purely syntactic, no semantic change"

requirements-completed:
  - PROD-01-03

# Metrics
duration: 3min (~190s wall)
completed: 2026-05-09
---

# Phase 01 Plan 03: Cross-Replica Integration Test Suite Summary

**Four integration tests boot two independent FastAPI app instances against one shared Redis db=1 and prove that the implementations from 01-01 (Redis-backed OIDC state) and 01-02 (Redis-backed rate limiter) actually share state across replicas — the entire reason Phase 1 exists.**

## Performance

- **Duration:** ~190 s (~3 min)
- **Started:** 2026-05-09T10:16:51Z
- **Completed:** 2026-05-09T10:20:01Z
- **Tasks:** 1 / 1
- **Files modified:** 1 (1 created, 0 modified)

## Accomplishments

- Created `backend/tests/test_multi_replica.py` with 4 named tests covering all PROD-01-03 acceptance rows in `01-VALIDATION.md`:
  - `test_oidc_cross_replica` (row 01-03-01) — App A's `/auth/login/google` returns a state token; the key `oidc:state:{state}` is visible to App B in shared Redis db=1; App B's `/auth/callback/google` GETDELs the key (verified gone after the call); the callback's HTTP response is in `(400, 401, 502, 503)` because the IdP token exchange against a fake `code` fails — that is fine; the assertion is on the side effect, not the response.
  - `test_oidc_one_shot` (row 01-03-02) — App A mints state; App B's first callback consumes it; App B's SECOND callback with the same state returns HTTP 400 with detail `"Invalid or expired state parameter"`. Replay defense survives across replicas.
  - `test_ratelimit_shared_budget` (row 01-03-03) — 100 anonymous GETs through App A + 100 through App B = 200 (all allowed). The 201st request (issued through App B) returns HTTP 429 with `Retry-After: 60`. Issuing one more on App A also returns 429. The shared sorted-set in Redis is the single source of truth.
  - `test_redis_outage_failure_modes` (row 01-03-04) — Builds the two apps locally so we can monkeypatch `app.state.redis.{pipeline,set,getdel}` to raise `RedisConnectionError`. After the patches: App A's `/api/v1/reports` request returns NOT 429 (limiter fails OPEN — D-05) AND `structlog.testing.capture_logs()` captures `event=redis_unavailable subsystem=rate_limiter`. App A's `/auth/login/google` returns 503 with detail `"Auth backend unavailable"` (OIDC fails CLOSED — D-06). App B's `/auth/callback/google` likewise returns 503. Both behaviors are tested on independent app instances.
- Phase 1 suite: **15 / 15 passing** (5 OIDC + 6 rate-limit + 4 cross-replica). Full backend suite: **47 / 47 passing** (no regressions).
- Lint clean on all created files (`ruff check tests/test_multi_replica.py` — `All checks passed!`).

## D-17 Subcase → Test Map

The plan's threat-model rows and CONTEXT.md's D-17 specify three required test cases (a, b, c). Each is encoded into a named test:

| D-17 subcase | Behavior required | Test name | VALIDATION row |
|---|---|---|---|
| **(a)** | State set on app A, GETDEL on app B succeeds; second GETDEL fails | `test_oidc_cross_replica` + `test_oidc_one_shot` | 01-03-01 + 01-03-02 |
| **(b)** | Tenant T issues 100 reqs through A and 101 through B → 201st = HTTP 429 | `test_ratelimit_shared_budget` | 01-03-03 |
| **(c)** | Redis stopped mid-test → rate limit allows + warns; OIDC callback returns 503 | `test_redis_outage_failure_modes` | 01-03-04 |

All three subcases are observable: a developer can re-run `cd backend && pytest tests/test_multi_replica.py -v` and see the four cross-replica behaviors verified.

## Task Commits

Single-task plan; committed atomically with `--no-verify` per the parallel-executor protocol:

1. **Task 1 — test(01-03): add 4 PROD-01-03 cross-replica integration tests** — `43d1036`

## Files Created/Modified

### Created

- **`backend/tests/test_multi_replica.py`** (159 lines, 4 tests) — see "D-17 Subcase → Test Map" above for behavior summary. Imports: `pytest`, `structlog`, `asgi_lifespan.LifespanManager`, `httpx.{ASGITransport,AsyncClient}`, `redis.exceptions.ConnectionError as RedisConnectionError`. The `TEST_API_ENDPOINT = "/api/v1/reports"` constant is used by both `test_ratelimit_shared_budget` and `test_redis_outage_failure_modes`; the rate-limit middleware fires for any path starting with `/api/`, which is the contract under test.

### Modified

- None.

## Decisions Made

- **Followed the plan's test names verbatim** — all four match VALIDATION.md rows 01-03-01 through 01-03-04 exactly (`test_oidc_cross_replica`, `test_oidc_one_shot`, `test_ratelimit_shared_budget`, `test_redis_outage_failure_modes`).
- **Three of four tests use the existing `two_apps` fixture** (per plan's must_haves). Only `test_redis_outage_failure_modes` builds its apps locally because it needs direct `app.state.redis` access for monkeypatching — the `two_apps` fixture as defined in 01-00 yields only `(client_a, client_b)`.
- **Did NOT extend the `two_apps` fixture** to also yield app instances. The plan explicitly allowed both approaches ("either approach is acceptable — the test author should pick whichever requires the minimum churn"). Building two apps locally for one test is a 6-line copy of the conftest pattern; extending the fixture would change a Wave 0 deliverable shipped by 01-00 and risk breaking other downstream consumers (none today, but the fixture is now part of the conftest contract).
- **Sequential warm-up in `test_ratelimit_shared_budget`** (not `asyncio.gather`) — the plan's action body specifies sequential GETs and the `<notes>` block calls this out explicitly: "issuing them sequentially is sufficient to prove cross-replica accounting because we are NOT testing the sub-ms duplicate-member bug here (that's covered by `test_concurrent_burst_respects_limit` in plan 01-02)."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `LifespanManager.app.state` does not exist**

- **Found during:** Task 1, first run of `test_redis_outage_failure_modes`.
- **Issue:** The plan's action body calls `mgr_a.app.state.redis.set(...)` to seed the probe key. `LifespanManager`'s `.app` attribute is the wrapped state-middleware closure (`state_middleware.<locals>.app_with_state`, a bare `function`), not the original FastAPI instance. So `mgr.app.state` raises `AttributeError: 'function' object has no attribute 'state'` — the test crashed before any assertion ran. This is the same bug 01-01 fixed in `conftest.py::single_app` (which previously yielded `mgr.app` and was changed to yield the original `app`). The plan's own `<interfaces>` block prescribed this pattern, but it is incorrect for the same reason 01-01 had to fix the fixture.
- **Fix:** Kept direct references to `app_a` and `app_b` (the original FastAPI instances returned by `app_factory()`); access `app_a.state.redis` for the probe and the monkeypatch. HTTP requests still flow through `mgr_a.app` / `mgr_b.app` via `ASGITransport` — only the `.state` access path changed. Added a docstring to `test_redis_outage_failure_modes` explaining the rationale so future readers don't re-introduce the pattern from the plan.
- **Files modified:** `backend/tests/test_multi_replica.py`
- **Commit:** `43d1036` (rolled into Task 1)
- **Risk to other plans:** None. No fixture contract changes; the fix is local to one test.

**2. [Rule 1 - Lint] Removed unused `import asyncio`**

- **Found during:** Task 1 ruff post-check (F401).
- **Issue:** The plan's action body imported `asyncio` but never used it. The plan's own `<notes>` block clarified "test_ratelimit_shared_budget does NOT use asyncio.gather" — so the import was orphan boilerplate.
- **Fix:** Dropped the import line.
- **Files modified:** `backend/tests/test_multi_replica.py`
- **Commit:** `43d1036`

**3. [Rule 1 - Lint] Combined nested `async with` (ruff SIM117 auto-fix)**

- **Found during:** Task 1 ruff post-check (SIM117).
- **Issue:** The plan's action body has `async with LifespanManager(app_a) as mgr_a, LifespanManager(app_b) as mgr_b: \n async with (AsyncClient(...), AsyncClient(...)):` — two nested `async with` blocks. ruff SIM117 prefers a single combined statement.
- **Fix:** Combined into one `async with (LifespanManager(app_a), LifespanManager(app_b), AsyncClient(...), AsyncClient(...)):`. Re-indented the body to match. Pure syntactic refactor; no behavior change. `ruff check --fix` produced the change.
- **Files modified:** `backend/tests/test_multi_replica.py`
- **Commit:** `43d1036`

## Authentication Gates

None — Phase 1 has no external service auth (Redis is local infra; OIDC token exchange against the IdP is mocked via `code=fake` and the assertion is on the cross-replica side effect, not the IdP response).

## Issues Encountered

- **Worktree base mismatch (resolved before any task started):** Worktree branch was based on `8cede77` (older `main`) instead of `1dfce14` (the 01-02 final commit which contains all phase-1 planning files and prior plan summaries). Resolved via `git reset --hard 1dfce148c1b319d4b3082714806489e2a2f821b4`. After the reset, `.planning/phases/01-multi-replica-state/` contains 01-00-SUMMARY.md, 01-01-SUMMARY.md, 01-02-PLAN.md, 01-02-SUMMARY.md, 01-CONTEXT.md, 01-DISCUSSION-LOG.md, 01-RESEARCH.md, 01-VALIDATION.md as expected.
- **Planning files copied for read access:** The 01-03-PLAN.md, PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and config.json existed in the parent repo but were untracked. Copied them into the worktree's untracked tree purely for read access; they are NOT included in any of this plan's commits (the orchestrator owns those writes).
- **No local Python venv:** Created `backend/.venv` (Python 3.12.13) via `python3.12 -m venv .venv && pip install -e ".[dev]"`. `.venv/` is in `.gitignore`.
- **Redis container reused from prior plan:** `gsd-redis-01-01` (Redis 7-alpine on `redis://localhost:6379`) from 01-01's run was still up; tests use db=1 via `monkeypatch.setenv` in the conftest fixture, so coexistence with any data on db=0 is safe.

## User Setup Required

None — Phase 1 is purely backend infra. The deployment already documents `REDIS_URL` in `.env.example` and provides the redis service in `docker-compose.yml`. Production deploys will hit the existing Redis without configuration changes.

## Next Phase Readiness

This plan **closes Phase 1**: PROD-01-01 (01-01), PROD-01-02 (01-02), and PROD-01-03 (01-03) are all green.

This plan unblocks:

- **Phase 2: CI Gating (PROD-02)** — the next phase will wire push/PR triggers and remove the `|| true` masks. Phase 1's 15 tests (and the broader 47-test backend suite) will run on every push/PR after Phase 2 ships, providing continuous regression coverage for the multi-replica claims.

This plan does NOT block:

- **Phase 1 wave 2 has no other plans** — this is the only Wave-2 plan.

No blockers to phase-1 completion.

## Self-Check: PASSED

Verification (run from worktree root):

| Claim | Check | Result |
|---|---|---|
| `backend/tests/test_multi_replica.py` created | `[ -f backend/tests/test_multi_replica.py ]` | FOUND |
| 4 named tests defined | `grep -c "def test_oidc_cross_replica\|def test_oidc_one_shot\|def test_ratelimit_shared_budget\|def test_redis_outage_failure_modes" backend/tests/test_multi_replica.py` | `4` |
| `two_apps` fixture used | `grep -cF "two_apps" backend/tests/test_multi_replica.py` | `7` (≥3 required) |
| `LifespanManager` used | `grep -cF "LifespanManager" backend/tests/test_multi_replica.py` | `5` (≥1 required) |
| `structlog.testing.capture_logs` used | `grep -cF "structlog.testing.capture_logs" backend/tests/test_multi_replica.py` | `1` |
| `Auth backend unavailable` asserted | `grep -cF "Auth backend unavailable" backend/tests/test_multi_replica.py` | `2` |
| File ≥ 150 lines (plan min_lines) | `wc -l backend/tests/test_multi_replica.py` | `159` |
| All 4 PROD-01-03 tests green | `pytest tests/test_multi_replica.py -v` | `4 passed` |
| Full Phase 1 suite green (15 tests) | `pytest tests/test_oidc_state.py tests/test_rate_limit.py tests/test_multi_replica.py -v` | `15 passed` |
| Full backend suite green | `pytest -x` | `47 passed` |
| Lint clean on changed files | `ruff check tests/test_multi_replica.py` | `All checks passed!` |
| Commit `43d1036` exists | `git log --oneline \| grep 43d1036` | FOUND |

---
*Phase: 01-multi-replica-state, Plan: 03*
*Completed: 2026-05-09*
