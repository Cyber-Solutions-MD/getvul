---
phase: 43-executive-compliance-reporting
plan: 01
subsystem: compliance-reporting
tags: [fastapi, pydantic, sqlalchemy, nextjs, react, tanstack-query, tailwind]

# Dependency graph
requires:
  - phase: 36-remediation-sla-engine-escalation
    provides: get_sla_metrics, get_mttr_by_tier, sla_tier_service.get_tier_policy
  - phase: 41-coverage-blind-spot-detection
    provides: coverage/service.py::get_coverage_summary (zero-denominator discipline, has_scanner_connector)
  - phase: 42-risk-trend-analytics-burndown
    provides: analytics/service.py::get_aging_distribution
  - phase: 39-exception-risk-acceptance-workflow
    provides: exceptions/service.py::active_exception_subquery
provides:
  - "GET /api/v1/compliance/overview — tenant-scoped, require_viewer-gated framework-control rollup"
  - "backend/app/compliance/ package (catalog.py pure evaluator, service.py compute-once orchestration, schemas.py, router.py)"
  - "get_sla_metrics(severity=, exclude_exceptions=) additive extension consumed by later RPT-01/RPT-02 plans"
  - "/dashboard/compliance page + control-card.tsx + use-compliance.ts + nav entry, consumable by Plan 04's framework-posture strip"
affects: [43-02-rpt01-pdf-backend, 43-03-rpt01-export-dialog, 43-04-rpt02-dashboard-lenses]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Built-in curated compliance catalog as pure in-code data + a pure evaluator function (no DB table, no I/O)"
    - "Compute-each-metric-once-then-evaluate-catalog orchestration (multiple controls share one metric_key)"
    - "Boolean and tenant-calibrated catalog controls special-cased outside the generic numeric threshold path"
    - "Single-select local chip bar (vs. the shared multi-select ChipBar) when 'All' must be a real default state"

key-files:
  created:
    - backend/app/compliance/__init__.py
    - backend/app/compliance/catalog.py
    - backend/app/compliance/service.py
    - backend/app/compliance/schemas.py
    - backend/app/compliance/router.py
    - backend/tests/test_compliance.py
    - frontend/src/lib/queries/use-compliance.ts
    - frontend/src/app/(authed)/dashboard/compliance/page.tsx
    - frontend/src/app/(authed)/dashboard/compliance/page.test.tsx
    - frontend/src/components/compliance/control-card.tsx
  modified:
    - backend/app/vulnerabilities/sla_service.py
    - backend/tests/test_sla_service.py
    - backend/app/main.py
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/shell/nav-items.ts

key-decisions:
  - "exclude_exceptions applied to ALL 6 original get_sla_metrics queries (open-backlog AND remediated/compliance_pct-source), not just breached/at_risk — Pitfall 2's own text names remediated_total/remediated_within_sla, and RPT-03's sla_compliance_pct control reads only compliance_pct, so scoping the fix to breached/at_risk alone would give exclude_exceptions=True zero real effect on this control"
  - "has_active_scanning (PCI 6.3.1) is ALWAYS a real pass/fail signal, never not_measured — has_scanner_connector is a plain boolean, always defined; 'no scanner connected' is an honest, confident fail, not an absent-denominator case (unlike every percentage metric, which has a genuine zero-denominator not_measured case)"
  - "Frontend empty-state condition excludes has_active_scanning from the 'every control is not_measured' check — without this, the empty branch would be unreachable (even a brand-new tenant always has exactly one non-not_measured control)"
  - "coverage_pct aggregate = MAX across enabled scanner cards' individual coverage_pct — a conservative, never-overclaiming proxy since get_coverage_summary has no cross-connector union count without an extra query"
  - "critical_sla_health_pct combines critical+high severities (not critical-only) — matches the PCI 6.3.3/11.3.1.1 control text's explicit 'critical/high' wording"
  - "PR.PS-02 (mttr_by_tier) is tenant-calibrated: compared per-tier against sla_tier_service.get_tier_policy's own tier_days, never a hardcoded day count; tiers with zero remediation history are excluded from the ratio, not counted as failures"
  - "Framework chip bar is a small local single-select control (useUrlState), not the shared multi-select ChipBar primitive — 'All' needs to be a genuine default selection, which the multi-select toggle model doesn't express cleanly"
  - "SLA-policy empty-state CTA deep-links to /dashboard/settings?category=sla, matching the real settings page's URL-param convention"

