---
phase: 37-two-way-ticket-sync-remediation-verification
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, alembic, postgres, remediation, scanner-sync]

# Dependency graph
requires:
  - phase: 36-remediation-sla-engine-escalation
    provides: mark_vulnerability_remediated single-helper discipline + RemediationEvent (MTTR) table
provides:
  - "Vulnerability.clean_scan_streak column (migration 048)"
  - "mark_vulnerability_remediated(db, vuln, verified_by=...) extended helper"
  - "run_sync SUCCESS-branch absent-sweep: streak bookkeeping + rescan-verified auto-close"
affects: [37-02, 37-03, phase-38-remediation-campaigns, phase-42-risk-trend-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SUCCESS-branch-only sweep gating (D-02): a mutating consequence (streak advance / auto-close) is placed strictly inside the code path that already proved success, never in a shared post-processing step reachable from FAILED"
    - "Single-helper REMEDIATED discipline extended via an additive optional kwarg (verified_by) rather than a sibling status-writer"

key-files:
  created:
    - backend/alembic/versions/048_add_clean_scan_streak.py
    - backend/tests/test_rescan_autoclose.py
  modified:
    - backend/app/vulnerabilities/models.py
    - backend/app/vulnerabilities/service.py
    - backend/app/connectors/sync.py

key-decisions:
  - "verified_by kwarg is log-only provenance, never changes remediated_at (Q1: rescan is the truth per D-03, so the honest MTTR clock is the 2nd-clean-scan moment)"
  - "mark_vulnerability_remediated now unconditionally resets clean_scan_streak=0 on every REMEDIATED transition (including the pre-existing no-kwarg callers), so a remediated row never carries a stale streak into a later SYNC-03 reopen"
  - "Absent-sweep lives in a new _run_rescan_verify_sweep() helper called once, inline, right after compute_finding_risk_scores and before log.status='SUCCESS' is set — never reachable from the except/auth-failure branches"

patterns-established:
  - "New Vulnerability.clean_scan_streak mirrors ConnectorConfig.consecutive_failure_count exactly (Integer, server_default '0') — establishes the shape Plan 02/03 extend for reopen-on-recurrence"

requirements-completed: [SYNC-02]

coverage:
  - id: D1
    description: "A finding absent from 2 consecutive SUCCESSful scanner syncs of its source auto-closes as rescan-verified, with a RemediationEvent and a system:rescan-verify AuditLog row"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_two_clean_success_syncs_auto_close_via_helper_with_audit"
        status: pass
    human_judgment: false
  - id: D2
    description: "1 clean sync does not close (streak==1)"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_one_clean_sync_does_not_close"
        status: pass
    human_judgment: false
  - id: D3
    description: "A FAILED/partial scanner sync never advances any streak and never closes anything"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_failed_sync_never_advances_streak_or_closes"
        status: pass
    human_judgment: false
  - id: D4
    description: "A re-detected finding resets its clean_scan_streak to 0"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_redetected_finding_resets_streak"
        status: pass
    human_judgment: false
  - id: D5
    description: "mark_vulnerability_remediated extended with verified_by kwarg; existing no-kwarg callers behave exactly as before (regression)"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_helper_regression_no_verified_by_unchanged"
        status: pass
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_helper_verified_by_rescan_still_produces_event_and_mttr"
        status: pass
      - kind: unit
        ref: "backend/tests/test_mttr.py (13/13, regression guard)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_sla_tier_service.py (29/29, regression guard)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Migration 048 chains cleanly off 047 and clean_scan_streak defaults 0 for every pre-existing/new row"
    requirement: "SYNC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py#test_migration_048_clean_scan_streak_defaults_zero"
        status: pass
      - kind: other
        ref: "alembic upgrade head / alembic downgrade -1 round-trip, verified manually against live Postgres"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-15
status: complete
---

# Phase 37 Plan 01: Rescan-Verified Auto-Close Tracer Slice Summary

**Migration 048 adds `Vulnerability.clean_scan_streak`; `mark_vulnerability_remediated` gains an optional `verified_by` kwarg; `run_sync`'s SUCCESS branch now sweeps for absent findings, advances/resets the streak, and auto-closes at streak>=2 via the single helper plus a `system:rescan-verify` AuditLog row — proving SYNC-02's "verified by rescan, not by a human closing a ticket" end to end.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-08-15 (session start)
- **Completed:** 2026-08-15T08:47:27Z
- **Tasks:** 2 completed
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- Migration `048_add_clean_scan_streak` chained off `047_add_remediation_events`, adding `Vulnerability.clean_scan_streak` (Integer, NOT NULL, `server_default "0"`) — mirrors `ConnectorConfig.consecutive_failure_count` exactly.
- `mark_vulnerability_remediated` extended with an optional `verified_by` kwarg (structured-log-only provenance, never alters `remediated_at` per resolved Q1) and now always resets `clean_scan_streak=0` on every REMEDIATED transition — zero behavior change for the ~7 pre-existing no-kwarg call sites.
- `run_sync`'s SUCCESS branch (only) now runs a new `_run_rescan_verify_sweep()`: absent OPEN/IN_PROGRESS findings of the connector's own `(tenant_id, source)` get `clean_scan_streak += 1`; at `>= 2` the finding auto-closes via `mark_vulnerability_remediated(verified_by="rescan")` plus a direct tenant-scoped `AuditLog(user_email="system:rescan-verify", action="vuln.rescan_verified_close")`; re-detected findings reset to 0 in one bulk `UPDATE`.
- FAILED/auth-failure branches of `run_sync` never reach the sweep — proven with a dedicated test driving a real 401 auth failure through the actual `CrowdStrikeConnector`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 048 + clean_scan_streak column + verified_by helper kwarg** - `473a203` (feat, TDD)
2. **Task 2: SUCCESS-branch absent-sweep + streak + rescan-verified auto-close (SYNC-02)** - `dd9b0bd` (feat, TDD)

_Note: both tasks were implemented and verified together with their tests (single RED→GREEN pass per task rather than a separate literal RED-only commit), matching the established Phase 25/26 route-level `tdd=true` precedent noted in prior STATE.md entries — the test file existed and was run to failure/success in the same working session before each task's commit._

## Files Created/Modified
- `backend/alembic/versions/048_add_clean_scan_streak.py` - New migration, chained off 047, adds `clean_scan_streak` column
- `backend/app/vulnerabilities/models.py` - `Vulnerability.clean_scan_streak: Mapped[int]` column
- `backend/app/vulnerabilities/service.py` - `mark_vulnerability_remediated(..., *, verified_by=None)`, structlog logger added, streak reset on every REMEDIATED write
- `backend/app/connectors/sync.py` - New `_run_rescan_verify_sweep()` helper, wired into `run_sync`'s SUCCESS branch; `AuditLog`/`update`/`mark_vulnerability_remediated` imports added
- `backend/tests/test_rescan_autoclose.py` - 7 new tests covering both tasks' `<behavior>` bullets

## Decisions Made
- **Q1 resolved as planned:** `verified_by` is log-only provenance; `remediated_at` stays the 2nd-clean-scan moment (D-03: rescan is truth), not a separate fix-moment timestamp.
- **Streak reset lives inside the single helper**, not the sweep caller — guarantees every REMEDIATED transition (rescan-verified or otherwise) leaves `clean_scan_streak` at 0, closing a latent SYNC-03 hazard (a reopened row inheriting a stale streak) before Plan 03 needs it.
- **`_run_rescan_verify_sweep` returns a close-count int**, surfaced in `SyncLog.details["rescan_verified_closed"]` for operator observability — additive, not required by any test, follows the existing `details` dict convention in the same function.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<action>` steps were followed verbatim; the only addition beyond the plan's literal text is the `rescan_verified_closed` count surfaced in `SyncLog.details` (additive observability, mirrors the existing `corr_stats`/`risk_stats`/`finding_risk_stats` keys already in that dict — not a deviation from any `<behavior>` or `<done>` criterion).

## Issues Encountered
- **Mock auth status code:** initial `httpx.MockTransport` handler returned `200` for the CrowdStrike OAuth2 token endpoint; the real `CrowdStrikeConnector.authenticate()` only accepts `201`. Fixed in the test fixture (test-file-only, zero production-code impact) before the first full run.
- **Pre-existing mypy-baseline drift (not fixed, out of scope):** `mypy app/ | mypy-baseline filter --allow-unsynced` reports "6 new violations" even on the Task-1-only committed state with zero Task 2 changes present (reproduced via `git stash` + `rm -rf .mypy_cache` diffing against unmodified HEAD, mirroring the identical drift pattern already documented in STATE.md's Phase 29 entry — a note-line/version-sensitivity artifact of the pinned `mypy==2.1.0`/`mypy-baseline==0.7.4` tooling, not a real new type error). Directly verified zero new errors in the three touched files (`sync.py`, `service.py`, `models.py`) by diffing each file's mypy output against its exact baseline entries — all match byte-for-byte. `ruff check` on all touched files is clean.
- **`backend/uv.lock` untracked/ungitignored:** pre-existing repo gap unrelated to this plan's file scope, logged to `.planning/phases/37-two-way-ticket-sync-remediation-verification/deferred-items.md`, not fixed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 02 (inbound ticket-status → workflow-state sync, SYNC-01) and Plan 03 (reopen-on-recurrence, SYNC-03) can now build directly on `clean_scan_streak` + the `verified_by`-extended helper without any further schema change.
- `_upsert_vulnerability`'s existing-row branch (the SYNC-03 reopen hook site) will need to reset `clean_scan_streak=0` itself on reopen for consistency with the reset-on-REMEDIATE guarantee this plan established — flagged for Plan 03, not a blocker for Plan 02.
- No blockers. Migration 048 is the current alembic head; upgrade/downgrade round-trip verified clean against the live dev Postgres.

---
*Phase: 37-two-way-ticket-sync-remediation-verification*
*Completed: 2026-08-15*

## Self-Check: PASSED

All referenced files exist on disk and all 3 commit hashes (473a203, dd9b0bd, 5f6b9a5) are present in git log.
