---
phase: 23-ingestion-reliability-precursor
verified: 2026-07-28T09:00:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "An analyst can create a Jira ticket directly from a vulnerability (REL-04) — mobile nested-confirm path now renders TicketProviderPicker and gates confirm on ticketProvider !== null (CR-01, closed by 23-11)"
    - "Per-connector health data (last_error) is trustworthy — no secrets leak through the health/audit trail (REL-06, adjacent) — SyncLog.error_message now sanitized via _sanitize_error, sibling to connector_config.last_error (CR-03, closed by 23-10)"
  gaps_remaining: []
  regressions: []
---

# Phase 23: Ingestion Reliability Precursor Verification Report

**Phase Goal:** Analysts can rely on every scanner connector actually syncing, every ticketing path actually working, and can see per-connector health at a glance — the grounding data every later AI phase depends on is trustworthy.
**Verified:** 2026-07-28T09:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plans 23-10, 23-11)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Wiz connector completes a full sync end-to-end (REL-01) | ✓ VERIFIED (regression) | `wiz.py:189` still `return True` on success; untouched by closure plans (git log shows last touch `bcb6b2a`, pre-dating 23-10/23-11); `pytest tests/test_connectors/ -q` → 33 passed |
| 2 | Rapid7 connector completes a full sync end-to-end (REL-02) | ✓ VERIFIED (regression) | `rapid7.py:25` still no-arg `__init__`; untouched by closure plans (last touch `54e41b8`); same 33-test run passes |
| 3 | All six scanner connectors have HTTP-layer integration tests covering auth, pagination, mapping (REL-03) | ✓ VERIFIED (regression) | `backend/tests/test_connectors/{test_wiz,test_rapid7,test_crowdstrike,test_defender,test_nessus,test_qualys}_connector.py` all present; `pytest tests/test_connectors/ -q` → 33 passed |
| 4 | An analyst can create a Jira ticket directly from a vulnerability, on BOTH desktop and mobile (REL-04) | ✓ VERIFIED — gap CR-01 closed | Desktop unchanged (`ConfirmModal` branch, `confirmDisabled={!ticketProvider}`). Mobile: `drill-content.tsx`'s `renderConfirm` slot type now carries `ticketProvider: TicketProvider \| null` + `onProviderChange` (lines 55-62) and the call site forwards live state (lines 317-324, unchanged desktop branch at 325-337). `drill-panel-mobile.tsx` imports `TicketProviderPicker`, renders it inside the nested confirm dialog (lines 140-143), and gates the Create-ticket button with `disabled={ticketProvider === null}` (line 156). Regression test `drill-panel-mobile.test.tsx` Case A asserts `mutateAsync` called with `provider: 'JIRA'` and explicitly NOT `'ASANA'` (lines 169-174); Case B asserts the confirm button `toBeDisabled()` and that `mutateAsync` is never called while no provider is loaded (lines 194-196). Ran `npx vitest run src/components/vulnerabilities/drill-panel-mobile.test.tsx` → **8 passed** |
| 5 | GitHub ticketing works end-to-end (create + sync), no dead stub (REL-05) | ✓ VERIFIED (regression) | `GITHUB` still registered at all 4 points (`schemas.py`, `router.py`, `tester.py`, `sync.py:77`); `pytest tests/test_ticketing_dispatch.py tests/test_github_sync.py -q` → 21 passed (with correctly-formatted Fernet key; see Anti-Patterns/Notes on test-env pitfall below) |
| 6 | The Connectors UI shows each connector's last sync time, last error, and status, AND no secret in an upstream error body reaches the persisted/logged health trail (REL-06 + CR-03 adjacent hardening) | ✓ VERIFIED — gap CR-03 closed | UI-facing `connector_config.last_error` sanitization unchanged (`sync.py:199`). The previously-unsanitized sibling `SyncLog.error_message` (`sync.py:196`) now reads `log.error_message = sanitized` — same `sanitized = _sanitize_error(e)` binding reused, no second call site added (confirmed by direct read, lines 192-199). `scheduler.py:45`'s `background_sync_complete` event logs `error=log.error_message`, which is now clean by construction. Regression test `test_scheduler_path_error_message_and_log_are_sanitized` in `test_connector_health.py` drives a `Bearer sk-log-leak-42`-bearing exception through `scheduler._run_single_sync`, and asserts the secret/`Bearer` are absent from BOTH the persisted `log.error_message` (with `[REDACTED]` present, proving redaction not truncation) AND the captured `background_sync_complete` structured-log event via `structlog.testing.capture_logs()` (lines 211-251). Ran `pytest tests/test_connector_health.py -q` → **9 passed** |

