---
phase: 37-two-way-ticket-sync-remediation-verification
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, postgres, remediation, scanner-sync, mttr]

# Dependency graph
requires:
  - phase: 37-two-way-ticket-sync-remediation-verification
    provides: "Vulnerability.clean_scan_streak column (migration 048) + mark_vulnerability_remediated(verified_by=...) helper (Plan 01)"
provides:
  - "reopen_vulnerability(db, vuln) soft-close resurrection helper in vulnerabilities/service.py"
  - "_upsert_vulnerability existing-row reopen branch: recurrence-after-auto-close resurrects the same row"
affects: [37-03, phase-38-remediation-campaigns, phase-42-risk-trend-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sibling resurrection helper mirrors mark_vulnerability_remediated's transaction-boundary + direct-AuditLog conventions exactly (no flush/commit, tenant_id sourced from the ORM row, system:* user_email)"
    - "Reopen hooked into the existing dedup-identity-key branch (uq_vuln_dedup) rather than inventing new recurrence-detection logic"

key-files:
  created:
    - backend/tests/test_finding_reopen.py
  modified:
    - backend/app/vulnerabilities/service.py
    - backend/app/connectors/sync.py

key-decisions:
  - "reopen_vulnerability is a no-op (returns False, no audit row) on any non-REMEDIATED row -- callers (the upsert existing-branch) can call it unconditionally on every recurrence without a separate status check, matching the plan's idempotent-guard requirement"
  - "Local import of reopen_vulnerability inside _upsert_vulnerability's existing-row branch (matching the plan's specified daily_sync.py-style local-import convention), even though sync.py already has a module-level import of mark_vulnerability_remediated -- followed the plan's explicit instruction rather than the file's own pre-existing convention"
  - "first_detected_at is never touched by reopen -- MTTR lineage (RemediationEvent history) survives a close -> recur -> reopen -> re-close cycle with each RemediationEvent's own frozen tier/duration intact"

patterns-established:
  - "Recurrence detection needs no new logic: the existing uq_vuln_dedup(tenant_id, cve_id, asset_id, source) constraint already routes a re-detected finding to the same row in _upsert_vulnerability's existing branch -- the reopen hook is purely 'if that row is REMEDIATED, resurrect it'"

requirements-completed: [SYNC-03]

coverage:
  - id: D1
    description: "reopen_vulnerability on a REMEDIATED row sets OPEN/remediated_at=None/clean_scan_streak=0, preserves first_detected_at, and audits system:rescan-reopen"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_finding_reopen.py#test_reopen_helper_resurrects_remediated_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "The prior RemediationEvent row survives reopen -- MTTR history is never deleted"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_finding_reopen.py#test_reopen_helper_preserves_prior_remediation_event"
        status: pass
    human_judgment: false
  - id: D3
    description: "reopen_vulnerability is a no-op on a non-REMEDIATED row (idempotent guard, no audit row written)"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_finding_reopen.py#test_reopen_helper_noop_on_non_remediated_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "A scan re-detecting a REMEDIATED finding through _upsert_vulnerability reopens the SAME row (no duplicate finding, no duplicate ticket), preserving first_detected_at and the linked Ticket FK"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_finding_reopen.py#test_redetection_reopens_same_row_no_duplicate"
        status: pass
    human_judgment: false
  - id: D5
    description: "Re-detecting an already-OPEN row (never closed) does not trigger the reopen branch or write a reopen audit row -- regression guard"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_finding_reopen.py#test_redetection_of_open_row_does_not_reopen_again"
        status: pass
      - kind: unit
        ref: "backend/tests/test_github_sync.py (8/8, regression guard on the upsert path)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_rescan_autoclose.py (7/7, regression guard on SYNC-02)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_mttr.py (13/13, regression guard)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_sla_tier_service.py (29/29, regression guard)"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-08-15
status: complete
---

# Phase 37 Plan 02: Reopen-on-Recurrence (SYNC-03) Summary

**A scan re-detecting a rescan-verified-closed finding now resurrects the SAME `Vulnerability` row via a new `reopen_vulnerability` helper wired into `_upsert_vulnerability`'s existing-row branch — status flips back to OPEN, `clean_scan_streak` resets, `first_detected_at`/MTTR history and the linked Jira/Asana/GitHub `Ticket` FK are preserved untouched, and every reopen is audited as `system:rescan-reopen`.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-08-15 (session start)
- **Completed:** 2026-08-15
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `reopen_vulnerability(db, vuln)` added to `vulnerabilities/service.py`: on a REMEDIATED row it sets `status="OPEN"`, `remediated_at=None`, `clean_scan_streak=0`, leaves `first_detected_at` untouched, and writes a direct tenant-scoped `AuditLog(user_email="system:rescan-reopen", action="vuln.reopen_recurrence")`. No-op (returns `False`, no audit row) on any other status — safe to call unconditionally.
- `_upsert_vulnerability`'s existing-row branch (`connectors/sync.py`) now calls `reopen_vulnerability` when the re-detected row's `status == "REMEDIATED"`, immediately after the existing field-refresh block and before `return False` — the dedup identity key `uq_vuln_dedup(tenant_id, cve_id, asset_id, source)` already routes recurrence to the same row, so no new dedup logic was needed.
- Historical `RemediationEvent` rows are never deleted on reopen — a subsequent 2-clean-scan re-close will write a second event, and both remain queryable for the full close→recur→reopen→re-close timeline.
- The pre-existing `Ticket.vulnerability_id` (singular FK) automatically keeps pointing at the reopened row — verified end-to-end with a seeded Jira ticket + real re-detection through `_upsert_vulnerability`.

## Task Commits

Each task was committed atomically:

1. **Task 1: reopen_vulnerability soft-close resurrection helper (SYNC-03)** - `18619ec` (feat, TDD)
2. **Task 2: wire reopen into _upsert_vulnerability recurrence branch (SYNC-03)** - `865d5fc` (feat, TDD)

_Note: as in Plan 01, both tasks' RED (test-first) and GREEN (implementation) steps were run and verified in the same working session before each task's commit, rather than producing a separate test-only commit — Task 1's tests (`test_reopen_helper_*`) were run against the helper before commit to confirm GREEN; Task 2's upsert-integration tests were confirmed RED against Task-1-only HEAD (asserting `status == "REMEDIATED"` after re-detection, i.e. the un-wired state) before the `sync.py` wiring turned them GREEN._

## Files Created/Modified
- `backend/app/vulnerabilities/service.py` - `reopen_vulnerability(db, vuln)` helper + `AuditLog` import
- `backend/app/connectors/sync.py` - `_upsert_vulnerability` existing-row branch now calls `reopen_vulnerability` on a REMEDIATED row
- `backend/tests/test_finding_reopen.py` - 5 new tests: 3 for the helper (resurrection, MTTR-event preservation, no-op guard), 2 for the wired upsert path (same-row reopen + ticket relink; OPEN-row regression guard)

## Decisions Made
- **Idempotent no-op guard, not a status precondition on the caller:** `reopen_vulnerability` checks `vuln.status != "REMEDIATED"` itself and returns `False` silently — the upsert branch calls it unconditionally inside `if existing.status == "REMEDIATED":`, but the helper's own guard means it's also safe for any future caller to invoke without checking status first.
- **Local import inside the upsert branch:** followed the plan's explicit instruction to import `reopen_vulnerability` locally (matching `daily_sync.py`'s convention) even though `sync.py` already has a module-level import of `mark_vulnerability_remediated` — a minor internal inconsistency within `sync.py` itself, but it's what the plan's `<action>` literally specified and doesn't affect behavior or testability.
- **No proactive backfill of previously-prematurely-closed findings** (resolved Q3 from 37-CONTEXT.md): any such row that recurs will now be naturally reopened by this plan's branch; no separate migration/backfill task was needed or added.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<action>` steps were followed verbatim.

