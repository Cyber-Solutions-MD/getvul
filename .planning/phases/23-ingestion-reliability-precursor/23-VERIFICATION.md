---
phase: 23-ingestion-reliability-precursor
verified: 2026-07-27T14:49:55Z
status: gaps_found
score: 5/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "An analyst can create a Jira ticket directly from a vulnerability, not just receive status-sync updates (REL-04)"
    status: partial
    reason: "Desktop create-ticket flow is fully wired (TicketProviderPicker + backend provider dispatch, proven by test_post_tickets_provider_jira_reaches_jira_client_and_persists_jira and drill-content.tsx's ConfirmModal branch). The MOBILE nested-confirm path (drill-panel-mobile.tsx -> DrillContent's renderConfirm slot) never renders TicketProviderPicker; ticketProvider state stays null for the entire mobile flow and fireTicket() falls through to provider: ticketProvider ?? 'ASANA'. Every mobile ticket creation is fired as ASANA regardless of tenant config or analyst choice — the same 'provider silently becomes Asana' defect class (D-07) this phase's backend work fixed, reintroduced on an unaudited frontend surface. Confirmed by direct code read (CR-01) and self-disclosed as a Known Gap in 23-08-SUMMARY.md."
    artifacts:
      - path: "frontend/src/components/vulnerabilities/drill-content.tsx"
        issue: "renderConfirm slot signature (lines ~55-60) carries no ticketProvider/onChange; when renderConfirm is supplied, DrillContent renders ONLY that slot (lines ~314-320), skipping TicketProviderPicker + confirmDisabled gate entirely"
      - path: "frontend/src/components/vulnerabilities/drill-panel-mobile.tsx"
        issue: "renders its own bare confirm dialog through renderConfirm with no provider picker of its own (line ~101)"
    missing:
      - "Extend renderConfirm's callback args to pass ticketProvider + onProviderChange (or the whole picker element) through to the caller"
      - "Wire <TicketProviderPicker> into drill-panel-mobile.tsx's nested confirm dialog and gate its confirm button on ticketProvider !== null, mirroring ConfirmModal's confirmDisabled={!ticketProvider} on desktop"
  - truth: "Per-connector health data (last_error) is trustworthy — no secrets leak through the health/audit trail (REL-06, adjacent to 'sync health is trustworthy')"
    status: partial
    reason: "connector_config.last_error (the field the Connectors UI actually reads) IS correctly sanitized via _sanitize_error before persist and render — the literal SC#5 UI claim ('last error' shown in the Connectors UI) holds. However, the SIBLING field SyncLog.error_message (sync.py:196, log.error_message = str(e)[:2000]) is never passed through _sanitize_error, and scheduler.py logs it verbatim as `error=log.error_message` in the background_sync_complete structured-log event. A crafted upstream HTTP error body containing 'Authorization: Bearer <token>' or Basic-auth-shaped credentials survives verbatim into both the sync_logs table and the application's structured log stream on every background sync failure. Confirmed by direct code read (CR-03); the existing test test_scheduler_path_failure_parity constructs exactly such a secret-bearing exception but only asserts on connector.last_error, not log.error_message or the emitted log line, so nothing currently catches the leak. Not exposed to end users via any API route (no router.py reference to SyncLog found), but reaches DB admins and log-aggregator operators — a real, unresolved secret-hygiene defect in the exact subsystem (D-18/D-19 error capture) this phase built for 'trustworthy grounding data.'"
      artifacts:
      - path: "backend/app/connectors/sync.py"
        issue: "line ~196: log.error_message = str(e)[:2000] bypasses _sanitize_error, unlike connector_config.last_error two lines below it"
      - path: "backend/app/connectors/scheduler.py"
        issue: "lines ~38-46: logger.info('background_sync_complete', ..., error=log.error_message) logs the raw unsanitized string; structlog's key-based redact_sensitive_keys processor does not scan string CONTENT, only dict key names, so this bypasses redaction entirely"
    missing:
      - "Sanitize log.error_message the same way last_error is sanitized (log.error_message = sanitized instead of str(e)[:2000])"
      - "Add a regression test driving a secret-bearing exception through run_sync/scheduler._run_single_sync and asserting the secret is absent from log.error_message and the emitted log line, not just connector_config.last_error"
