---
phase: 34-historical-recompute-consumer-cutover
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, asyncpg, postgres, scheduler, backfill, risk-scoring]

# Dependency graph
requires:
  - phase: 33-risk-exposure-model-definition
    provides: "score_finding/FindingScoreInputs (risk_exposure_service.py) + RISK_MODEL_VERSION + Vulnerability.risk_exposure_score/risk_exposure_breakdown/risk_model_version columns (migration 042/043)"
provides:
  - "RiskExposureBackfillJob durable per-tenant job table (migration 044)"
  - "3 additive Tenant columns: cutover_risk_exposure_scoring, risk_cutover_threshold_ack_at, risk_cutover_threshold_ack_diff_hash (migration 044, full Phase-34 schema spine)"
  - "risk_backfill_service.py: enqueue_backfill_job / process_backfill_chunk / dispatch_backfill_chunks — idempotent, resumable, throttled, per-tenant-isolated historical recompute"
  - "scheduler._dispatch_risk_exposure_backfill wired into _scheduler_loop (create_task, no in-memory gate)"
affects: [34-02-flag-gated-cutover, 34-03-diff-ack-flag-flip, 34-04-boundary-guards]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Claim-row concurrency guard: single UPDATE...WHERE status IN (...) AND stale-or-null-heartbeat RETURNING, race-safe without an asyncio.Lock()"
    - "Heartbeat cleared to NULL on every successful chunk commit (not left at claim-time 'now') so the very next scheduler tick can reclaim immediately — the 5-min staleness window only matters for a truly abandoned/never-committed claim"
    - "Bulk UPDATE...FROM (VALUES ...) with an explicit CAST on every column of every row — required for SQLAlchemy 2.0.50 + asyncpg to infer a consistent VALUES column type across parameterized rows"
    - "db.expire_all() after a raw-SQL bulk UPDATE that bypasses the ORM, to avoid identity-map staleness under expire_on_commit=False"

key-files:
  created:
    - backend/alembic/versions/044_add_risk_backfill_job.py
    - backend/app/vulnerabilities/risk_backfill_service.py
    - backend/tests/test_risk_recompute.py
    - .planning/phases/34-historical-recompute-consumer-cutover/deferred-items.md
  modified:
    - backend/app/vulnerabilities/models.py
    - backend/app/tenants/models.py
    - backend/app/connectors/scheduler.py

key-decisions:
  - "Bulk UPDATE...FROM (VALUES ...) bind syntax verified live against SQLAlchemy 2.0.50 + asyncpg: every column of every VALUES row needs an explicit CAST (uuid/int/jsonb/varchar) — untyped params default inconsistently and Postgres rejects a VALUES list whose inferred column type isn't uniform across rows"
  - "Steps 3 (score) + 4 (bulk UPDATE...FROM) + 5 (cursor/counter advance) share ONE transaction with ONE db.commit() (Pitfall 5 option (a)) — a crash anywhere before that commit rolls the whole chunk back, so rows_migrated can never be double-counted on resume"
  - "Heartbeat is cleared to NULL on every successful chunk commit (both the 'processed a chunk' and 'marked completed' paths) rather than left at the claim-time timestamp — discovered during GREEN that leaving it at 'now' would make the 5-minute staleness WHERE-guard block the very next scheduler tick (60s later) from reclaiming the same tenant, silently turning 'one chunk per tick' into 'one chunk per 5 minutes'"
  - "Scheduler dispatch pattern: _dispatch_risk_exposure_backfill is a thin wrapper that itself does asyncio.create_task on a one-shot multi-tenant sweep (mirrors _dispatch_ai_batch_prewarm/poll's internal-create_task shape); the call site in _scheduler_loop does a plain `await _dispatch_risk_exposure_backfill()`, matching the established direct-await test convention"
  - "No in-memory _last_* gate for this dispatcher (the only scheduler dispatcher without one) — the durable per-tenant claim-row inside process_backfill_chunk IS the gate, since an in-memory gate would reset on the exact process restart RISK-07 must survive"

patterns-established:
  - "Claim-row + keyset-cursor + WHERE-guard as the three-part resumable/idempotent/throttled backfill shape — reusable by any future one-time historical recompute in this codebase"

requirements-completed: [RISK-07]

# Metrics
duration: 40min
completed: 2026-08-11
status: complete
---

# Phase 34 Plan 01: Resumable Historical Risk-Exposure Backfill (LEAD TRACER) Summary

