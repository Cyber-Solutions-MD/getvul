---
phase: 23-ingestion-reliability-precursor
plan: 10
subsystem: connectors
tags: [sync, structlog, security, redaction, pytest]

# Dependency graph
requires:
  - phase: 23-ingestion-reliability-precursor
    provides: "REL-06 secret-hygiene redaction pipeline (_sanitize_error, _SECRET_PATTERN) established in an earlier 23-XX plan for connector_config.last_error"
provides:
  - "SyncLog.error_message routed through the same _sanitize_error redaction as its sibling connector_config.last_error"
  - "Regression test proving the scheduler's background_sync_complete structured-log event is clean by construction"
affects: [23-VERIFICATION, 23-REVIEW, future ingestion-reliability gap-closure plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single sanitize-once-reuse-everywhere: the `sanitized = _sanitize_error(e)` binding computed once in the exception handler is reused for logger.error, log.error_message, AND connector_config.last_error — no second redactor call site."

key-files:
  created: []
  modified:
    - backend/app/connectors/sync.py
    - backend/tests/test_connector_health.py

key-decisions:
  - "Reused the existing `sanitized` binding for log.error_message instead of adding a second _sanitize_error() call, per the plan's explicit prohibition against a second call site."
  - "New regression test lives alongside test_scheduler_path_failure_parity in test_connector_health.py rather than a new file, matching the existing scheduler-path-parity test group and reusing its fixtures."

patterns-established: []

requirements-completed: [REL-06]

coverage:
  - id: D1
    description: "SyncLog.error_message is sanitized before persist (log.error_message = sanitized, not str(e)[:2000])"
    requirement: REL-06
    verification:
      - kind: unit
        ref: "backend/app/connectors/sync.py grep check: 'str(e)[:2000]' absent, 'log.error_message = sanitized' present"
        status: pass
      - kind: integration
        ref: "backend/tests/test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized"
        status: pass
    human_judgment: false
  - id: D2
    description: "background_sync_complete structured-log event carries only sanitized error text (no Bearer/secret substrings), proven via structlog.testing.capture_logs()"
    requirement: REL-06
    verification:
      - kind: integration
        ref: "backend/tests/test_connector_health.py::test_scheduler_path_error_message_and_log_are_sanitized"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-28
status: complete
---

# Phase 23 Plan 10: SyncLog.error_message Secret-Hygiene Gap Closure (CR-03/REL-06) Summary

**Closed the asymmetry where `SyncLog.error_message` persisted the raw `str(e)[:2000]` exception string while its sibling `connector_config.last_error` was already sanitized — now both fields, and the scheduler's `background_sync_complete` log line that echoes `error_message` verbatim, are redacted via the same `_sanitize_error()` call.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-28T05:44:18Z (per STATE.md context load)
- **Completed:** 2026-07-28T08:46:26+03:00
- **Tasks:** 2/2 completed
- **Files modified:** 2

## Accomplishments
- `backend/app/connectors/sync.py`'s exception handler now assigns `log.error_message = sanitized` (reusing the already-computed `_sanitize_error(e)` result), eliminating the last unsanitized path a secret-bearing upstream HTTP error body could take into persisted/logged data.
- Added `test_scheduler_path_error_message_and_log_are_sanitized`, a regression test that drives a `Bearer`-shaped secret through `scheduler._run_single_sync`, reloads the persisted `SyncLog` row, and asserts the secret is absent (and `[REDACTED]` present) in `error_message` — and also asserts the secret is absent from the captured `background_sync_complete` structured-log event via `structlog.testing.capture_logs()`.
- Verified the regression test is a live guard, not a tautology: temporarily reverting the Task 1 fix (restoring `log.error_message = str(e)[:2000]`) causes the new test to FAIL with the raw secret token visible in the assertion diff; re-applying the fix makes all 9 tests in the file pass again.

## Task Commits

Each task was committed atomically:

1. **Task 1: Sanitize log.error_message before persisting it on the SyncLog row** - `a352c5b` (fix)
2. **Task 2: Add scheduler-path regression test asserting the secret is absent from error_message AND the emitted log line** - `776eda6` (test)

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified
- `backend/app/connectors/sync.py` - One-line fix in the `run_sync` exception handler: `log.error_message = sanitized` replaces `log.error_message = str(e)[:2000]`. SUCCESS branch and `finally` block untouched.
- `backend/tests/test_connector_health.py` - Added `structlog.testing` and `SyncLog`/`select` imports; added `test_scheduler_path_error_message_and_log_are_sanitized` asserting both the persisted `SyncLog.error_message` and the captured `background_sync_complete` log event are free of the secret token and the literal `Bearer`, and that `[REDACTED]` is present (proving redaction, not mere truncation).

## Decisions Made
None beyond what's in `key-decisions` above — plan executed exactly as written, with the reused `sanitized` binding as explicitly directed by the plan (no second `_sanitize_error` call site introduced).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Backend test env vars (`ENCRYPTION_KEY`, `JWT_SECRET_KEY`) and the project's `.venv/bin/python` (not bare `python`/`python3`, which resolve to pyenv shims / homebrew python without pytest installed) were required per the backend pytest-env memory; running per-file (`tests/test_connector_health.py`, not the whole `tests/` directory) avoided the known false-failure mode.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Gap CR-03 (REL-06) is closed: no known path remains for a secret echoed in an upstream HTTP error body to reach `SyncLog.error_message`, the `sync_logs` table, or the `background_sync_complete` structured-log line.
- Deferred adjacent items (CR-02 duplicate `POST /sync-status` route, WR-01 `TicketRuleAction.provider` validation) remain explicitly out of scope for this closure and are documented in the plan's `<deferred_adjacent_items>` — routed to a follow-up ticketing-router backlog item, not silently dropped.
- Ready for plan 23-11 (CR-01 mobile provider gap closure) and the rest of Phase 23's gap-closure sequence.

## Self-Check: PASSED

- FOUND: backend/app/connectors/sync.py
- FOUND: backend/tests/test_connector_health.py
- FOUND: .planning/phases/23-ingestion-reliability-precursor/23-10-SUMMARY.md
- FOUND commit a352c5b (Task 1)
- FOUND commit 776eda6 (Task 2)

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-28*
