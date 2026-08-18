---
phase: 38-remediation-campaigns
verified: 2026-08-18T09:51:10Z
status: passed
score: 27/27 must-haves verified
overrides_applied: 0
---

# Phase 38: Remediation Campaigns Verification Report

**Phase Goal:** An analyst can act on a whole class of findings at once — group by shared fix
across every affected asset/owner, bulk-create/assign tickets respecting existing routing, and
watch the campaign burn down live — instead of ticketing one finding at a time.
**Verified:** 2026-08-18T09:51:10Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria — CAMP-01..04)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **CAMP-01** — Group findings by shared fix across multiple assets/owners into a campaign in one action | ✓ VERIFIED | `POST /api/v1/campaigns {remediation_id}` (`app/campaigns/router.py:112-127`) wraps the pre-existing cross-asset `Vulnerability.remediation_id` grouping key (`app/vulnerabilities/remediation_service.py`) in a persisted `Campaign` row via `get_or_create_campaign()`. D-11 race-safe get-or-create confirmed live: DB partial unique index `uq_campaign_active_remediation ... WHERE closed_at IS NULL` verified directly against the running Postgres container (`\d+ campaigns`). Frontend entry point `/dashboard/vulnerabilities/remediations` ships a "Start campaign" CTA per grouped row (`remediations-table.tsx`) wired to `useStartCampaign()`, which POSTs and routes to `/dashboard/campaigns/{id}` for both fresh-create and D-11 already-existed (redirect toast verified in `use-campaign-mutations.test.ts`). Backend tests `test_create_campaign_new`, `test_create_campaign_reopens_existing`, `test_campaign_unique_active_index`, `test_new_campaign_after_close`, `test_campaign_cross_tenant_isolation` all pass live (24/24 `pytest tests/test_campaigns.py`). |
| 2 | **CAMP-02** — Bulk-create/assign tickets for a campaign, respecting existing owner routing | ✓ VERIFIED | `bulk_create_campaign_tickets()` (`app/campaigns/service.py:249-372`) carves live campaign members into one ticket per distinct `owner_email` bucket, derived byte-identically to `ticketing/service.py:614`'s `(mdm or {}).get("humaans_email")` (D-05, proven by `test_owner_derivation_matches_ticketing_service`). Owner-less findings land in the `None`/unassigned bucket rather than being dropped (D-08, `test_bulk_assign_unassigned_bucket`). Re-runs adopt already-ticketed members via a per-vulnerability unresolved-`Ticket` check rather than duplicating (D-06, `test_bulk_assign_adopts_existing_ticket` / `test_bulk_assign_idempotent_rerun`). `POST /api/v1/campaigns/{id}/bulk-assign` is live in the running backend's OpenAPI schema. Frontend "Create N tickets" CTA on `/dashboard/campaigns/[id]` wires `useBulkAssign()`, renders the amber (never red) partial-failure banner on `failed_owners`. |
| 3 | **CAMP-03** — Live per-campaign progress (open/in-progress/done, % remediated) and campaign MTTR | ✓ VERIFIED | `get_campaign_progress()` computes total/open/in_progress/done/pct_remediated fresh on every read (compute-on-read, D-07), counting `REMEDIATED` in `done` (Pitfall-2 regression guard, `test_progress_counts_include_remediated`) while excluding `SUPPRESSED`/`FALSE_POSITIVE` from the denominator (D-18). Zero-member guard proven (`test_progress_zero_member_no_crash` — no `ZeroDivisionError`, HTTP 200). `get_campaign_mttr()` averages `RemediationEvent.duration_seconds` joined through `remediation_id`, `float`-coerced (Pitfall 7), `None` (never 0) when nothing remediated (`test_campaign_mttr_average`, `test_campaign_mttr_null_when_none_remediated`). D-03 live-membership growth proven (`test_live_membership_grows`). Frontend `CampaignBurndownCard` wraps `RiskRing` (score=pct_remediated) with a status-family breakdown row and MTTR line, proven zero-crash on 0/0 and free of severity-class leakage (`campaign-burndown-card.test.tsx`, 7 tests). |
| 4 | **CAMP-04** — All campaign actions are audited | ✓ VERIFIED | `campaign.create` written exactly once, only on a genuinely new campaign (`test_create_campaign_new`/`test_create_campaign_reopens_existing`). `campaign.bulk_assign` written on **every** run including a no-op re-run (D-10, `test_bulk_assign_endpoint_audited_every_run`). `campaign.close` written on manual close (real-actor, `test_campaign_actions_audited`) and on lazy auto-complete (system-actor `system:campaign-complete`, exactly once, `test_auto_complete_audited_once`). `campaign.reactivate` written exactly once on recurrence after auto-complete (`test_reopen_reactivates_campaign`); a manually-closed campaign stays sticky and never reactivates (`test_manual_close_is_sticky_no_reactivation`). All writes go through `app/audit.py::audit()` (fail-closed, BL-04/WR-12) except the two lazy system-actor rows, which mirror the pre-existing `reopen_vulnerability` direct-`AuditLog`-construction precedent. |