---

# Phase 23: Ingestion Reliability Precursor Verification Report

**Phase Goal:** Analysts can rely on every scanner connector actually syncing, every ticketing path actually working, and can see per-connector health at a glance — the grounding data every later AI phase depends on is trustworthy.
**Verified:** 2026-07-27T14:49:55Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Wiz connector completes a full sync end-to-end (REL-01) | VERIFIED | `wiz.py::authenticate` (lines 155-189) now ends `return True` on success, replacing the falsy `None` return; `test_wiz_connector.py` MockTransport tests (`test_authenticate_success_returns_true`, `test_fetch_vulnerabilities_paginates_to_completion`, `test_fetch_vulnerabilities_field_mapping`) pass |
| 2 | Rapid7 connector completes a full sync end-to-end (REL-02) | VERIFIED | `rapid7.py::__init__` (line 25) is now no-arg (`def __init__(self) -> None`); `async def authenticate(self, credentials, config)` (line 40) reads `credentials.get("url"/"username"/"password")` + returns `bool`; `test_rapid7_connector.py::test_constructs_with_no_arguments` and 4 other tests pass |
| 3 | All six scanner connectors have HTTP-layer integration tests covering auth, pagination, mapping (REL-03) | VERIFIED | `backend/tests/test_connectors/{test_wiz,test_rapid7,test_crowdstrike,test_defender,test_nessus,test_qualys}_connector.py` all exist, each with `test_authenticate_*`, pagination, and field-mapping tests. Ran `pytest tests/test_connectors/ -q`: **33 passed**. `verify=False` no longer appears anywhere in `app/connectors/` (grep confirmed empty) |
| 4 | An analyst can create a Jira ticket directly from a vulnerability (REL-04) | **PARTIAL / FAILED** | Desktop: VERIFIED — `test_ticketing_dispatch.py::test_post_tickets_provider_jira_reaches_jira_client_and_persists_jira` passes; `drill-content.tsx`'s `ConfirmModal` branch renders `<TicketProviderPicker>` with `confirmDisabled={!ticketProvider}`. Mobile: FAILED — see gap CR-01 above; `provider: ticketProvider ?? 'ASANA'` always resolves to `'ASANA'` on the mobile nested-confirm path |
| 5 | GitHub ticketing works end-to-end (create + sync), no dead stub (REL-05) | VERIFIED | `GITHUB` registered in all 4 required points: `schemas.py:323` (`CONNECTOR_TYPES`), `router.py:42` (`CONNECTOR_CATEGORIES`), `tester.py:509` (dispatch), `sync.py:77` (`SPECIAL_CONNECTORS`). `daily_sync.py` has a full GitHub branch (`_sync_github_tickets`, inbound state map + outbound auto-close via `close_issue`/`add_comment`). `test_ticketing_dispatch.py::test_post_tickets_provider_github_reaches_github_client` and `test_github_sync.py` pass |
| 6 | The Connectors UI shows each connector's last sync time, last error, and status (REL-06) | VERIFIED (with adjacent WARNING — see gap CR-03) | Migration `030_add_connector_health_columns.py` (single head, chained on `029`) adds `last_error`/`consecutive_failure_count`; `service.py::_to_response` normalizes `SUCCESS/FAILED/None -> ok/failed/None` and exposes both new fields; `SyncStatusPill` no longer crashes on real backend values (total-lookup fallback); `connector-card.tsx` renders inline last-error summary (only on failure), frontend-derived "next sync in ~Xm", and "failed N times in a row." All 12 connector/vuln frontend test files pass (67 tests). The UI-facing `last_error` value IS correctly sanitized — but see CR-03 re: the sibling `SyncLog.error_message`/structured-log leak, which undermines the broader "trustworthy grounding data" framing even though it doesn't break this literal UI claim |

