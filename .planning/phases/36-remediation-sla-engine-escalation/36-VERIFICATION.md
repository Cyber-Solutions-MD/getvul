---
phase: 36-remediation-sla-engine-escalation
verified: 2026-08-14T00:00:00Z
status: human_needed
score: 4/4 must-haves verified (code-level); live-delivery + visual gates require human
overrides_applied: 0
human_verification:
  - test: "Real webhook delivery to a live Slack / Teams-Workflows / PagerDuty endpoint"
    expected: "Configure a real webhook in a scratch tenant, map it to the approaching transition, force an approaching transition, and confirm the message arrives with correct per-channel formatting"
    why_human: "Third-party delivery cannot be asserted in CI without live per-tenant credentials (36-VALIDATION.md Manual-Only Verifications; 36-06 Task 3). This is a known open manual gate, NOT a code failure — the firing loop + channel senders are fully built and unit-proven against monkeypatched httpx."
  - test: "SLA & Escalation admin pane renders on the sunset theme in a running app"
    expected: "/settings → 'SLA & Escalation' shows the three token-styled cards (no zinc-gray/raw hex), Inter + JetBrains Mono only, SaveBar 'Save changes' is the sole gradient element; loading/empty/error states each render per state-patterns.md; D-13 PagerDuty manual-resolution copy and D-15 Teams Workflows setup copy are present"
    why_human: "Visual appearance, theme-token contrast, and live state rendering cannot be asserted in jsdom unit tests (reinforced by memory note: axe/AA sweep never run during execution)"
  - test: "SlaPill visual placement on the real finding row + drill panel"
    expected: "SlaPill renders the server sla_state with correct color/alignment on the desktop table, mobile card, and drill panel in a running browser; drill-panel escalation-history list shows fired events and renders a failed delivery as an amber, audit-only row with NO retry button"
    why_human: "36-01 coverage D6 self-flags jsdom-only proof; no live-browser/Playwright screenshot exists for actual visual placement/contrast"
---

# Phase 36: Remediation SLA Engine & Escalation — Verification Report

**Phase Goal:** Every open finding carries a live, tenant-configurable SLA state driven by its v4.0 risk tier, escalates automatically to the right channel exactly once per state transition, and accumulates MTTR-by-tier data for later reporting — replacing today's flat severity-keyed SLA with a real engine.
**Verified:** 2026-08-14
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (Requirement) | Status | Evidence |
|---|---------------------|--------|----------|
| 1 | **SLA-01** — Tenant-configurable, risk-tier-keyed SLA policy (default critical 7d / high 30d / moderate 90d) computed off the v4.0 risk-exposure tier, editable on an admin settings page | ✓ VERIFIED (live-visual → human) | Engine: `sla_tier_service.py:48` `DEFAULT_TIER_POLICY={"critical":7,"high":30,"moderate":90}`, `tier_for_score` (L56), `get_tier_policy` custom-or-default merge over `Tenant.sla_config` (L90-107). Admin backend: `tenants/router.py` GET/PATCH `sla_config` with validation + Fernet + mask + `require_admin`/`require_owner`. Admin UI: `settings/sla-escalation-pane.tsx` (718L) routed at `settings/page.tsx:47,134-135`. Tests: `test_sla_tier_service.py` 29✓, `test_sla_policy.py` 16✓ |
| 2 | **SLA-02** — Every open finding shows a live SLA state (on-track / approaching / breached) from the policy, visible on the finding row AND drill panel | ✓ VERIFIED (live-visual → human) | Backend read-time resolution: `service.py:141,249,266` attaches `sla_state`/`sla_due_at` via `resolve_state_for_vuln`; carried on both schemas (`schemas.py:76-77,108-109`). Row: `vuln-table.tsx` renders `<SlaPill state dueAt />`. Drill: `drill-content.tsx:718-719` renders `<SlaPill state={v.sla_state} …/>`. Tests: `sla-pill.test.tsx`✓, drill-panel component tests✓ |
| 3 | **SLA-03** — An approaching/breach transition fires the configured channel (Slack / Teams / email / PagerDuty) exactly once per transition, and every escalation is audited | ✓ VERIFIED code-level; **live delivery → human gate** | Firing loop: `sla_tier_service.py:353` `detect_and_escalate` — insert-first once-only reservation via `begin_nested()` + `uq_escalation_once` (`046_add_sla_escalation_events.py:64`), tier-floor + per-transition routing gating, audit every fire (`_audit_escalation_fire` L309, `action="sla.escalation_fire"` L336), one in-app twin per breach. Channels: `escalation_channels.py` `dispatch_channel`+4 senders, SSRF guard (`_validate_webhook_url` L69, `follow_redirects=False`), PagerDuty `event_action="trigger"` only (D-13). Wired: `scheduler.py:337`. History endpoint: `router.py` `GET /{id}/escalations`. D-08 reconcile: `alerts.py:100` `_check_sla_breaches` → no-op. Tests: `test_escalation_channels.py` 33✓, `test_escalation_engine.py` 7✓ |
| 4 | **SLA-04** — MTTR is captured per risk tier and is queryable (feeds Phase 42/43) | ✓ VERIFIED | `remediation_events` table (`047_add_remediation_events.py`, `tier_at_remediation`/`duration_seconds` on `models.py:287-288`); `mark_vulnerability_remediated` helper (`service.py:370`) routed at all 7 REMEDIATED write sites (service.py x2 + ticketing/service.py x2 + daily_sync.py x3); `get_mttr_by_tier` real GROUP-BY aggregate (`service.py:405`), admin-gated `GET /vulnerabilities/mttr/by-tier` (`router.py:269-283`). Tests: `test_mttr.py` 13✓ |