**Durable per-tenant `RiskExposureBackfillJob` + chunked keyset-resumable bulk `UPDATE...FROM` backfill of `Vulnerability.risk_exposure_score`, dispatched via `asyncio.create_task` every scheduler tick with no in-memory gate — proven idempotent/resumable/throttled/per-tenant-isolated by a 9-test fixture suite including kill-mid-chunk and simulated-process-restart resume.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-11T17:52:11+03:00 (RED commit)
- **Completed:** 2026-08-11T18:32:32+03:00 (GREEN commit)
- **Tasks:** 3 completed (RED, migration+model, service+scheduler wire)
- **Files modified:** 6 (3 created, 3 modified) + 1 deferred-items log

## Accomplishments

- Migration 044 lands the FULL Phase-34 schema spine in one additive migration: the `risk_exposure_backfill_jobs` table plus all 3 Tenant columns Plans 02/03/04 will read (`cutover_risk_exposure_scoring`, `risk_cutover_threshold_ack_at`, `risk_cutover_threshold_ack_diff_hash`) — no `op.execute` row work, no blocking data migration.
- `risk_backfill_service.py` implements the full claim → keyset-select → score (`score_finding` reused verbatim, zero second scoring implementation) → bulk `UPDATE...FROM (VALUES ...)` → cursor/counter advance cycle, all inside ONE transaction per chunk.
- `_dispatch_risk_exposure_backfill` wired into `_scheduler_loop` via `asyncio.create_task`, mirroring `_dispatch_ai_batch_prewarm`'s non-blocking shape, explicitly NOT `_dispatch_enrichment_refresh`'s inline-await/lock shape.
- 9/9 RISK-07 fixture tests green: chunk correctness (scores match `score_finding` byte-for-byte), idempotent re-run, chunk-size throttle bound (2+2+1 over 5 rows), kill-mid-chunk-and-resume with no double-counted `rows_migrated`, simulated-process-restart resume via a genuinely fresh `async_session_factory()` session, per-tenant failure isolation (tenant B's forced failure never touches tenant A's progress), a scaled multi-chunk load fixture (105 rows / chunk_size 20 / 6 passes), and dispatcher non-blocking + failure-swallowing.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — RISK-07 fixture suite** - `f2db2ab` (test)
2. **Task 2: GREEN part 1 — migration 044 + model + Tenant columns** - `05bdf84` (feat)
3. **Task 3: GREEN part 2 — risk_backfill_service.py + scheduler wire** - `23efe96` (feat)

_No REFACTOR commit needed — the implementation didn't require post-GREEN cleanup beyond what was fixed inline during GREEN (see Deviations)._

## Files Created/Modified

- `backend/alembic/versions/044_add_risk_backfill_job.py` - New table + 3 Tenant columns, purely additive, no data migration
- `backend/app/vulnerabilities/models.py` - `RiskExposureBackfillJob` model (appended after `CisaKev`, domain-file convention)
- `backend/app/tenants/models.py` - 3 new columns + comment documenting the "real branch, not inert stub" distinction from `exposure_hard_cap_enabled`
- `backend/app/vulnerabilities/risk_backfill_service.py` - `enqueue_backfill_job`, `process_backfill_chunk`, `dispatch_backfill_chunks`
- `backend/app/connectors/scheduler.py` - `_dispatch_risk_exposure_backfill` + call site in `_scheduler_loop`
- `backend/tests/test_risk_recompute.py` - the 9-test RISK-07 fixture suite
- `.planning/phases/34-historical-recompute-consumer-cutover/deferred-items.md` - pre-existing (non-Phase-34) test-isolation hang, logged not fixed (out of scope)

## Decisions Made

