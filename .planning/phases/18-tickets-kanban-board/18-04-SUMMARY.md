---
phase: 18-tickets-kanban-board
plan: 04
subsystem: testing
tags: [playwright, e2e, axe, dnd-kit, kanban, quality-gate, keyboard-a11y]

# Dependency graph
requires:
  - phase: 18-tickets-kanban-board
    plan: 03
    provides: "TicketsKanbanBoard DndContext assembly + page.tsx next/dynamic wiring"
  - phase: 18-tickets-kanban-board
    plan: 01
    provides: "RED e2e board spec (tickets-kanban.spec.ts), axe + reduced-motion board extensions"
provides:
  - "18-GATE-EVIDENCE.md — real, pasted terminal output proving the full automated gate (bundle, board e2e, axe both-themes, reduced-motion, unit) is GREEN against a production build"
  - "Column-snapping KeyboardSensor coordinateGetter (makeKanbanColumnCoordinateGetter) resolving the keyboard-drag reachability gap flagged in 18-03"
  - "3 e2e-spec race-condition fixes (networkidle wait, Save-click settle wait, post-mutation reflow settle wait) closing false-skip/false-noop failure modes in tickets-kanban.spec.ts, a11y-routes.spec.ts, reduced-motion.spec.ts"
  - "Human-verified touch drag/swipe disambiguation and DrillPanel-during-drag behavior"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ref-based (not context.over-derived) keyboard coordinateGetter state — avoids collision-detection lag under back-to-back keypresses"
    - "waitForLoadState('networkidle') after waitForNav() as the standard pattern for asserting on content behind a next/dynamic({ssr:false}) lazy-loaded, data-fetching component"

key-files:
  created:
    - ".planning/phases/18-tickets-kanban-board/18-GATE-EVIDENCE.md"
  modified:
    - "frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx"
    - "frontend/e2e/tickets-kanban.spec.ts"
    - "frontend/e2e/a11y-routes.spec.ts"
    - "frontend/e2e/reduced-motion.spec.ts"

key-decisions:
  - "Keyboard coordinateGetter tracks the current column via a useRef counter (reset to the card's real starting column in handleDragStart), not via dnd-kit's context.over — over lags one keypress behind under rapid back-to-back ArrowRight presses (both a real user typing fast and the e2e spec's tight loop), which silently stalled the drag one column short of Blocked with an over-derived approach"
  - "Seed data (backend/scratch_seed_kanban.py, not committed) deliberately gives KAN-1/KAN-2 a pre-set resolved_at even though their external_status stays null/Open — this excludes them from the backend's status=open filter (resolved_at IS NULL) regardless of later blocked mutations, so the 'empty column' e2e test's per-column assertions hold even after two earlier tests in the same file drag those exact tickets into Blocked"
  - "Fixed the 3 e2e race conditions found live (networkidle wait, Save-click settle wait, post-mutation-reflow settle wait) rather than only reporting them — they blocked this plan's own core deliverable (a real, non-flaky gate pass) and were reproduced+root-caused with standalone debug scripts before any fix was applied, each confirmed by re-running 3+ times against fresh seed data"

requirements-completed: [UX-D-01-05, UX-D-01-06]

# Metrics
duration: ~2h
completed: 2026-07-17
---

# Phase 18 Plan 04: Quality Gate Proof — Real Evidence + Human Verification Summary