**Score:** 4/4 truths verified at code level. All are code-complete, wired, and proven by automated tests. SLA-01/02/03 additionally carry live-visual / live-delivery checks that CANNOT be asserted in CI (see Human Verification).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/vulnerabilities/sla_tier_service.py` | Tier engine + firing loop | ✓ VERIFIED | 534L; all named functions present + wired into scheduler + service |
| `backend/app/notifications/escalation_channels.py` | 4-channel dispatch + SSRF | ✓ VERIFIED | 298L; `dispatch_channel` + senders + guard |
| `backend/alembic/versions/046_add_sla_escalation_events.py` | Once-only escalation table | ✓ VERIFIED | `uq_escalation_once` UniqueConstraint, up+down |
| `backend/alembic/versions/047_add_remediation_events.py` | MTTR event table | ✓ VERIFIED | chains off 046, up+down |
| `backend/app/tenants/router.py` | sla_config GET/PATCH | ✓ VERIFIED | validation + Fernet + mask + RBAC + `sla.policy_update` audit |
| `backend/app/connectors/scheduler.py` | tick calls new engine | ✓ VERIFIED | L336-337 `run_sla_tier_pass`+`detect_and_escalate`; old `check_sla_breaches` removed |
| `frontend/.../settings/sla-escalation-pane.tsx` | Admin pane | ✓ VERIFIED | 718L; routed; D-13/D-15 copy present (L69,71) |
| `frontend/.../vulnerabilities/drill-content.tsx` | SlaPill + escalation history | ✓ VERIFIED | 1027L; `useVulnEscalations` + SlaPill wired |
| `frontend/.../lib/queries/use-vuln-escalations.ts` | history query hook | ✓ VERIFIED | 35L; GETs `/vulnerabilities/{id}/escalations` |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| scheduler tick | run_sla_tier_pass + detect_and_escalate | `scheduler.py:336-337` per-tenant call | ✓ WIRED |
| detect_and_escalate | dispatch_channel | `sla_tier_service.py:432` after once-only reservation | ✓ WIRED |
| detect_and_escalate | AuditLog | `_audit_escalation_fire` L309-336, `sla.escalation_fire` | ✓ WIRED |
| REMEDIATED transitions | remediation_events | `mark_vulnerability_remediated` at all 7 sites | ✓ WIRED |
| admin pane | GET/PATCH /tenant/settings sla_config | `use-tenant-settings.ts` | ✓ WIRED |
| drill panel | GET /vulnerabilities/{id}/escalations | `useVulnEscalations` → `drill-content.tsx:483,908-910` | ✓ WIRED |
| vuln list/detail response | sla_state/sla_due_at | `service.py:249,266` read-time resolve | ✓ WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| vuln-table / drill SlaPill | `sla_state`,`sla_due_at` | `resolve_state_for_vuln` off `risk_exposure_score` + tenant policy | Yes (computed per finding) | ✓ FLOWING |
| drill escalation history | `escalationsQuery.data` | `GET /{id}/escalations` → `sla_escalation_events` table | Yes (tenant-scoped query) | ✓ FLOWING |
| MTTR endpoint | aggregate rows | `get_mttr_by_tier` GROUP BY over `remediation_events` | Yes (real SQL aggregate) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Tier engine boundaries/fallback/policy (SLA-01/02) | `pytest tests/test_sla_tier_service.py` | 29 passed | ✓ PASS |
| Channel payloads + SSRF + failure handling (SLA-03) | `pytest tests/test_escalation_channels.py` | 33 passed | ✓ PASS |
| Exactly-once firing + floor + routing + audit + D-08 (SLA-03) | `pytest tests/test_escalation_engine.py` | 7 passed | ✓ PASS |
| Policy CRUD + RBAC + Fernet + mask + validation (SLA-01/03) | `pytest tests/test_sla_policy.py` | 16 passed | ✓ PASS |
| MTTR capture across all sites + by-tier aggregate (SLA-04) | `pytest tests/test_mttr.py` | 13 passed | ✓ PASS |
| Admin pane + SlaPill component render | `vitest run sla-escalation-pane / sla-pill` | 23 passed | ✓ PASS |
| Drill panel component render | `vitest run vulnerabilities/*` | 104 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| SLA-01 | 36-01, 36-05, 36-06 | ✓ SATISFIED | Tier engine + policy CRUD + admin pane (live-visual → human) |
| SLA-02 | 36-01, 36-06 | ✓ SATISFIED | Read-time sla_state on list/detail + row/drill SlaPill (live-visual → human) |
| SLA-03 | 36-02, 36-03, 36-05, 36-06 | ✓ SATISFIED (code); live delivery → human | Once-only firing + audit + 4 channels + history + reconcile |
| SLA-04 | 36-04 | ✓ SATISFIED | remediation_events + helper at all sites + by-tier endpoint |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No stubs/TODOs/empty-returns in any Phase-36 source file | ℹ️ Info | The only `vuln.status="REMEDIATED"` assignment is inside the `mark_vulnerability_remediated` helper itself (`service.py:387`) — no bypass sites |

### Known Coverage Notes (not gaps)

- **36-03 D8 — concurrent double-tick IntegrityError branch:** proven by static code review + structural mirror of `seed.py`'s existing `begin_nested()/except/continue` idiom, NOT a live race test. Justified: this single-process asyncio scheduler has no genuine concurrency today; the `uq_escalation_once` branch is defense-in-depth for a future multi-replica scenario. Accepted.
- **VALIDATION.md test-file reference drift (ℹ️ Info):** `36-VALIDATION.md` cites `src/components/vulnerabilities/drill-content.test.tsx`; the actual drill tests live in `drill-panel.test.tsx` + `drill-panel-mobile.test.tsx` (all 104 vuln component tests pass). Filename-reference discrepancy only — coverage exists.

### Tracking-File Discrepancy (documentation, not a code gap)

- `ROADMAP.md:82,99` still shows "4/6 plans executed" and 36-06 unchecked; `REQUIREMENTS.md:30-32` shows SLA-01/02/03 unchecked. Per the SUMMARYs' deliberate shared-ID gate decision, these were intentionally left Pending until 36-06 human-verify sign-off, and per memory (`getvul-execute-phase-tracking-hazards`) executors leave ROADMAP/REQUIREMENTS for the verifier to reconcile. All 6 plans ARE committed (git log: `3e05075`, `b7729b2`, plus 36-01..05). Recommend reconciling ROADMAP to "6/6" and flipping SLA-01/02/03 to `[x]` after the human-verify gate below is signed off.

### Human Verification Required

1. **Live webhook delivery (SLA-03 — 36-06 Task 3, known open manual gate)** — Configure a real Slack / Teams-Workflows / PagerDuty webhook in a scratch tenant, map to the approaching transition, force an approaching transition, confirm the message arrives with correct per-channel formatting. *Why human:* third-party delivery cannot be asserted in CI without live creds. **This is an expected gate, not a failure** — the firing loop + senders are code-complete and unit-proven against monkeypatched httpx.
2. **Admin pane visual + states (SLA-01)** — `/settings → SLA & Escalation`: three token-styled cards on the sunset theme, SaveBar sole gradient, loading/empty/error states, D-13 PagerDuty + D-15 Teams copy present.
3. **SlaPill live visual (SLA-02)** — SlaPill placement/contrast on desktop row, mobile card, and drill panel; escalation-history failed row renders amber with no retry button.

### Gaps Summary

No code gaps found. All four success criteria (SLA-01..04) are delivered as real, wired implementations backed by 98 passing backend tests and 127 passing frontend component tests. The escalation engine, channel senders, once-only gate, audit path, MTTR capture, admin settings API, admin pane, and drill-panel wiring all exist and function at the code level with real data flow end-to-end.

The phase is **not fully signable** only because three checks are inherently un-CI-assertable: (1) live third-party webhook delivery — an explicitly documented manual gate (36-06 Task 3); (2) admin-pane visual/theme rendering; (3) SlaPill live-browser visual placement. These are surfaced as human-verification items per the Escalation Gate pattern, not as failures.

---

_Verified: 2026-08-14_
_Verifier: Claude (gsd-verifier)_

---

## Addendum — Live Human-Verify Session (2026-08-14)

A live run against the local Docker stack (admin `admin@getvul.local`, seeded finding
`CVE-2024-3094` on `prod-web-01.getvul.internal` + 2 escalation events) closed two of the
three human-verification items above and surfaced two **pre-existing** bugs (Phase 11 drill
scaffolding, NOT Phase 36 defects) that were blocking the path to the Phase 36 drill UI.

### Human-verify items now CLOSED (live)

- **Item 2 — Admin pane visual + states (SLA-01):** ✅ Three token-styled cards render on the
  sunset theme in **both dark and light**; SaveBar "Save changes" is the sole gradient CTA
  (appears only on dirty); empty state ("No escalation channels configured"), error state
  (amber PartialFailureBanner), D-13 PagerDuty copy, and D-15 Teams-Workflows copy (shown on
  Teams channel enable) all present; per-transition Approaching/Breach checkboxes render. Zero
  console errors.
- **Item 3 — SlaPill + escalation history live (SLA-02/03):** ✅ Drill header shows the `-1d`
  breached pill matching the row (D-11); escalation-history lists Slack "On track →
  Approaching" (delivered) and PagerDuty "Approaching → Breached" as an **amber, audit-only row
  with no retry button** ("PagerDuty delivery failed — Invalid routing key · fired …", D-08),
  transition record still visible (D-07).
- **Item 1 — Live webhook delivery (SLA-03):** ⏳ STILL OPEN — inherently un-CI-assertable;
  needs real per-tenant Slack/Teams/PagerDuty creds. Unchanged.

### Bugs found + fixed during the session (pre-existing, Phase 11 scope)

1. **Drill crashes on any finding with a CVSS score.** The backend serializes numeric columns
   (`cvss_v3_score`, `epss_score`) as JSON **strings** (`"10.0"`); `drill-content.tsx` typed
   `cvss_v3_score` as `number` and called `.toFixed()` → `TypeError`, error boundary killed the
   panel. **Fixed:** coerce `Number(...)` into `cvssLabel` (guarded `Number.isFinite`), widen
   type. Regression test added (mocks CVSS as a string). The vuln **list** endpoint omits
   `cvss_v3_score`, so only detail-consumers hit this — and component tests mocked it as a
   number, hiding it.
2. **Clicking a CVE-bearing row 422s the whole drill.** The `?cve=` deep-link carried a CVE
   string into the UUID-only detail/escalations endpoints (`vuln_id: uuid.UUID`). The CVE→UUID
   resolution that `use-vulnerability-detail.ts` *documents* was unimplemented. **Fixed:** added
   `resolvedDrillId` in the vulnerabilities `page.tsx` (resolves against the loaded list, guards
   the group-by-host union). Regression test added (asserts detail hook receives the UUID, never
   the CVE).

Both fixes: `tsc` + eslint clean; drill-panel (27) + page (9) + mobile-drill (17) tests green.
Root cause of #1 (Decimal→string serialization) left for a future backend serializer pass —
tracked in memory `getvul-decimal-serialized-as-string`. Contract for #2 tracked in
`getvul-drill-panel-cve-uuid-resolution`.

_Live-verified: 2026-08-14 — Claude (Opus 4.8)_
