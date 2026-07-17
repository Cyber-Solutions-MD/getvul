---
phase: 18-tickets-kanban-board
plan: 03
subsystem: ui
tags: [react, dnd-kit, tickets, kanban, next-dynamic, tanstack-query]

# Dependency graph
requires:
  - phase: 18-tickets-kanban-board
    plan: 00
    provides: "@dnd-kit/core install, bucketTickets() projection, useMarkBlocked cache-key fix"
  - phase: 18-tickets-kanban-board
    plan: 01
    provides: "RED e2e board DOM contract (data-column/data-ticket-id, view=board)"
  - phase: 18-tickets-kanban-board
    plan: 02
    provides: "KanbanCard, KanbanColumn, KanbanReasonPrompt leaf components"
provides:
  - "TicketsKanbanBoard — the DndContext assembly (sensors, onDragEnd gating, DragOverlay, a11y announcements, reason-prompt flow, mobile scroll-snap)"
  - "page.tsx view==='board' branch renders the real board (placeholder removed), dynamically imported with ssr:false"
affects: [18-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "next/dynamic({ssr:false}) module-scope lazy import to keep a client-only, non-SSR-safe dependency (@dnd-kit) out of a route's First-Load JS bundle"
    - "Board container derives per-column drag-target validity from a single activeCard (looked up via activeId) rather than tracking per-column disabled state"

key-files:
  created:
    - "frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx"
  modified:
    - "frontend/src/app/(authed)/dashboard/tickets/page.tsx"

key-decisions:
  - "Loading-state skeleton is a lightweight bespoke per-column shimmer block (not SkeletonTable, which renders a <table>) — avoids nesting an unrelated table element inside kanban column layout while still satisfying the mandatory loading-state coverage"
  - "KanbanReasonPrompt renders inside a `fixed inset-x-0 top-20 z-50` centered overlay wrapper (not anchored to the dropped card) since the drop origin varies by column width/scroll position; the component's own role=dialog + Escape/Enter handling and deferred autofocus (Pitfall 6) are unchanged"
  - "Shipped with the default KeyboardSensor coordinateGetter + closestCorners (RESEARCH Open Question 1 primary path) — did not add a custom column-snapping coordinateGetter, since verifying keyboard reachability of Blocked requires the full e2e run (prod build + server), which is explicitly out of scope for this plan and deferred to 18-04's gate per the plan notes"

requirements-completed: [UX-D-01-01, UX-D-01-02, UX-D-01-03, UX-D-01-04, UX-D-01-05, UX-D-01-06]

# Metrics
duration: ~20min
completed: 2026-07-17
---

# Phase 18 Plan 03: Kanban Board Assembly — DndContext container + page.tsx wiring Summary

**Assembled the tickets kanban board's `DndContext` container (pointer/touch/keyboard sensors, block/unblock `onDragEnd` gating, reduced-motion-safe `DragOverlay`, screen-reader announcements, reason-prompt flow, mobile scroll-snap) and replaced the copy-only board placeholder in `page.tsx` with a `next/dynamic({ssr:false})` lazy import, confirming `/dashboard/tickets` stays at 167 KB First Load JS (well under the 250 KB budget) since @dnd-kit never enters the route's static bundle.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-17
- **Tasks:** 2 completed, 0 deviations
- **Files modified:** 2 (1 new, 1 modified)

## Accomplishments
- `TicketsKanbanBoard` composes the 18-02 leaf components (`KanbanCard`, `KanbanColumn`, `KanbanReasonPrompt`) under one `DndContext` with the exact RESEARCH-specified sensor config: `PointerSensor` `activationConstraint: { distance: 8 }` (D-CARD-02 click-vs-drag), `TouchSensor` `activationConstraint: { delay: 200, tolerance: 5 }` (D-DRAG-05 long-press-vs-swipe), and a default `KeyboardSensor` (D-DRAG-04)
- Board holds **no local copy of ticket rows** — `bucketTickets(rows)` re-derives the 4 columns on every render from the `useTickets` cache the page passes down, so `useMarkBlocked`'s optimistic `onMutate` flip (fixed in 18-00 Pitfall 1) and its `onError` rollback both flow through automatically with zero board-local state to revert
- `onDragEnd` gates exactly two mutating transitions per D-DRAG-01/02/03: read-only→Blocked opens the reason prompt (`setPendingBlock`, no mutate call — Cancel is a true no-op since nothing moved optimistically yet) and Blocked→read-only unblocks immediately via `markBlocked.mutate({blocked:false, blocked_reason:null})`; every other drop (read-only→read-only, blocked→blocked, drop outside a column) is a no-op
- Per-column `isValidTarget` is derived from a single `activeCard` lookup (via `activeId` set in `onDragStart`) rather than per-column disabled toggling, matching the 18-02 `KanbanColumn` contract (droppables stay enabled at all times; the dim cue and gating are separate concerns)
- `DragOverlay dropAnimation={reduced ? null : undefined}` suppresses the WAAPI drop tween under `prefers-reduced-motion` (Pitfall 2 — the globals.css CSS-animation blanket does not catch WAAPI `element.animate()`)
- `accessibility={{ announcements, screenReaderInstructions }}` verified against the installed `@dnd-kit/core@6.3.1` TypeScript types (`DndContext.d.ts`, `Accessibility/types.d.ts`) before finalizing — the shape matches the RESEARCH assumption exactly, no adjustment needed (Assumption A1 confirmed correct)
- Mobile layout: `flex gap-4 overflow-x-auto snap-x snap-mandatory md:overflow-visible md:snap-none` with each `KanbanColumn` at `basis-[85vw] md:basis-0 md:flex-1` — no `position:fixed`/`sticky` (Pitfall 4, does not collide with the bottom-nav)
- `page.tsx`: `TicketsKanbanBoard` is lazily imported via `dynamic(() => import('./tickets-kanban-board').then(m => m.TicketsKanbanBoard), { ssr: false, loading: () => <SkeletonTable .../> })`; the `view === 'board'` placeholder branch and the now-unused `BOARD_PLACEHOLDER` const are both removed; the list branch, chip-bar, `DrillPanel`/`DrillPanelMobile`, and List/Board toggle are byte-for-byte unchanged
- `npx next build` confirms `/dashboard/tickets` at **167 kB First Load JS** (was ~166 kB pre-phase per RESEARCH) — @dnd-kit's dynamic chunk is correctly excluded from the First-Load column, comfortably inside the 250 KB budget (UX-D-01-06)
- `npx tsc --noEmit`, `npx eslint` on both touched files, and `npx vitest run src/components/tickets/` (69/69) all pass with zero errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the DndContext board container** - `ed5bf88` (feat)
2. **Task 2: Wire the board into page.tsx via next/dynamic (ssr:false)** - `47a2ef7` (feat)

## Files Created/Modified
- `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx` (new) — the `TicketsKanbanBoard` DndContext assembly: sensors, `onDragEnd` block/unblock gating, `DragOverlay`, a11y announcements/instructions, reason-prompt state, per-column skeleton for the loading branch, `PartialFailureBanner` for the error branch
- `frontend/src/app/(authed)/dashboard/tickets/page.tsx` (modified) — added the `next/dynamic` board import, replaced the placeholder branch with `<TicketsKanbanBoard rows={items} isLoading={isLoading} error={q.error as Error | null} onOpen={onRowClick} />`, removed `BOARD_PLACEHOLDER`, updated the file-header doc comment

## Decisions Made
- Loading-state skeleton for the board is a bespoke lightweight per-column shimmer block (`BoardSkeletonColumn`), not `SkeletonTable` (which renders a `<table>` — unsuitable nested inside a kanban column's flex layout). Reuses the same `motion-safe:animate-shimmer` / sunset gradient classes as `SkeletonTable`'s cells for visual consistency.
- `KanbanReasonPrompt` renders inside a `fixed inset-x-0 top-20 z-50` centered overlay wrapper rather than anchored to the dropped card's position — the drop location varies by column width and horizontal scroll offset on mobile, so a fixed, always-visible placement is simpler and more reliable than trying to anchor to a transient drop coordinate. The component's own `role="dialog"`, Escape/Enter handling, and deferred (`setTimeout(...,0)`) autofocus (Pitfall 6) are unchanged from 18-02.
- Kept the default `KeyboardSensor` coordinateGetter + `closestCorners` (RESEARCH Open Question 1's primary/first path) rather than pre-emptively adding a custom column-snapping `coordinateGetter`. Verifying whether the default reaches the Blocked column reliably requires the full Playwright e2e run (prod build + running server), which this plan's notes explicitly scope out to 18-04's gate. If the 18-04 keyboard-drag e2e test fails to reach Blocked, the documented fallback (a custom `coordinateGetter` returning the next column droppable's rect) should be applied then.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' exact `<verify>` grep/tsc/build commands passed on the first attempt; the `@dnd-kit/core@6.3.1` `accessibility` prop shape matched the plan's `<interfaces>` block verbatim (confirmed against the installed `.d.ts` files), so no A1 adjustment was needed.

## Known Stubs

None. `onOpen={() => {}}` on the `DragOverlay`'s `KanbanCard` clone is not a stub — it is the documented 18-02 `overlay` contract (a non-interactive static clone with no click affordance; the prop is required by `KanbanCardProps` but intentionally unused for the overlay render path).

## Threat Flags

None. This plan wires existing leaf components and an existing mutation (`useMarkBlocked` → `POST /{id}/blocked`) into a new client-only container; no new network endpoint, auth path, or schema surface is introduced. The plan's own threat register (T-18-08/09/10/11) is satisfied as designed: only two mutation call sites exist in `onDragEnd`, both send the existing `{blocked, blocked_reason}`-only body; the dynamic import removes the SSR hydration surface (T-18-11, accepted, no secrets in the chunk); `dropAnimation={reduced ? null : undefined}` mitigates T-18-10.

## Issues Encountered
None. All acceptance criteria (grep-based DndContext/bucketTickets/dropAnimation/activationConstraint checks, no-raw-hex, `tsc --noEmit`, `next build`, `eslint`, `vitest`) passed on the first attempt for both tasks.

## User Setup Required
None — no external service configuration required. Full e2e verification (`tickets-kanban.spec.ts`'s pointer drag, keyboard drag, rollback, and mobile bottom-nav assertions) requires a prod build + running backend and is explicitly the 18-04 gate, not this plan's scope.

## Next Phase Readiness
- The board's DOM contract (`data-column` on `KanbanColumn`, `data-ticket-id` on `KanbanCard`, four column labels, live count badges) is fully wired end-to-end — 18-01's RED `tickets-kanban.spec.ts` should now have real markup to assert against for `renders four columns` and `empty column`.
- The pointer-drag-into-Blocked → reason-prompt → Save flow and the Blocked→unblock immediate flow are both wired to `useMarkBlocked`; 18-04 can now run the `drag into Blocked persists` (incl. the 500-rollback second half) and `keyboard drag` e2e cases against real behavior.
- `board mobile bottom-nav` at 360px should pass unchanged — the board uses only `overflow-x-auto`/`snap-x` (no `position:fixed`/`sticky`), so it does not touch the Phase 15 bottom-nav DOM or its focus behavior.
- **Open item for 18-04:** if the keyboard-drag e2e test cannot reach the Blocked column with the default `KeyboardSensor` coordinateGetter (6 `ArrowRight` presses from the first card), apply the documented custom column-snapping `coordinateGetter` fallback (RESEARCH Open Question 1) and re-run — this was not verified in this plan since it requires the full e2e harness.
- No blockers for 18-04 (the full quality gate: `next build` + `check-bundle-all.mjs` + axe both themes + `tickets-kanban.spec.ts` + `reduced-motion.spec.ts`).

---
*Phase: 18-tickets-kanban-board*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files confirmed present on disk (tickets-kanban-board.tsx, page.tsx, this SUMMARY.md). Both task commits (`ed5bf88`, `47a2ef7`) confirmed present in `git log --oneline --all`.
