---
phase: 37-two-way-ticket-sync-remediation-verification
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, jira, asana, github, ticketing, remediation, scanner-sync]

# Dependency graph
requires:
  - phase: 37-two-way-ticket-sync-remediation-verification
    provides: "clean_scan_streak + mark_vulnerability_remediated(verified_by=...) (Plan 01); reopen_vulnerability soft-close resurrection (Plan 02)"
provides:
  - "map_ticket_status(provider, payload) — D-03-safe provider-status -> workflow-intent mapper (ticketing/service.py)"
  - "GitHubClient.reopen_issue — PATCH state=open, mirrors close_issue (SYNC-03 ticket-side reopen)"
  - "daily_sync.py D-03 split: ticket-done drives IN_PROGRESS + comment + audit, NEVER REMEDIATED; recurrence reopens the external ticket"
  - "SYNC-04: per-ticketing-connector last_sync_*/consecutive_failure_count/last_error resilience columns + bounded retry (_sync_with_retry) + SyncLog rows"
affects: [phase-38-remediation-campaigns, phase-39-exception-risk-acceptance, phase-40-alerting-digests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Workflow-intent mapping (in_progress/done_awaiting_rescan/open/unknown) as a whitelist function — never a bare done/not-done bool — so a caller structurally cannot mistake 'ticket says done' for 'close the finding' (D-03)"
    - "Stored Ticket.external_status doubles as the state-machine memory for a 3-way transition (fresh-done / recurrence / steady-state) via a per-provider 'was this already done last cycle' set-membership check, avoiding any new DB column"
    - "Bounded retry wrapper referenced by module-level function name (not a bound closure) so tests can monkeypatch the wrapped `_sync_*` function and still exercise the real retry/backoff path"
    - "Ticketing connector resilience columns (last_sync_at/last_sync_status/last_sync_record_count/consecutive_failure_count/last_error) + SyncLog now mirror the scanner-connector precedent (connectors/sync.py::run_sync), closing the 'stub SUCCESS, no real status' gap RESEARCH.md flagged"

key-files:
  created:
    - backend/tests/test_ticket_status_sync.py
    - backend/tests/test_ticket_sync_resilience.py
  modified:
    - backend/app/ticketing/service.py
    - backend/app/ticketing/github_client.py
    - backend/app/ticketing/daily_sync.py
    - backend/tests/test_github_sync.py
    - backend/tests/test_mttr.py

key-decisions:
  - "Jira recurrence-reopen transition target is the literal string \"To Do\" (Jira Cloud's default simplified-workflow open status) — JiraClient.transition already no-ops (logs, never raises) if a tenant's workflow has no matching transition name, so a non-default workflow degrades to a logged no-match rather than a crash"
  - "The done-transition edge (fire IN_PROGRESS + comment + audit) and the recurrence edge (fire external reopen + comment) are distinguished by the STORED prior Ticket.external_status value (a per-provider 'was this already done as of last cycle' set-membership check), not by re-deriving state from the fresh provider payload alone — this is what makes the branch fire exactly once per transition instead of re-commenting every 24h cycle while steady-state holds"
  - "ticket.resolved_at is no longer set by the ticket-done branch at all (Task 2) — a done ticket now stays permanently poll-able until either the rescan-verified second pass actually closes it (all linked vulns REMEDIATED) or a recurrence reopens it; this is the load-bearing mechanism that makes the recurrence branch reachable on a later cycle"
  - "run_daily_ticket_sync's db.commit() is now unconditional (previously gated on total_synced>0) — SYNC-04's last_sync_*/SyncLog bookkeeping must persist even on a zero-tickets or FAILED cycle, matching the scanner-connector precedent where every poll outcome is visible in the connector list regardless of record count"

patterns-established:
  - "A 3-way per-ticket state check (fresh-done / recurrence / steady-state) derived entirely from already-persisted columns (Ticket.external_status + Vulnerability.status) — no new schema needed for SYNC-01/SYNC-03's workflow-intent tracking"

requirements-completed: [SYNC-01, SYNC-03, SYNC-04]

coverage:
  - id: D1
    description: "A Jira/Asana/GitHub ticket going done/completed/closed drives the linked finding to IN_PROGRESS + an 'awaiting rescan' comment + a system:ticket-sync AuditLog — never REMEDIATED"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_github_ticket_done_drives_in_progress_never_remediated"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_jira_ticket_done_drives_in_progress_never_remediated"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_asana_ticket_done_drives_in_progress_never_remediated"
        status: pass
    human_judgment: false
  - id: D2
    description: "A ticket in an in-progress state drives the finding to IN_PROGRESS"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_jira_in_progress_status_drives_finding_in_progress"
        status: pass
    human_judgment: false
  - id: D3
    description: "An unknown/garbage provider status is a no-op (logged), never a close"
    requirement: "SYNC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_github_unknown_status_is_noop"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_asana_unknown_status_is_noop"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py::TestMapTicketStatusJira/Asana/GitHub (whitelist mapping table)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A finding OPEN again while its ticket is still closed/done (recurrence) reopens the external ticket + a recurrence comment, no duplicate Ticket row"
    requirement: "SYNC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_github_recurrence_reopens_external_ticket_no_duplicate"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_jira_recurrence_reopens_external_ticket_no_duplicate"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_status_sync.py#test_asana_recurrence_reopens_external_ticket_no_duplicate"
        status: pass
    human_judgment: false
  - id: D5
    description: "Each ticketing connector poll sets last_sync_at/last_sync_status/last_sync_record_count/consecutive_failure_count/last_error; a transient failure retries (bounded) then surfaces FAILED with a sanitized last_error, no data loss, and never blocks other connectors"
    requirement: "SYNC-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_ticket_sync_resilience.py#test_transient_failure_retries_then_succeeds_records_success_columns"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_sync_resilience.py#test_all_retries_exhausted_marks_failed_with_sanitized_error"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_sync_resilience.py#test_failed_connector_does_not_abort_pass_second_connector_still_succeeds"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_sync_resilience.py#test_repeated_failures_increment_consecutive_failure_count"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ticket_sync_resilience.py#test_success_resets_consecutive_failure_count_to_zero"
        status: pass
    human_judgment: false
  - id: D6
    description: "No mark_vulnerability_remediated call remains anywhere in daily_sync.py (D-03 grep gate); regression suite (test_github_sync.py, test_ticketing_clients.py, test_mttr.py, test_sla_tier_service.py, test_rescan_autoclose.py, test_finding_reopen.py) stays green"
    requirement: "SYNC-01"
    verification:
      - kind: other
        ref: "grep -vE '^[[:space:]]*#' backend/app/ticketing/daily_sync.py | grep -c mark_vulnerability_remediated -> 0"
        status: pass
      - kind: unit
        ref: "backend/tests/test_github_sync.py (8/8), test_ticketing_clients.py (13/13), test_mttr.py (13/13), test_sla_tier_service.py (29/29), test_rescan_autoclose.py (7/7), test_finding_reopen.py (5/5)"
        status: pass
    human_judgment: false

duration: 70min
completed: 2026-08-15
status: complete
---

# Phase 37 Plan 03: Two-Way Ticket Sync Remediation (D-03 Fix) + Sync Resilience Summary

**Removed the three `mark_vulnerability_remediated` calls that fired on ticket-done in `daily_sync.py` (the D-03 violation this whole phase exists to fix) — a closed Jira/Asana/GitHub ticket now only drives the linked finding to `IN_PROGRESS` + an "awaiting rescan" comment via a new whitelist `map_ticket_status` mapper, a recurrence (finding reopened by Plan 01/02's rescan machinery while its ticket is still done) reopens the SAME external ticket via a new `GitHubClient.reopen_issue`/`JiraClient.transition`/`AsanaClient.update_task`, and every ticketing connector poll now records a real `last_sync_*`/`consecutive_failure_count`/`last_error` outcome with bounded 3-attempt retry, mirroring the scanner-connector resilience precedent.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-08-15 (session start)
- **Completed:** 2026-08-15
- **Tasks:** 3 completed
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments
- `map_ticket_status(provider, payload)` (`ticketing/service.py`) — a whitelist mapper returning `{"in_progress","done_awaiting_rescan","open","unknown"}`, NEVER `"remediated"` (T-37-08). Every read is `.get(...)`-defaulted so a malformed/garbage payload falls through to `"unknown"` instead of raising.
- `GitHubClient.reopen_issue` — PATCH `{"state":"open"}`, byte-for-byte mirroring `close_issue`'s auth headers, single-429-retry, and log-never-raise convention.
- `daily_sync.py`'s three `_sync_<provider>_tickets` functions rewritten around a 3-way transition derived entirely from already-persisted columns (`Ticket.external_status` + `Vulnerability.status`, no new schema):
  - **Fresh done-transition:** ticket-done (Jira/Asana/GitHub) drives the linked finding `OPEN`/`IN_PROGRESS` → `IN_PROGRESS`, posts an "awaiting rescan verification" comment, and writes a direct tenant-scoped `AuditLog(user_email="system:ticket-sync", action="vuln.ticket_status_sync")`. `ticket.resolved_at` is **never** set here anymore — closure stays rescan-only (Plan 01's SUCCESS-branch sweep).
  - **Recurrence (SYNC-03/D-04):** if the ticket was *already* done as of the prior cycle and the linked finding is `OPEN` again (resurrected by Plan 02's `reopen_vulnerability`), the SAME external ticket is reopened (Asana `update_task(completed=False)`, Jira `transition(..., "To Do")`, GitHub `reopen_issue`) + a recurrence comment — never a duplicate `Ticket` row.
  - **Steady-state:** ticket still done, finding already `IN_PROGRESS`/`REMEDIATED`/`SUPPRESSED` → no-op (no re-commenting every 24h cycle).
  - **Unknown status:** logged, no-op — never touches `vuln.status` or `ticket.external_status`.
- SYNC-04: `run_daily_ticket_sync` now wraps each provider's `_sync_*` call in `_sync_with_retry` (3 attempts, 1s/2s/4s backoff) and unconditionally records a `SyncLog` row (RUNNING→SUCCESS/FAILED) plus the five `ConnectorConfig` resilience columns, reusing `connectors/sync.py::_sanitize_error` so no credential/token ever reaches `last_error`. One connector exhausting retries surfaces `FAILED` without blocking any other connector in the same pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: status-mapping helper (D-03 safe) + GitHubClient.reopen_issue** - `0cd68ca` (feat, TDD)
2. **Task 2: D-03 split — ticket status drives IN_PROGRESS, never closes (SYNC-01) + recurrence reopen (SYNC-03)** - `51fd340` (feat, TDD)
3. **Task 3: SYNC-04 — per-connector last_sync_* resilience + bounded retry** - `996731f` (feat, TDD)

_Note: as in Plans 01/02, each task's tests were written and run to GREEN in the same working session as the implementation rather than a separate literal RED-only commit — Task 1's mapping/reopen tests were confirmed green before Task 2 began; Task 2's tests were extended and re-run (including three previously-untouched `test_mttr.py` MTTR tests that encoded the OLD D-03-violating behavior and had to be corrected, see Deviations) before that commit; Task 3's resilience tests were run to green before that commit._

## Files Created/Modified
- `backend/app/ticketing/service.py` - `map_ticket_status(provider, payload)` added beside `_is_ticket_completed`
- `backend/app/ticketing/github_client.py` - `reopen_issue(number)` added, mirrors `close_issue`
- `backend/app/ticketing/daily_sync.py` - three `_sync_<provider>_tickets` functions rewritten (D-03 split + SYNC-03 recurrence); `run_daily_ticket_sync` rewritten for SYNC-04 (bounded retry + resilience columns + SyncLog + unconditional commit)
- `backend/tests/test_ticket_status_sync.py` - new file, 27 tests: mapping (all 3 providers + never-remediated whitelist assertion), `reopen_issue` (success/429-retry/log-never-raise), ticket-done→IN_PROGRESS (all 3 providers), unknown-status no-op (GitHub/Asana), Jira in-progress mapping, recurrence-reopen (all 3 providers)
- `backend/tests/test_ticket_sync_resilience.py` - new file, 5 tests: retry-then-succeed, all-retries-exhausted + sanitized error, cross-connector isolation, failure-count increment/reset
- `backend/tests/test_github_sync.py` - updated the one pre-existing regression test that asserted the old D-03-violating REMEDIATED behavior
- `backend/tests/test_mttr.py` - updated three pre-existing Phase-36 tests that asserted the same old D-03-violating behavior via `daily_sync.py`'s ticket-done paths

## Decisions Made
- **Jira reopen transition target = literal `"To Do"`** (Jira Cloud's default simplified-workflow open status). `JiraClient.transition` already no-ops with a logged warning (never raises) if a tenant's custom workflow has no matching transition name — a non-default workflow degrades gracefully rather than crashing the sync pass.
- **3-way transition state derived from stored columns, not a new column:** the done-transition / recurrence / steady-state branches are distinguished by a per-provider "was `Ticket.external_status` already a done value as of the last cycle" set-membership check (`_was_previously_done`) combined with the linked `Vulnerability.status`. This is what makes the "awaiting rescan" comment fire exactly once per transition (not every 24h cycle) and makes the recurrence branch reachable at all — see the "`ticket.resolved_at` never set on ticket-done" decision below.
- **`ticket.resolved_at` is never set by the ticket-done branch anymore.** This is a deliberate, load-bearing change from the pre-Phase-37 code (which set it alongside the REMEDIATED write): a done ticket must stay poll-able indefinitely so a later recurrence cycle can detect "ticket still done, finding OPEN again" and fire the reopen branch. Only the rescan-verified second-pass close (unchanged, still gated on ALL linked vulns being `REMEDIATED`) ever sets it now.
- **`run_daily_ticket_sync`'s commit is now unconditional** (previously `if total_synced > 0`). SYNC-04's resilience columns and `SyncLog` rows must persist even when zero tickets were touched or a connector failed outright — matching the scanner-connector precedent where the connector list always reflects the last real poll outcome.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated three pre-existing `test_mttr.py` tests asserting the removed D-03-violating behavior**
- **Found during:** Task 2 regression sweep (running the full ticketing-adjacent test surface, not just the plan's explicitly-named `test_github_sync.py`/`test_ticketing_clients.py`)
- **Issue:** `test_mttr.py` (Phase 36) contained three tests — `test_sync_{asana,jira,github}_tickets_remediated_routes_through_helper` — that drove `daily_sync.py`'s ticket-done branches and asserted `vuln.status == "REMEDIATED"` plus a `RemediationEvent` row. This was the EXACT anti-pattern D-03/this plan removes; leaving these tests unmodified would have made the D-03 fix itself fail its own regression suite.
- **Fix:** Renamed and rewrote all three to assert the corrected behavior (`vuln.status == "IN_PROGRESS"`, zero `RemediationEvent` rows from this path) and updated the module docstring's bullet describing this test group's intent.
- **Files modified:** `backend/tests/test_mttr.py`
- **Verification:** `pytest tests/test_mttr.py` — 13/13 green (unchanged count; 3 renamed, not added/removed)
- **Committed in:** `996731f` (Task 3 commit — surfaced during the pre-commit regression sweep for Task 2/3)

---

**Total deviations:** 1 auto-fixed (Rule 1 — necessary test correction, not scope creep: these tests encoded the exact bug this plan exists to fix)
**Impact on plan:** No behavior change beyond what the plan's Task 2 already specified. The fix only corrects test assertions to match the now-intentional (and required) IN_PROGRESS-not-REMEDIATED outcome.

## Issues Encountered
- **Asana MockTransport payload shape:** `AsanaClient.get_task` reads `resp.json().get("data")` (Asana's real API wraps every payload in a top-level `"data"` key). Initial test mocks returned the bare object without the `"data"` wrapper, which silently produced `task=None` (mock request succeeded, but the client's own unwrap wobbled) rather than a test failure with a clear cause — caught immediately via a debug script when `stats["synced"]` came back `0` instead of `1`. Fixed in the test fixtures only (zero production-code impact); no other provider mock needed this (Jira/GitHub responses are unwrapped raw dicts, matching their real APIs).
- **Accidental `mypy-baseline sync` invocation while investigating the "new: 3" note-line drift** (the same pre-existing version-sensitivity artifact documented in Plans 01/02's summaries) rewrote `backend/mypy-baseline.txt` in the working tree. Caught immediately via `git status`/`git diff --stat` before any commit; reverted with `git checkout -- mypy-baseline.txt`. Confirmed via a `git stash`-based before/after diff on the three touched files (`daily_sync.py`, `service.py`, `github_client.py`) that every mypy violation is a byte-for-byte pre-existing entry (only line numbers shifted from the added code) — zero new real type errors introduced. `mypy-baseline.txt` was never staged or committed.
- **Pre-existing `backend/uv.lock` untracked/ungitignored:** same repo gap already logged in `.planning/phases/37-two-way-ticket-sync-remediation-verification/deferred-items.md` by Plan 01 — left untouched, out of this plan's file scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SYNC-01/02/03/04 are now all delivered end-to-end across Plans 01-03: rescan-verified auto-close (Plan 01), DB-side reopen-on-recurrence (Plan 02), and inbound ticket-status-driven workflow state + ticket-side recurrence reopen + sync resilience (this plan). The full close → recur → reopen → re-close loop is provable with real tests at every layer.
- Phase 38 (remediation campaigns) can build directly on the now-correct `IN_PROGRESS`-only ticket-done signal and the resilient `last_sync_*` columns without any further schema change.
- No blockers. All Phase 37 test files plus the shared-helper regression guards (`test_mttr.py`, `test_sla_tier_service.py`, `test_rescan_autoclose.py`, `test_finding_reopen.py`, `test_github_sync.py`, `test_ticketing_clients.py`) are green — 107 tests total across the touched surface.

---
*Phase: 37-two-way-ticket-sync-remediation-verification*
*Completed: 2026-08-15*

## Self-Check: PASSED

All 7 referenced files exist on disk and all 3 commit hashes (0cd68ca, 51fd340, 996731f) are present in git log.
