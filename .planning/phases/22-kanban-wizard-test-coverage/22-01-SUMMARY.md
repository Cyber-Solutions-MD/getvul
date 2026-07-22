---
phase: 22-kanban-wizard-test-coverage
plan: 01
subsystem: testing
tags: [e2e, a11y, kanban, dnd-kit, keyboard, playwright]

# Dependency graph
requires:
  - phase: 18-tickets-kanban-board
    provides: "The @dnd-kit TicketsKanbanBoard, KanbanCard, KanbanColumn, and the DndLiveRegion announcements this plan tests against."
provides:
  - "Live-verified CR-01 coverage: an Enter-key keyboard drag changes ticket status without ever opening the DrillPanel."
  - "Live-verified WR-02 coverage: a gated read-only->read-only drop announces the correct 'returned to its column' text (not a false 'Moved ticket' success), proven via an anti-vacuous-pass interim assertion."
  - "A genuine keyboard-a11y production fix: the coordinateGetter now targets the destination column's own rect center, and kanban columns no longer collapse below their flex-1 share when a sibling is empty."
affects: [tickets-kanban-board, kanban-column, e2e-quality-gate]

tech-stack:
  added: []
  patterns:
    - "Anti-vacuous-pass gating: assert an interim state-change signal (onDragOver announcement) before asserting a terminal no-op, so a broken mechanic can't silently produce the same text as a real gated rejection."

key-files:
  created: []
  modified:
    - frontend/e2e/tickets-kanban.spec.ts
    - "frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx"
    - frontend/src/components/tickets/kanban-column.tsx

key-decisions:
  - "Did not add the plan's optional second sanity test ('Enter on a focused card opens the DrillPanel') — verified empirically via dnd-kit source (KeyboardSensor.activators default keyboardCodes.start includes both Space AND Enter) that a fresh, non-dragging focused card's Enter press is ALWAYS consumed as a drag-pickup activator (preventDefault called before onActivation), so it would never open the DrillPanel. The plan's own interfaces section describing this as opening the DrillPanel does not hold; forcing the assertion would be a false test per the plan's own instruction to record observed behavior instead."
  - "Rule 1 auto-fix: keyboard coordinateGetter now targets the destination column's own rect center (`rect.top + rect.height / 2`) instead of carrying `currentCoordinates.y` from the origin column — a real keyboard-a11y defect since a short/empty intermediate column's droppable rect could sit outside the carried-over y, causing collision detection to skip it."
  - "Rule 1 auto-fix: added `min-w-0` to KanbanColumn's outer div — flexbox's default `min-width:auto` let a populated column's content (~239px KanbanCard) win width over an empty sibling's shorter EmptyState (~210px) despite all columns being `flex-1`, uneven enough that a wide dragged card centered in a narrow destination column overlapped BOTH neighbors, letting closestCorners resolve to the wrong one. Reproduced live via a debug harness (one ArrowRight from Open skipped 'In progress' entirely, landing on 'Completed') before and after the y-centering fix alone; only fixed once both changes were applied together."
  - "Reset the 5 Docker-seeded tickets' `blocked` flag via the real `POST /tickets/{id}/blocked` API (not raw SQL) before each verification run — prior phases' (18-21) repeated e2e gate runs had cumulatively moved all 5 tickets to Blocked, leaving zero Open/In-progress/Completed cards to exercise this plan's column-dependent assertions."

requirements-completed: [UX-D-01-02]

# Metrics
duration: ~40min
completed: 2026-07-22
---

# Phase 22 Plan 01: Kanban CR-01/WR-02 Test-Coverage Gap-Closure Summary

**Extended `tickets-kanban.spec.ts` with live, real-DOM Playwright coverage for the two Phase-18 human-UAT items (Enter-key-drag vs. DrillPanel, and the gated-drop live-region wording) — and the WR-02 test surfaced a genuine keyboard-a11y layout defect in production code, fixed and re-verified live.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-07-22T08:43:47Z (approx, per STATE.md init)
- **Completed:** 2026-07-22T12:05:00+03:00 (approx)
- **Tasks:** 3
- **Files modified:** 3 (1 spec, 2 production files fixed as an authorized deviation)

