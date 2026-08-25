---
phase: 37-two-way-ticket-sync-remediation-verification
verified: 2026-08-17T09:27:34Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/7
  gaps_closed:
    - "A closed/done ticket NEVER force-closes a still-detected finding, anywhere in the ticketing surface (D-03 discipline; phase goal: 'a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop')"
  gaps_remaining: []
  regressions: []
---

# Phase 37: Two-Way Ticket Sync & Remediation Verification — Verification Report

**Phase Goal:** Ticket state stops being one-way (GetVul → Jira/Asana/GitHub only); a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop. Core guarantee D-03: a closed/done ticket NEVER force-closes a still-detected finding — closure is rescan-only.
**Verified:** 2026-08-17T09:27:34Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plan 37-04)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A ticket status change in Jira/Asana/GitHub writes back onto the linked finding automatically, via the scheduled sync pass (SYNC-01) | ✓ VERIFIED (regression-checked) | `backend/app/ticketing/daily_sync.py`'s three `_sync_{asana,jira,github}_tickets` functions are byte-for-byte unmodified by 37-04 (`git show 2abc51e -- app/ticketing/daily_sync.py` shows only the shared-helper import/definition block changed — zero lines touched inside the three sync functions or `run_daily_ticket_sync`). Re-ran the full regression set: 94/94 passed. |
| 2 | A closed/done ticket NEVER force-closes a still-detected finding, anywhere in the ticketing surface (D-03) — **the closed gap** | ✓ VERIFIED | `grep -rvE '^[[:space:]]*#' backend/app/ticketing/*.py \| grep -c 'mark_vulnerability_remediated('` → **0** (was 2 un-gated call sites). Whole-app `grep -rn "mark_vulnerability_remediated(" backend/app/` now shows exactly 3 sites, none under `ticketing/`: `connectors/sync.py:258` (rescan-gated, `verified_by="rescan"`) and `vulnerabilities/service.py:530,570` (manual/bulk vuln-status API, analyst-direct, outside the ticketing surface). `sync_ticket_status` (service.py:1257-1281) and `close_ticket` (service.py:1443-1470) both now branch on `map_ticket_status`/a captured pre-overwrite guard and drive the linked finding to `IN_PROGRESS` + `_AWAITING_RESCAN_COMMENT` + `AuditLog(user_email="system:ticket-sync", action="vuln.ticket_status_sync")` — never `mark_vulnerability_remediated`, never `ticket.resolved_at` on the done arm. `_is_ticket_completed` (the old boolean gate) is deleted with zero remaining callers (`grep -rn "_is_ticket_completed" backend/` → empty). Idempotency: `not was_done_before` / `not row_was_resolved` guards captured *before* the respective overwrite. See detailed re-verification below. |
| 3 | A finding absent from 2 consecutive SUCCESSful scanner syncs auto-closes as rescan-verified with a full audit trail (SYNC-02, D-02) | ✓ VERIFIED (regression-checked) | `backend/app/connectors/sync.py` untouched by 37-04 (absent from both gap-closure commits' diffs). `_run_rescan_verify_sweep` + `mark_vulnerability_remediated(verified_by="rescan")` + `AuditLog(user_email="system:rescan-verify")` unchanged. Alembic head confirmed unchanged: `048_add_clean_scan_streak (head)`. 7/7 `test_rescan_autoclose.py` still green in the re-run. |
| 4 | 1 clean sync does not close; a FAILED sync never advances any streak or closes anything (D-02) | ✓ VERIFIED (regression-checked) | Same untouched file (`connectors/sync.py`) as truth 3 — sweep still strictly SUCCESS-branch-only. No code delta possible to regress this; re-run tests green. |
| 5 | A recurrence of an auto-closed finding reopens the SAME row (no duplicate finding/ticket), MTTR lineage preserved (SYNC-03, D-04) | ✓ VERIFIED (regression-checked) | `reopen_vulnerability()` (`vulnerabilities/service.py`) and the `_upsert_vulnerability` reopen hook (`connectors/sync.py`) are both outside 37-04's `files_modified` (service.py, daily_sync.py, test_mttr.py only) and outside its diffs. 5/5 `test_finding_reopen.py` green in the re-run. |
| 6 | A finding OPEN again while its ticket is still closed/done reopens the SAME external ticket + a recurrence comment (SYNC-03 ticket-side, D-04) | ✓ VERIFIED (regression-checked) | The three `_sync_*_tickets` provider-reopen branches (`_was_previously_done(...) and vuln.status == "OPEN"` → `update_task`/`transition`/`reopen_issue` + `_RECURRENCE_COMMENT`) live in `daily_sync.py` and are untouched by 37-04's diff. 37-04-PLAN.md explicitly scoped recurrence-reopen for the *router* path (`sync_ticket_status`/`close_ticket`) as **out of scope** (dispatch `TicketingClient` Protocol has no `reopen` verb) — this is a documented boundary, not a regression, because `daily_sync.py`'s scheduled pass reopens the same ticket on its own next cycle regardless of which code path last closed it (it reads persisted `Ticket`/`Vulnerability` state, not "who closed it"). `test_github_sync.py` + related green in the re-run. |
| 7 | Each ticketing connector poll is resilient: real `last_sync_*`/`consecutive_failure_count`/`last_error` outcome, bounded retry, no data loss, one bad connector never blocks another (SYNC-04) | ✓ VERIFIED (regression-checked) | `_sync_with_retry`, the five `ConnectorConfig` resilience-column writes, and the unconditional commit in `run_daily_ticket_sync` are all outside the 37-04 diff (only the import block above them changed). 5/5 `test_ticket_sync_resilience.py` green in the re-run. |

**Score:** 7/7 truths verified — 0 BLOCKERS (was 6/7, 1 BLOCKER)

### Re-Verification Detail: Truth #2 (the closed gap)

**What was required to close it (from `missing:` in the prior report):**
1. Apply the same D-03 split to `sync_ticket_status()`.
2. Decide + document `close_ticket()`'s intended semantics (product/policy call).
3. Update/replace the two `test_mttr.py` tests so the suite no longer green-lights force-close.

**What the codebase now shows:**

1. **D-03 addendum decision recorded** — `.planning/phases/37-two-way-ticket-sync-remediation-verification/37-CONTEXT.md` (lines 57-67) documents: *"Decision (user, gap closure): D-03 applies to BOTH. Neither an inbound status sync NOR an analyst's explicit 'Close Ticket' click may close a finding — the scanner re-scanning clean is the ONLY closure path."* This resolves the prior report's `human_verification` policy question — it is no longer an open product question.

2. **`sync_ticket_status` (service.py:1182-1397) — code matches the decision.** Read directly: the ticket-done arm (`intent == "done_awaiting_rescan"`, lines 1257-1281) sets `ticket.external_status = "completed"`, then `if vuln and not was_done_before and vuln.status in ("OPEN", "IN_PROGRESS"): vuln.status = "IN_PROGRESS"; await client.comment(ref, _AWAITING_RESCAN_COMMENT); db.add(AuditLog(user_email="system:ticket-sync", action="vuln.ticket_status_sync", ...))`. No `mark_vulnerability_remediated` call anywhere in the function. `resolved_at` is never touched on this arm. `was_done_before = _was_previously_done(provider, ticket.external_status)` is captured *before* the `external_status` overwrite (line 1243), giving the re-poll idempotency guarantee. The `in_progress` intent is a plain, side-effect-free status set (no comment/audit — matches the already-verified `daily_sync.py` Jira branch). The D-03-safe second pass (auto-close the *ticket* when all linked findings are already rescan-remediated, lines 1298-1396) is untouched.

3. **`close_ticket` (service.py:1400-1477) — code matches the decision.** Still calls `client.close(ref)` and resolves ticket rows (`external_status = "completed"`, `resolved_at = now`), but the guard `row_was_resolved = ticket.resolved_at is not None` is captured *before* that overwrite, and the block that used to call `mark_vulnerability_remediated` is replaced with: `if not row_was_resolved and vuln and vuln.status in ("OPEN", "IN_PROGRESS"): vuln.status = "IN_PROGRESS"; db.add(AuditLog(..., details={..., "trigger": "manual_close"}))`. One `_AWAITING_RESCAN_COMMENT` is posted per ref (not per finding row) if `findings_awaiting_rescan > 0`. Return dict now exposes `findings_awaiting_rescan` instead of `vulns_remediated` — confirmed harmless: `router.py`'s only checks on the result are `if "error" in result`, and `grep -rn "vulns_remediated\|findings_awaiting_rescan" frontend/` returns zero matches (no frontend consumer of either key).

4. **Both router-invoked entry points still live and now safe.** `POST /tickets/sync-status` (`router.py:355-366`, calls `sync_ticket_status`), `POST /tickets/bulk-action` `action=sync-update` (`router.py:429-435`) and `action=close` (`router.py:391-399`, plus the dedicated `POST /tickets/close` at `router.py:502-519`) all still route to the two now-fixed functions — the fix reaches every entry point the prior report flagged as reachable.

5. **Tests renamed and rewritten (not just renamed).** `test_sync_ticket_status_remediated_routes_through_helper` → `test_sync_ticket_status_done_drives_in_progress_never_remediated` (test_mttr.py:244); `test_close_ticket_remediated_routes_through_helper` → `test_close_ticket_done_drives_in_progress_never_remediated` (test_mttr.py:290). Read directly: neither test asserts `REMEDIATED` anywhere. Both assert `vuln.status == "IN_PROGRESS"`, `await _events_for(db_session, vuln.id) == []` (zero `RemediationEvent` rows), and both make a **second call** on the now-steady/already-resolved state and assert `fake_client.comment_calls` count and `_audit_rows_for(...)` count do **not** grow — proving the `not was_done_before` / `not row_was_resolved` guards actually hold under repeat invocation, not just on a fresh call.

6. **Executed directly** — re-ran the exact check the prior report used to prove the gap was live:
   `pytest tests/test_mttr.py -k "sync_ticket_status or close_ticket"` → **2 passed** (`test_sync_ticket_status_done_drives_in_progress_never_remediated`, `test_close_ticket_done_drives_in_progress_never_remediated`) — the inverse of the prior report's "2 passed — old REMEDIATED assertion" finding.

**Conclusion:** Truth #2 flips from FAILED to VERIFIED. All three `missing:` items from the prior report are closed with direct code + test evidence, not just SUMMARY narrative.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/048_add_clean_scan_streak.py` | clean_scan_streak migration chained off 047 | ✓ VERIFIED (unchanged) | Alembic head still `048_add_clean_scan_streak` — no new migration added by 37-04, as the plan required. |
| `backend/app/vulnerabilities/models.py` | `Vulnerability.clean_scan_streak` column | ✓ VERIFIED (unchanged) | Untouched by 37-04. |
| `backend/app/vulnerabilities/service.py` | `mark_vulnerability_remediated(..., verified_by=...)` + `reopen_vulnerability` | ✓ VERIFIED (unchanged) | Untouched by 37-04; still the single REMEDIATED-transition helper. Its two direct call sites (lines 530, 570) are manual/bulk vuln-status-management, outside the ticketing surface — correctly left alone per 37-04-PLAN.md Task 3. |
| `backend/app/connectors/sync.py` | SUCCESS-branch absent-sweep + reopen hook | ✓ VERIFIED (unchanged) | Untouched by 37-04; the sole rescan-gated `mark_vulnerability_remediated` call (line 258) is unaffected. |
| `backend/app/ticketing/service.py` | D-03-safe `sync_ticket_status` + `close_ticket`, `map_ticket_status`, shared helpers | ✓ VERIFIED (was partial artifact — now fully verified) | `map_ticket_status` (line 1133) unchanged. `_DONE_EXTERNAL_STATUSES`, `_AWAITING_RESCAN_COMMENT`, `_was_previously_done` promoted here (lines 1102-1117) as single owner. `sync_ticket_status` (1182) and `close_ticket` (1400) rewritten D-03-safe. `_is_ticket_completed` deleted (no remaining callers, confirmed by grep). `AuditLog` imported (line 26). |
| `backend/app/ticketing/daily_sync.py` | Imports promoted helpers back; D-03 split + resilience + external reopen preserved | ✓ VERIFIED | Import block now `from app.ticketing.service import (_AWAITING_RESCAN_COMMENT, _was_previously_done, map_ticket_status)` (lines 18-22); local `_DONE_EXTERNAL_STATUSES`/`_AWAITING_RESCAN_COMMENT`/`_was_previously_done` definitions deleted (no duplicate copy). All other logic (three provider sync functions, retry wrapper, resilience bookkeeping) byte-for-byte unchanged. |
| `backend/app/ticketing/github_client.py` | `reopen_issue` PATCH state=open | ✓ VERIFIED (unchanged) | Untouched by 37-04. |
| `backend/tests/test_mttr.py` | Two rewritten regression tests, IN_PROGRESS-only + zero-event + idempotency assertions | ✓ VERIFIED | `test_sync_ticket_status_done_drives_in_progress_never_remediated` (line 244), `test_close_ticket_done_drives_in_progress_never_remediated` (line 290); `_FakeTicketingClient.comment_calls` list + `_audit_rows_for` helper added to support the idempotency assertions. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `connectors/sync.py run_sync` SUCCESS branch | `mark_vulnerability_remediated(verified_by='rescan')` | streak >= 2 auto-close call | ✓ WIRED (unchanged) | sync.py:258, untouched by 37-04. |
| `_upsert_vulnerability` existing branch | `reopen_vulnerability` | recurrence resurrection | ✓ WIRED (unchanged) | sync.py:472-475, untouched by 37-04. |
| `daily_sync.py` ticket-done branches | `finding.status = IN_PROGRESS` (+comment) | `map_ticket_status` intent branch (D-03) | ✓ WIRED (unchanged) | Untouched provider-sync functions; grep gate on this file alone = 0 (still). |
| **`ticketing/service.py::sync_ticket_status` ticket-done branch** | **`finding.status = IN_PROGRESS` (+ comment + `system:ticket-sync` AuditLog)** | `map_ticket_status` intent `"done_awaiting_rescan"`, gated on `not was_done_before` | ✓ **NOW WIRED** (was NOT_WIRED) | Confirmed service.py:1257-1281; test-proven fresh-transition fire + steady-state no-op (double-call assertion, comment/audit counts held at 1). |
| **`ticketing/service.py::close_ticket` per-ticket loop** | **`finding.status = IN_PROGRESS` (+ single comment + audit)** | removal of `mark_vulnerability_remediated`, gated on `not row_was_resolved` | ✓ **NOW WIRED** (was NOT_WIRED) | Confirmed service.py:1443-1470; test-proven fresh-close fire (`findings_awaiting_rescan == 1`) + repeat-close no-op (`findings_awaiting_rescan == 0` on 2nd call, counts held). |
| `router.py` (`/sync-status`, `/bulk-action` sync-update, `/bulk-action` close, `/close`) | `sync_ticket_status` / `close_ticket` | direct calls, `if "error" in result` only check on return shape | ✓ WIRED (unchanged, confirmed return-shape rename is safe) | router.py untouched by 37-04 diff; no caller reads the removed `vulns_remediated` key; frontend grep for both key names = 0 matches. |
| `run_daily_ticket_sync` per-connector loop | `connector.last_sync_status` | SUCCESS/FAILED resilience bookkeeping (SYNC-04) | ✓ WIRED (unchanged) | Untouched by 37-04. |

### Data-Flow Trace (Level 4 — backend persistence variant)

This phase has no UI/rendering surface (confirmed: "no frontend change" in 37-04-SUMMARY.md, and no matches for the renamed/removed field names in `frontend/`). The Level 4 analog here is: does the `IN_PROGRESS` status write actually **persist** (survive a commit + re-fetch), not just mutate an in-memory ORM object that gets discarded?

| Artifact | Write | Source of Truth | Persists Past Commit? | Status |
|----------|-------|-----------------|------------------------|--------|
| `sync_ticket_status` done arm | `vuln.status = "IN_PROGRESS"` | ORM object loaded via `select(Vulnerability).where(...)`, mutated, `db.add(AuditLog(...))`, then test calls `await db_session.commit()` + `await db_session.refresh(vuln)` | ✓ Yes | ✓ FLOWING — `test_sync_ticket_status_done_drives_in_progress_never_remediated` re-reads `vuln.status` post-commit-and-refresh, not just the pre-commit in-memory value. |
| `close_ticket` fresh-close arm | `vuln.status = "IN_PROGRESS"` | Same pattern; `_audit_rows_for` issues a fresh `select(AuditLog)` query (not a cached reference) to confirm the audit row round-trips through the DB | ✓ Yes | ✓ FLOWING — `_events_for`/`_audit_rows_for` are independent re-queries, not object-identity checks. |
| Idempotency guards (`was_done_before`, `row_was_resolved`) | Read from persisted `Ticket.external_status` / `Ticket.resolved_at` *before* this cycle's write | DB row state carried across the two sequential calls in each test (both go through `db.commit()` between calls) | ✓ Yes | ✓ FLOWING — the guard is observably keyed off durable state, not a same-process-only flag that would reset between real HTTP requests. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Ticketing-surface D-03 grep gate (whole surface, all files) | `grep -rvE '^[[:space:]]*#' backend/app/ticketing/*.py \| grep -c 'mark_vulnerability_remediated('` | `0` | ✓ PASS (was `2` pre-closure — the exact prior-report FAIL, now flipped) |
| Whole-app `mark_vulnerability_remediated(` site audit | `grep -rn "mark_vulnerability_remediated(" backend/app/` | 3 sites: `connectors/sync.py:258` (rescan-gated), `vulnerabilities/service.py:530`, `vulnerabilities/service.py:570` (manual/bulk vuln API) — **zero** under `app/ticketing/` | ✓ PASS (was `ticketing/service.py:1246`, `:1399` present — now absent) |
| Prior-report's exact "old behavior still green" check, re-run | `pytest tests/test_mttr.py -k "sync_ticket_status or close_ticket"` | `2 passed` — `test_sync_ticket_status_done_drives_in_progress_never_remediated`, `test_close_ticket_done_drives_in_progress_never_remediated` (IN_PROGRESS-asserting, not REMEDIATED-asserting) | ✓ PASS (inverse of prior report's FAIL — same command, opposite/correct outcome) |
| Full requested ticketing test surface | `pytest tests/test_mttr.py tests/test_ticket_status_sync.py tests/test_ticket_sync_resilience.py tests/test_github_sync.py tests/test_ticketing_dispatch.py tests/test_ticketing_clients.py` | `109 passed` | ✓ PASS (matches task-prompt expectation exactly) |
| Full prior-verification regression surface (no-touch files) | `pytest tests/test_rescan_autoclose.py tests/test_finding_reopen.py tests/test_ticket_status_sync.py tests/test_ticket_sync_resilience.py tests/test_github_sync.py tests/test_mttr.py tests/test_sla_tier_service.py` | `94 passed` | ✓ PASS (identical count to prior verification — zero regressions) |
| `_is_ticket_completed` fully removed, no dangling references | `grep -rn "_is_ticket_completed" backend/` (app/ + tests/) | no matches | ✓ PASS |
| Modules import cleanly (no circular-import regression from the helper promotion) | `python3 -c "import app.ticketing.service; import app.ticketing.daily_sync; import app.ticketing.router"` | `imports OK` | ✓ PASS |
| Alembic head unchanged (no migration added) | `alembic heads` | `048_add_clean_scan_streak (head)` | ✓ PASS |
| Lint/format on the three touched files | `ruff check` + `ruff format --check` on `service.py`, `daily_sync.py`, `test_mttr.py` | `All checks passed!` / `3 files already formatted` | ✓ PASS |
| Frontend has no dependency on the renamed return-dict key | `grep -rn "vulns_remediated\|findings_awaiting_rescan" frontend/` | no matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| SYNC-01 | 37-03, 37-04 | Ticket status writes back from Jira/Asana/GitHub into the linked finding (bi-directional, not create-only) | ✓ **SATISFIED** (was PARTIALLY SATISFIED — BLOCKED) | Now true via every reachable entry point: scheduled poll (`daily_sync.py`) AND both router-invoked twins (`sync_ticket_status`, `close_ticket`) — all three drive `IN_PROGRESS` and none can force-close. |
| SYNC-02 | 37-01 | A finding absent from N consecutive post-fix scanner syncs auto-closes as rescan-verified, with an audit trail | ✓ SATISFIED (unchanged) | Regression-confirmed: 7/7 `test_rescan_autoclose.py` green; file untouched. |
| SYNC-03 | 37-02, 37-03 | A recurrence after auto-close reopens the finding rather than silently creating a duplicate | ✓ SATISFIED (unchanged) | Regression-confirmed: 5/5 `test_finding_reopen.py` green; DB-side + ticket-side (daily_sync.py) untouched. Router-path recurrence-reopen intentionally deferred to the scheduled pass (documented boundary, not a gap — see truth #6). |
| SYNC-04 | 37-03 | Sync is resilient to connector/API failure (retry, last-sync surfaced, no data loss) | ✓ SATISFIED (unchanged) | Regression-confirmed: 5/5 `test_ticket_sync_resilience.py` green; file untouched. |

No orphaned requirements — all four (SYNC-01..04) claimed across the four plans (37-01/02/03/04) and cross-referenced cleanly against `.planning/REQUIREMENTS.md` (Phase 37 block, lines 37-40). SYNC-01 is the only requirement whose status changed since the prior report, and it changed from blocked to fully satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/ticketing/router.py` | 355 vs. 1258 | Two distinct `@router.post("/sync-status")` handlers registered on the same router (`sync_all_ticket_statuses` → `sync_ticket_status`, and `trigger_ticket_sync` → `run_daily_ticket_sync`) — a path/method collision; one is effectively unreachable depending on route-matching order | ℹ️ Info | **Not introduced by this phase** — confirmed via `git blame`, the second handler (line 1258) dates to 2026-03-23, five months before Phase 37 opened (2026-08-14). Does not affect D-03 correctness either way: both underlying functions (`sync_ticket_status` and `run_daily_ticket_sync` → `daily_sync.py`) are independently D-03-safe as of this verification, so whichever handler actually wins the route match is safe. Flagged for awareness only, not a phase-37 gap — pre-existing, out of this phase's remit. |

No TODO/FIXME/placeholder/HACK patterns found in any of the three files 37-04 touched (`service.py`, `daily_sync.py`, `test_mttr.py`). No empty/stub implementations introduced. The one pre-existing `return {}` in `service.py` (`_provider_create_kwargs`, line 70) is unrelated, untouched, legitimate "no extra kwargs for this provider" logic, not a stub.

### Human Verification Required

**None.** The prior report's single `human_verification` item — *"Confirm intended product behavior for the manual 'Sync ticket statuses now' action and the ticket bulk-bar 'Close Ticket' action"* — is resolved. `.planning/phases/37-two-way-ticket-sync-remediation-verification/37-CONTEXT.md` records the explicit user decision (D-03 addendum, gap closure, 2026-08-17): *"D-03 applies to BOTH sync_ticket_status AND close_ticket."* The codebase now matches that decision exactly for both functions (verified above at the code and test level). No further product/policy ambiguity remains for this phase.

### Gaps Summary

None. This is a clean re-verification pass: the single BLOCKER from the initial verification (truth #2 — the D-03 twins in `backend/app/ticketing/service.py`) is closed with direct code evidence (both functions rewritten, `_is_ticket_completed` deleted, shared helpers promoted to a single owner) and direct test evidence (both renamed `test_mttr.py` tests pass, asserting `IN_PROGRESS`-only + zero `RemediationEvent` rows + double-call idempotency — the exact three things the prior report's `missing:` list required).

37-04 was scoped as a surgical, three-file closure (`service.py`, `daily_sync.py`'s import line only, `test_mttr.py`), and the diff evidence backs that claim precisely: `git show --stat` on the two gap-closure commits shows only those three files changed, with the `daily_sync.py` diff confined entirely to the shared-helper promotion (no line inside any of the three provider-sync functions or `run_daily_ticket_sync` changed). Combined with a full re-run of the already-verified regression surface (94/94 passed, identical count to the prior verification) and the newly-expanded ticketing surface (109/109 passed, matching both the plan's own verification command and the task prompt's stated expectation), there is no evidence of regression to truths 1, 3, 4, 5, 6, or 7.

The phase goal — *"a fix is verified by the scanner itself re-scanning clean, not by a human remembering to close the loop"* — now holds everywhere in the codebase it is reachable: the scheduled poll pass, the manual "Sync ticket statuses now" action, and the manual "Close Ticket" action all drive a done/closed ticket to `IN_PROGRESS` + an audited awaiting-rescan comment, and none of them can write `REMEDIATED`. Closure remains exclusively the property of `connectors/sync.py`'s rescan-verified sweep (SYNC-02). All four requirements (SYNC-01..04) are now fully satisfied. Ready to proceed.

---

*Verified: 2026-08-17T09:27:34Z*
*Verifier: Claude (gsd-verifier)*
