---
phase: 23-ingestion-reliability-precursor
plan: 07
subsystem: api
tags: [fastapi, sqlalchemy, structlog, pytest]

# Dependency graph
requires: ["23-06 (connector_configs.last_error + consecutive_failure_count columns)"]
provides:
  - "sync.py _sanitize_error() — dict-wrap Phase-7 _redact_value reuse + Bearer/Basic/api-key pattern scrub + 500-char truncation"
  - "consecutive_failure_count increment (exception path + auth-fail early-return path) / reset-to-0 on SUCCESS in run_sync"
  - "last_error redacted+truncated capture on FAILED, cleared on SUCCESS, in both the direct and scheduler-triggered sync paths"
affects: [23-09-connector-card-health-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Secret redaction on a bare exception string composes two layers: Phase-7 app.logging._redact_value (key-based, via a dict-wrap) + a lightweight regex scrub (Bearer/Basic/api-key-shaped substrings) — never a second standalone redactor"
    - "Truncation always happens AFTER redaction so a secret can't survive by falling past the cap"
    - "scheduler.py has no independent write-back logic — it delegates straight to sync.run_sync, so counter/last_error semantics are proven with a single implementation, confirmed by a scheduler-driven test rather than duplicated code"

key-files:
  created:
    - backend/tests/test_connector_health.py
  modified:
    - backend/app/connectors/sync.py

key-decisions:
  - "Truncation cap set to 500 chars (Claude's discretion per plan; SyncLog.error_message keeps its pre-existing 2000-char cap unchanged — only the persisted connector_config.last_error uses the smaller, redacted cap)"
  - "Fixed a pre-existing gap (Rule 1 bug) in the auth-failure early-return path: it recorded FAILED on the SyncLog but never updated connector_config.last_sync_status, leaving the connector's health signal stale even though the sync had failed"
  - "logger.error(\"sync_error\", error=...) now passes the sanitized string instead of a raw str(exc) — closes T-23-20: the structlog redact_sensitive_keys processor only scrubs by dict key name, so a bare string value would have bypassed it entirely"
  - "Left the 'Unknown connector type' branch (a defensive, believed-unreachable path — connector types are validated at creation) unmodified — out of the plan's three explicitly enumerated outcome paths (auth-fail, success, except), avoiding scope creep on an unreachable edge case"
  - "Test connector type 'FAKE' registered into sync.CONNECTOR_CLASSES via monkeypatch.setitem for test duration only — connector_type is a plain string column with no DB-level enum constraint, so this is safe and avoids any real scanner HTTP layer"

requirements-completed: [REL-06]

# Metrics
duration: 25min
completed: 2026-07-27
---

# Phase 23 Plan 07: Connector Health Runtime Wiring Summary

**`consecutive_failure_count` now increments on every failed sync (exception or auth-failure) and resets on success, with `last_error` captured through a composed redaction (Phase-7 key-based `_redact_value` + a Bearer/Basic/api-key pattern scrub) and truncated to 500 chars — proven identical on both the direct and scheduler-triggered sync paths.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-27 (session start, after reading plan/context files)
- **Completed:** 2026-07-27
- **Tasks:** 2 completed
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments

- Added `_sanitize_error(exc, cap=500)` to `sync.py`: wraps the exception in `{"exception_type": ..., "message": str(exc)}`, passes it through the reused Phase-7 `app.logging._redact_value` (key-based redaction), then applies a regex scrub (`Bearer\s+[\w.\-]+|Basic\s+[\w+/=]+|[A-Za-z0-9_\-]{32,}`) before truncating — composes both layers per the 23-RESEARCH Pitfall 4 / Open Question 7 correction, introduces no parallel redactor.
- All three sync outcome paths in `run_sync` now update the health columns:
  - **Success write-back:** `consecutive_failure_count = 0`, `last_error = None`.
  - **`except Exception` block:** `consecutive_failure_count += 1`, `last_error = _sanitize_error(e)`; `logger.error("sync_error", ...)` now logs the sanitized string (closes T-23-20).
  - **Auth-failure early return:** `consecutive_failure_count += 1`, `last_error = "Authentication failed"`, and (bug fix) `connector_config.last_sync_status = "FAILED"` — this path previously never touched `connector_config` at all despite the `SyncLog` recording FAILED.
- Confirmed `scheduler.py`'s `_run_single_sync` delegates directly to `sync.run_sync` with no independent write-back logic — no source change needed there; parity proven with a dedicated test pair instead.
- `backend/tests/test_connector_health.py` (8 tests, all green): success reset, failure increment (fresh + from a prior nonzero value), auth-fail-path increment, Bearer-token redaction (secret not present in `last_error`), truncation-after-redaction, Basic-auth/long-token scrub, and two scheduler-path parity tests (failure + success) that drive `scheduler._run_single_sync` directly and assert identical outcomes to the direct path.

## Task Commits

Each task was committed atomically:

1. **Task 1: Failure-counter increment/reset + redacted+truncated last_error capture in sync.py (D-18, D-19)** - `68ccf01` (feat)
2. **Task 2: Scheduler path parity for counter/last_error (D-18)** - `1d08b65` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `backend/app/connectors/sync.py` - `_sanitize_error()` helper + `_SECRET_PATTERN`; success/except/auth-fail paths populate `consecutive_failure_count`/`last_error`; `logger.error("sync_error", ...)` now logs the sanitized string
- `backend/tests/test_connector_health.py` - new file; 8 tests covering increment/reset/auth-fail/redaction/truncation/scheduler-parity, driven by an in-memory `_FakeConnector` registered into `CONNECTOR_CLASSES` via monkeypatch

## Decisions Made

- 500-char truncation cap (plan left this to discretion) — chosen to keep the persisted `last_error` short enough for a UI inline display (Plan 09) while still being diagnostically useful; `SyncLog.error_message`'s existing 2000-char cap is untouched (different record, different purpose).
- Truncation happens strictly after redaction, so a secret positioned past the cap can't "hide" — the whole message is scrubbed first, then cut.
- Did not touch the "Unknown connector type" defensive branch (believed unreachable in production; connector types are validated at creation) — out of the plan's three explicitly named outcome paths, avoiding scope creep.
- Test double (`_FakeConnector`) uses class-level attributes (not `__init__` args) because `sync.py`'s harness instantiates connectors with `connector_cls()` — no constructor arguments are passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Auth-failure early-return path never updated `connector_config.last_sync_status`**
- **Found during:** Task 1, reading the three outcome paths before implementing
- **Issue:** The pre-existing `if not authed:` branch set `log.status = "FAILED"` on the `SyncLog` record but never touched `connector_config` at all — so a connector stuck failing auth would show a stale `last_sync_status` (e.g. still `"SUCCESS"` from a prior sync) even though every subsequent sync attempt was failing.
- **Fix:** Added `connector_config.last_sync_status = "FAILED"` alongside the new counter/last_error assignments in that branch.
- **Files modified:** backend/app/connectors/sync.py
- **Commit:** `68ccf01`

**2. [Rule 2 - Missing critical functionality] `logger.error("sync_error", error=str(e))` bypassed the structlog redaction pipeline (T-23-20)**
- **Found during:** Task 1, reviewing the threat model's T-23-20 disposition
- **Issue:** `app.logging.redact_sensitive_keys` redacts by dict key name; a bare string passed as a value (`str(e)`) is not itself a dict, so `_redact_value` returns it unchanged — meaning a secret embedded in an exception message would reach the log stream unredacted even though the same secret is now scrubbed before persistence.
- **Fix:** Changed the log call to `logger.error("sync_error", error=_sanitize_error(e))`, reusing the same sanitized string used for `last_error`.
- **Files modified:** backend/app/connectors/sync.py
- **Commit:** `68ccf01`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing-mitigation) — both directly required by the plan's own threat model (T-23-20) and must-haves ("on any failed sync ... last_error is set"), no scope creep beyond the three outcome paths the plan named.
**Impact on plan:** Both fixes are within the exact files/paths the plan's `<action>` block already directed changes to; no new files or architectural surface introduced.

## Issues Encountered

None blocking. `mypy` on `sync.py`/`scheduler.py` reports 264 pre-existing baseline errors both before and after this change (confirmed via `git stash` A/B comparison) — no regression introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 09 (connector-card health UI) can now render real `last_error`/`consecutive_failure_count` data — both fields are populated on every sync outcome, on both the direct (`/connectors/{id}/sync`) and scheduler-triggered paths.
- No production behavior changed for existing connectors beyond the two bug fixes above (auth-fail path health-signal staleness; unredacted secret in structured logs) — this plan does not add new user-visible surface.

---
*Phase: 23-ingestion-reliability-precursor*
*Completed: 2026-07-27*

## Self-Check: PASSED

`backend/app/connectors/sync.py` and `backend/tests/test_connector_health.py` both found on disk; commits `68ccf01` and `1d08b65` both found in `git log`.