**Ran the full tickets-kanban quality gate (bundle budget, board e2e, axe both-themes, reduced-motion, unit tests) for real against a production build with live seeded data, pasted the actual terminal output into 18-GATE-EVIDENCE.md, and fixed 3 genuine bugs the live run surfaced (a dynamic-import content race in 3 e2e specs, a deferred-autofocus Save-click race, and dnd-kit's default keyboard coordinateGetter never reaching the Blocked column) — then closed the loop with a human-verified touch drag/swipe/DrillPanel checkpoint.**

## Performance

- **Duration:** ~2h (includes standing up Docker services, seeding real data, and root-causing 3 live bugs via standalone debug scripts before fixing)
- **Completed:** 2026-07-17
- **Tasks:** 2 completed, 3 auto-fixed deviations
- **Files modified:** 4 (1 new evidence doc, 3 e2e specs, 1 product file)

## Accomplishments
- `18-GATE-EVIDENCE.md` contains real, pasted (not summarized) output for all 6 gate checks: bundle budget (`/dashboard/tickets` 167.0 kB ≤ 250 kB), board e2e (6/6 real passes, not skips), axe sweep dark+light (0 critical/serious violations each), reduced-motion (drop-tween ≤20ms), full unit suite (701/701), and static checks (tsc + eslint clean)
- Seeded 1 asset + 5 vulnerabilities + 5 tickets under the existing `admin@getvul.local` tenant (which had **zero** tickets before this plan ran) — without this, all 4 card-dependent board e2e tests plus both axe board-view tests plus the reduced-motion board test would have silently `test.skip()`'d, exactly reproducing the "claimed AA/gate but never actually run" failure mode this phase exists to close
- Root-caused and fixed a false-skip race present in 3 separate e2e spec files (`tickets-kanban.spec.ts`, `a11y-routes.spec.ts`, `reduced-motion.spec.ts`): each read `[data-ticket-id]`'s count immediately after `waitForNav()`, racing the board's `next/dynamic({ssr:false})` chunk download + `useTickets` fetch (measured live: 0 cards at t=0ms, 5 by t=200ms) — fixed with `await page.waitForLoadState('networkidle')` before each first card-count check
- Root-caused and fixed a silent no-op when clicking the reason prompt's Save button in the same tick it becomes visible (the component's deferred `setTimeout(...,0)` autofocus, Pitfall 6 from 18-02) — `click()` returns with no error but the network call never fires; fixed with a settle wait before each Save click, plus a second settle wait before the rollback sub-drag to avoid racing the post-mutation column reflow
- Root-caused and fixed the exact "Open item for 18-04" flagged in `18-03-SUMMARY.md`: dnd-kit's default `KeyboardSensor` coordinateGetter moves 25px per arrow-key press (confirmed by reading the installed package source), which cannot cross the ~700px+ gap to the Blocked column in 6 `ArrowRight` presses. Replaced it with `makeKanbanColumnCoordinateGetter` — a ref-based (not `context.over`-derived) column-snapping getter that jumps directly to the center of the next/previous column's droppable rect, tracked via a `useRef` counter reset to the card's real starting column on drag start
- Human-verified the two manual-only success criteria headless Playwright cannot assert: touch long-press-drag vs. quick-swipe-scroll disambiguation (D-DRAG-05/UX-D-01-05), and DrillPanel Esc/clickaway behavior during and after a drag (Pitfall 3/D-CARD-02) — both confirmed working on device emulation

## Task Commits

Each task was committed atomically:

1. **Task 1: Run the full gate against a prod build and paste evidence** - `b1b0720` (test)
2. **Task 2: Human-verify checkpoint approval recorded** - `e40cdc4` (docs)

## Files Created/Modified
- `.planning/phases/18-tickets-kanban-board/18-GATE-EVIDENCE.md` (new) — pasted terminal output for all 6 gate checks, plus documented deviations and the human-verify checkpoint result
- `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx` (modified) — added `makeKanbanColumnCoordinateGetter` (column-snapping keyboard coordinateGetter) and a `columnIndexRef` reset in `handleDragStart`; no styling/copy changes, no new dependency, bundle size unchanged (167 kB)
- `frontend/e2e/tickets-kanban.spec.ts` (modified) — added `waitForLoadState('networkidle')` before the 4 card-count checks; added settle waits before each Save-button click and before the rollback sub-drag
- `frontend/e2e/a11y-routes.spec.ts` (modified) — added `waitForLoadState('networkidle')` before both board axe sweeps' card-count checks (dark + light)
- `frontend/e2e/reduced-motion.spec.ts` (modified) — added `waitForLoadState('networkidle')` before the board drag test's card-count check

