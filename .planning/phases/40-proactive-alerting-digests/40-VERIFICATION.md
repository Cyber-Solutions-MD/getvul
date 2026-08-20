---
status: passed
phase: 40-proactive-alerting-digests
requirements: [ALERT-01, ALERT-02, ALERT-03]
must_haves_verified: 3
must_haves_total: 3
human_verification: 2
verified_by: orchestrator (inline — gsd-verifier subagent terminated 3× on transient stream/sleep API errors; goal-backward checks re-run directly against source + test suites)
verified: "2026-08-20"
---

# Phase 40: Proactive Alerting & Digests — Verification

**Goal:** Analysts and owners learn about a new critical exposure or a looming SLA breach from GetVul pushing to them, not from opening the dashboard and finding out late.

**Verdict:** ✅ PASSED — 3/3 automated success criteria verified against the actual codebase; 2 live-delivery items deferred on-trust to `/gsd-verify-work 40`.

## Method

The `gsd-verifier` subagent was dispatched three times and terminated each time on transient environment API errors (computer-sleep mid-response ×2, then a 600s stream stall) before it could write this file. Its recovered partial output reported all checks passing. Verification was therefore completed inline by the orchestrator via goal-backward source inspection (grep of the real implementations, not SUMMARY trust) plus direct test-suite execution. Evidence below is reproducible.

## Success Criteria (goal-backward)

### 1. New KEV-listed / high-EPSS CVE matching a tenant asset fires a targeted alert to the right channel — ✅ VERIFIED (ALERT-01)

- `backend/app/notifications/alerts.py`: `run_alert_checks` → `_check_new_kev_epss` (line 248) performs guard-table subtraction against the durable `AlertingGuard` table (lines 315–351), seeding silently on first pass (D-06 cold-start) and firing only on genuine future transitions; `_fire_kev_epss_alert` resolves the owner via the extracted `get_directory_user` (`backend/app/assets/directory.py`), dispatches to the tenant channel + owner email + in-app twin, writes an audit row, and inserts a guard row to prevent re-fire.
- A finding both KEV-listed and above the EPSS threshold fires exactly once (KEV precedence at the SQL predicate).
- Tests: `backend/tests/test_alerts_kev_epss.py` — 5/5 green (detection, silent seed, single-fire, no-re-fire, owner routing).

### 2. Scheduled per-owner / per-team digests deliver on the in-process scheduler, no new infra — ✅ VERIFIED (ALERT-02)

- `backend/app/notifications/digests.py`: `run_digests` (line 549), `_send_hour_due` wall-clock gate (line 128), `_assemble_sections` (SLA due/breaching from Phase 36 + Phase 39 exception expiry, line 185), `_render_digest_html` escaped HTML (line 345), empty-suppression, top-N, per-owner (email) + per-team (shared channel) routing.
- `backend/app/connectors/scheduler.py` (lines 381–395): digest-dispatch block runs every tick on the existing in-process asyncio scheduler; the send-hour gate lives inside `run_digests`. No new infra.
- `backend/app/email.py` (lines 23–62): additive `html_body` multipart/alternative support; None path byte-for-byte unchanged.
- Tests: `backend/tests/test_digests.py` — 7/7 green.

### 3. Alert rules and delivery channels are tenant-configurable on a settings page, every change audited — ✅ VERIFIED (ALERT-03)

- `backend/app/tenants/router.py`: `AlertingConfigUpdate` validation gate (line 137), `alerting_config` PATCH branch with `model_validate` + fail-closed `alerting.config_update` audit event (lines 423–443), GET /settings exposure via `_safe_alerting` (line 306, no channel secrets — D-19), and the self-targeted `POST /settings/alerting/test-digest` preview endpoint with distinguishable empty-vs-error responses (E1 backstop).
- Frontend `AlertingDigestsPane` (`frontend/src/components/settings/alerting-digests-pane.tsx`) registered across `microcopy.ts` (category + label), `settings-sidebar-shell.tsx` (`ALL_CATEGORIES` + `ADMIN_ONLY`), and `page.tsx` (import + `case 'alerting'` + allow-list). Three section cards, RBAC owner-gate, mandatory loading/empty/error states, "Send test digest" action.
- Tests: `backend/tests/test_alerting_settings.py` — 8/8 green; `frontend` settings suite — 57/57 green (8 files).

## Requirement traceability

| Req | Status in REQUIREMENTS.md | Closed by |
|-----|---------------------------|-----------|
| ALERT-01 | [x] | 40-05 (designated closer) |
| ALERT-02 | [x] | 40-05 |
| ALERT-03 | [x] | 40-05 |

All 3 phase requirement IDs accounted for; no orphans.

## Test evidence (re-run at verification)

- Phase 40 backend: `test_alerts_kev_epss.py` + `test_digests.py` + `test_alerting_settings.py` → 15 passed, 5 xpassed, 0 failed.
- Adjacent regression: `test_sla_policy.py` + `test_scheduler_*` + `test_exceptions_*` → 75 passed, 0 failed.
- Frontend: `src/components/settings` → 57 passed, 0 failed.

## Human verification (deferred on-trust to `/gsd-verify-work 40`)

The 40-05 Task 3 blocking human-verify checkpoint was **approved on-trust** by the user during execution (consistent with the project's Phase 24–27 / 38 / 39 precedent). Two items require a live environment and were not exercised live:

1. **Live third-party digest delivery** — real Slack/Teams webhook + SMTP send of an owner/team digest; and the "Send test digest" round-trip to the acting admin's own inbox (incl. the E4 cross-client hostname-truncation visual check on Gmail web / Apple Mail).
2. **Live KEV/EPSS real-time alert fire** — trigger a genuine transition on a matched asset; confirm the alert posts to channel + owner email + in-app bell, an audit row appears, and a repeat tick does NOT re-fire.

Both are logic-proven by the automated suites above; only live third-party wiring is unverified. Tracked in STATE.md Deferred Items.

## Gaps

None blocking. Phase goal achieved.