**Score:** 5/6 truths verified (1 partial/failed: REL-04 mobile path)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/connectors/wiz.py` | `authenticate() -> bool` returning `True` on success | VERIFIED | Line 189: `return True` |
| `backend/app/connectors/rapid7.py` | no-arg `__init__` + async `authenticate` + config-driven `verify_tls` | VERIFIED | Lines 25, 40, 61, 70 |
| `backend/tests/test_connectors/test_wiz_connector.py` | Wiz MockTransport integration test | VERIFIED | 4 tests, all pass |
| `backend/tests/test_connectors/test_rapid7_connector.py` | Rapid7 MockTransport integration test | VERIFIED | 5 tests, all pass |
| `backend/tests/test_connectors/test_crowdstrike_connector.py` | CrowdStrike HTTP-layer test | VERIFIED | 6 tests, all pass |
| `backend/tests/test_connectors/test_defender_connector.py` | Defender HTTP-layer test | VERIFIED | 6 tests, all pass |
| `backend/tests/test_connectors/test_nessus_connector.py` | Nessus HTTP-layer test | VERIFIED | 5 tests, all pass |
| `backend/tests/test_connectors/test_qualys_connector.py` | Qualys HTTP-layer test | VERIFIED | 6 tests, all pass |
| `backend/app/ticketing/providers.py` | `TicketProvider` str-Enum | VERIFIED | Consumed throughout dispatch.py/service.py/rule_engine.py |
| `backend/app/ticketing/dispatch.py` | `TicketingClient` Protocol + adapters + factory | VERIFIED | `build_ticketing_client` used by router._get_ticketing_client |
| `backend/app/ticketing/jira_client.py` | canonical JiraClient with comment/transition/close | VERIFIED | `app/connectors/jira_client.py` deleted, no dangling imports (confirmed by review + grep) |
| `backend/app/ticketing/github_client.py` | GitHubClient with add_comment/close_issue | VERIFIED | Used by daily_sync.py's GitHub branch |
| `backend/tests/test_ticketing_dispatch.py` | asserts provider:'JIRA'/'GITHUB' reach the right client | VERIFIED | 16 tests, all pass |
| `backend/alembic/versions/030_add_connector_health_columns.py` | additive migration, `down_revision=029` | VERIFIED | Single alembic head confirmed |
| `frontend/src/components/connectors/sync-status-pill.tsx` | non-crashing status mapping | VERIFIED | `__never` fallback key; 20 pill+card tests pass |
| `frontend/src/components/connectors/connector-card.tsx` | last-error + next-sync + failure-count | VERIFIED | Confirmed via source read + passing tests |
| `frontend/src/components/vulnerabilities/ticket-provider-picker.tsx` | provider picker w/ loading/empty/error | VERIFIED | Desktop-only; not reachable from mobile confirm (see gap) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `sync.py` auth-truthiness check | `wiz.py::authenticate` | `bool` return contract | WIRED | `return True` on success |
| `rapid7.py httpx.AsyncClient` | `config.verify_tls` | `verify=self.verify_tls` | WIRED | Line 70; defaults `True` |
| `router.py` mutating endpoints | `build_ticketing_client` (dispatch.py) | `_get_ticketing_client(provider)` | WIRED | Proven by `test_post_tickets_provider_jira_reaches_jira_client_and_persists_jira` |
| `drill-content.tsx` (desktop `ConfirmModal` branch) | `TicketProviderPicker` selected provider | state replacing hardcoded `'ASANA'` | WIRED | `confirmDisabled={!ticketProvider}` gates the create action |
| `drill-content.tsx` (mobile `renderConfirm` branch, via `drill-panel-mobile.tsx`) | `TicketProviderPicker` selected provider | — | **NOT WIRED** | `renderConfirm` slot never receives/exposes `ticketProvider`; mobile confirm dialog has no picker (CR-01) |
| `daily_sync.py` GitHub branch | `GitHubClient.get_issue`/`close_issue`/`add_comment` | provider dispatch on `Ticket.provider == GITHUB` | WIRED | `_sync_github_tickets`, tested by `test_github_sync.py` |
| `add-connector wizard` | `connectors/router.py CONNECTOR_CATEGORIES` | `GITHUB` category registration | WIRED | `router.py:42` |
| `connector-card.tsx` | `ConnectorConfig.last_error`/`consecutive_failure_count`/`last_sync_at`/`sync_interval_minutes` | conditional render on failed status + derived next-sync | WIRED | Confirmed via source + passing tests |
| `sync.py` write-back (`connector_config.last_error`) | `_sanitize_error` | redact-before-store | WIRED | Line 199: `connector_config.last_error = sanitized` |
| `sync.py` write-back (`log.error_message`, `SyncLog` row) | `_sanitize_error` | — | **NOT WIRED** | Line 196: `log.error_message = str(e)[:2000]` — raw, unsanitized (CR-03); then logged verbatim by `scheduler.py`'s `background_sync_complete` event |

### Behavioral Spot-Checks / Test Runs

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 6 scanner connector HTTP-layer tests pass | `pytest tests/test_connectors/ -q` | 33 passed | PASS |
| Ticketing dispatch, clients, GitHub sync, connector health tests pass | `pytest tests/test_ticketing_dispatch.py tests/test_ticketing_clients.py tests/test_github_sync.py tests/test_connector_health.py -q` | 51 passed | PASS |
| No hardcoded `verify=False` remains in connectors | `grep -rn "verify=False" app/connectors/` | empty | PASS |
| Alembic migration chain has a single head | `alembic heads` | `030_add_connector_health_columns (head)` | PASS |
| Frontend connector/vuln component tests pass | `npx vitest run src/components/connectors src/components/vulnerabilities/{ticket-provider-picker,drill-panel,drill-panel-mobile}*` | 12 files / 67 tests passed | PASS |
| No debt markers (TBD/FIXME/XXX/TODO/HACK) in phase-touched files | grep across 20 modified files | none found | PASS |
| Duplicate `POST /sync-status` route still present (CR-02, not independently re-fixed) | `grep -n "sync-status" app/ticketing/router.py` | two matches: lines 348, 1251 | Confirms review finding — see Anti-Patterns |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REL-01 | 23-01 | Wiz connector completes full sync (authenticate return-type fix) | SATISFIED | `wiz.py::authenticate` returns `True`; test coverage passes |
| REL-02 | 23-01 | Rapid7 connector completes full sync (no-arg init + authenticate) | SATISFIED | `rapid7.py` no-arg `__init__` + `authenticate`; test coverage passes |
| REL-03 | 23-01, 23-02 | All six connectors have HTTP-layer integration tests | SATISFIED | 6 test files, 33 passing tests |
| REL-04 | 23-03, 23-04, 23-08 | Analyst can create a Jira ticket directly from a vulnerability | **PARTIALLY SATISFIED** | Desktop path fully wired and tested; mobile path hardcodes ASANA (CR-01) — not a regression from pre-phase state, but the phase's stated fix is incomplete for this surface |
| REL-05 | 23-03, 23-04, 23-05 | GitHub ticketing finished end-to-end or retired | SATISFIED | Registered in all 4 backend points; daily_sync branch; tests pass |
| REL-06 | 23-06, 23-07, 23-09 | Per-connector sync health visible in Connectors UI | SATISFIED (UI claim literal) with adjacent unresolved defect (CR-03, log/DB secret leak in `SyncLog.error_message`, sibling to the correctly-sanitized `last_error` field) | Migration + normalization + card UI all verified; CR-03 doesn't break the literal UI claim but weakens the phase's "trustworthy grounding data" framing |

No orphaned requirements — all of REL-01 through REL-06 are claimed by at least one plan's `requirements:` frontmatter, matching REQUIREMENTS.md's phase-23 mapping exactly.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/vulnerabilities/drill-content.tsx` | ~55-60, 142-168, 314-333 | Mobile `renderConfirm` slot never exposes/gates `ticketProvider` | 🛑 BLOCKER (CR-01) | Every mobile ticket creation silently fires as ASANA regardless of tenant config/analyst choice — reintroduces the exact bug class (D-07) this phase's backend work fixed |
| `backend/app/connectors/sync.py` (line ~196) + `backend/app/connectors/scheduler.py` (line ~46) | — | `SyncLog.error_message` bypasses `_sanitize_error`, logged verbatim | 🛑 BLOCKER (CR-03) | Secrets (Bearer/Basic tokens) in an upstream HTTP error body can reach the `sync_logs` table and structured application logs on every background sync failure |
| `backend/app/ticketing/router.py` (lines 348, 1251) | — | Duplicate `POST /sync-status` route; the older handler (with its own audit-log call) is permanently unreachable | ⚠️ WARNING (CR-02, not in scope of the two flagged findings but independently confirmed) | The legacy `trigger_ticket_sync` audit trail entry (`ticket.sync_status`) never fires; not a stated success-criterion failure, but a genuine dead-code/audit-gap worth closing alongside the two gaps above |
| `backend/app/ticketing/schemas.py` (100-107) | — | `TicketRuleAction.provider` has no enum/pattern validation | ⚠️ WARNING (CR review WR-01) | A garbage `action.provider` on a manually-triggered rule raises an unhandled 500 instead of a 400; scheduler path already guards this |
| `backend/app/connectors/wiz.py` (155-189) | — | `authenticate`'s `config` param is accepted but never read (no `verify_tls` parity) | ℹ️ INFO (CR review WR-02) | Not exploitable (SaaS-only, secure httpx default); inconsistent with Nessus/Rapid7 pattern |