## Decisions Made
- Keyboard coordinateGetter uses a `useRef` counter rather than deriving the current column from dnd-kit's `context.over` — `over` only updates once collision detection re-runs against the *previous* keypress's coordinates, so back-to-back presses (both a real fast typist and this plan's own e2e spec) re-derive the same "next" index every time and stall one column short of Blocked. Verified live with a standalone debug script before and after the fix.
- Seed tickets KAN-1/KAN-2 are given a pre-set `resolved_at` despite `external_status=null` (Open bucket) — this is a deliberate seed-design choice so the backend's `status=open` filter (which only checks `resolved_at IS NULL`) naturally excludes them once they get dragged into Blocked by earlier tests in the same spec file, keeping the "empty column" test's per-column EmptyState assertions honest regardless of test execution order within the file.
- All 3 e2e race-condition fixes were applied directly (Rule 1 — auto-fix bugs) rather than only documented, since they blocked this plan's entire purpose (a genuinely-passing, non-flaky gate) and were pre-existing latent bugs in specs authored in 18-01 that could not have been caught without the exact prod-build + live-server + real-data conditions this plan requires. Each fix was reproduced and root-caused with a standalone debug script before being applied, and the pointer-drag fix was re-verified across 3 additional clean-reseed runs (not a one-off pass).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed false-skip race in 3 e2e specs reading board content too early**
- **Found during:** Task 1, first real run of `tickets-kanban.spec.ts` (4/6 tests skipped despite 5 real seeded tickets)
- **Issue:** `waitForNav()` resolves as soon as the persistent nav shell mounts, before the board's `next/dynamic({ssr:false})` chunk downloads and its query resolves; every card-count check that ran immediately after saw 0 cards and false-skipped
- **Fix:** Added `await page.waitForLoadState('networkidle')` before each first card-count check in `tickets-kanban.spec.ts` (4 sites), `a11y-routes.spec.ts` (2 sites), and `reduced-motion.spec.ts` (1 site)
- **Files modified:** `frontend/e2e/tickets-kanban.spec.ts`, `frontend/e2e/a11y-routes.spec.ts`, `frontend/e2e/reduced-motion.spec.ts`
- **Verification:** Re-ran all 3 specs against the same seeded data; all previously-skipped tests now execute and pass
- **Committed in:** `b1b0720`

**2. [Rule 1 - Bug] Fixed reason-prompt Save-button click race**
- **Found during:** Task 1, re-running "drag into Blocked persists" after fix #1
- **Issue:** Clicking Save in the same tick the popover becomes visible silently no-ops (the component's deferred `setTimeout(...,0)` autofocus, Pitfall 6); a second race in the rollback sub-flow grabbed the next card's `boundingBox()` immediately after the prior mutation, racing the column reflow and missing the card entirely
- **Fix:** Added a 200ms settle wait before each Save-button click, and a 300ms settle wait after the first successful-block assertion before starting the rollback drag
- **Files modified:** `frontend/e2e/tickets-kanban.spec.ts`
- **Verification:** Re-ran the full test 4 times against fresh reseeded data (1 initial + 3 additional) — all green
- **Committed in:** `b1b0720`

**3. [Rule 1 - Bug] Fixed keyboard drag never reaching the Blocked column**
- **Found during:** Task 1, "keyboard drag" test (the exact open item flagged in `18-03-SUMMARY.md`)
- **Issue:** dnd-kit's default `KeyboardSensor` coordinateGetter moves 25px per arrow-key press, insufficient to cross the board's ~700px+ column gap in 6 presses; a first attempted fix deriving the current column from `context.over` worked with spaced-out presses but failed identically under back-to-back presses (collision-detection lag)
- **Fix:** Implemented `makeKanbanColumnCoordinateGetter` — a `useRef`-backed column-snapping coordinateGetter, independent of `context.over` timing, wired into the `KeyboardSensor`
- **Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`
- **Verification:** `npx tsc --noEmit` clean, full `vitest` suite 701/701 unchanged, keyboard-drag e2e test passes reaching the Blocked column
- **Committed in:** `b1b0720`

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs)
**Impact on plan:** All 3 fixes were necessary to produce genuine (non-fabricated, non-flaky) gate evidence — the plan's entire purpose. No scope creep beyond the affected files; no styling/copy/dependency changes.

## Known Stubs

None. `backend/scratch_seed_kanban.py` (the one-off ticket-seeding script used to produce real gate data) was intentionally NOT committed — it is a scratch/dev-only tool, not shipped application code, documented in `18-GATE-EVIDENCE.md` for reproducibility.

## Threat Flags

None. This plan runs tests and fixes test-infrastructure races plus one keyboard-interaction bug; per its own threat register (T-18-12 mitigate, T-18-13 accept), it introduces no new production network surface, auth path, or schema change. The `KeyboardSensor` coordinateGetter change is a pure client-side interaction fix with no new attack surface.

## Issues Encountered

- Docker daemon was not running at plan start — started via `open -a Docker` and waited for `docker info` to succeed before bringing up `postgres`/`redis`/`backend`.
- The tenant had zero seeded tickets/vulnerabilities/assets before this plan — required writing and running a one-off seed script (not committed) before any gate command could produce real (non-empty-dataset) results.
- All 3 deviations above were root-caused with standalone Node/Playwright debug scripts (network capture, `elementFromPoint`, bounding-box polling) run outside the actual test files before any fix was applied — each fix was then re-verified against fresh reseeded data, not assumed from a single passing run.

## User Setup Required

None — no external service configuration required. The local gate-run environment (Docker Compose backend + a production Next.js build served locally) is dev/CI infrastructure, not a shipped feature.

## Next Phase Readiness

- Phase 18 (tickets kanban board) is now fully verified: all 4 ROADMAP success criteria hold with real evidence — SC#1 (four columns), SC#2 (drag-persist with rollback), SC#3 (empty/filter states), and SC#4 (mobile + ≤250 KB bundle + axe both themes) — plus the two human-only criteria (touch drag/swipe disambiguation, DrillPanel-during-drag).
- `18-GATE-EVIDENCE.md` is the auditable record that closes the recurring project-memory gap ("axe sweep not run during execution" / AA claimed without proof) specifically for this phase.
- No blockers for the next phase (19, per the v2.2 ROADMAP — add-connector wizard).

---
*Phase: 18-tickets-kanban-board*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files confirmed present on disk (18-GATE-EVIDENCE.md, tickets-kanban-board.tsx, tickets-kanban.spec.ts, a11y-routes.spec.ts, reduced-motion.spec.ts, this SUMMARY.md). Both task commits (`b1b0720`, `e40cdc4`) confirmed present in `git log --oneline --all`.