patterns-established:
  - "compliance/catalog.py: pure ControlDef dataclass list + evaluate_catalog(metrics) pure function, zero I/O, reused by every future catalog-consuming surface (Plan 02 PDF section, Plan 04 posture strip)"
  - "compliance/service.py: compute ~5 metrics exactly once (4 async calls total), evaluate the static catalog in one pass regardless of catalog size"

requirements-completed: [RPT-03]

coverage:
  - id: D1
    description: "get_sla_metrics additively extended with severity + exclude_exceptions (Pitfall 1/2 landmine guards), byte-compatible with all 3 existing call sites"
    requirement: "RPT-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_sla_service.py (17 tests, incl. exception-exclusion on breached/at_risk AND compliance_pct-source queries, severity scoping, lapsed-exception non-suppression)"
        status: pass
    human_judgment: false
  - id: D2
    description: "compliance/catalog.py — built-in 10-control catalog across all 4 frameworks (SOC 2/ISO 27001/PCI DSS v4.0.1/NIST CSF), pure evaluate_catalog() with None-short-circuit, boolean and tenant-calibrated special-casing"
    requirement: "RPT-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_compliance.py (catalog boundary/boolean/tenant-calibrated tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "compliance/service.py compute-once orchestration + GET /api/v1/compliance/overview (require_viewer, tenant-scoped, cross-tenant isolation proven)"
    requirement: "RPT-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_compliance.py::test_compliance_overview_computes_each_metric_exactly_once"
        status: pass
      - kind: integration
        ref: "backend/tests/test_compliance.py::test_compliance_overview_endpoint_200_for_viewer, ::test_compliance_overview_cross_tenant_isolation, ::test_compliance_overview_fresh_tenant_all_not_measured, ::test_compliance_overview_reflects_real_posture_when_data_exists"
        status: pass
    human_judgment: false
  - id: D4
    description: "/dashboard/compliance page (error/loading/two-branch-empty/populated states) + control-card.tsx + use-compliance.ts hook + Compliance nav entry"
    requirement: "RPT-03"
    verification:
      - kind: automated_ui
        ref: "frontend/src/app/(authed)/dashboard/compliance/page.test.tsx (7 tests: branch order, both empty-state root causes by distinguishing CTA, populated grouping, chip-bar filtering)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live-browser visual verification of the compliance page (colors/contrast/glyphs/layout as actually rendered, WCAG AA in both themes)"
    verification: []
    human_judgment: true
    rationale: "No prod-build Playwright/axe sweep was run this session (requires a running server + built frontend, out of scope for backend/logic-level plan execution per established project convention — see memory getvul-axe-sweep-not-run-during-exec). jsdom/testing-library tests prove all four state branches render the correct DOM/copy/roles but cannot confirm live visual contrast or actual browser rendering."

duration: 33min
completed: 2026-08-24
status: complete
---

# Phase 43 Plan 01: Compliance Vertical Tracer Summary

**RPT-03 compliance vertical shipped end-to-end: a built-in 10-control catalog spanning SOC 2/ISO 27001/PCI DSS v4.0.1/NIST CSF, evaluated by a compute-once backend service against Phase 36/41/42 posture metrics, rendered as a new `/dashboard/compliance` page with honest not-measured/pass/partial/fail states.**

## Performance

- **Duration:** 33 min
- **Started:** 2026-08-24T07:33:55Z
- **Completed:** 2026-08-24T08:06:00Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments
- `get_sla_metrics` additively extended with `severity`/`exclude_exceptions` params, closing two RESEARCH.md landmines (fake-100 compliance_pct on zero remediation history; missing exception-exclusion), applied uniformly across every open-backlog AND compliance_pct-source query
- New `backend/app/compliance/` package: a pure, zero-I/O framework-control catalog (`catalog.py`) + a compute-once orchestration service (`service.py`) that never issues more than 4 async calls regardless of catalog size + tenant-scoped `require_viewer` endpoint at `GET /api/v1/compliance/overview`
- New `/dashboard/compliance` page with all four mandatory states (loading skeleton, two-branch cause-specific empty state, amber error banner, populated framework-grouped grid), a new `ControlCard` presentation component, and a `Compliance` nav entry
- Zero fabricated pass/fail on absent data proven end-to-end: fresh-tenant test asserts every percentage-based control renders `not_measured`, never a false 100%/0%

