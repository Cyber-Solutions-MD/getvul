---
phase: 41-coverage-blind-spot-detection
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, postgres, tanstack-query, nextjs, coverage]

# Dependency graph
requires:
  - phase: 35-source-aware-filtering-provenance-badges
    provides: "SCANNER_SOURCES/ENRICHMENT_SOURCES source-class partition (backend/app/assets/constants.py) — the exact set this plan's reconciliation filters over"
provides:
  - "backend/app/coverage/ module (schemas/service/router) — the reconciliation service and GET /blind-spots endpoint every later Phase 41 plan extends"
  - "GET /api/v1/coverage/blind-spots — tenant-scoped, paginated blind-spot asset list + has_authoritative_inventory/total_authoritative_assets signals"
  - "/dashboard/coverage page — full loading/error/no-inventory-empty/all-covered-empty/populated state coverage, read-only tracer"
  - "useBlindSpotAssets hook + queryKeys.coverage key group (summary() reserved for Plan 03)"
  - "Coverage sidebar nav entry (Radar icon) + e2e STATIC_ROUTES entry"
affects: [41-02-intune-sync-fix, 41-03-coverage-strip, 41-04-route-to-owner-backend, 41-05-route-to-owner-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reconciliation via intra-row .contains() boolean composition over Asset.seen_by_sources (authoritative = OR across ENRICHMENT_SOURCES, never_scanned = NOT OR across SCANNER_SOURCES) — no join, no new table"
    - "Two-signal D-11 empty-state contract: has_authoritative_inventory (boolean, drives branch selection) + total_authoritative_assets (int, drives quiet-win copy's real device count)"

key-files:
  created:
    - backend/app/coverage/__init__.py
    - backend/app/coverage/schemas.py
    - backend/app/coverage/service.py
    - backend/app/coverage/router.py
    - backend/tests/test_coverage.py
    - "frontend/src/app/(authed)/dashboard/coverage/page.tsx"
    - "frontend/src/app/(authed)/dashboard/coverage/page.test.tsx"
    - frontend/src/components/coverage/microcopy.ts
    - frontend/src/lib/queries/use-blind-spot-assets.ts
  modified:
    - backend/app/main.py
    - frontend/src/lib/queries/keys.ts
    - frontend/src/components/shell/nav-items.ts
    - frontend/e2e/routes.ts

key-decisions:
  - "Extended BlindSpotAssetListResponse with total_authoritative_assets (int) beyond the plan's literal has_authoritative_inventory-only spec — the UI-SPEC quiet-win copy needs a real device count the boolean alone can't supply, and the blind-spot total is 0 in exactly that state"
  - "COV-01 requirement left unmarked ([ ]) in REQUIREMENTS.md — shared with 41-02 (Intune sync fix), which has not yet produced a SUMMARY.md (mirrors the Phase 38 CAMP-01 precedent)"

patterns-established:
  - "Coverage empty-state branch order: error -> loading -> !has_authoritative_inventory (D-11) -> total===0 (quiet win) -> populated, never branching on items.length alone"

requirements-completed: []  # COV-01 shared with 41-02; not yet closeable (see key-decisions)

# Metrics
duration: 31min
completed: 2026-08-20
---

# Phase 41 Plan 01: Coverage & Blind-Spot Detection Summary

**GET /api/v1/coverage/blind-spots reconciliation (authoritative MDM/HR inventory minus anything ever scanner-touched) plus the /dashboard/coverage page rendering all five loading/error/no-inventory/all-covered/populated states — the full browser-to-Postgres tracer slice for COV-01.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-08-20T08:43:46Z
- **Completed:** 2026-08-20T09:14:53Z
- **Tasks:** 2 completed
- **Files modified:** 13 (9 created, 4 modified)

## Accomplishments
- New `backend/app/coverage/` module: `schemas.py` (BlindSpotAssetResponse/BlindSpotAssetListResponse), `service.py` (the D-01/D-02 reconciliation query + authoritative-count), `router.py` (`GET /blind-spots` on `require_viewer` + a tenant-scoped `_get_asset_or_404` helper staged for Plan 04's route-to-owner)
- `GET /api/v1/coverage/blind-spots` registered in `main.py`, tenant-scoped in every WHERE clause (list, count, and the authoritative-inventory count), stable `hostname ASC, id ASC` ordering, `is_ignored` exclusion mirroring `/assets`
- New `/dashboard/coverage` page: full WR-13 state-branch order (error -> loading -> D-11 no-inventory empty -> quiet-win all-covered empty -> populated table), amber-only "No scanner coverage" badge (never severity-critical), Radar sidebar nav entry, e2e route registration
- 5/5 backend tests green (partition correctness, empty-inventory, all-covered, stable ordering, cross-tenant isolation) + 5/5 frontend branch tests green + `tsc`/ruff/mypy-baseline all clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend coverage module + GET /blind-spots reconciliation (COV-01)** - `6961e3a` (feat)
2. **Deviation fix: expose `total_authoritative_assets`** - `a850d3a` (fix) — found while building Task 2's frontend copy; see Deviations below
3. **Task 2: Coverage page + nav entry + query wiring** - `92c29a2` (feat)

**Plan metadata:** _(pending — this commit)_

## Files Created/Modified
- `backend/app/coverage/schemas.py` - `BlindSpotAssetResponse` + `BlindSpotAssetListResponse` (pagination envelope mirroring `AssetsResponse` verbatim, plus `has_authoritative_inventory`/`total_authoritative_assets`)
- `backend/app/coverage/service.py` - `list_blind_spot_assets()`: `authoritative`/`never_scanned` `.contains()` clauses over `Asset.seen_by_sources`, paginated list + count + authoritative-count, all tenant-scoped
- `backend/app/coverage/router.py` - `GET /blind-spots` (`require_viewer`) + `_get_asset_or_404` (tenant-scoped 404, staged for Plan 04)
- `backend/app/coverage/__init__.py` - bare package marker
- `backend/app/main.py` - registers `coverage_router` at `/api/v1/coverage`
- `backend/tests/test_coverage.py` - 5 tests: list partition (JAMF-only in, JAMF+QUALYS out, QUALYS-only out, ignored-JAMF out), empty-inventory, all-covered, stable ordering, cross-tenant isolation
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` - the Coverage page (244 lines): header + 5-branch state machine + inline read-only blind-spot table
- `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` - 5 branch tests (loading/error/no-inventory/all-covered/populated)
- `frontend/src/components/coverage/microcopy.ts` - UI-SPEC copy verbatim, singular-safe `{N}` interpolation
- `frontend/src/lib/queries/use-blind-spot-assets.ts` - `useBlindSpotAssets({page})`, `staleTime: 0` (D-10)
- `frontend/src/lib/queries/keys.ts` - `coverage.{all,summary,blindSpots}` key group (`summary()` reserved for Plan 03)
- `frontend/src/components/shell/nav-items.ts` - `Coverage` entry (Radar icon) in `WORKFLOW_ITEMS`
- `frontend/e2e/routes.ts` - `/dashboard/coverage` added to `STATIC_ROUTES` (axe sweep coverage for free)

## Decisions Made
- Extended the committed backend response with `total_authoritative_assets` (see Deviations) — named to match the field 41-PATTERNS.md already anticipates on the future `/coverage/summary` (COV-02) response, so Plan 03 can adopt the same name without a frontend rename.
- Quiet-win empty-state body uses `total_authoritative_assets` (the real authoritative-inventory count), never the blind-spot list's own `total` (which is always 0 in that exact branch) — avoids a "All 0 devices..." bug.
- COV-01 requirement checkbox in REQUIREMENTS.md left unmarked: 41-02 (Intune sync defect fix) also declares `requirements: [COV-01]` and has not yet executed. Marking it complete here would be premature (mirrors the Phase 38 CAMP-01 precedent documented in STATE.md's Decisions log).
- No separate `CoverageAssetsTable` component file was created — the read-only blind-spot table lives inline in `page.tsx` (matching the plan's `files_modified` list, which names only `page.tsx`/`page.test.tsx` for the frontend surface).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `total_authoritative_assets` to `BlindSpotAssetListResponse`**
- **Found during:** Task 2 (building `microcopy.ts` / `page.tsx` against 41-UI-SPEC.md's Copywriting Contract)
- **Issue:** The UI-SPEC's quiet-win empty-state copy is `"All {N} devices in your inventory have been touched by at least one scanner..."`. The plan's Task 1 schema only exposed `has_authoritative_inventory` (a boolean) — no field supplied the real `{N}`. The blind-spot list's own `total` field is the WRONG number here (it is, by definition, 0 in the exact state this copy renders for), so using it would have produced a false "All 0 devices..." message.
- **Fix:** Widened the existing `_has_authoritative_inventory` (`EXISTS ... LIMIT 1`) helper into `_count_authoritative_assets` (`SELECT COUNT(*)`) over the *identical* `authoritative` clause already built for the main query — no second join, no new query shape, no schema/migration. `has_authoritative_inventory` is now derived as `count > 0`. Field named `total_authoritative_assets` to match what 41-PATTERNS.md already anticipates on the future `/coverage/summary` (Plan 03) response, so that plan can reuse the name without a frontend rename.
- **Files modified:** `backend/app/coverage/schemas.py`, `backend/app/coverage/service.py`, `backend/tests/test_coverage.py`
- **Verification:** All 5 backend tests re-run green (3 extended with a `total_authoritative_assets` assertion); ruff/ruff-format/mypy-baseline (`new: 0`) all clean.
- **Committed in:** `a850d3a`

---

**Total deviations:** 1 auto-fixed (1 blocking-issue fix)
**Impact on plan:** Purely additive (one new int field derived from an existing filter clause) — no architectural change, no new join/table/migration. Necessary for the plan's own specified copy to render a true number instead of a wrong one. No scope creep into Plan 03's `/coverage/summary` endpoint itself.

## Issues Encountered

- `npm run lint` exits 1 project-wide due to a pre-existing, unrelated Phase 39 error (`frontend/src/components/exceptions/approver-combobox.tsx:176`, `jsx-a11y/click-events-have-key-events`, introduced in commit `8757fdd`). Confirmed none of this plan's files appear anywhere in the lint output (verified by grep) and none were modified by this plan. Logged to `41-coverage-blind-spot-detection/deferred-items.md` per the scope-boundary rule rather than fixed here.
- The plan's optional "Manual smoke (start the dev stack, log in as a viewer...)" verification step was not run — this plan has no `checkpoint:*` tasks (both tasks are `type="tracer"`/`type="auto"`, fully autonomous), the step is explicitly marked optional, and the automated coverage (5 backend integration tests against real Postgres + 5 frontend branch tests + clean `tsc`/ruff/mypy) already proves every acceptance criterion end-to-end.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `backend/app/coverage/` and `/dashboard/coverage` are established as the single vertical slice every later Phase 41 plan extends (per the plan's own stated purpose) — Plan 02 (Intune fix), Plan 03 (COV-02 coverage strip via `queryKeys.coverage.summary()`, already reserved), Plan 04 (COV-03 backend via `_get_asset_or_404`, already staged), and Plan 05 (COV-03 frontend) all have their integration points ready.
- COV-01 requirement stays open in REQUIREMENTS.md until Plan 02 (Intune sync fix) also lands — do not close it from Plan 02/03's context without checking this file first.
- No blockers.

## Self-Check: PASSED

- All 10 created files verified present on disk (9 code files + `deferred-items.md`).
- All 3 commit hashes (`6961e3a`, `a850d3a`, `92c29a2`) verified present in `git log --oneline --all`.

---
*Phase: 41-coverage-blind-spot-detection*
*Completed: 2026-08-20*
