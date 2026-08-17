---
phase: 37-two-way-ticket-sync-remediation-verification
verified: 2026-08-17T07:33:50Z
status: gaps_found
score: 6/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "A closed/done ticket NEVER force-closes a still-detected finding, anywhere in the ticketing surface (D-03 discipline; phase goal: 'a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop')"
    status: failed
    reason: >
      Plan 37-03 removed the three D-03-violating `mark_vulnerability_remediated` calls from
      `backend/app/ticketing/daily_sync.py` (the scheduled poll pass) and the grep gate on that
      one file correctly returns 0. But `backend/app/ticketing/service.py` contains a SEPARATE,
      live, wired implementation of inbound ticket-status sync — `sync_ticket_status()` — that
      still calls `mark_vulnerability_remediated(db, vuln)` directly the moment a ticket's own
      provider status reads as done/completed/closed, with NO rescan-verification gate at all.
      This function is reachable via two real, authenticated API endpoints
      (`POST /api/v1/tickets/sync-status` and `POST /api/v1/tickets/bulk-action` with
      `action=sync-update`), both wired in `app/ticketing/router.py` (lines 353-364, 431-435).
      37-RESEARCH.md itself identified `sync_ticket_status` as "the router-invoked twin of the
      scheduler pass" and one of the pre-existing `mark_vulnerability_remediated` call sites
      alongside `daily_sync.py`'s three — but 37-03-PLAN.md's task scope ("The THREE
      D-03-VIOLATING blocks to rewrite in backend/app/ticketing/daily_sync.py") only targeted
      daily_sync.py, so this analog was never rewritten. A regression test
      (`tests/test_mttr.py::test_sync_ticket_status_remediated_routes_through_helper`) still
      exists UNMODIFIED and explicitly asserts `vuln.status == "REMEDIATED"` after a ticket-done
      sync through this path — i.e. the exact behavior this whole phase exists to eliminate is
      still green in the test suite, just via a different entry point than the one the plan
      patched.
    artifacts:
      - path: "backend/app/ticketing/service.py"
        issue: "sync_ticket_status() (line 1176) and close_ticket() (line 1352) both still call mark_vulnerability_remediated(db, vuln) directly on ticket-done/close, bypassing the rescan-verified closure path (D-02/D-03) entirely. Lines 1244-1246 and 1397-1399."
      - path: "backend/app/ticketing/router.py"
        issue: "POST /sync-status (line 353) and POST /bulk-action action=sync-update (line 431) wire sync_ticket_status() into the live API surface — this is not dead code."
      - path: "backend/tests/test_mttr.py"
        issue: "test_sync_ticket_status_remediated_routes_through_helper (line 227) and test_close_ticket_remediated_routes_through_helper still assert/lock in the pre-Phase-37 REMEDIATED-on-ticket-done behavior for this code path; Plan 03 only updated the three daily_sync.py-flavored tests, not these."
    missing:
      - "Apply the same D-03 split to sync_ticket_status(): a done/completed/closed ticket status read should drive the linked finding to IN_PROGRESS (+ awaiting-rescan comment/audit), never call mark_vulnerability_remediated directly."
      - "Decide + document close_ticket()'s intended semantics: is an analyst's explicit 'Close Ticket' click meant to be a manual override that bypasses rescan-verification (arguably legitimate, distinct from an inbound status sync), or should it also route only through the rescan path? Either way, this should be an explicit, documented decision (D-03 addendum or an accepted override), not a silent gap."
      - "Update/replace the two test_mttr.py tests above once the behavior changes, so the suite no longer green-lights the old force-close semantics."
human_verification:
  - test: "Confirm intended product behavior for the manual 'Sync ticket statuses now' action and the ticket bulk-bar 'Close Ticket' action"
    expected: "Either both respect D-03 (never force-close a scanner-detected finding) or the team explicitly accepts close_ticket as an intentional human-override escape hatch outside D-03's scope"
    why_human: "This is a product/policy decision (which entry points count as 'the loop being closed by a human' vs. legitimate manual override), not something resolvable by code inspection alone"
---

# Phase 37: Two-Way Ticket Sync & Remediation Verification — Verification Report

**Phase Goal:** Ticket state stops being one-way (GetVul → Jira/Asana/GitHub only); a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop.
**Verified:** 2026-08-17T07:33:50Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A ticket status change in Jira/Asana/GitHub writes back onto the linked finding automatically, via the scheduled sync pass (SYNC-01) | VERIFIED | `backend/app/ticketing/daily_sync.py` `_sync_{asana,jira,github}_tickets` all rewritten around `map_ticket_status()`; ticket-done drives `vuln.status = "IN_PROGRESS"` + comment + `system:ticket-sync` AuditLog. Confirmed by direct code read + 94/94 green tests. |
| 2 | A closed/done ticket NEVER force-closes a still-detected finding, anywhere in the ticketing surface (D-03) | **FAILED** | `backend/app/ticketing/service.py::sync_ticket_status` (line 1176) and `::close_ticket` (line 1352) still call `mark_vulnerability_remediated(db, vuln)` directly on ticket-done, with no rescan gate. Both are live, wired API endpoints (`POST /tickets/sync-status`, `POST /tickets/bulk-action` action=sync-update / action=close). See Gaps Summary. |
| 3 | A finding absent from 2 consecutive SUCCESSful scanner syncs auto-closes as rescan-verified with a full audit trail (SYNC-02, D-02) | VERIFIED | `backend/app/connectors/sync.py::_run_rescan_verify_sweep` (SUCCESS-branch only) + `mark_vulnerability_remediated(verified_by="rescan")` + direct `AuditLog(user_email="system:rescan-verify")`. Migration 048 confirmed at alembic head. 7/7 `test_rescan_autoclose.py` green. |
| 4 | 1 clean sync does not close; a FAILED sync never advances any streak or closes anything (D-02) | VERIFIED | Sweep is called strictly inside `run_sync`'s SUCCESS branch, after the upsert loop, never reachable from the `except`/auth-failure branches. Verified by direct code read (lines 145-154, 216-223 vs. 184-209) + passing tests. |
| 5 | A recurrence of an auto-closed finding reopens the SAME row (no duplicate finding/ticket), MTTR lineage preserved (SYNC-03, D-04) | VERIFIED | `reopen_vulnerability()` (service.py:439) + `_upsert_vulnerability`'s existing-branch hook (`if existing.status == "REMEDIATED": await reopen_vulnerability(...)`, sync.py:472-475). `first_detected_at` untouched; `RemediationEvent` rows never deleted. 5/5 `test_finding_reopen.py` green. |
| 6 | A finding OPEN again while its ticket is still closed/done reopens the SAME external ticket + a recurrence comment (SYNC-03 ticket-side, D-04) | VERIFIED | All three `_sync_*_tickets` functions have a `_was_previously_done(...) and vuln.status == "OPEN"` branch calling `client.update_task(completed=False)` / `client.transition(..., "To Do")` / `client.reopen_issue(...)` + recurrence comment; `GitHubClient.reopen_issue` added (mirrors `close_issue`). Verified by direct code read; tests green. |
| 7 | Each ticketing connector poll is resilient: real `last_sync_*`/`consecutive_failure_count`/`last_error` outcome, bounded retry, no data loss, one bad connector never blocks another (SYNC-04) | VERIFIED | `run_daily_ticket_sync` wraps each provider call in `_sync_with_retry` (3 attempts, 1s/2s/4s backoff), sets the five `ConnectorConfig` resilience columns unconditionally, uses `_sanitize_error` (reused from `connectors/sync.py`), commit is now unconditional. 5/5 `test_ticket_sync_resilience.py` green; existing `ConnectorResponse` schema already surfaces these columns generically (no router/schema change needed, confirmed). |

**Score:** 6/7 truths verified — 1 BLOCKER

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/048_add_clean_scan_streak.py` | clean_scan_streak migration chained off 047 | ✓ VERIFIED | `down_revision = "047_add_remediation_events"`; confirmed current alembic head is `048_add_clean_scan_streak`. |
| `backend/app/vulnerabilities/models.py` | `Vulnerability.clean_scan_streak` column | ✓ VERIFIED | `clean_scan_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")` (line 103). |
| `backend/app/vulnerabilities/service.py` | `mark_vulnerability_remediated(..., verified_by=...)` + `reopen_vulnerability` | ✓ VERIFIED | Both present, exact behavior matches PLAN spec (streak reset, MTTR preserved, system-actor audit). |
| `backend/app/connectors/sync.py` | SUCCESS-branch absent-sweep + reopen hook | ✓ VERIFIED | `_run_rescan_verify_sweep` called only in SUCCESS branch (line 193); `_upsert_vulnerability` reopen hook (line 472-475). |
| `backend/app/ticketing/service.py` | `map_ticket_status` (D-03-safe mapper) | ✓ VERIFIED (partial artifact) | `map_ticket_status` exists and never returns "remediated" — but the FILE also still contains two un-remediated D-03 violations (`sync_ticket_status`, `close_ticket`) that the plan didn't touch. See gap. |
| `backend/app/ticketing/github_client.py` | `reopen_issue` PATCH state=open | ✓ VERIFIED | Mirrors `close_issue` exactly (line 225-245). |
| `backend/app/ticketing/daily_sync.py` | D-03 split + last_sync_* wiring + retry + external reopen | ✓ VERIFIED | Grep gate confirmed 0 `mark_vulnerability_remediated` occurrences in this file; all resilience columns + retry wrapper present and wired. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `connectors/sync.py run_sync` SUCCESS branch | `mark_vulnerability_remediated(verified_by='rescan')` | streak >= 2 auto-close call | ✓ WIRED | Confirmed at sync.py:258, only inside `_run_rescan_verify_sweep`, only called from the SUCCESS branch. |
| `run_sync` absent-sweep | `AuditLog(user_email='system:rescan-verify')` | direct AuditLog construction | ✓ WIRED | Confirmed sync.py:259-271, real `tenant_id=vuln.tenant_id`. |
| `_upsert_vulnerability` existing branch | `reopen_vulnerability` | recurrence resurrection | ✓ WIRED | Confirmed sync.py:472-475, gated on `existing.status == "REMEDIATED"`. |
| `reopen_vulnerability` | `AuditLog(user_email='system:rescan-reopen')` | direct AuditLog construction | ✓ WIRED | Confirmed service.py:464-471. |
| `daily_sync.py` ticket-done branches | `finding.status = IN_PROGRESS` (+comment) | removal of `mark_vulnerability_remediated` calls (D-03) | ✓ WIRED | Confirmed for all 3 providers in `daily_sync.py`; grep gate = 0. |
| `ticketing/service.py::sync_ticket_status` / `close_ticket` ticket-done branches | `finding.status = IN_PROGRESS` (D-03) | — | ✗ **NOT WIRED** | These two functions still call `mark_vulnerability_remediated` directly — never rewritten to the D-03-safe pattern. Not in scope of any of the 3 plans' `files_modified`, despite RESEARCH.md flagging the analog. |
| `run_daily_ticket_sync` per-connector loop | `connector.last_sync_status` | SUCCESS/FAILED resilience bookkeeping (SYNC-04) | ✓ WIRED | Confirmed daily_sync.py:176-180, 203-205; unconditional commit confirmed line 217. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| D-03 grep gate on daily_sync.py | `grep -vE '^[[:space:]]*#' backend/app/ticketing/daily_sync.py \| grep -c mark_vulnerability_remediated` | `0` | ✓ PASS |
| Full Phase 37 unit-test surface | `pytest tests/test_rescan_autoclose.py tests/test_finding_reopen.py tests/test_ticket_status_sync.py tests/test_ticket_sync_resilience.py tests/test_github_sync.py tests/test_mttr.py tests/test_sla_tier_service.py` | 94 passed | ✓ PASS |
| Regression: ticketing dispatch + clients | `pytest tests/test_ticketing_clients.py tests/test_ticketing_dispatch.py` | 56 passed | ✓ PASS |
| Alembic head | `alembic heads` | `048_add_clean_scan_streak (head)` | ✓ PASS |
| Whole-surface D-03 grep (not scoped to daily_sync.py) | `grep -rn "mark_vulnerability_remediated(" backend/app/` | 3 real call sites: `connectors/sync.py:258` (correct, rescan-gated), `ticketing/service.py:1246` and `ticketing/service.py:1399` (both un-gated, D-03 violations) | ✗ **FAIL** |
| Test suite still asserts the old violating behavior | `pytest tests/test_mttr.py -k "sync_ticket_status or close_ticket"` | 2 passed — `test_sync_ticket_status_remediated_routes_through_helper` still asserts `vuln.status == "REMEDIATED"` from a ticket-done sync | ✗ **FAIL** (confirms the gap is live, not theoretical) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| SYNC-01 | 37-03 | Ticket status writes back from Jira/Asana/GitHub into the linked finding (bi-directional, not create-only) | **PARTIALLY SATISFIED — BLOCKED** | Scheduled poll path (`daily_sync.py`) fully correct and D-03-safe. Manual/router path (`ticketing/service.py::sync_ticket_status`) is also "ticket status → finding" sync but still force-closes on done — the bi-directional link exists but is not safely governed everywhere it's exposed. |
| SYNC-02 | 37-01 | A finding absent from N consecutive post-fix scanner syncs auto-closes as rescan-verified, with an audit trail | ✓ SATISFIED | Fully verified in code + 7/7 tests + audit trail confirmed. |
| SYNC-03 | 37-02, 37-03 | A recurrence after auto-close reopens the finding rather than silently creating a duplicate | ✓ SATISFIED | DB-side (Plan 02) + ticket-side (Plan 03) both verified in code + tests. |
| SYNC-04 | 37-03 | Sync is resilient to connector/API failure (retry, last-sync surfaced, no data loss) | ✓ SATISFIED | Verified in code + 5/5 tests; generic `ConnectorConfig` surfacing confirmed to already cover ticketing connectors with no schema change. |

No orphaned requirements — all four (SYNC-01..04) are claimed across the three plans and cross-reference cleanly against `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/ticketing/service.py` | 1244-1246, 1397-1399 | Direct, un-gated `mark_vulnerability_remediated` call on ticket-done, identical to the exact pattern this phase's Plan 03 explicitly removed from `daily_sync.py` | 🛑 Blocker | Undermines the phase's core stated guarantee ("verified by rescan, not by a human closing a ticket") for two live API entry points. |
| `backend/tests/test_mttr.py` | 227 (`test_sync_ticket_status_remediated_routes_through_helper`), ~262 (`test_close_ticket_remediated_routes_through_helper`) | Regression tests still assert the pre-Phase-37 REMEDIATED-on-ticket-done behavior as correct | ⚠️ Warning | The test suite actively locks in the violating behavior rather than flagging it; a future refactor could "fix forward" into this trap again without any red test to catch it. |

No TODO/FIXME/placeholder patterns found in any of the phase's newly-created/modified files (`clean_scan_streak` migration, `service.py` helpers, `sync.py` sweep, `daily_sync.py` rewrite, `github_client.py`). No empty/stub implementations, no hardcoded-empty data flows.

### Human Verification Required

See `human_verification` in frontmatter — one item: confirm the intended product/policy stance on `close_ticket`'s explicit manual-override semantics (whether it should also be rescan-gated, or is deliberately a distinct "analyst says done" escape hatch outside D-03's scope). This does not block classifying `sync_ticket_status` as a hard gap (that one is unambiguously an inbound ticket-status sync, the exact SYNC-01/D-03 concern), but it affects how broadly the closure plan should scope its fix.