### Deferred Items (from `deferred-items.md`, informational only)

- **Qualys lowercase-only key reads** (`_fetch_all_hosts`, `_fetch_all_detections`, KB-prefetch, `_fetch_kb_entries`): plausible production bug against a real Qualys tenant using uppercase `<ID>`/`<QID>` XML tags — would silently break pagination cursoring, host/detection association, and KB enrichment. Explicitly out of scope for the 23-02 test-authoring plan (D-22); test fixture deliberately pins the CURRENT working (lowercase) path rather than papering over the mismatch. Not required by any of REL-01..06's literal text; flagged for a future connector-hardening phase.
- **mypy-baseline drift in `google_workspace.py`**: pre-existing, unrelated to this phase's diff (confirmed via stash test).

## Human Verification Required

None. All six success criteria are resolvable from code/tests without live credentials or visual/UX judgment. The two gaps above (CR-01 mobile ticket provider, CR-03 log/DB secret leak) are both objectively demonstrated by direct code reads and are actionable without further human input — they should route to a closure plan, not a UAT session.

## Gaps Summary

Two gaps block full goal achievement, both surfaced independently in the code review and confirmed here by direct source inspection:

1. **REL-04 is only fully met on desktop.** The mobile ticket-creation confirm flow (`drill-panel-mobile.tsx` -> `DrillContent`'s `renderConfirm` slot) never renders the provider picker built in Plan 08, so `ticketProvider` state stays `null` for the whole mobile flow and every mobile ticket creation silently defaults to `'ASANA'`. This is the *same defect class* (D-07, "provider silently becomes Asana") the phase's backend work (Plans 03/04) explicitly set out to eliminate — now reintroduced on a frontend surface the phase's own plans didn't audit. The gap was self-disclosed by the 23-08 executor as a "Known Gap," so it is not a surprise, but it does mean the analyst-facing story is incomplete for any tenant using the mobile drill panel with a non-Asana (or Asana-less) provider configuration.

2. **REL-06's "trustworthy" framing has an unresolved sibling defect.** `connector_config.last_error` (what the Connectors UI actually shows) is correctly sanitized — the literal SC#5 claim holds. But `SyncLog.error_message`, populated in the same exception handler two lines away, is not, and is then logged verbatim in the scheduler's structured `background_sync_complete` event on every failed sync. This means a scanner/ticketing credential leaked in an upstream HTTP error body can reach the `sync_logs` table and the application's log stream — not visible to analysts through the product UI, but a real secret-hygiene defect in the exact health-signal subsystem (D-18/D-19) this phase built specifically to be trustworthy.

Both gaps have concrete, scoped fixes documented above (also detailed in `23-REVIEW.md` CR-01 and CR-03) and should be closed via `/gsd-plan-phase 23 --gaps` before this phase is considered fully shippable.

---

_Verified: 2026-07-27T14:49:55Z_
_Verifier: Claude (gsd-verifier)_