**Score:** 4/4 roadmap success criteria verified.

### Supplementary Plan-Level Truths (must_haves across 38-01..05)

All 23 additional plan-level `must_haves.truths` entries across the 5 plans were checked against the live codebase and running stack (not just SUMMARY claims). All pass:

| Plan | Truth (abbreviated) | Status |
|------|----------------------|--------|
| 38-01 | POST persists 1 row / GET reads it back | ✓ VERIFIED (test + live DB) |
| 38-01 | audit-once-on-create (D-15) | ✓ VERIFIED |
| 38-01 | RBAC: viewer 403 write / 200 read (D-16) | ✓ VERIFIED (`require_analyst`/`require_viewer` gates confirmed in `router.py`) |
| 38-01 | Tenant-scoped WHERE on every query | ✓ VERIFIED (`_get_campaign_or_404`, `list_campaigns`, `get_campaign_progress` all filter `tenant_id`) |
| 38-01 | D-11 relaunch opens existing, no dup/no 2nd audit | ✓ VERIFIED |
| 38-01 | zero/single-member campaign renders pct=0, no 500 | ✓ VERIFIED |
| 38-01 | zero-member read: 0/0/0/0, no auto-complete audit | ✓ VERIFIED (`is_complete` requires `total > 0`) |
| 38-02 | one external ticket per distinct owner (D-04) | ✓ VERIFIED |
| 38-02 | owner derivation == ticketing/service.py (D-05) | ✓ VERIFIED |
| 38-02 | owner-less finding still ticketed (D-08) | ✓ VERIFIED |
| 38-02 | bulk-assign audited every run incl. no-op (D-10) | ✓ VERIFIED |
| 38-02 | created_by_rule = bare remediation_id (D-20) | ✓ VERIFIED (`service.py:356`) |
| 38-02 | bulk-assign requires require_analyst | ✓ VERIFIED |
| 38-02 | re-run adopts, no duplicate (D-06/D-10) | ✓ VERIFIED |
| 38-02 | live members status IN (OPEN,IN_PROGRESS), N-rows-share-1-url | ✓ VERIFIED (`Ticket.vulnerability_id` stays singular) |
| 38-03 | MTTR = avg RemediationEvent.duration_seconds, null when none (D-12) | ✓ VERIFIED |
| 38-03 | done only at REMEDIATED, ticket-closed alone ≠ done (D-09) | ✓ VERIFIED |
| 38-03 | new-asset finding counted live, no membership row (D-03) | ✓ VERIFIED |
| 38-03 | POST /close sets manual fields + 1 audit row | ✓ VERIFIED |
| 38-03 | lazy auto-complete: 1 system-actor audit row, idempotent (D-13/19) | ✓ VERIFIED |
| 38-03 | system-actor rows never client-derived | ✓ VERIFIED (constructed only from server-computed `progress` dict) |
| 38-03 | recurrence after auto-complete reactivates (D-14) | ✓ VERIFIED |
| 38-03 | manual close sticky, no reactivation (D-17) | ✓ VERIFIED |
| 38-03 | SUPPRESSED/FALSE_POSITIVE excluded from denominator (D-18) | ✓ VERIFIED |
| 38-03 | auto-complete audits exactly once, no dup on 2nd read (D-19) | ✓ VERIFIED |
| 38-04 | Campaigns nav item routes to /dashboard/campaigns | ✓ VERIFIED (`nav-items.ts:49`) |
| 38-04 | list page renders UI-SPEC columns, row click navigates | ✓ VERIFIED |
| 38-04 | status pill violet ACTIVE / green COMPLETE, never severity | ✓ VERIFIED (`campaign-status-ribbon.tsx`, no severity class present) |
| 38-04 | hooks staleTime:0 (D-07) | ✓ VERIFIED (`use-campaigns.test.ts`) |
| 38-04 | empty/loading/error states, WR-13 branch order | ✓ VERIFIED |
| 38-04 | singularization at M=1 | ✓ VERIFIED |
| 38-05 | entry point lists remediation groups + Start campaign CTA | ✓ VERIFIED |
| 38-05 | D-11 redirect toast verbatim on already_existed | ✓ VERIFIED |
| 38-05 | Create tickets CTA POSTs bulk-assign, "Create N tickets" label | ✓ VERIFIED |
| 38-05 | partial bulk-create failure -> amber banner, never red | ✓ VERIFIED |
| 38-05 | burndown ring + breakdown + MTTR on detail rail | ✓ VERIFIED |
| 38-05 | Close campaign routed through destructive dialog | ✓ VERIFIED (dialog gating confirmed; see Anti-Patterns note on default-focus) |
| 38-05 | zero-member burndown 0%, no crash (E6) | ✓ VERIFIED |
| 38-05 | D-03/D-10 notes render on detail | ✓ VERIFIED (verbatim copy present in `[id]/page.tsx`) |
| 38-05 | singularization across burndown/member/owner counts | ✓ VERIFIED |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/049_add_campaigns.py` | campaigns table + partial unique index | ✓ VERIFIED | Applied live; `alembic current` = `049_add_campaigns (head)`; `\d+ campaigns` shows `uq_campaign_active_remediation ... WHERE closed_at IS NULL` |
| `backend/app/campaigns/models.py::Campaign` | identity+lifecycle-only model | ✓ VERIFIED | No progress/percentage/member-count columns (D-07 honored) |
| `backend/app/campaigns/service.py` | get_or_create/get_progress/get_mttr/bulk_create/apply_lifecycle_transition/list_campaigns | ✓ VERIFIED | All 6 functions present, read in full |
| `backend/app/campaigns/router.py` | POST/GET/GET-detail/close/bulk-assign | ✓ VERIFIED | All 4 endpoints confirmed live via `curl http://localhost:8000/openapi.json` against the running `getvul-backend-1` container |
| `backend/app/campaigns/schemas.py` | request/response schemas, extra=forbid | ✓ VERIFIED | `CampaignCreateRequest`/`CampaignBulkAssignRequest` both `extra="forbid"` |
| `backend/tests/test_campaigns.py` | full CAMP-01..04 coverage | ✓ VERIFIED | 24/24 passed live (`pytest tests/test_campaigns.py -q`) |
| `frontend/src/lib/queries/use-campaigns.ts` | useCampaigns/useCampaignDetail | ✓ VERIFIED | staleTime:0 confirmed in test |
| `frontend/src/lib/queries/use-campaign-mutations.ts` | start/bulkAssign/close mutations | ✓ VERIFIED | D-11 toast branching confirmed |
| `frontend/src/components/campaigns/*` (7 components) | table/chip-bar/ribbon/burndown/remediations-table | ✓ VERIFIED | All present, exceed min_lines, all tests green |
| `frontend/src/app/(authed)/dashboard/campaigns/page.tsx` | list view | ✓ VERIFIED | 162 lines, ErrorBoundary>Suspense>Inner, WR-13 order |
| `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx` | detail view | ✓ VERIFIED | 394 lines, two-column sticky rail |
| `frontend/src/app/(authed)/dashboard/vulnerabilities/remediations/page.tsx` | entry point | ✓ VERIFIED | 135 lines, Start campaign wired |
| `frontend/src/components/shell/nav-items.ts` | Campaigns WORKFLOW_ITEMS entry | ✓ VERIFIED | `grep -n "Campaigns"` matches line 49 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/main.py` | `app/campaigns/router.py` | `app.include_router(campaigns_router, prefix="/api/v1/campaigns")` | ✓ WIRED | `grep -n campaigns app/main.py` shows import (line 31) + registration (line 319) |
| `app/campaigns/service.py` | `app/vulnerabilities/models.py::Vulnerability` | live `WHERE remediation_id` join | ✓ WIRED | `get_campaign_progress`/`bulk_create_campaign_tickets` both join on `remediation_id` |
| `app/campaigns/service.py::bulk_create_campaign_tickets` | `app/ticketing/dispatch.py`/`app/ticketing/models.py::Ticket` | `client.create()` + N-rows-share-1-url | ✓ WIRED | Confirmed in code; `created_by_rule=campaign.remediation_id` |
| `app/campaigns/service.py::get_campaign_mttr` | `app/vulnerabilities/models.py::RemediationEvent` | AVG join on `remediation_id` | ✓ WIRED | Confirmed in code, `test_campaign_mttr_average` passes |
| `frontend/use-campaigns.ts` | `/api/v1/campaigns` | `api()` fetch | ✓ WIRED | Confirmed URLs in `use-campaigns.test.ts` |
| `frontend/campaigns/page.tsx` | `campaigns-table.tsx` | renders table with `useCampaigns` data | ✓ WIRED | |
| `frontend/campaigns/page.tsx` | `/dashboard/campaigns/{id}` | `onRowClick` → `router.push` | ✓ WIRED | `grep -n router.push` matches; `campaigns-table.tsx` has zero `useRouter` import |
| `frontend/vulnerabilities/remediations/page.tsx` | `POST /api/v1/campaigns` | `useStartCampaign` mutation → route to detail | ✓ WIRED | D-11 already_existed branch confirmed in `use-campaign-mutations.test.ts` |
| `frontend/campaigns/[id]/page.tsx` | `POST /{id}/bulk-assign`, `POST /{id}/close` | `useBulkAssign`/`useCloseCampaign` | ✓ WIRED | Confirmed in code (dialogs gate both) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `campaigns-table.tsx` rows | `CampaignSummary[]` | `GET /api/v1/campaigns` → `list_campaigns()` + `get_campaign_progress()` (live SQL aggregation over `vulnerabilities`) | Yes — confirmed via live Postgres query shape, not a static return | ✓ FLOWING |
| `campaign-burndown-card.tsx` | `pctRemediated`/`open`/`in_progress`/`done`/`mttrSeconds` | `GET /{id}` → `get_campaign_progress()` + `get_campaign_mttr()` (both real SQL aggregations, `func.count()`/`func.avg()`) | Yes | ✓ FLOWING |
| `remediations-table.tsx` rows | grouped remediation rows | `GET /api/v1/vulnerabilities/remediations/grouped` (pre-existing Phase-36-era endpoint, unmodified) | Yes | ✓ FLOWING |
| `[id]/page.tsx` member table | `MemberHost[]` | `GET /vulnerabilities/remediations/{id}/hosts` (pre-existing endpoint, reused) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend campaigns test suite green | `pytest tests/test_campaigns.py -q` (live run, this session) | `24 passed` | ✓ PASS |
| Frontend campaigns-related unit tests green | `npm run test -- campaigns remediations campaign-burndown-card ...` (live run) | `9 files / 42 tests passed` | ✓ PASS |
| Full frontend regression green | `npm run test -- run` (live run) | `148 files / 1027 tests passed` | ✓ PASS |
| Frontend production build clean, bundle budget | `npm run build` (live run) | `/dashboard/campaigns` 130 KB, `/dashboard/campaigns/[id]` 157 KB, `/dashboard/vulnerabilities/remediations` 129 KB — all < 250 KB budget | ✓ PASS |
| Campaign routes live on the running backend container | `curl localhost:8000/openapi.json` (live run against `getvul-backend-1`) | 4 campaign paths present (`GET/POST /campaigns`, `GET /{id}`, `POST /{id}/close`, `POST /{id}/bulk-assign`) | ✓ PASS |
| Unauthenticated request rejected | `curl -o /dev/null -w '%{http_code}' localhost:8000/api/v1/campaigns` | `401` | ✓ PASS |
| DB migration applied, partial unique index present | `alembic current` + `\d+ campaigns` against live Postgres | head=`049_add_campaigns`; index present with correct `WHERE` predicate | ✓ PASS |
| ruff clean on campaigns module | `ruff check app/campaigns/` | `All checks passed!` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|--------------|--------|----------|
| CAMP-01 | 38-01, 38-04, 38-05 | Group findings by shared fix into a campaign in one action | ✓ SATISFIED | `[x]` in REQUIREMENTS.md; get-or-create + entry point + list view all live and tested |
| CAMP-02 | 38-02, 38-05 | Bulk-create/assign tickets respecting existing owner routing | ✓ SATISFIED | `[x]` in REQUIREMENTS.md; per-owner carve-up service + UI CTA live and tested |
| CAMP-03 | 38-01 (partial), 38-03, 38-05 | Live per-campaign progress + campaign MTTR | ✓ SATISFIED | `[x]` in REQUIREMENTS.md; compute-on-read progress/MTTR + burndown UI live and tested |
| CAMP-04 | 38-01, 38-02, 38-03 | All campaign actions are audited | ✓ SATISFIED | `[x]` in REQUIREMENTS.md; create/bulk_assign/close/auto-complete/reactivate all write audit rows, proven live |

No orphaned requirements: every CAMP-01..04 ID declared across the 5 phase-38 plans' `requirements:` frontmatter is accounted for above; REQUIREMENTS.md's Traceability table maps all four to Phase 38 with no additional IDs left unclaimed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/components/ui/ConfirmModal.tsx` | 56-60 | `confirmRef.current?.focus()` unconditionally focuses the **Confirm** button on open, regardless of `variant` | ℹ️ Info | 38-UI-SPEC.md's Copywriting Contract for the "Close campaign" destructive dialog specifies "cancel default-focused" as an accessibility safeguard for destructive actions. The shared `ConfirmModal` (a pre-existing component, last touched Phase 15-03, not modified by Phase 38) instead focuses Confirm for every variant including `danger`. This is inherited, app-wide behavior — not introduced by this phase, and not listed as an explicit `must_haves.truth` in 38-05-PLAN.md (only implied by UI-SPEC prose). Does not block CAMP-01..04 achievement. Flagged for a future accessibility pass on `ConfirmModal` itself (affects every `variant="danger"` caller app-wide, not just campaigns). |
| `.planning/phases/38-remediation-campaigns/38-VALIDATION.md` | frontmatter | `nyquist_compliant: false`, `status: draft` never flipped post-execution | ℹ️ Info | Per project memory (`getvul-nyquist-validation-state`), this class of stale flag has repeatedly been found to be a pre-exec artifact never reconciled after execution, not an indicator of a real test-infra gap — consistent with the fact that every Wave-0 file/test this VALIDATION.md lists as "pending" is confirmed to exist and pass live in this verification. Bookkeeping-only; does not affect goal achievement. |
| `backend/app/ticketing/jira_client.py` | `create_ticket()` | Doesn't catch connection-level `httpx` exceptions (only bad status codes) | ℹ️ Info (pre-existing, out of phase-38 scope) | Logged in `deferred-items.md` by the Plan-05 executor (Phase 23 code); worked around at the data layer for the checkpoint smoke test, not a Phase 38 regression. |