## Issues Encountered
- **Pre-existing mypy-baseline drift (not fixed, out of scope):** `mypy app/ | mypy-baseline filter --allow-unsynced` reports "3 new violations" even on the Task-1-only committed state with zero Task 2 changes present (reproduced via `git stash` + rerun against the exact same HEAD Task 2 committed onto) — an identical note-line/version-sensitivity artifact of the pinned `mypy==2.1.0`/`mypy-baseline==0.7.4` tooling already documented in Plan 01's Summary and STATE.md's Phase 29 entry, not a real new type error introduced by this plan. `ruff check` on both touched files (`sync.py`, `service.py`) is clean.
- **`backend/uv.lock` untracked/ungitignored:** same pre-existing repo gap noted in Plan 01, already logged to `.planning/phases/37-two-way-ticket-sync-remediation-verification/deferred-items.md` — left untouched, not part of this plan's file scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (removing the remaining ticket-done→REMEDIATED writes from `daily_sync.py`, D-03) can now build on a fully closed close→recur→reopen loop: `mark_vulnerability_remediated` (Plan 01), the SUCCESS-branch absent-sweep (Plan 01), and `reopen_vulnerability` (this plan) together prove SYNC-02 and SYNC-03 end to end.
- No blockers. All Phase 37 test files (`test_rescan_autoclose.py`, `test_finding_reopen.py`, `test_github_sync.py`) plus the shared-helper regression guards (`test_mttr.py`, `test_sla_tier_service.py`) are green.

---
*Phase: 37-two-way-ticket-sync-remediation-verification*
*Completed: 2026-08-15*

## Self-Check: PASSED

All referenced files exist on disk and both commit hashes (18619ec, 865d5fc) are present in git log.
