---
phase: 37-two-way-ticket-sync-remediation-verification
plan: 04
subsystem: api
gap_closure: true
tags: [fastapi, sqlalchemy, jira, asana, github, ticketing, remediation, d-03]

# Dependency graph
requires:
  - phase: 37-two-way-ticket-sync-remediation-verification
    provides: "map_ticket_status + _was_previously_done + _AWAITING_RESCAN_COMMENT + the D-03 done-transition pattern (Plan 03, daily_sync.py); mark_vulnerability_remediated single-helper discipline (Plan 01)"
provides:
  - "D-03-safe ticketing/service.py::sync_ticket_status — a done ticket read drives the linked finding to IN_PROGRESS (+ awaiting-rescan comment + audit), never REMEDIATED; gated on `not was_done_before` for re-poll idempotency"
  - "D-03-safe ticketing/service.py::close_ticket — manual close still closes the ticket + resolves rows, but drives findings to IN_PROGRESS (+ audit), never REMEDIATED; returns findings_awaiting_rescan; gated on `not row_was_resolved`"
  - "Single-owner shared helpers in service.py: _AWAITING_RESCAN_COMMENT, _DONE_EXTERNAL_STATUSES, _was_previously_done (daily_sync.py imports them back)"
affects: [phase-38-remediation-campaigns, phase-39-exception-risk-acceptance, phase-40-alerting-digests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The D-03 fresh-transition guard is now applied uniformly across the ENTIRE ticketing surface — scheduled poll (daily_sync.py, Plan 03) AND the two router-invoked twins (service.py, this plan) — closing the gap where the phase goal held for the automatic path but not the manual API entry points"
    - "close_ticket's idempotency axis is the ticket row's prior resolved_at (not a provider-status set-membership like the poll path), because a manual close is a one-shot terminal action on the ticket rather than a repeated status read — same 'fire exactly once per real transition' guarantee, different signal"

key-files:
  created:
    - .planning/phases/37-two-way-ticket-sync-remediation-verification/37-04-SUMMARY.md
  modified:
    - backend/app/ticketing/service.py
    - backend/app/ticketing/daily_sync.py
    - backend/tests/test_mttr.py

key-decisions:
  - "D-03 addendum (user decision, gap closure): D-03 applies to BOTH sync_ticket_status AND close_ticket — neither an inbound status sync nor an analyst's explicit 'Close Ticket' click may close a finding; the scanner re-scanning clean (SYNC-02) is the only closure path"
  - "The three shared helpers (_AWAITING_RESCAN_COMMENT, _DONE_EXTERNAL_STATUSES, _was_previously_done) are promoted to service.py as the single owner and imported back by daily_sync.py — service.py already owns map_ticket_status and daily_sync.py already imports FROM service.py, so the reverse ownership would be circular"
  - "close_ticket's return dict now exposes findings_awaiting_rescan instead of vulns_remediated — safe because router.py's only checks on this result are `if 'error' in result`, and the frontend discards the bulk-action response body (verified)"
  - "_is_ticket_completed is deleted: after sync_ticket_status switches to map_ticket_status for the finding-status decision, grep confirms it had no remaining callers anywhere in the backend"

patterns-established:
  - "Whole-surface invariant enforcement via a scoped grep gate: `grep -rvE '^[[:space:]]*#' backend/app/ticketing/*.py | grep -c 'mark_vulnerability_remediated('` must be 0 — the closure guarantee is now a mechanically checkable property of the ticketing package, not a claim about one file"

status: complete
---

# Phase 37 Plan 04: Two-Way Ticket Sync — D-03 Twin Gap Closure Summary

**Gap closed:** the single BLOCKER from `37-VERIFICATION.md` (score was 6/7). Plan 37-03 removed all three D-03-violating `mark_vulnerability_remediated` calls from `daily_sync.py` (the scheduled poll pass), but `ticketing/service.py` held a separate, live, router-wired implementation of inbound ticket-status sync (`sync_ticket_status`) and manual close (`close_ticket`) that still force-closed a finding the instant a ticket read done — reachable via `POST /tickets/sync-status` and `POST /tickets/bulk-action`. Two `test_mttr.py` tests actively locked in the old REMEDIATED-on-ticket-done behavior.

## Accomplishments

- **`sync_ticket_status` (service.py):** the ticket-done arm now branches on `map_ticket_status(provider, payload)` instead of the boolean `_is_ticket_completed`. On `done_awaiting_rescan` and a *fresh* transition (`not was_done_before`, captured before the `external_status` overwrite), the linked finding goes OPEN/IN_PROGRESS → IN_PROGRESS with an `_AWAITING_RESCAN_COMMENT` and a `system:ticket-sync` AuditLog — never REMEDIATED, never `resolved_at`. The `in_progress` intent is a plain side-effect-free status set (no comment/audit), matching the verified `daily_sync.py` Jira branch. The D-03-safe second pass (auto-close the *ticket* when all linked findings are already rescan-remediated) is preserved untouched.
- **`close_ticket` (service.py):** still calls `client.close(ref)` and resolves the ticket rows, but replaces the `mark_vulnerability_remediated` call with an IN_PROGRESS drive + audit, gated on `not row_was_resolved` so a repeat close on an already-resolved URL is a no-op on the finding. Posts one awaiting-rescan comment per ref (not per row). Returns `findings_awaiting_rescan`.
- **Shared helpers promoted** to `service.py` (single owner); `daily_sync.py` imports them back. `_is_ticket_completed` deleted (no remaining callers).
- **Tests rewritten** with the D-03-safe assertions AND a double-call idempotency assertion (comment-count / audit-row-count do not grow on a second invocation of the steady state).

## Task Commits

- `2abc51e` — feat(37-04): D-03 addendum — sync_ticket_status + close_ticket drive IN_PROGRESS, never REMEDIATED
- `34979a1` — test(37-04): rewrite mttr ticket-sync regressions — IN_PROGRESS-only + re-poll idempotency

(Tasks 1 and 2 both edit `service.py`; they are committed as one implementation commit + one test commit rather than split mid-file. The plan doc was committed earlier as `76f77d4`.)

## Verification

- Ticketing-surface D-03 grep gate: `grep -rvE '^[[:space:]]*#' backend/app/ticketing/*.py | grep -c 'mark_vulnerability_remediated('` → **0**.
- `pytest tests/test_mttr.py tests/test_ticket_status_sync.py tests/test_ticket_sync_resilience.py tests/test_github_sync.py tests/test_ticketing_dispatch.py tests/test_ticketing_clients.py` → **109 passed** (with real Fernet `ENCRYPTION_KEY` + `JWT_SECRET_KEY`, per project memory).
- `ruff check` + `ruff format --check` clean on all three files; `mypy` introduces no new errors in `service.py` (the daily_sync.py baseline-filter deltas reproduce identically on clean HEAD — a local dep-env vs baseline-env artifact documented in `ci.yml`, not caused by this plan).
- Legitimate out-of-scope `mark_vulnerability_remediated` sites left untouched: `connectors/sync.py:258` (rescan-gated) and the manual/bulk vuln-status calls in `vulnerabilities/service.py`.

## Deviations from Plan

- **Executed inline by the orchestrator, not a spawned gsd-executor.** The gsd-executor subagent died mid-run four times this session on a recurring "your computer went to sleep mid-response" API error (an environment issue, not a logic one). With explicit user approval, the orchestrator finished the plan inline, task-by-task (short tool-call bursts survive sleep interruptions far better than one long agent turn). The plan-checker had already validated the plan twice, so the quality gate remained intact. Task 1's edits were already applied in the working tree by the dying executor before the switch; they were audited for correctness (guard captured before overwrite, plain in_progress branch, clean helper promotion) before Task 2 was built on top.

## Recurrence-reopen scope (documented boundary, not a dropped requirement)

`daily_sync.py` reopens the *same external ticket* on recurrence via provider-specific verbs (`update_task(completed=False)` / `transition(..., "To Do")` / `reopen_issue`). This was **deliberately not** added to `sync_ticket_status`/`close_ticket`: the generic dispatch `TicketingClient` Protocol exposes only `create`/`get`/`comment`/`close` — it has no reopen verb — and `daily_sync.py` (which uses the provider-specific clients) already owns provider reopen, which `37-VERIFICATION.md` marked VERIFIED (truth #6). The verification `missing:` list required only the IN_PROGRESS split + the two test rewrites, both delivered.

## Next Phase Readiness

SYNC-01 is now fully satisfied everywhere it is reachable: a ticket status change writes back onto the linked finding as a workflow transition (IN_PROGRESS) via the scheduled poll AND both manual router endpoints AND manual close, and no entry point can force-close a still-detected finding. Re-run `/gsd-verify-work 37` (or the phase verifier) to flip the phase from 6/7 to 7/7.

---

## Self-Check: PASSED

- [x] Every `missing:` item from 37-VERIFICATION.md addressed (sync_ticket_status D-03 split; close_ticket decision + fix; both tests rewritten)
- [x] Ticketing-surface grep gate = 0
- [x] 109 tests pass; both rewritten tests assert IN_PROGRESS-only + zero RemediationEvent + double-call idempotency
- [x] No regression to already-verified SYNC-02/03/04 work
- [x] STATE.md / ROADMAP.md left for the orchestrator (per this project's tracking-file-corruption hazard)