1. **Exact bulk `UPDATE...FROM (VALUES ...)` bind syntax** — verified live against this project's installed SQLAlchemy 2.0.50 + asyncpg (34-RESEARCH.md flagged the shape as `[ASSUMED]`): every column of every VALUES row needs its own explicit `CAST(:param AS type)` (`uuid`, `int`, `jsonb`, `varchar`). Without per-row casts, asyncpg/Postgres cannot infer a single consistent column type across the parameterized VALUES list and either raises `UndefinedFunctionError` (uuid = text) or `DatatypeMismatchError` (column is integer but expression is text). Reproduced and fixed via a standalone throwaway-temp-table script before writing the real implementation.
2. **Pitfall 5 resolved as option (a):** steps 3 (score) + 4 (bulk UPDATE) + 5 (cursor/counter advance) share ONE transaction with a single `db.commit()` at the end. A crash anywhere before that commit rolls the whole chunk back atomically — `rows_migrated` can never be double-counted, and the WHERE-guard naturally re-selects the identical not-yet-migrated rows on the next attempt.
3. **Claim-row heartbeat clear-on-success (found during GREEN, not in the original interfaces spec):** the plan's interfaces block showed the claim UPDATE setting `last_heartbeat_at=now` and didn't specify clearing it afterward. Running the fixture suite exposed that leaving heartbeat at "now" after a successful commit would make the 5-minute staleness WHERE-guard block the very NEXT scheduler tick (60 seconds later) from reclaiming the same tenant's job — since 60s < 5min, "one chunk per tenant per tick" would silently degrade to "one chunk per tenant per 5 minutes." Fix: clear `last_heartbeat_at` to `NULL` on every successful commit (both the "processed a chunk" and "marked completed" paths). The staleness WHERE-guard remains in place exactly as specified for defense-in-depth against a genuinely abandoned/never-committed claim; it simply never fires in the normal successful-tick-after-tick path.
4. **Dispatcher shape:** `_dispatch_risk_exposure_backfill` itself does `asyncio.create_task` on a one-shot multi-tenant sweep (mirrors `_dispatch_ai_batch_prewarm`/`_dispatch_ai_batch_poll`'s internal-create_task idiom); the `_scheduler_loop` call site is a plain `await _dispatch_risk_exposure_backfill()`. This matches the established `from app.connectors import scheduler as scheduler_module; await scheduler_module._dispatch_...()` direct-await test convention and is what `test_dispatcher_is_non_blocking`/`test_dispatcher_swallows_failure` assert against.
5. **`db.expire_all()` after the raw bulk UPDATE's commit** — the bulk `UPDATE...FROM` is raw SQL bypassing the ORM entirely; since `async_session_factory` sets `expire_on_commit=False`, any `Vulnerability` object already loaded into the session's identity map (including the very rows just scored) would otherwise keep serving stale cached attribute values on a subsequent query within the same session.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Heartbeat-staleness gate would block the next scheduler tick's reclaim**
- **Found during:** Task 3, running `test_chunk_processes_correct_rows` (a following empty-select pass never claimed because the just-set heartbeat wasn't stale yet)
- **Issue:** The claim UPDATE's WHERE-guard (`heartbeat IS NULL OR heartbeat < now - 5min`) would leave a successfully-committed chunk's heartbeat at "now," blocking the very next call/tick from reclaiming for up to 5 minutes — a correctness bug for the "one chunk per tenant per tick" throttle design, not just a test artifact (production ticks are 60s apart, far shorter than the 5-min window).
- **Fix:** Clear `last_heartbeat_at` to `NULL` on every successful commit (both the mid-chunk and completed paths), documented inline in `risk_backfill_service.py`.
- **Files modified:** `backend/app/vulnerabilities/risk_backfill_service.py`
- **Verification:** All 9 fixture tests green, including back-to-back sequential `process_backfill_chunk` calls across `test_chunk_processes_correct_rows`, `test_chunk_size_bounds_each_pass`, `test_large_tenant_backfill_throughput`.
- **Committed in:** `23efe96` (Task 3 commit)

**2. [Rule 1 - Bug] Identity-map staleness after the raw bulk UPDATE**
- **Found during:** Task 3, `test_chunk_processes_correct_rows` initially failed asserting `risk_exposure_score is not None` on freshly-persisted rows
- **Issue:** The bulk `UPDATE...FROM` is raw SQL, bypassing the ORM; `expire_on_commit=False` (app/db/session.py) meant previously-loaded `Vulnerability` instances in the session's identity map kept serving cached `None` scores after the commit.
- **Fix:** `db.expire_all()` immediately after the bulk-update commit inside `process_backfill_chunk`.
- **Files modified:** `backend/app/vulnerabilities/risk_backfill_service.py` (implementation); `backend/tests/test_risk_recompute.py` (one test needed to capture `Asset` attribute values before the call, since `expire_all()` also expires the test's own loaded `Asset` reference — expected, documented inline).
- **Verification:** All 9 fixture tests green.
- **Committed in:** `23efe96` (Task 3 commit)

**3. [Rule 3 - Blocking] mypy-baseline flagged 3 new `type-arg` violations + 1 new `operator` violation in the new file**
- **Found during:** Task 3, running the project's `mypy | mypy-baseline filter --allow-unsynced` CI gate against the new `risk_backfill_service.py`
- **Issue:** Bare `-> dict:` return-type annotations (matching a pervasive pre-existing codebase-wide style) are flagged as NEW violations by `mypy-baseline` for a brand-new file, even though hundreds of pre-existing occurrences elsewhere are baselined.
- **Fix:** Added proper generics (`dict[str, object]`, `dict[str, int]`, `list[tuple[uuid.UUID, int, list[dict[str, object]], str]]`) and a `typing.cast(int, ...)` at the one call site that needed a narrowed type for a comparison.
- **Files modified:** `backend/app/vulnerabilities/risk_backfill_service.py`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` reports 0 new violations (626 pre-existing, unchanged); `ruff check`/`ruff format --check` clean.
- **Committed in:** `23efe96` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs found during GREEN, 1 Rule 3 blocking lint gate)
**Impact on plan:** All 3 were necessary for correctness (heartbeat gate, identity-map staleness) or to pass the project's existing CI type-check gate. No scope creep — no files touched beyond what the plan named.

## Issues Encountered

- **Pre-existing test-isolation hang (NOT a Phase 34 regression):** running the plan's specified regression command (`pytest tests/test_risk_exposure_service.py tests/test_scheduler_ai_batch.py tests/test_scheduler_enrichment_refresh.py`) hung indefinitely. Root-caused to `test_risk_exposure_service.py::test_get_vulnerability_returns_risk_fields` being the only test in that file using the `client` fixture, which runs the FastAPI app's real `lifespan()` — which calls `start_scheduler()` for real. Because `asyncio_default_test_loop_scope=session`, the resulting background `_scheduler_loop()` task and its module-level globals (`_last_enrichment_refresh`, `_enrichment_refresh_lock`) persist for the rest of the pytest session, poisoning `test_scheduler_enrichment_refresh.py`'s own gate-state assumptions and (plausibly) hanging on a real outbound HTTP call inside `refresh_enrichment_reference_data` that this sandboxed environment cannot complete.
  - **Confirmed NOT caused by this plan's changes:** reverted `scheduler.py` to its pre-Plan-01 committed state and reproduced the identical hang with zero Phase 34 code present.
  - **Confirmed no regression:** each of the 3 files passes cleanly in total isolation (12 + 7 + 8 = 27 passed) and the `test_scheduler_ai_batch.py` + `test_scheduler_enrichment_refresh.py` 2-file combination also passes together (15 passed) — the hang is specific to `test_scheduler_enrichment_refresh.py` sharing a session with any test that boots the real app lifespan.
  - Logged in `.planning/phases/34-historical-recompute-consumer-cutover/deferred-items.md` per the scope-boundary protocol (out of scope for this plan's files) rather than fixed inline.

## User Setup Required

None - no external service configuration required. The migration is purely additive; no manual DB steps needed beyond the normal `alembic upgrade head` already exercised in CI/dev workflows.

## Next Phase Readiness

- The full Phase-34 schema spine (job table + cutover flag + 2 RISK-09 ack columns) is landed for Plan 02 (flag read at `sort="triage"` / `get_top_findings_for_ai_batch`), Plan 03 (ack columns + `RiskExposureBackfillJob.status == "completed"` gate on the flag-flip endpoint), and Plan 04 (flag read for the boundary-guard dual-write) to READ — none of them need their own migration.
- `chunk_size` used in fixtures: default 500 (production), scaled to 2/20 in specific fixtures for throttle-bound and load-test proofs. Load-fixture row count: 105 rows, chunk_size 20, 6 passes observed (5 full + 1 partial + a following empty completion pass in the same loop-until-done pattern) — scaled down from 34-RESEARCH.md's own 2500-row/500-chunk-size example to keep this file's runtime bounded (<2s observed, well under the 30s target).
- Claim-row heartbeat interval used: 5 minutes stale-threshold (as specified), cleared to `NULL` on every successful commit (see Decisions #3) so it never blocks normal tick-to-tick progress.
- Dispatcher shape: `_dispatch_risk_exposure_backfill` internally `asyncio.create_task`s a one-shot sweep across ALL active tenants (not a separate create_task per tenant) — per-tenant isolation is achieved via `dispatch_backfill_chunks`'s own per-tenant try/except, not via separate tasks.
- No blockers for Plan 02/03/04.

---
*Phase: 34-historical-recompute-consumer-cutover*
*Completed: 2026-08-11*

## Self-Check: PASSED

All created files verified present on disk; all 3 task commit hashes (`f2db2ab`, `05bdf84`, `23efe96`) verified present in `git log`.
