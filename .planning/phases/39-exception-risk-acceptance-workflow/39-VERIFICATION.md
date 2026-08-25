---
phase: 39-exception-risk-acceptance-workflow
verified: 2026-08-19T14:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 39: Exception & Risk-Acceptance Workflow Verification Report

**Phase Goal:** False-positive and accept-risk decisions become first-class, governed records
— not an ad-hoc suppress flag — with a mandatory expiry so nothing is silently ignored forever.
**Verified:** 2026-08-19T14:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An analyst can mark a finding/asset/asset-group false-positive or accept-risk via a form requiring justification, an approver, and an explicit scope | ✓ VERIFIED | Backend: `ExceptionCreate` (backend/app/exceptions/schemas.py:50-52) requires `justification` (min_length=1, max_length=1000), `approver_user_id` (UUID, tenant-validated), `expires_at`; `type` Literal[FALSE_POSITIVE,ACCEPTED_RISK], `scope_type` Literal[FINDING,ASSET,ASSET_GROUP]; `grant_exception` (service.py:276) resolves all 3 scope types server-side (39-02). Frontend: `ExceptionGrantDialog` (frontend/src/components/exceptions/exception-grant-dialog.tsx) presents Scope→Approver→Justification→Expires, gates "Grant exception" until all four are filled (D-06), reachable via drill-panel "Accept risk"/"Mark false positive" buttons (drill-content.tsx). 12 scope tests (test_exceptions_scope.py) + 15 dialog tests (exception-grant-dialog.test.tsx) pass. |
| 2 | An accepted-risk item is excluded from active queues, SLA timers, and dashboards until its mandatory expiry date — never permanently silenced | ✓ VERIFIED | `active_exception_subquery(tenant_id, now)` (39-01) is a strict `expires_at > now` correlated EXISTS, threaded into 12+ real call sites: vuln list (`_apply_filters`), SLA read-time/persisted-mirror/escalation (`sla_tier_service.py`, gate: 5 occurrences), risk score, remediation grouped view + hand-rolled host bypass, campaigns progress/bulk-ticket, ticketing rule engine (`find_matching_assets`/`run_rule`), asset badges incl. sla_breach, owner-risk aggregates, dashboard tiles/nav, CSV/exec export, risk_exposure_score rollup. `expires_at` is DB-level `NOT NULL`; `validate_expiry` rejects past/present AND caps at `MAX_EXPIRY_DAYS=365` (D-14) — no infinite/2099 exception possible. Grep gates for all 5 plans (01/02/03/04/05) pass; 44 backend tests (test_exceptions*.py, 5 files) pass; Tier-3 non-exclusion (search.py/sync.py/trends.py) also verified untouched (0 hits). |
| 3 | Every exception records who/why/scope/expiry as a tenant-scoped audit event | ✓ VERIFIED | `audit()` called audit-then-commit for `exception.grant` (payload: type/scope_type/cve_id/vulnerability_id/asset_id/asset_group_id/approver_user_id/justification/expires_at — enriched in 39-02) and `exception.revoke` (user_id/created_at); every query/mutation is tenant-scoped in its WHERE (cross-tenant 404s, not 403s). Verified via `test_grant_revoke_audit_payload`, `test_grant_audit_includes_resolved_target`, `test_cross_tenant_404` — all pass. |
| 4 | An expired exception automatically resurfaces into the active queue with no manual re-trigger | ✓ VERIFIED | Compute-on-read design (D-01/D-04): `active_exception_subquery`'s `expires_at > now` predicate means a lapsed exception simply stops matching on the very next read — no scheduler tick required. Pattern 4 lazy-on-read audit sweep (`sweep_expired_audits`, service.py:226) writes exactly one system-attributed `exception.expire` audit row per lapse, guarded by `resurfaced_audited_at IS NULL` (idempotent — proven by `test_expiry_lazy_audit_once` calling GET twice). D-16 SLA-clock subtraction (39-03, interval-merged, `lapsed_exception_seconds`) prevents an instant-breach escalation storm on resurface — proven by `test_escalation_not_fired_on_resurface` (this was a self-discovered Rule-2 gap that was fixed, not left latent). Human checkpoint (39-08, APPROVED 2026-08-19) independently confirmed live: revoke → immediate reappearance in vuln list + dashboard counts, not instantly SLA-breached. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/exceptions/models.py` | `ExceptionRecord` model | ✓ VERIFIED | Exists, correct class name (not `Exception`), all interface columns present |
| `backend/app/exceptions/service.py` | `active_exception_subquery`, `validate_expiry`, `sweep_expired_audits`, `lapsed_exception_seconds`, `_merge_intervals`, grant/list/revoke | ✓ VERIFIED | All symbols present; `MAX_EXPIRY_DAYS`/`DEFAULT_EXPIRY_DAYS` constants present |
| `backend/app/exceptions/router.py` | grant/list/revoke endpoints, RBAC | ✓ VERIFIED | POST/GET/POST-revoke mounted at `/api/v1/exceptions` in main.py |
| `backend/alembic/versions/050_add_exceptions.py` | migration | ✓ VERIFIED | `alembic heads` shows single clean head `050_add_exceptions`; table shape matches interfaces |
| `backend/tests/test_exceptions*.py` (5 files) | tracer + scope + SLA + consumer + dashboard coverage | ✓ VERIFIED | 44/44 tests pass (8+12+10+7+7) |
| `frontend/src/app/(authed)/dashboard/exceptions/page.tsx` | list page, WR-13 states | ✓ VERIFIED | Exists; 4 page tests pass |
| `frontend/src/components/exceptions/exceptions-table.tsx` | sortable table, no useRouter, live Revoke | ✓ VERIFIED | `useRouter` grep = 0; `useRevokeException` grep ≥ 1; 12 tests pass |
| `frontend/src/components/exceptions/exceptions-chip-bar.tsx` | Type + Scope axes | ✓ VERIFIED | Exists |
| `frontend/src/lib/queries/use-exceptions.ts` | list query hook | ✓ VERIFIED | Exists, staleTime:0 |
| `frontend/src/components/exceptions/exception-grant-dialog.tsx` | 4-field grant form | ✓ VERIFIED | Exists; 15 tests pass |
| `frontend/src/components/exceptions/approver-combobox.tsx` | controlled picker, no mutation | ✓ VERIFIED | `useReassignAsset` grep = 0; 10 tests pass |
| `frontend/src/lib/queries/use-exception-mutations.ts` | grant/revoke mutation hooks | ✓ VERIFIED | Exists; 5 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `vulnerabilities/service.py::_apply_filters` | `exceptions/service.py::active_exception_subquery` | `~active_exception_subquery(...)` | ✓ WIRED | grep count 3 in service.py |
| `main.py` | `exceptions/router.py` | `app.include_router(exceptions_router, prefix="/api/v1/exceptions")` | ✓ WIRED | App boots, routes mounted |
| `sla_tier_service.py` (run_sla_tier_pass, detect_and_escalate) | `active_exception_subquery` + `excepted_seconds` | WHERE exclusion + subtraction | ✓ WIRED | grep counts 5 and 14 respectively; `test_escalation_not_fired_on_resurface` passes |
| `risk_score.py`, `remediation_service.py`, `router.py` (host bypass), `campaigns/service.py`, `ticketing/rule_engine.py` | `active_exception_subquery` | WHERE exclusion | ✓ WIRED | grep gate = 5/5 files; 7 consumer tests pass |
| `assets/router.py`, `users/router.py`, `dashboard.py`, `export.py`, `risk_exposure_service.py` | `active_exception_subquery` | WHERE exclusion | ✓ WIRED | 7 dashboard tests pass; Tier-3 non-application confirmed (0 hits in search/sync/trends) |
| `drill-content.tsx` (Actions) | `exception-grant-dialog.tsx` | Accept risk / Mark false positive buttons | ✓ WIRED | grep count 2 for acceptRisk/markFalsePositive; drill-panel tests (59) pass |
| `use-exception-mutations.ts::useGrantException` | `POST /api/v1/exceptions` | api POST + invalidate + toast | ✓ WIRED | mutation hook tests pass |
| `exceptions-table.tsx` (Revoke) | `useRevokeException` | ConfirmModal → mutate | ✓ WIRED | grep ≥1; confirm-then-mutate tests pass |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `/dashboard/exceptions` table rows | `useExceptions()` result | `GET /api/v1/exceptions` → `list_exceptions` (real DB query, tenant-scoped) | Yes | ✓ FLOWING |
| Vuln list exclusion | query WHERE clause | `active_exception_subquery` (real correlated EXISTS against `exceptions` table) | Yes | ✓ FLOWING |
| Dashboard tiles/badges/export | count queries | Same shared subquery, threaded into 12+ real SQLAlchemy queries (not static returns) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend tracer suite (grant→exclude→expire→revoke→audit) | `pytest tests/test_exceptions.py -q` | 8 passed | ✓ PASS |
| Full scope resolution (FINDING/ASSET/ASSET_GROUP) | `pytest tests/test_exceptions_scope.py -q` | 12 passed | ✓ PASS |
| SLA exclusion + resurface subtraction | `pytest tests/test_exceptions_sla.py -q` | 10 passed | ✓ PASS |
| Consumer sweep (risk score/remediation/campaigns/rule engine) | `pytest tests/test_exceptions_consumers.py -q` | 7 passed | ✓ PASS |
| Dashboard/export/rollup sweep | `pytest tests/test_exceptions_dashboards.py -q` | 7 passed | ✓ PASS |
| Regression: vulnerabilities/campaigns/rule-engine/SLA/escalation/tenant-isolation | `pytest tests/test_vulnerabilities.py tests/test_campaigns.py tests/test_rule_engine.py tests/test_sla_tier_service.py tests/test_escalation_engine.py tests/test_tenant_isolation.py -q` | 96 passed, 0 failed | ✓ PASS |
| Alembic migration head | `alembic heads` | Single clean head `050_add_exceptions` | ✓ PASS |
| Frontend type-check | `npx tsc --noEmit` | 0 errors in exceptions/drill-content/nav-items files | ✓ PASS |
| Frontend exceptions test suites | `npx vitest run src/components/exceptions src/lib/queries/use-exceptions* "src/app/(authed)/dashboard/exceptions"` | 46 passed | ✓ PASS |
| Frontend drill-panel integration | `npx vitest run drill-panel.test.tsx drill-panel-mobile.test.tsx` | 59 passed | ✓ PASS |
| All grep gates (39-01 through 39-07, both backend and frontend) | see individual commands above | All pass at expected counts | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|-------------|--------|----------|
| EXC-01 | 39-01, 39-02, 39-06, 39-07, 39-08 | Mark false-positive / accept-risk with required justification, approver, scope | ✓ SATISFIED | Grant form + all 3 scope types + server-side validation; human-verified live |
| EXC-02 | 39-01, 39-02, 39-03, 39-04, 39-05, 39-06, 39-08 | Mandatory expiry; excluded from active queues, SLA timers, dashboards | ✓ SATISFIED | expires_at NOT NULL + 365d cap; ~20 consumers swept (vuln list, SLA×3 surfaces, risk score, remediation, campaigns, rule engine, asset/owner/dashboard badges, export, risk-exposure rollup) |
| EXC-03 | 39-01, 39-02, 39-06, 39-08 | Every exception emits audit event (who/why/scope/expiry) | ✓ SATISFIED | grant/revoke/expire all audited, tenant-scoped, audit-then-commit |
| EXC-04 | 39-01, 39-03, 39-08 | Expired exceptions auto-resurface with no manual re-trigger | ✓ SATISFIED | Compute-on-read `expires_at > now`; lazy-audit sweep; SLA-clock subtraction prevents instant-breach storm |