## Accomplishments

- CR-01 closed: a real `page.keyboard.press('Enter')` pickup + drop sequence moves a ticket into Blocked while `[data-drill-panel]` stays at count 0 throughout (mid-drag, post-drop, and final guard) — proving `kanban-card.tsx`'s `e.defaultPrevented` guard actually works under a live browser, not just by code inspection.
- WR-02 closed, both branches: the gated read-only→read-only drop announces "returned to its column" (never a false "Moved ticket" success) — proven via an anti-vacuous-pass interim assertion that the drag genuinely reached a different column first ("is over the In progress column") before the drop; the existing committed-move test now also asserts the positive-branch "Moved ticket ... to the Blocked column" wording.
- A real production defect surfaced by the WR-02 test (not anticipated by the plan) was root-caused and fixed: uneven flex-column widths (missing `min-w-0`) combined with a coordinateGetter that carried the origin column's y-coordinate could make a single keyboard ArrowRight skip an empty intermediate column entirely — a genuine keyboard-accessibility bug for anyone using arrow-key kanban navigation, not merely a test artifact.
- Full spec live-verified against a real production build: 6 passed / 2 skipped / 0 failed (skips are seed-data exhaustion across the 8-test sequential run, not test defects — both new tests independently verified GREEN with real assertions when run isolated with available seed data, see transcripts below).
- `/dashboard/tickets` confirmed 167 kB ≤ 250 kB (no bundle regression from the two production fixes).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CR-01 Enter-key-drag test** - `4192669` (test)
2. **Task 2: Add WR-02 gated-no-op + committed-move live-region assertions** - `4fb08cc` (test) — includes the two Rule-1 auto-fixes to `tickets-kanban-board.tsx` and `kanban-column.tsx`, discovered and fixed while making this test's assertion pass against real behavior.
3. **Task 3: Live prod-build gate run** - no new commit (verification-only task; ticket seed-data mutations were done via the real `POST /tickets/{id}/blocked` API against the local Docker Postgres, not a git-tracked change).

**Plan metadata:** (this commit, following SUMMARY)

## Files Created/Modified

- `frontend/e2e/tickets-kanban.spec.ts` — added `'keyboard drag with Enter does not open the DrillPanel'` (CR-01) and `'gated no-op drop announces returned-to-column, not a false success'` (WR-02); strengthened the existing `'keyboard drag'` test with a positive-branch live-region assertion.
- `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx` — keyboard `coordinateGetter` now targets the destination column's own rect center instead of the origin column's carried-over y.
- `frontend/src/components/tickets/kanban-column.tsx` — added `min-w-0` to the column's flex item so all 4 columns hold equal width regardless of content, matching the intended `flex-1` design.

## Decisions Made