### Gaps Summary

Three of the phase's four requirements (SYNC-02, SYNC-03, SYNC-04) are fully and cleanly delivered — the `clean_scan_streak` column, the `verified_by`-extended single-helper discipline, the SUCCESS-branch absent-sweep, the DB-side and ticket-side reopen-on-recurrence machinery, and the per-connector resilience bookkeeping all exist, are wired correctly, and are covered by real, passing tests that exercise the actual code paths (not mocks-in-isolation).

The gap is narrow but structurally important: **Plan 37-03 scoped its D-03 fix to exactly the three blocks in `daily_sync.py`** (the scheduled/automatic ticket-sync pass) that 37-RESEARCH.md identified as violating — but RESEARCH.md *also* identified `ticketing/service.py::sync_ticket_status` as "the router-invoked twin of the scheduler pass" and one of the pre-existing `mark_vulnerability_remediated` call sites, and this analog was never rewritten. It (and its sibling `close_ticket`) remain live behind real, authenticated API endpoints and still force-close a finding the instant a ticket reads as done — completely bypassing rescan verification. A currently-green regression test in `test_mttr.py` explicitly locks in this exact behavior as "correct," meaning this is not a theoretical risk: the SUMMARY's claim of "no `mark_vulnerability_remediated` call remains anywhere in daily_sync.py" is true and accurately scoped, but the phase's actual GOAL — closure only ever coming from the scanner, never from a ticket — is not yet true everywhere it's reachable in the codebase.

Recommended next step: a closure plan (`/gsd-plan-phase 37 --gaps`) targeting `backend/app/ticketing/service.py::sync_ticket_status` (apply the same `map_ticket_status` + IN_PROGRESS-only pattern already proven in `daily_sync.py`) and an explicit product decision on `close_ticket`'s manual-override semantics.

---

*Verified: 2026-08-17T07:33:50Z*
*Verifier: Claude (gsd-verifier)*