**Orphaned requirements check:** REQUIREMENTS.md Phase 39 rows are exactly EXC-01..04; all four are declared across the phase's 8 plans (verified via each PLAN.md's `requirements:` frontmatter). No orphans.

**REQUIREMENTS.md checkbox note:** EXC-01..04 remain `[ ]` unmarked in REQUIREMENTS.md as of this verification. Every plan summary (01, 02, 03, 04, 05, 06, 07) explicitly and consistently documents that 39-08 is the phase's designated last-declaring plan and that checkbox-marking is deferred to phase completion (mirroring the Phase 38 CAMP-01 precedent) — this is a documented process convention, not a gap in implementation. The task instructions for this verification confirm this same understanding. Flagged here for the orchestrator to update REQUIREMENTS.md at phase-completion time, not as an implementation defect.

### Anti-Patterns Found

None blocking. Scanned all created/modified files for TODO/FIXME/placeholder/empty-return patterns:
- The only intentional "placeholder" was `exceptions-table.tsx`'s Revoke button in 39-06 (explicitly plan-sanctioned pending 39-07's mutation hook) — resolved by 39-07, confirmed live-wired (`useRevokeException` grep ≥1, tests updated from "always disabled" to "enabled for active / disabled for historical").
- No console.log-only handlers, no hardcoded empty-array dashboard responses, no stub `return null`/`return {}` found in the exceptions module or its 12+ consumer call sites.