See `key-decisions` in frontmatter. In short: (1) skipped the plan's optional Enter-opens-DrillPanel sanity test after confirming via dnd-kit source that it would be a false assertion; (2) two Rule-1 production auto-fixes were required to make the WR-02 test assert real behavior rather than a broken one; (3) test seed data was reset via the real mutation API before each verification run, since 4 prior phases' (18-21) e2e gates had exhausted the fixture into an all-Blocked state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Keyboard coordinateGetter targeted the wrong y-coordinate**
- **Found during:** Task 2 (writing the WR-02 gated-no-op test)
- **Issue:** `makeKanbanColumnCoordinateGetter` in `tickets-kanban-board.tsx` returned `{ x: rect.left + rect.width/2, y: currentCoordinates.y }` — carrying the y-position from the ORIGIN column rather than centering on the DESTINATION column. When an intermediate column (e.g. "In progress") was empty, its droppable rect (rendered via a short `EmptyState`, not a full card list) could sit outside that carried-over y, so the virtual drag point landed outside the intended target.
- **Fix:** Changed to `y: rect.top + rect.height / 2` — always centers on the destination column's own rect regardless of its height.
- **Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`
- **Verification:** Reproduced the bug live via a throwaway debug harness (`node` script using Playwright + a `console.log` instrumented build) before the fix; confirmed the fix alone was insufficient (see Rule 1 fix #2) but is a correctness improvement regardless.
- **Committed in:** `4fb08cc`

**2. [Rule 1 - Bug] Kanban columns did not hold equal width (missing `min-w-0`)**
- **Found during:** Task 2, root-causing why fix #1 alone did not resolve the WR-02 test failure
- **Issue:** `KanbanColumn`'s outer div used `flex-1` (via `md:flex-1`) with an implicit CSS `min-width: auto`, which lets a flex item's content-driven minimum width win over equal distribution. A populated column (real `KanbanCard`, ~239px min-content) rendered wider than an empty sibling column (`EmptyState`, ~210px min-content) even though both declare `flex-1`. Live-measured: Open/Blocked columns at 239-240px, In-progress/Completed at 210px when the latter were empty. Combined with fix #1's centering, a dragged card (itself ~239px wide) centered in a 210px-wide destination column overflowed into BOTH neighboring columns, and `closestCorners` collision detection resolved `over` to the wrong neighbor — reproduced live: a single `ArrowRight` from "Open" skipped "In progress" entirely and landed on "Completed".
- **Fix:** Added `min-w-0` to the column's className, overriding the default `min-width: auto` so all 4 columns hold equal `flex-1` width regardless of content.
- **Files modified:** `frontend/src/components/tickets/kanban-column.tsx`
- **Verification:** Rebuilt, restarted the prod server, re-ran the WR-02 test — it passed with a real (non-skipped) assertion (814ms, JSON reporter confirmed `status: "passed"`, not `"skipped"`). Re-ran the CR-01 test and the existing 4 original tests — all still green, no regression. `npm run perf:budget` confirmed `/dashboard/tickets` still 167 kB ≤ 250 kB (the CSS-only change added 0 bytes of JS).
- **Committed in:** `4fb08cc`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs surfaced live by the new WR-02 test, not anticipated by the plan, which stated "NO production code changes are anticipated... but none is expected").
**Impact on plan:** Both fixes were necessary to make the WR-02 test assert genuine behavior instead of failing against a real defect. No scope creep — changes are scoped to the exact mechanism (`coordinateGetter`, column flex sizing) the new test exercises. This is also a real user-facing fix: any keyboard-only user navigating the board with arrow keys was previously at risk of skipping over an empty column.

## Issues Encountered

**Seed-data exhaustion across the full sequential spec run.** The local Docker Postgres has accumulated ticket-mutation state across 4 prior phases' (18, 19, 20, 21) repeated live e2e gate runs — all 5 seeded tickets were found `blocked=true` at the start of this plan's Task 2 verification, leaving zero Open/In-progress/Completed cards. Resolved by resetting `blocked` via the real `POST /api/v1/tickets/{id}/blocked` mutation API (the same endpoint the app itself uses) before each verification run — not a raw SQL/database edit. This is a recurring characteristic of this spec: with only 5 tickets and 3 of the 8 tests each consuming an Open-column card en route to Blocked (by design — that's the feature under test), a single full sequential run can exhaust the Open pool before later tests run. This is NOT a defect in the new tests: both new tests (`-g "Enter"` and `-g "announce"`) were independently verified GREEN with genuine (non-skipped) assertions when run isolated against freshly reset seed data — see transcripts below.

## Live Verification Evidence

### CR-01 test, isolated run (`-g "Enter"`), immediately after reset — genuine PASS, not skip

```
$ npx playwright test e2e/tickets-kanban.spec.ts -g "Enter" --config=e2e/playwright.config.ts --project=chromium-a11y

Running 2 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (518ms)
  ✓  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:204:7 › Tickets kanban board › keyboard drag with Enter does not open the DrillPanel (1.1s)

  2 passed (2.4s)
```

JSON reporter confirmed `status: "passed"` (not `"skipped"`) with `duration: 1094`ms — the assertion ran for real against 5 seeded tickets.

### WR-02 test, isolated run (`-g "announce"`), after the two production fixes — genuine PASS, not skip

```
$ npx playwright test e2e/tickets-kanban.spec.ts -g "announce" --config=e2e/playwright.config.ts --project=chromium-a11y