**Score:** 6/6 truths verified (0 present-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/connectors/sync.py` | `log.error_message` sanitized (line ~196) | ✓ VERIFIED | Line 196: `log.error_message = sanitized`; line 193: `sanitized = _sanitize_error(e)` (single call site, reused for logger, log.error_message, connector_config.last_error) |
| `backend/tests/test_connector_health.py` | Regression test proving secret absent from error_message AND emitted log line | ✓ VERIFIED | `test_scheduler_path_error_message_and_log_are_sanitized` (lines 211-251); asserts on both `log.error_message` and `structlog.testing.capture_logs()` output |
| `frontend/src/components/vulnerabilities/drill-content.tsx` | `renderConfirm` slot carries `ticketProvider`/`onProviderChange` | ✓ VERIFIED | Type at lines 55-62; call site forwards live state at lines 317-324; desktop branch (325-337) untouched |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` | Renders `<TicketProviderPicker>`, gates confirm button | ✓ VERIFIED | Picker at lines 140-143; `disabled={ticketProvider === null}` at line 156 |
| `frontend/src/components/vulnerabilities/drill-panel-mobile.test.tsx` | Regression test: selected provider fires, confirm gated | ✓ VERIFIED | Case A (lines 144-175) + Case B (lines 177-197); both pass |
| (regression) `backend/app/connectors/wiz.py`, `rapid7.py`, ticketing dispatch/clients, migration 030, connector-card.tsx, sync-status-pill.tsx | Unchanged since prior VERIFIED pass | ✓ VERIFIED (light check) | Not modified by 23-10/23-11 (confirmed via git log); full connector + ticketing test suites re-run and pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `sync.py` write-back (`log.error_message`) | `_sanitize_error` | reused `sanitized` binding | ✓ WIRED | Line 196; was NOT WIRED in prior verification — now closed |
| `scheduler.py` `background_sync_complete` log event | `log.error_message` (now sanitized) | `error=log.error_message` | ✓ WIRED (clean by construction) | Line 45; downstream of the sync.py fix, no separate scheduler change needed |
| `drill-content.tsx` (mobile `renderConfirm` branch, via `drill-panel-mobile.tsx`) | `TicketProviderPicker` selected provider | extended slot signature | ✓ WIRED | Was NOT WIRED in prior verification — now closed; picker rendered, `onProviderChange` wired to `setTicketProvider` |
| `drill-panel-mobile.tsx` Create-ticket button | `ticketProvider` state | `disabled={ticketProvider === null}` | ✓ WIRED | Mirrors desktop `confirmDisabled={!ticketProvider}` exactly |
| (regression) `router.py` mutating endpoints | `build_ticketing_client` | `_get_ticketing_client(provider)` | ✓ WIRED | Unchanged; `test_post_tickets_provider_jira_...` still passes |
| (regression) `daily_sync.py` GitHub branch | `GitHubClient` | provider dispatch | ✓ WIRED | Unchanged; `test_github_sync.py` still passes |

### Behavioral Spot-Checks / Test Runs

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-03 regression test passes (secret absent from error_message + log line) | `ENCRYPTION_KEY=... JWT_SECRET_KEY=... .venv/bin/python -m pytest tests/test_connector_health.py -q` | 9 passed | PASS |
| CR-01 regression test passes (mobile fires selected provider, gated confirm) | `npx vitest run src/components/vulnerabilities/drill-panel-mobile.test.tsx` | 8 passed | PASS |
| All 6 scanner connector HTTP-layer tests still pass (regression) | `pytest tests/test_connectors/ -q` | 33 passed | PASS |
| Ticketing dispatch + GitHub sync tests still pass (regression) | `pytest tests/test_ticketing_dispatch.py tests/test_github_sync.py -q` | 21 passed | PASS |
| Frontend connector/vuln component tests still pass (regression) | `npx vitest run src/components/connectors "src/components/vulnerabilities/ticket-provider-picker" "src/components/vulnerabilities/drill-panel"` | 12 files / 69 tests passed | PASS |
| No new TypeScript errors in modified files | `npx tsc --noEmit -p tsconfig.json \| grep -E "drill-content\|drill-panel-mobile"` | "no type errors in drill files" | PASS |
| No debt markers (TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER) in the 5 files touched by 23-10/23-11 | grep across sync.py, test_connector_health.py, drill-content.tsx, drill-panel-mobile.tsx, drill-panel-mobile.test.tsx | none found | PASS |

**Note on test-env pitfall encountered during verification:** the first regression run of `tests/test_ticketing_dispatch.py`/`test_github_sync.py` using the literal `ENCRYPTION_KEY=test-encryption-key-32-bytes-long-xx` string from the plan's example command failed with `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` — that string is not a valid base64-encoded 32-byte key (it's a 37-char placeholder). This is an environment artifact of the example key string, not a code regression: substituting a properly-generated Fernet key (`Fernet.generate_key()`) made all 63 backend tests across connectors/dispatch/github-sync pass. `test_connector_health.py` (the plan's actual verify command) does not exercise the Fernet-encrypted-credential path and was unaffected either way.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REL-01 | 23-01 | Wiz connector completes full sync | ✓ SATISFIED (regression-confirmed) | `wiz.py::authenticate` returns `True`; 33 connector tests pass |
| REL-02 | 23-01 | Rapid7 connector completes full sync | ✓ SATISFIED (regression-confirmed) | `rapid7.py` no-arg `__init__`; same test run passes |
| REL-03 | 23-01, 23-02 | All six connectors have HTTP-layer integration tests | ✓ SATISFIED (regression-confirmed) | 6 test files, 33 passing tests |
| REL-04 | 23-03, 23-04, 23-08, 23-11 | Analyst can create a Jira ticket directly from a vulnerability (desktop AND mobile) | ✓ SATISFIED — CR-01 closed | Desktop unchanged + regression-tested; mobile now wired + gated + regression-tested (8 passing tests incl. 2 new cases) |
| REL-05 | 23-03, 23-04, 23-05 | GitHub ticketing finished end-to-end | ✓ SATISFIED (regression-confirmed) | Registered in all 4 backend points; daily_sync branch; tests pass |
| REL-06 | 23-06, 23-07, 23-09, 23-10 | Per-connector sync health visible in Connectors UI, and the health/audit trail is secret-hygienic end-to-end | ✓ SATISFIED — CR-03 closed | Migration + normalization + card UI unchanged and re-verified; `SyncLog.error_message` now sanitized to parity with `connector_config.last_error`; scheduler log line clean by construction; regression-tested |

All of REL-01 through REL-06 are claimed by at least one plan's `requirements:` frontmatter (23-10 claims REL-06, 23-11 claims REL-04), matching REQUIREMENTS.md's phase-23 mapping. No orphaned requirements.

*Note: `.planning/REQUIREMENTS.md`'s top-of-file checklist still shows `[ ]` for REL-01/02/03/05 and the phase-mapping table still shows "Pending" for those four IDs — this is stale documentation bookkeeping (REL-04/06 were flipped to `[x]`/"Complete" but the other four weren't, despite being VERIFIED in the initial 23-VERIFICATION.md pass and reconfirmed here). This is a documentation-sync gap, not a code/goal gap, and does not affect this phase's `passed` status — flagged for the ship/milestone-close step to reconcile.*

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/ticketing/router.py` | 348, 1251 | Duplicate `POST /sync-status` route (CR-02) — unchanged, still present | ⚠️ WARNING (explicitly deferred) | Documented as deferred in `23-10-PLAN.md`'s `<deferred_adjacent_items>`; legacy handler's audit-log call remains unreachable; routed to a follow-up ticketing-router backlog item, not silently dropped |
| `backend/app/ticketing/schemas.py` | 101 | `TicketRuleAction.provider: str = "ASANA"` — no enum/pattern validation | ⚠️ WARNING (explicitly deferred) | Documented as deferred in `23-10-PLAN.md`'s `<deferred_adjacent_items>` (WR-01); scheduler path already guards this; not a REL-truth failure |
| `.planning/REQUIREMENTS.md` | 18-23, 79-84 | Stale checkbox/status bookkeeping for REL-01/02/03/05 | ℹ️ INFO | Documentation-only staleness, not a code gap; see Requirements Coverage note above |

Both WARNINGs were independently re-confirmed present in the codebase (not just re-asserted from the prior REVIEW) and are explicitly documented as deferred in `23-10-PLAN.md`, not silently omitted. Since the prior verification already classified them as WARNING (not BLOCKER) and no roadmap Success Criterion depends on closing them, they do not block `passed` status for this phase.

### Deferred Items

None new. The two adjacent findings above (CR-02, WR-01) were already deferred in the prior verification pass and remain explicitly deferred (not silently dropped) per `23-10-PLAN.md`'s `<deferred_adjacent_items>` section — confirmed still present and still documented as out-of-scope-but-tracked.

## Human Verification Required

None. Both previously-open gaps (CR-01, CR-03) are closed by direct code evidence and passing regression tests that were proven to be live guards (both 23-10-SUMMARY.md and 23-11-SUMMARY.md document manual revert-and-confirm-failure checks, and this verification independently re-ran the tests against the current code). All six roadmap Success Criteria are resolvable from code/tests without live credentials or visual/UX judgment.

## Gaps Summary

None. Both gaps from the prior `gaps_found` verification are closed:

1. **CR-01 / REL-04 (mobile ticket provider) — CLOSED.** `drill-panel-mobile.tsx` now renders `<TicketProviderPicker>` inside its nested confirm dialog and disables the Create-ticket button until `ticketProvider !== null`, mirroring the desktop `ConfirmModal` branch exactly. Confirmed by direct source read of `drill-content.tsx` (extended `renderConfirm` slot) and `drill-panel-mobile.tsx` (picker + gate), and by a passing regression test that explicitly asserts the fired provider is `'JIRA'` (the tenant's configured/default-selected provider) and NOT `'ASANA'`, plus a second case proving the confirm button is disabled (not silently defaulted) while no provider is available.

2. **CR-03 / REL-06 (SyncLog secret leak) — CLOSED.** `sync.py`'s exception handler now assigns `log.error_message = sanitized`, reusing the same `_sanitize_error(e)` call already used for `connector_config.last_error` — no second sanitizer call site was introduced. The scheduler's `background_sync_complete` structured-log event is clean by construction since it reads the now-sanitized `log.error_message`. Confirmed by direct source read and a passing regression test that drives a `Bearer`-shaped secret through the actual scheduler path (`scheduler._run_single_sync`) and asserts the secret is absent from both the persisted `SyncLog.error_message` and the captured structured-log event, while `[REDACTED]` is present (proving redaction, not mere truncation).

Both fixes were verified independently in this pass (not merely trusted from the SUMMARYs): the exact source lines were read, the regression tests were re-run from a fresh shell and passed, and the previously-verified truths (REL-01/02/03/05) were regression-checked via their full test suites (33 connector tests + 21 ticketing/GitHub tests, all passing) to confirm the closure plans introduced no collateral regressions.

Phase 23's goal — "Analysts can rely on every scanner connector actually syncing, every ticketing path actually working, and can see per-connector health at a glance — the grounding data every later AI phase depends on is trustworthy" — is now fully achieved in the codebase, on both desktop and mobile surfaces, and across both the UI-facing and log/DB-facing halves of the health-data trail.

---

_Verified: 2026-07-28T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