### Human Verification Required

None outstanding. The one item that genuinely required human/visual confirmation — the live grant→exclude-everywhere→list→revoke→resurface loop, dashboard exclusion, and UI-SPEC copy/sort rendering — was already executed as 39-08's blocking `checkpoint:human-verify` gate and **APPROVED by the user on 2026-08-19** (all 8 acceptance steps confirmed, no defects). This verification independently corroborates that approval with static/automated evidence (code, grep gates, 149+ passing backend/frontend tests) rather than re-trusting the SUMMARY narrative alone.

### Gaps Summary

No gaps found. All four roadmap success criteria are independently verified against actual code:
1. Governed grant form (justification + approver + scope) — implemented, tested, human-confirmed.
2. Exclusion from active queues/SLA timers/dashboards until mandatory expiry — implemented across ~20 real consumer call sites (not just the tracer), verified via grep gates + passing test suites for each sweep plan, with an explicit hard 365-day cap preventing permanent silence.
3. Tenant-scoped audit trail (who/why/scope/expiry) on every mutation including the once-only lazy expiry-audit — implemented and tested.
4. Automatic resurface with zero manual re-trigger, including the SLA-clock subtraction that prevents a resurfaced finding from immediately re-breaching (a real governance gap the executor self-discovered and fixed during 39-03) — implemented and tested.

The one process-level note (REQUIREMENTS.md checkboxes not yet flipped) is an expected, well-documented convention tied to phase-completion timing, not a functional or implementation gap.

---

*Verified: 2026-08-19T14:30:00Z*
*Verifier: Claude (gsd-verifier)*