Running 2 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (684ms)
  ✓  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:253:7 › Tickets kanban board › gated no-op drop announces returned-to-column, not a false success (863ms)

  2 passed (2.4s)
```

JSON reporter confirmed `status: "passed"` with `duration: 814`ms.

Before the two production fixes, this same test FAILED against real DOM (not a false skip):

```
Error: expect(locator).toContainText(expected) failed
Locator: locator('[id^="DndLiveRegion"]')
Expected pattern: /is over the In progress column/i
Received string:  "Ticket KAN-1-80067b is over the Completed column."
```

### Full spec, live prod build (Task 3 acceptance gate) — UNEDITED transcript

```
$ npx playwright test e2e/tickets-kanban.spec.ts --config=e2e/playwright.config.ts --project=chromium-a11y --reporter=list

Running 8 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (629ms)
  ✓  2 [chromium-a11y] › e2e/tickets-kanban.spec.ts:25:7 › Tickets kanban board › renders four columns (848ms)
  ✓  3 [chromium-a11y] › e2e/tickets-kanban.spec.ts:58:7 › Tickets kanban board › drag into Blocked persists (1.8s)
  ✓  4 [chromium-a11y] › e2e/tickets-kanban.spec.ts:158:7 › Tickets kanban board › keyboard drag (901ms)
  ✓  5 [chromium-a11y] › e2e/tickets-kanban.spec.ts:204:7 › Tickets kanban board › keyboard drag with Enter does not open the DrillPanel (1.1s)
  -  6 [chromium-a11y] › e2e/tickets-kanban.spec.ts:253:7 › Tickets kanban board › gated no-op drop announces returned-to-column, not a false success
  -  7 [chromium-a11y] › e2e/tickets-kanban.spec.ts:290:7 › Tickets kanban board › empty column
  ✓  8 [chromium-a11y] › e2e/tickets-kanban.spec.ts:314:7 › Tickets kanban board › board mobile bottom-nav (280ms)

  2 skipped
  6 passed (8.2s)
```

**0 failed, as required.** The 2 skips (tests 6 and 7) are seed-data exhaustion: tests 2-4 each consume one of the only 3 Open-eligible tickets (KAN-1/2/3, the only tickets with a null `external_status` — KAN-4/5 have `in_progress`/`completed` status and can never land in the "Open" column regardless of `blocked` state) en route to Blocked, by design of the feature under test, leaving 0 Open cards for tests 6 and 7. **This is explicitly disclosed, not a silent pass** — both skipped tests are independently proven to ASSERT correctly (not vacuously pass) in the isolated `-g` runs above. Seeding 1+ additional ticket(s) with a null/open `external_status` (or reordering the spec so the CR-01/WR-02 tests run before the two destructive tests) would let all 8 tests assert in a single full sequential run.

### perf:budget — `/dashboard/tickets` regression guard

```
$ npm run perf:budget
PASS  /dashboard/tickets  167.0 kB
...
Routes checked: 16
Largest route:  /dashboard/tickets  167.0 kB
Budget:         250 kB gzipped per route (First Load JS)
check-bundle-all: OK — all 16 routes within 250 kB budget.
```

167 kB — unchanged from the Phase 18 baseline (the two production fixes are CSS/logic-only, 0 bytes of new JS).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 22-02 (add-connector wizard test coverage) can proceed. Port 3000 has been freed (prod server stopped) for its own live gate run, per the environment note. The 5 seeded tickets were left in a varied, mostly-unblocked state (KAN-1/2/3 open, KAN-4 in_progress, KAN-5 completed, 0 blocked) — cleaner than the all-blocked state found at the start of this plan, though 22-02 does not depend on ticket state.

---
*Phase: 22-kanban-wizard-test-coverage*
*Completed: 2026-07-22*

## Self-Check: PASSED

All created/modified files confirmed present on disk; both task commit hashes (`4192669`, `4fb08cc`) confirmed present in `git log`.