## Task Commits

Each task was committed atomically:

1. **Task 1: Additively extend get_sla_metrics with severity + exclude_exceptions** - `f9aace0` (feat)
2. **Task 2: compliance backend package — catalog + compute-once service + tenant-scoped endpoint** - `de1360f` (feat)
3. **Task 3: /dashboard/compliance page + control card + hook + nav entry** - `ea5cba6` (feat)

_Both Task 1 and Task 2 carry `tdd="true"` in the plan — see "TDD Gate Compliance" below for a disclosure on how that was executed._

## Files Created/Modified
- `backend/app/vulnerabilities/sla_service.py` - Additive `severity`/`exclude_exceptions` kwargs on `get_sla_metrics`, applied to every open-backlog and remediated/compliance_pct-source query
- `backend/tests/test_sla_service.py` - 6 new regression tests (byte-identical defaults, exception exclusion on breached/at_risk and on compliance_pct's source queries, lapsed-exception non-suppression, severity scoping, Pitfall 1 documentation)
- `backend/app/compliance/__init__.py` - Empty package marker (mirrors coverage/analytics)
- `backend/app/compliance/catalog.py` - `ControlDef` frozen dataclass, 10-row `CATALOG` across 4 frameworks, `evaluate_catalog()` pure function with None-short-circuit + boolean/tenant-calibrated special-casing
- `backend/app/compliance/service.py` - `get_compliance_overview()`: 4 async calls (coverage, SLA, aging, MTTR-by-tier) computed once, fed to `evaluate_catalog()`
- `backend/app/compliance/schemas.py` - `ComplianceOverviewResponse`/`ControlStatusResponse` Pydantic models
- `backend/app/compliance/router.py` - `GET /overview`, `require_viewer`-gated
- `backend/app/main.py` - Registers `compliance_router` at `/api/v1/compliance`
- `backend/tests/test_compliance.py` - 11 tests: catalog pure-evaluator unit tests, compute-once call-count spy, fresh-tenant honesty, real-posture reflection, cross-tenant isolation
- `frontend/src/lib/queries/use-compliance.ts` - `useComplianceOverview()` hook + `ControlStatus`/`ComplianceOverviewResponse` types
- `frontend/src/lib/queries/keys.ts` - New top-level `compliance` query-key factory
- `frontend/src/components/compliance/control-card.tsx` - Presentation-only control card (framework glyph, mono control ID, 4-state status pill, evidencing line)
- `frontend/src/app/(authed)/dashboard/compliance/page.tsx` - Full page: `ErrorBoundary>Suspense>Inner`, error/loading/two-branch-empty/populated states, single-select framework chip bar
- `frontend/src/app/(authed)/dashboard/compliance/page.test.tsx` - 7 tests covering branch order and both empty-state root causes
- `frontend/src/components/shell/nav-items.ts` - New `Compliance` entry in `WORKFLOW_ITEMS` (ShieldCheck icon, no chip)

## Decisions Made

See `key-decisions` in frontmatter for the full list. The two most consequential:

1. **`exclude_exceptions` reaches the compliance_pct-source queries, not just breached/at_risk.** RESEARCH.md's Pitfall 2 explicitly names `remediated_total`/`remediated_within_sla` as needing the fix, and RPT-03's `sla_compliance_pct` control reads only `compliance_pct` — restricting the fix to the open-backlog queries alone would make `exclude_exceptions=True` a no-op for this specific consumer.
2. **`has_active_scanning` is never `not_measured`.** `has_scanner_connector` is a plain, always-defined boolean — "no scanner" is a real, honest "fail," not a zero-denominator ambiguity. This required a corresponding fix on the frontend's empty-state condition (excluding this one control from the "all not_measured" check), since otherwise the empty branch would have been permanently unreachable — even a brand-new tenant always has exactly one non-`not_measured` control.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Frontend empty-state condition would have been permanently unreachable**
- **Found during:** Task 3 (writing page.test.tsx against the real backend semantics established in Task 2)
- **Issue:** The plan's literal empty condition ("every control is not_measured") can never be true, because `has_active_scanning` always resolves to a real pass/fail (never `not_measured`) by design — a brand-new tenant would always show the populated grid (with 9 honest not_measured cards + 1 real pass/fail card) instead of the intended guided two-branch empty state.
- **Fix:** Excluded the `has_active_scanning` control from the "every control is not_measured" check on the frontend (`measurableControls` filter in page.tsx), with an inline comment documenting why. Backend catalog/service logic unchanged — this is purely a frontend empty-state-detection fix.
- **Files modified:** frontend/src/app/(authed)/dashboard/compliance/page.tsx
- **Verification:** page.test.tsx's two empty-branch tests (no-scanner and no-SLA-policy) both pass, using realistic mock data mirroring the backend's actual fresh-tenant output (`has_active_scanning` = pass/fail, every other control = not_measured)
- **Committed in:** ea5cba6 (Task 3 commit — caught and fixed before commit, not a follow-up patch)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for the mandatory two-branch empty state (a must_haves truth) to ever actually render. No scope creep — fixed within the same file/task the bug was found in.

## TDD Gate Compliance

Tasks 1 and 2 both carry `tdd="true"`. Per-task execution did not produce a standalone `test(...)` RED commit before the `feat(...)` GREEN commit — for both tasks, the `<behavior>` test cases were written immediately alongside the implementation, run and iterated to green, and committed together as a single `feat(43-01): ...` commit once fully verified. `git log` for this plan shows no `test(...)`-prefixed commits.

This is a **process deviation from the literal RED-then-GREEN commit sequence**, not a coverage gap: every `<behavior>` bullet specified in both tasks has a corresponding passing test (17 tests for Task 1, 11 for Task 2, enumerated in the `coverage:` frontmatter block above), and no implementation code shipped without a verifying test in the same commit. The plan's frontmatter `type` is `tracer` (not `tdd`), so the stricter plan-level RED/GREEN/REFACTOR gate sequence enforcement does not apply here — only the per-task `tdd="true"` attribute's commit-shape expectation was not followed literally.

## Issues Encountered

- **Test fixture gaps required iteration:** two of the new `test_sla_service.py`/`test_compliance.py` tests initially failed because `Vulnerability.asset_id` was left `None` where an ASSET-scope exception match or a `coverage_pct` authoritative-inventory signal needed a real `Asset` row with the correct `seen_by_sources` values (`JAMF`+`QUALYS`, not `QUALYS` alone — `QUALYS` is a `SCANNER_SOURCE`, not an `ENRICHMENT_SOURCE`). Fixed by seeding real `Asset` rows with both source types where needed; both tests pass.
- **`python` vs `.venv/bin/python` for ENCRYPTION_KEY generation:** the bare `python -c "..."` command intermittently produced an empty key via the pyenv shim in one shell invocation, causing a spurious app-startup `RuntimeError`. Switched to `.venv/bin/python` explicitly for all subsequent test runs (consistent with the venv pytest itself uses) — no further failures.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `GET /api/v1/compliance/overview` is live and available for Plan 04's framework-posture strip (dashboard leadership/compliance lenses) to consume via the same `use-compliance.ts` hook.
- `get_sla_metrics(severity=, exclude_exceptions=)` is available for Plan 02's board-PDF SLA-compliance section — no further backend changes needed there.
- No blockers. The one flagged gap (D5, live-browser visual/axe verification) is standard for this project's phase-execution convention and should be swept in a later verification/UAT pass, not blocking for continuing to Plan 02.

---
*Phase: 43-executive-compliance-reporting*
*Completed: 2026-08-24*

## Self-Check: PASSED

- All 15 claimed created/modified files verified present on disk.
- All 3 claimed commit hashes (`f9aace0`, `de1360f`, `ea5cba6`) verified present in `git log`.
