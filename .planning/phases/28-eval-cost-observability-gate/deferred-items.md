# Phase 28 — Deferred Items

Out-of-scope discoveries logged during plan execution (not fixed, per the
executor's scope-boundary rule: only auto-fix issues directly caused by the
current task's changes).

## 28-01: Pre-existing ruff-format drift (3 files, unrelated to this plan)

**Found during:** Task 2 post-implementation regression sweep (`ruff format --check .` across the whole `backend/` tree).

**Files:**
- `backend/tests/test_ai_explain_remediation_guidance.py`
- `backend/tests/test_ai_schemas.py`
- `backend/tests/test_connectors/test_rapid7_connector.py`

**Issue:** `ruff format --check .` reports these 3 files "would reformat" (formatting drift from the pinned `ruff==0.15.21` formatter's current output). `ruff check .` (linting) reports zero issues — this is purely a formatter-output drift, not a lint violation.

**Why deferred:** None of these files were touched by 28-01 (confirmed via `git log -- <file>` and `git status --short`: last commits are 26-01/25-02/23-01 respectively, all pre-dating this phase). Reformatting them is outside 28-01's task scope (schema/prompt-builder tests, not the eval harness).

**Suggested fix:** `cd backend && ruff format tests/test_ai_explain_remediation_guidance.py tests/test_ai_schemas.py tests/test_connectors/test_rapid7_connector.py` as a small standalone housekeeping commit, whenever convenient (does not block any Phase 28 plan).

## 28-02: Background AI batch-prewarm scheduler races the `client` fixture's per-test app lifespan

**Found during:** Task 2 (`test_ai_budget_coverage.py`), verifying Test A (the 5 explain routes' no-bypass coverage) against live Postgres+Redis.

**Issue:** `app/connectors/scheduler.py::_dispatch_ai_batch_prewarm()` gates its dispatch of `run_batch_prewarm()` on a MODULE-LEVEL global (`_last_ai_batch_prewarm`), not a per-app-instance or per-test state. Its very first tick per Python process fires unconditionally (`_last_ai_batch_prewarm is None` branch). Since `pyproject.toml` shares one event loop for the whole pytest session (`asyncio_default_fixture_loop_scope = "session"`) and the `client`/`client_factory` fixtures each start a REAL `create_app()` + lifespan (which starts a fresh `_scheduler_loop()` background task per test), that one process-wide first tick can land at ANY test in the session that happens to be the first to give the scheduler task an execution turn — non-deterministically, depending on exact `await` interleaving. Observed empirically: with `app.ai.explain.AsyncAnthropic` patched and a real ANTHROPIC connector configured for `tenant_a` (both needed for this coverage test's own scenario), 1 of 10 parametrized Test A cases failed with `mock_cls.call_count == 1` instead of `0` — traced via a stray `ai_batch_prewarm_tenant_error` log line to the scheduler's OWN background `run_batch_prewarm()` call independently constructing a client through the same patched name.

**Why deferred (not fixed in `scheduler.py`):** The bug is a genuine test-reliability hazard, but the *production* code's behavior (dispatch-on-first-tick-per-process) is reasonable outside a shared-loop, `create_app()`-per-test-function harness; fixing it structurally (e.g. per-app-instance dispatch state, or a test-mode disable flag) is an architectural change to `app/connectors/scheduler.py` (Rule 4 territory) out of this narrowly-scoped coverage-test task. **Fixed locally instead**, scoped to `test_ai_budget_coverage.py`'s own Test A: both the over-budget test and its under-budget regression control now additionally patch `app.connectors.scheduler._dispatch_ai_batch_prewarm` to a no-op (`AsyncMock`) for their full duration, eliminating the race without touching production code. Verified stable over 3 consecutive full-suite reruns post-fix (11/11 passed each time).

**Residual, still-benign artifact:** An intermittent `SAWarning: Session's state has been changed on a non-active transaction - this state will be discarded` sometimes still appears in the warnings summary for `test_under_budget_control_constructs_anthropic_client` cases (does not fail any test; only 1 pytest process in 4 test runs showed it, never reproduced under `-W error::sqlalchemy.exc.SAWarning`). Plausibly a residual artifact of the same background-scheduler-task-vs-per-test-session-teardown timing family. Not chased further (non-fatal, non-deterministic, pre-existing architecture, out of this task's scope).

**Suggested fix (future, optional):** If this class of flake resurfaces in other `client`-fixture-based AI tests, consider a `conftest.py`-level `autouse` fixture that patches `app.connectors.scheduler._dispatch_ai_batch_prewarm`/`_dispatch_ai_batch_poll` to no-ops for the whole test session (or resets `_last_ai_batch_prewarm` to `datetime.now(UTC)` at session start), rather than each test file re-discovering and re-patching it individually.

## 28-03: Pre-existing `mypy-baseline.txt` note-line drift (local env, unrelated to this plan)

**Found during:** Task 1 post-implementation verification (`mypy app/ | mypy-baseline filter --allow-unsynced`, mirroring `ci.yml`'s exact invocation) after adding `backend/app/api/v1/ai/usage.py` + registering it in `backend/app/api/v1/ai/__init__.py`.

**Issue:** The filter reports `note 27 -3 +6` and a "Your changes introduced new violations" banner. The 6 "new" lines are all `note:` sub-lines attached to the pre-existing, already-baselined `error: Library stubs not installed for "jose"  [import-untyped]` (on `app/auth/jwt.py`, `app/auth/service.py`, `app/auth/dependencies.py`) — mypy only emits the 3-line `Hint:`/`install-types`/`See ...` note trio the FIRST time it encounters that import-untyped error per run, and WHICH file "wins" that first-occurrence slot depends on mypy's internal file-processing order, which can shift when the `app/api/v1/ai/` package gains a new sibling module (or with a different local mypy/mypy-baseline version than whatever produced the committed baseline).

**Confirmed pre-existing, not caused by this plan:** Reverted `usage.py` + `__init__.py` to clean HEAD (temporarily, restored immediately after) and re-ran the IDENTICAL `mypy app/ | mypy-baseline filter --allow-unsynced` command — the exact same `note 27 -3 +6` delta and false-positive banner appear with ZERO Plan 03 changes present. Also reproduced by running mypy against only the two untouched sibling files `status.py`/`feedback.py`. This matches the already-documented `getvul-backend-test-harness-rot`-adjacent artifact from Phase 24 Plan 08 ("a pre-existing mypy-baseline.txt note-line-number-drift artifact... confirmed unrelated").

**Why deferred:** Root cause is environment/tooling drift (local mypy/mypy-baseline install vs. whatever produced the committed baseline, or file-walk-order sensitivity), not a real type violation in any file this plan touches. `usage.py`/`__init__.py` produce ZERO mypy errors when checked in isolation (`mypy app/api/v1/ai/usage.py app/api/v1/ai/__init__.py` — no errors reported against either file). Fixing the baseline tool's run-order sensitivity is out of this narrowly-scoped endpoint task (Rule 4 territory / a `mypy-baseline sync` housekeeping pass, not an AIE-04 concern).

**Suggested fix (future, optional):** Re-run `mypy-baseline sync` in CI (the exact environment/versions the gate runs in) if this drift starts failing the real CI job — do not `sync` from a local machine, since that would bake in whatever local drift exists instead of resolving it.
