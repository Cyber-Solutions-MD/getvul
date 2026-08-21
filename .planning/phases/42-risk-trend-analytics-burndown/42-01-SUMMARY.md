---
phase: 42-risk-trend-analytics-burndown
plan: 01
subsystem: analytics
tags: [fastapi, pydantic-v2, sqlalchemy, recharts, tanstack-query, nextjs]

# Dependency graph
requires:
  - phase: 34-historical-recompute-consumer-cutover
    provides: "DailySnapshot.metrics history + risk_model_version_snapshot column (v4.0, already shipped) — the raw data this plan reads"
provides:
  - "GET /api/v1/analytics/overview — tenant-scoped, flag-decoupled, date-range-bounded risk-exposure trend series + server-detected version boundaries"
  - "backend/app/analytics/ — plain-async service module (get_scoped_trend_series, detect_version_boundaries, get_analytics_overview) with no FastAPI Depends, directly reusable by Phase 43's report generator (D-16)"
  - "/dashboard/analytics page + Analytics sidebar nav entry + RiskTrendChart (recharts pivot-by-version segmented line + ReferenceLine boundary markers) — the codebase's first connectNulls/ReferenceLine usage"
affects: [42-02-PLAN, 42-03-PLAN, 43-executive-compliance-reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Plain-async service layer (no FastAPI Depends) in new backend modules, so a later consumer (Phase 43) can call the functions directly instead of going through HTTP (D-16)"
    - "Recharts pivot-by-version Line splitting: one <Line dataKey=score_{version}> per detected risk_model_version (null outside its own dates) + connectNulls={false}, so the line breaks with zero interpolation across a version boundary; one neutral <ReferenceLine> per boundary (var(--color-border-strong), never violet/severity/success)"
    - "Empty-state gating on row/point COUNT (trend.length), never on score VALUE — a healthy tenant scoring 0 is not empty"
    - "Exactly-one-data-point renders a single dot marker, never a flat/zero-length line implying a trend (UI-SPEC E2 zero-one-many)"

key-files:
  created:
    - backend/app/analytics/__init__.py
    - backend/app/analytics/schemas.py
    - backend/app/analytics/service.py
    - backend/app/analytics/router.py
    - backend/tests/test_analytics.py
    - frontend/src/lib/queries/use-analytics.ts
    - frontend/src/components/analytics/microcopy.ts
    - frontend/src/components/analytics/risk-trend-chart.tsx
    - frontend/src/components/analytics/scope-window-controls.tsx
    - frontend/src/components/analytics/analytics-page-skeleton.tsx
    - "frontend/src/app/(authed)/dashboard/analytics/page.tsx"
    - "frontend/src/app/(authed)/dashboard/analytics/page.test.tsx"
  modified:
    - backend/app/main.py
    - frontend/src/components/shell/nav-items.ts
    - frontend/src/lib/queries/keys.ts

key-decisions:
  - "avg_risk_exposure_score is keyed unconditionally, decoupled from Tenant.cutover_risk_exposure_scoring (D-12) — no flag-branch in the new service"
  - "Date-range bounding ([start,end] on snapshot_date) replaces the legacy 90-row LIMIT pattern (D-13)"
  - "MIN_HISTORY_POINTS locked at 1, not the plan text's illustrative 'e.g. 2' — UI-SPEC E2's LOCKED zero-one-many decision: a lone data point renders a dot, never the empty state"
  - "TREND-01 / TREND-03 left unmarked '[ ]' in REQUIREMENTS.md — sibling plan 42-03-PLAN.md also declares both IDs (group scope + synthetic-boundary verification) and has no SUMMARY yet; confirmed BLOCKED via `requirements ready-ids`, not marked complete"
  - "STATE.md / ROADMAP.md hand-edited directly rather than via `state advance-plan` / `roadmap update-plan-progress` CLI verbs — this project's decision log (Phases 39-41) documents those verbs reproducibly corrupting STATE.md frontmatter and mis-writing plan counts"

patterns-established:
  - "New top-level backend module skeleton (schemas/service/router/__init__, main.py registration) mirrors backend/app/coverage/ exactly (D-01) — the template for 42-02/42-03 and any future net-new read-side module"
  - "Analytics query-key block in lib/queries/keys.ts uses the opts-object shape ({scope, window, from?, to?}), matching tickets.list's precedent, so Plan 03's scope/range params extend the same key without a shape change"

requirements-completed: [TREND-01, TREND-03]

coverage:
  - id: D1
    description: "Tenant-scoped risk-exposure trend series is flag-decoupled (ignores Tenant.cutover_risk_exposure_scoring) and date-range-bounded (never the legacy 90-row LIMIT)"
    requirement: "TREND-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_tenant_trend_ignores_cutover_flag"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_tenant_trend_respects_date_range"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_overview_is_tenant_scoped"
        status: pass
    human_judgment: false
  - id: D2
    description: "Version-boundary detection: zero boundaries + one continuous segment for single-version data; one {date, old_version, new_version} boundary emitted for a synthetic multi-version fixture"
    requirement: "TREND-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_no_boundary_when_single_version"
        status: pass
      - kind: unit
        ref: "backend/tests/test_analytics.py#test_version_boundary_detected_and_segmented"
        status: pass
    human_judgment: false
  - id: D3
    description: "/dashboard/analytics page structure: Analytics nav entry, ErrorBoundary>Suspense>Inner, error>loading>empty>populated branch order, single-point dot, boundary-marker rendering, no freehand hex, tsc clean"
    requirement: "TREND-01"
    verification:
      - kind: automated_ui
        ref: "frontend/src/app/(authed)/dashboard/analytics/page.test.tsx (7/7 assertions: loading/error/empty/falsy-score-guard/populated/single-point-dot/version-boundary)"
        status: pass
      - kind: other
        ref: "npx tsc --noEmit (new files); grep -rniE '#[0-9a-f]{3,6}' frontend/src/components/analytics/ (no freehand hex)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Live end-to-end tracer in the real dev stack: Analytics sidebar entry navigates to /dashboard/analytics; the trend line renders against real backend data; window presets (7d/30d/90d/1y) re-fetch and re-scope; loading skeleton, error banner+retry, and insufficient-history empty state behave correctly under live conditions"
    requirement: "TREND-01"
    verification:
      - kind: manual_procedural
        ref: "Task 3 checkpoint:human-verify (gate=\"blocking\") — 7-step how-to-verify script; resume-signal 'approved'"
        status: pass
    human_judgment: true
    rationale: "The plan's own reversibility analysis (Task 3) mandated a live human tracer checkpoint before Plans 02/03 expand on these files — visual rendering fidelity, live loading/error network behavior, and real single-version ('v1') production data cannot be fully proven by a mocked-hook unit-test harness. The human already reviewed and responded 'approved' in this session; recorded here for audit trail even though the judgment is already discharged (a redundant re-prompt in a later verify-work pass is an acceptable false-negative per this project's coverage contract)."

duration: 30min
completed: 2026-08-21
status: complete
---

# Phase 42 Plan 01: Risk-Exposure Trend Tracer Summary

**Tenant risk-exposure trend line shipped end-to-end — new `backend/app/analytics/` plain-async module behind `GET /api/v1/analytics/overview`, rendered on a new `/dashboard/analytics` page via a version-boundary-aware, non-interpolating recharts line (first `connectNulls`/`ReferenceLine` usage in the codebase) — human-verify tracer checkpoint approved.**

## Performance

- **Duration:** ~30 min (includes the Task 3 human-verify checkpoint pause between the Task 2 commit and the "approved" response)
- **Started:** 2026-08-21T11:32:51Z (`db7f3e5`, first RED test commit)
- **Completed:** 2026-08-21T12:03:19Z
- **Tasks:** 3/3 (2 auto/tracer tasks + 1 blocking human-verify checkpoint)
- **Files modified:** 15

## Accomplishments
- New `backend/app/analytics/` module (schemas/service/router, mirrors `coverage/` exactly per D-01): `get_scoped_trend_series` (tenant-scoped, date-range-bounded, flag-decoupled per D-12/D-13), `detect_version_boundaries`, `get_analytics_overview` orchestrator — all plain async with no FastAPI `Depends` (D-16), registered at `GET /api/v1/analytics/overview` under `require_viewer`
- 5/5 backend tests green, including a synthetic multi-version fixture proving `detect_version_boundaries` (no codebase precedent for a varying `risk_model_version_snapshot` before this plan) and a cross-tenant isolation test
- New `/dashboard/analytics` page: Analytics sidebar entry (LineChart icon, no chip) → `ErrorBoundary > Suspense > Inner`, error>loading>empty>populated branch order, window presets (7d/30d/90d/1y) via `useUrlState`
- New `RiskTrendChart`: recharts pivot-by-version segmented `<Line>` (`connectNulls={false}`) + neutral `<ReferenceLine>` per version boundary + sr-only `ChartDataTable`; single-point case renders a dot, never a misleading flat line
- 7/7 frontend tests green (loading/error/empty/falsy-score-guard/populated/single-point-dot/version-boundary), `tsc --noEmit` clean, no freehand hex, no new dependency
- Task 3 tracer checkpoint (`gate="blocking"`) reviewed live and **approved** by the user — unblocks Plans 02 (aging/burndown) and 03 (group scope, custom range, synthetic-boundary frontend verification)

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend analytics module + tenant trend series + version-boundary detection + Wave 0 tests** — `db7f3e5` (test, RED) → `9193643` (feat, GREEN)
2. **Task 2: Analytics page + nav + query hook + segmented trend-line chart + states** — `48c99f3` (feat)
3. **Task 3: checkpoint:human-verify (blocking)** — no code commit (pure verification gate); human responded "approved"

**Plan metadata:** committed alongside this SUMMARY (see Self-Check below for hash)

_Note: Task 1 is `tdd="true"` — RED (`db7f3e5`) then GREEN (`9193643`), both landed by the prior executor before this continuation session began._

## Files Created/Modified
- `backend/app/analytics/__init__.py` - empty, mirrors `coverage/__init__.py`
- `backend/app/analytics/schemas.py` - `AnalyticsTrendPointResponse`, `VersionBoundaryResponse`, `AnalyticsOverviewResponse` (Pydantic v2, `ConfigDict(from_attributes=True)`)
- `backend/app/analytics/service.py` - `get_scoped_trend_series`, `detect_version_boundaries`, `get_analytics_overview` — plain async, no `Depends`
- `backend/app/analytics/router.py` - `GET /overview` under `require_viewer`, `days: int = Query(30, ge=7, le=365)`
- `backend/app/main.py` - registers `analytics_router` at `/api/v1/analytics`, immediately after `coverage_router`
- `backend/tests/test_analytics.py` - 5 tests: cutover-flag-ignored, date-range-respected, no-boundary-single-version, boundary-detected-synthetic, tenant-isolation
- `frontend/src/components/shell/nav-items.ts` - `Analytics` entry (`LineChart` icon) in `WORKFLOW_ITEMS`, right after Coverage
- `frontend/src/lib/queries/keys.ts` - `analytics.overview(opts)` cache key (opts-object shape, mirrors `tickets.list`)
- `frontend/src/lib/queries/use-analytics.ts` - `useAnalytics(window)` hook, `staleTime: 0` (D-13 live compute-on-read), `AnalyticsWindow` type (named to avoid shadowing the DOM `Window` global)
- `frontend/src/components/analytics/microcopy.ts` - verbatim transcription of 42-UI-SPEC.md's Copywriting Contract
- `frontend/src/components/analytics/risk-trend-chart.tsx` - `RiskTrendChart`: pivot-by-version segmented `<Line>` + `<ReferenceLine>` boundary markers + sr-only `ChartDataTable`
- `frontend/src/components/analytics/scope-window-controls.tsx` - window `RangeToggle` (7d/30d/90d/1y), extends `trend-chart.tsx`'s idiom
- `frontend/src/components/analytics/analytics-page-skeleton.tsx` - loading shimmer (`aria-busy`/`aria-live`)
- `frontend/src/app/(authed)/dashboard/analytics/page.tsx` - `ErrorBoundary > Suspense > AnalyticsPageInner`, error>loading>empty>populated
- `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` - one test per state branch (7 total)

## Decisions Made
- `avg_risk_exposure_score` is read unconditionally, never branching on `Tenant.cutover_risk_exposure_scoring` (D-12) — same result regardless of the flag, proven by `test_tenant_trend_ignores_cutover_flag`
- Date-range filter (`snapshot_date.between(start, end)`) replaces the legacy `.limit(90)` pattern from `get_risk_score_trend` (D-13) — the plan explicitly forbade copying that function as-is
- Service layer is plain async with no FastAPI `Depends` (D-16), so Phase 43's report generator can call `get_analytics_overview` directly instead of going through HTTP
- `MIN_HISTORY_POINTS` locked at **1**, not the plan action text's illustrative "e.g. 2" — 42-UI-SPEC.md's E2 zero-one-many decision is LOCKED: a lone snapshot renders a single dot, never the empty state (a tenant with exactly one day of history is not "insufficient history")
- The version-boundary marker is strictly neutral (`var(--color-border-strong)`, dashed), never violet/severity/success-colored, per UI-SPEC and the plan's explicit prohibition
- **TREND-01 / TREND-03 left unmarked in REQUIREMENTS.md.** Ran `gsd-tools.cjs requirements ready-ids 42-01-PLAN.md TREND-01,TREND-03` — result: both `blocked` (sibling `42-03-PLAN.md` also declares these same IDs for group-scope + synthetic-boundary-verification work and has no SUMMARY yet). Do not flip until 42-03 also lands, mirroring the Phase 38/41 shared-ID-gate precedent.
- **STATE.md and ROADMAP.md were hand-edited directly, not via `state advance-plan` / `roadmap update-plan-progress`.** This project's own decision log (STATE.md `## Decisions`, Phases 39-41 entries) documents these CLI verbs reproducibly corrupting STATE.md frontmatter (dropped keys, fabricated counts) and mis-writing plan counts; a test invocation of `roadmap update-plan-progress 42` in this session (before any SUMMARY existed) returned a stale `0/3` count as expected given no summary was on disk yet, confirming the safer path is to write the SUMMARY first, then hand-edit both tracking files to the correct post-completion state.
- `gsd-sdk` is not installed in this environment (no `query` subcommand exists on the installed `gsd-tools.cjs`); used the project-local `gsd-tools.cjs`'s actual flag/subcommand syntax instead of the generic workflow template's `gsd-sdk query <verb>` invocations.

## Deviations from Plan

None — plan executed exactly as written for Tasks 1 and 2. The only executor-level adjustments were in this finalization session's *tracking-update mechanics* (documented above as decisions, not code deviations): confirming TREND-01/TREND-03 are correctly left open pending 42-03, and hand-editing STATE.md/ROADMAP.md instead of running the project's known-unreliable CLI verbs.

## Issues Encountered

None. The Task 3 checkpoint's optional item 7 (real multi-version boundary rendering) was, as the plan itself anticipated, not observable against live data — see "Known Limitations (Expected, Not a Gap)" below.

## Known Limitations (Expected, Not a Gap)

Per the plan's own Task 3 `how-to-verify` step 7: production data today is single-version (`RISK_MODEL_VERSION = "v1"`, never changed), so the live human-verify checkpoint could only observe zero boundary markers and one continuous line. The multi-version **detection logic** is proven server-side by the synthetic fixture test (`test_version_boundary_detected_and_segmented`), and the frontend's segmented-rendering code path (`connectNulls={false}` + per-version `<Line>` + `<ReferenceLine>`) exists and passes its mocked-data unit test (`page.test.tsx`'s version-boundary-marker assertion), but **visual confirmation of a real multi-segment boundary in a live browser has not happened yet** — this is explicitly deferred to Plan 42-03's synthetic-fixture verification task, exactly as the plan specifies. This is a planned verification-sequencing gap, not a stub or missing implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tracer spine fully proven end-to-end and human-approved: new backend module pattern, new page pattern, new chart primitive (recharts segmented line + ReferenceLine) all exist and work. Plans 02 (backlog aging/burndown) and 03 (group scope, custom range, synthetic-boundary frontend verification) build additively on these same files with no expected rework.
- `get_analytics_overview`'s `{trend, boundaries}` shape is intentionally structured for Plan 02 to add an `aging`/`burndown` key and Plan 03 to add scope/group params without reshaping the response.
- No blockers. TREND-01/TREND-03 requirement checkboxes intentionally remain open until 42-03 lands (see Decisions above).

---
*Phase: 42-risk-trend-analytics-burndown*
*Completed: 2026-08-21*
