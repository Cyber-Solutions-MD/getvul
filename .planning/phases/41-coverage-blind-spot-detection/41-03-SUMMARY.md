---
phase: 41-coverage-blind-spot-detection
plan: 03
subsystem: api+web
tags: [fastapi, sqlalchemy, postgres, tanstack-query, nextjs, coverage]

# Dependency graph
requires:
  - phase: 41-01
    provides: "backend/app/coverage/{schemas,service,router}.py module + /dashboard/coverage page's WR-13 branch-machine shell this plan extends additively"
provides:
  - "GET /api/v1/coverage/summary — per-connector coverage % (D-05), staleness (D-06, strict >7d), wire-normalized sync status (Pitfall 3)"
  - "CoverageConnectorCard component + useCoverageSummary() hook — the frontend strip rendered above the blind-spot list"
  - "Coverage page's third empty-state branch: 'No scanner connected' (UI-SPEC E4 backstop) for has_authoritative_inventory && !has_scanner_connector"
affects: [41-04-route-to-owner-backend, 41-05-route-to-owner-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-query WR-13 branch machine: page.tsx now derives its state branches from BOTH useBlindSpotAssets and useCoverageSummary (combined isLoading/error), not a second independent state machine — mirrors the single-branch-source discipline the D-11 empty states already established in Plan 01"
    - "Coverage-% 3-tier color reuses the existing SLA tone family verbatim via Tailwind's text-success/text-warning/text-danger utilities (which resolve to var(--color-success/warning/danger)) — zero new palette"

key-files:
  created:
    - frontend/src/lib/queries/use-coverage-summary.ts
    - frontend/src/components/coverage/coverage-connector-card.tsx
    - frontend/src/components/coverage/coverage-connector-card.test.tsx
  modified:
    - backend/app/coverage/schemas.py
    - backend/app/coverage/service.py
    - backend/app/coverage/router.py
    - backend/tests/test_coverage.py
    - "frontend/src/app/(authed)/dashboard/coverage/page.tsx"
    - "frontend/src/app/(authed)/dashboard/coverage/page.test.tsx"
    - frontend/src/components/coverage/microcopy.ts

key-decisions:
  - "Task 1 (backend GET /coverage/summary) was salvaged from an interrupted prior run — found already committed at cf346ee with all 5 COV-02 behavior tests + the 6 pre-existing Plan 01 tests green (11/11). Verified via git log, re-ran the full test file rather than redoing the work."
  - "Added a local CONNECTOR_DISPLAY_LABEL map inside coverage-connector-card.tsx (6 scanner types only) — no display-name lookup existed anywhere in the codebase for the raw uppercase connector_type string the summary endpoint returns (unlike ConnectorConfig.connector_name, which this card's payload doesn't have)."
  - "Extended page.test.tsx's mock harness with mockSummaryQuery (defaulting has_scanner_connector: true, cards: []) so every pre-existing Plan 01 branch test keeps exercising the exact same branch now that page.tsx reads two queries instead of one — this was a direct, in-scope consequence of Task 2's own change to page.tsx, not a pre-existing issue."
  - "Skeleton loading state for the strip uses a plain animate-pulse block (mirrors dashboard/hero.tsx's isPending precedent) rather than SkeletonTable, since SkeletonTable is table-row-shaped and the strip is card-shaped — no new skeleton primitive introduced."

patterns-established:
  - "Coverage page empty-state branch order (extends Plan 01's D-11 pair into a triad): error -> loading -> !has_authoritative_inventory (D-11) -> has_authoritative_inventory && !has_scanner_connector (E4 scanner-absent) -> total===0 (quiet win) -> populated"

requirements-completed: [COV-02]

# Metrics
duration: 48min
completed: 2026-08-21
---

# Phase 41 Plan 03: Per-Connector Coverage Strip + Staleness Summary

**GET /api/v1/coverage/summary (per-connector coverage %, D-06 stale badges, wire-normalized sync status) plus the CoverageConnectorCard strip rendered above the blind-spot list, with a third "No scanner connected" empty-state branch for the inventory-without-scanner edge case — COV-02 delivered end-to-end.**

## Performance

- **Duration:** 48 min (Task 1 backend salvaged from an interrupted prior run; Task 2 frontend executed this session)
- **Started:** 2026-08-21T07:10:00Z (approx, Task 2 frontend work)
- **Completed:** 2026-08-21T07:58:00Z
- **Tasks:** 2 completed (Task 1 salvaged + verified, Task 2 executed)
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- **Task 1 (backend, salvaged):** `CoverageConnectorCardResponse`/`CoverageSummaryResponse` schemas, `get_coverage_summary()` service function (reuses the Plan 01 `authoritative` clause verbatim, imports `_normalize_sync_status` rather than re-deriving it, D-06 strict `>7d` staleness), `GET /api/v1/coverage/summary` router endpoint on `require_viewer`. Found already committed at `cf346ee` with all 5 new behavior tests (percentage math, zero-denominator null-safety, stale-boundary strictness, status normalization, enabled/disabled connector filtering) plus the 6 pre-existing Plan 01 tests — 11/11 green, re-verified this session.
- **Task 2 (frontend):** `useCoverageSummary()` hook (staleTime 0, mirrors `use-blind-spot-assets.ts`'s shape); `CoverageConnectorCard` composing `ConnectorMark` + a display-label lookup + `SyncStatusPill` + a 40px mono tabular-nums coverage-% headline (3-tier SLA color family, null renders "—" never "0%") + an amber `stale · {N}d` pill; wired into `coverage/page.tsx` above the blind-spot list inside a `StatStrip`, with an `xl` (32px) gap per D-04; added the "No scanner connected" empty-state branch (UI-SPEC E4 backstop) and its `scannerAbsent` microcopy.
- 8/8 new frontend component tests green (color-tier boundaries, null-safety, Pitfall-3 status-passthrough, stale-pill chrome) + 8/8 page-level branch tests green (5 pre-existing Plan 01 branches re-verified against the new two-query shape + 3 new Plan 03 branch tests: populated-with-cards, scanner-absent, dual-query loading) + `tsc --noEmit` clean on all touched files + no freehand hex in the new files (grep-verified) + `npm run lint` shows zero new findings (the one pre-existing project-wide error is in an unrelated Phase-39 file, confirmed by grep).

## Task Commits

1. **Task 1: GET /summary — per-connector coverage % + staleness (COV-02)** — `cf346ee` (feat) — salvaged from an interrupted prior run; verified, not redone.
2. **Task 2: CoverageConnectorCard + strip on the page + scanner-absent empty variant** — `1c44f2c` (feat)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified

- `backend/app/coverage/schemas.py` — `CoverageConnectorCardResponse` + `CoverageSummaryResponse` (Task 1, pre-existing at `cf346ee`)
- `backend/app/coverage/service.py` — `get_coverage_summary()` (Task 1, pre-existing at `cf346ee`)
- `backend/app/coverage/router.py` — `GET /summary` endpoint (Task 1, pre-existing at `cf346ee`)
- `backend/tests/test_coverage.py` — 5 new COV-02 behavior tests (Task 1, pre-existing at `cf346ee`)
- `frontend/src/lib/queries/use-coverage-summary.ts` — `useCoverageSummary()` hook + `CoverageSummaryResponse`/`CoverageConnectorCard` TS types
- `frontend/src/components/coverage/coverage-connector-card.tsx` — the per-connector card (ConnectorMark + label + SyncStatusPill + % headline + stale pill)
- `frontend/src/components/coverage/coverage-connector-card.test.tsx` — 8 tests: 3-tier color boundaries, null-safety, Pitfall-3 status passthrough, stale-pill chrome/text, ConnectorMark/label rendering
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` — wires `useCoverageSummary`, adds the `CoverageStripSkeleton`, combines both queries into the WR-13 branch machine, adds the scanner-absent empty branch, renders the `StatStrip` of cards above the blind-spot table
- `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` — added `mockSummaryQuery` mock harness (kept the 5 pre-existing Plan 01 tests passing against the new two-query shape) + 3 new branch tests
- `frontend/src/components/coverage/microcopy.ts` — `empty.scannerAbsent` copy (title/body/action)

## Decisions Made

- Task 1 backend work was found already complete and committed (`cf346ee`) from an interrupted prior execution run — verified via `git log --oneline --grep="41-03"` and a full re-run of `tests/test_coverage.py` (11/11 green) rather than redone. No backend files were touched in this session.
- `CONNECTOR_DISPLAY_LABEL` is a small new literal lookup local to `coverage-connector-card.tsx` (6 scanner types: CrowdStrike/Nessus/Defender/Wiz/Qualys/Rapid7) — the backend summary payload has no `connector_name` field (unlike `ConnectorConfig`, which the existing `connector-card.tsx` reads for its display name), so a label had to be derived from the raw `connector_type` string. Falls through to the raw string for any unrecognized value, mirroring `connector-mark.tsx`'s own undefined-fallback convention.
- `page.test.tsx`'s mock harness was extended with `mockSummaryQuery` (default `has_scanner_connector: true`, `cards: []`) so every pre-existing Plan 01 test keeps landing on the same branch now that `page.tsx` reads two queries — this is a direct, in-scope consequence of this plan's own `page.tsx` change (Rule 1/3), not a pre-existing test-harness gap.
- The coverage-strip loading skeleton is a plain `animate-pulse` block (3 placeholder cards), not `SkeletonTable` — `SkeletonTable` is table-row shaped and would misrepresent the strip's card layout; mirrors `dashboard/hero.tsx`'s existing `isPending` skeleton precedent instead of inventing a new skeleton primitive.
- Empty-branch order finalized as: error → loading → `!has_authoritative_inventory` (D-11) → `has_authoritative_inventory && !has_scanner_connector` (E4 scanner-absent) → `total === 0` (quiet win) → populated. The scanner-absent check is placed before the quiet-win check because it answers a more specific "why is there nothing to show" question and matches the UI-SPEC's stated fallback order (D-11 no-inventory checked first, since it's a strict subset — no-inventory implies no coverage strip content and no blind-spot list content either).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing `page.test.tsx` branch tests would have hung in a permanent loading state**

- **Found during:** Task 2, wiring `useCoverageSummary` into `page.tsx`
- **Issue:** `page.tsx`'s `isLoading` now derives from `q.isPending || summaryQ.isPending`. The pre-existing Plan 01 `page.test.tsx` only mocked `useBlindSpotAssets`; with `useCoverageSummary` unmocked, TanStack Query would issue (and never resolve, in a `vitest` DOM environment with no fetch mock) a real request, leaving `summaryQ.isPending` permanently `true` and every non-loading branch assertion failing.
- **Fix:** Added a `mockSummaryQuery` helper (mirrors the existing `mockQuery` pattern) and call it in `beforeEach` with a default `has_scanner_connector: true`/`cards: []` payload, so every pre-existing test lands on the exact branch it did before this plan's change. Individual new tests override it where the scanner-absent/loading/populated-with-cards behavior needs to be exercised.
- **Files modified:** `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx`
- **Verification:** `npm test -- coverage` — 16/16 tests green (13 pre-existing across both test files + 3 new page-level branch tests + this fix reconciled all 5 pre-existing page.test.tsx assertions).
- **Committed in:** `1c44f2c`

---

**Total deviations:** 1 auto-fixed (test-harness fix, directly caused by this plan's own `page.tsx` change — in scope per the deviation rules' scope boundary, not a pre-existing issue).
**Impact on plan:** None on production code — the fix only extended the test mock harness so the pre-existing test suite continued to prove what it always proved, now against the two-query shape this plan introduced.

## Issues Encountered

- `npm run lint` exits non-zero project-wide due to the same pre-existing, unrelated Phase 39 error documented in 41-01-SUMMARY.md (`approver-combobox.tsx:176`, `jsx-a11y/click-events-have-key-events`). Confirmed via grep that none of this plan's files appear in the lint output.
- No `.stale-pill` CSS class literally exists in the codebase despite the UI-SPEC referring to it as "the existing `.stale-pill` token" — the actual precedent is the inline amber-chrome pattern already used by `page.tsx`'s "No scanner coverage" row badge (`border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]`). Reused that exact chrome for the stale pill rather than inventing a new class or a nonexistent one.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `GET /api/v1/coverage/summary` and the `CoverageConnectorCard`/`useCoverageSummary` frontend surface are established for Plan 04 (COV-03 backend, route-to-owner write endpoint) and Plan 05 (COV-03 frontend, route-to-owner drill panel) to build on top of, per Plan 01's original interface staging (`_get_asset_or_404` already present in `router.py`).
- COV-02 requirement can now be marked complete in REQUIREMENTS.md (no shared-plan blocker, unlike COV-01's Plan 01/02 split).
- No blockers.

## Self-Check: PASSED

- All 3 created files verified present on disk (`use-coverage-summary.ts`, `coverage-connector-card.tsx`, `coverage-connector-card.test.tsx`) — re-confirmed via `[ -f ... ]` immediately before this summary's commit.
- Both commit hashes (`cf346ee`, `1c44f2c`) verified present in `git log --oneline --all` immediately before this summary's commit.
- `npm test -- coverage` (16/16) and `backend tests/test_coverage.py` (11/11) both re-run green as part of this summary's verification.

---
*Phase: 41-coverage-blind-spot-detection*
*Completed: 2026-08-21*