### Human Verification Required

None outstanding. The Plan 38-05 Task 3 `checkpoint:human-verify` (full browser click-through of create→bulk-assign→close) was explicitly waived on-trust by the user per this verification's instructions. Per those same instructions, this verification instead confirmed the underlying code paths exist and function: all four campaign endpoints are live on the running backend, the frontend mutation hooks correctly wire to them, the destructive/non-destructive dialog gating is present in code, and the pre-existing SUMMARY documents an independent live API-level lifecycle proof (create → D-11 reopen → detail → bulk-assign → close → list) executed by the Plan-05 executor against the real dev stack before the checkpoint was raised.

### Gaps Summary

No gaps found. All 4 roadmap Success Criteria (CAMP-01..04) and all 23 supplementary plan-level must_haves truths verified directly against the running codebase — not merely against SUMMARY.md claims:

- Backend: migration applied live (confirmed against the running Postgres container), all 4 campaign endpoints live on the running backend container (confirmed via `openapi.json`), full `test_campaigns.py` suite re-run live (24/24 green), `ruff` clean.
- Frontend: full regression suite re-run live (1027/1027 green across 148 files), production build re-run live and clean, all campaigns-specific test files re-run in isolation (42/42 green), bundle budgets confirmed under the 250 KB ceiling.
- Wiring: nav entry, row-click navigation, hook-to-endpoint URLs, and RiskRing's additive (non-forked) prop extension were all traced directly in source, not inferred from prose.
- The two ℹ️-level anti-pattern notes (ConfirmModal default-focus, stale VALIDATION.md frontmatter) are both pre-existing/bookkeeping issues, not Phase 38 regressions, and do not block the phase goal.

---

_Verified: 2026-08-18T09:51:10Z_
_Verifier: Claude (gsd-verifier)_
