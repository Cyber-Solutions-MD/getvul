---
phase: 18-tickets-kanban-board
plan: 02
subsystem: ui
tags: [react, dnd-kit, tickets, kanban, tailwind, vitest, a11y]

# Dependency graph
requires:
  - phase: 18-tickets-kanban-board
    plan: 00
    provides: "@dnd-kit/core install, bucketTickets() projection (ColumnKey/COLUMN_ORDER/COLUMN_LABELS), useMarkBlocked cache-key fix"
  - phase: 18-tickets-kanban-board
    plan: 01
    provides: "RED kanban-reason-prompt.test.tsx contract (KanbanReasonPromptProps), RED board e2e DOM contract (data-column/data-ticket-id)"
provides:
  - "severity-glyph.ts — single-source SEVERITY_GLYPH/SEVERITY_CLASS maps, consumed by both tickets-table.tsx and kanban-card.tsx"
  - "KanbanCard — draggable compact card (useDraggable) satisfying D-CARD-01/02, emits data-ticket-id per the 18-01 e2e DOM contract"
  - "KanbanColumn — droppable column (useDroppable) satisfying D-COL-02/04 and D-DRAG-03, emits data-column per the 18-01 e2e DOM contract"
  - "KanbanReasonPrompt — GREEN implementation of the 18-01 RED unit spec (Save/Cancel/whitespace-null/maxLength/Enter/Esc)"
affects: [18-03, 18-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared literal-lookup module (severity-glyph.ts) extracted from a consuming component so two independent renderers (table + card) share one source of truth — mirrors the sla-pill.tsx single-threshold precedent"
    - "useDraggable/useDroppable called unconditionally at the top of the component (react-hooks/rules-of-hooks) even when a prop (`overlay`) means the returned ref/listeners won't be attached — never gate a hook call itself behind a prop"
    - "Droppable columns stay dnd-kit-enabled at all times; the 'invalid drop target' cue is purely visual (opacity-40) and gating happens in the DndContext's onDragEnd (18-03), not via useDroppable's `disabled` option"

key-files:
  created:
    - frontend/src/components/tickets/severity-glyph.ts
    - frontend/src/components/tickets/kanban-card.tsx
    - frontend/src/components/tickets/kanban-column.tsx
    - frontend/src/components/tickets/kanban-reason-prompt.tsx
  modified:
    - frontend/src/components/tickets/tickets-table.tsx

key-decisions:
  - "isTicketProvider narrowing guard duplicated locally in kanban-card.tsx (not extracted to a shared module) — mirrors the existing precedent where tickets-table.tsx and dashboard/tickets/page.tsx each already define their own private copy; the plan's <interfaces> block specified this local-duplication pattern explicitly"
  - "kanban-column.tsx drops aria-disabled on the role=region wrapper (ARIA spec does not define aria-disabled for the region role, and jsx-a11y/role-supports-aria-props flags it) — the opacity-40 dim cue already communicates the non-target state visually; isValidTarget/isDragActive props are unchanged so 18-03 wiring is unaffected"
  - "kanban-card.tsx's Enter key forwards to dnd-kit's own listeners.onKeyDown first, then also calls onOpen — this keeps the door open for the DndContext's future KeyboardSensor (18-03) while giving Enter an independent 'open the drill' meaning today, satisfying jsx-a11y/click-events-have-key-events without stealing Space (dnd-kit's typical drag-pickup key)"

patterns-established:
  - "Never gate a React hook call behind a conditional/early-return prop branch (overlay clones) — call the hook unconditionally and branch on what you DO with its return value instead"

requirements-completed: [UX-D-01-01, UX-D-01-02]

# Metrics
duration: ~20min
completed: 2026-07-17
---

# Phase 18 Plan 02: Kanban Leaf Components — severity-glyph extraction, draggable card, droppable column, reason prompt Summary

**Built the three leaf kanban components (draggable `KanbanCard`, droppable `KanbanColumn`, inline `KanbanReasonPrompt`) plus a shared `severity-glyph.ts` module so the list table and the new card render severity identically from one source — turning the 18-01 RED `kanban-reason-prompt.test.tsx` unit spec GREEN in the process.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-17
- **Tasks:** 3 completed (+ 1 deviation fix commit)
- **Files modified:** 5 (4 new, 1 modified)

## Accomplishments
- `severity-glyph.ts` extracted verbatim from `tickets-table.tsx` (`SEVERITY_GLYPH`/`SEVERITY_CLASS`); `tickets-table.tsx` rewired to import it with byte-identical rendering (pre-existing `tickets-table.test.tsx` stays green)
- `KanbanCard` renders the D-CARD-01 layout (provider mark + mono ID + truncated title on top; severity glyph + SLA pill + assignee avatar on bottom), red `border-l-severity-critical` accent when blocked, **no** status pill, `useDraggable`-wired with an `overlay` prop for the future `DragOverlay` clone, and emits `data-ticket-id` per the 18-01 e2e DOM contract
- `KanbanColumn` renders a status-accent header (dot + label + live count badge matching the D-P-04 color family), a canonical per-column `EmptyState` when empty, a drag-dim cue (`opacity-40` when not a valid drop target), stays `useDroppable`-enabled at all times (gating deferred to 18-03's `onDragEnd`), and emits `data-column` + `role="region"` per the 18-01 e2e DOM contract
- `KanbanReasonPrompt` mirrors `blocked-toggle.tsx` exactly (Save → `trim() || null`, Cancel → no mutation, Enter → Save, Escape → Cancel, deferred autofocus) — the 18-01 RED unit spec (`kanban-reason-prompt.test.tsx`, 4 cases) is now GREEN
- Post-task ESLint sweep surfaced 3 real violations (not caught by the plan's grep-based acceptance gates) — all fixed and verified before final commit: a `react-hooks/rules-of-hooks` bug in the overlay branch, a `jsx-a11y/click-events-have-key-events` gap on the card, and an unsupported `aria-disabled` on the column's `role="region"`
- `cd frontend && npx vitest run src/components/tickets/` — 13 files, 69/69 tests green (plan-completion gate)
- `cd frontend && npx tsc --noEmit` — zero errors in any of the 5 touched files
- `cd frontend && npx eslint src/components/tickets/` — zero errors/warnings after the deviation fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract severity-glyph.ts + build draggable KanbanCard** - `0c13f9e` (feat)
2. **Task 2: Build the droppable KanbanColumn** - `6fa68e9` (feat)
3. **Task 3: Build KanbanReasonPrompt (turns 18-01 RED test GREEN)** - `ab03406` (feat)
4. **Deviation fix: resolve eslint a11y/hooks violations** - `1395505` (fix)

## Files Created/Modified
- `frontend/src/components/tickets/severity-glyph.ts` - shared `SEVERITY_GLYPH`/`SEVERITY_CLASS` literal maps, pure module (no React)
- `frontend/src/components/tickets/tickets-table.tsx` - local severity consts removed, now imports from `./severity-glyph`; rendering unchanged
- `frontend/src/components/tickets/kanban-card.tsx` - draggable compact ticket card, `overlay` prop for `DragOverlay`, Enter-key + click both open the drill
- `frontend/src/components/tickets/kanban-column.tsx` - droppable column with status-accent header, live count badge, per-column `EmptyState`, drag-dim cue
- `frontend/src/components/tickets/kanban-reason-prompt.tsx` - inline optional-reason popover mirroring `blocked-toggle.tsx`

## Decisions Made
- `isTicketProvider` duplicated locally in `kanban-card.tsx` per the plan's `<interfaces>` block (not extracted to a shared module) — consistent with the existing codebase pattern of per-file private copies (`tickets-table.tsx`, `dashboard/tickets/page.tsx`)
- Dropped `aria-disabled` from `KanbanColumn`'s `role="region"` wrapper — not part of the ARIA spec for that role; the `opacity-40` dim cue alone satisfies the visual D-DRAG-03 requirement
- `KanbanCard`'s Enter key forwards to dnd-kit's own `listeners.onKeyDown` before also calling `onOpen`, so keyboard-drag activation (whatever sensors 18-03 wires) and "keyboard-equivalent of click" coexist without stealing Space

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `useDraggable` called conditionally in the `overlay` branch**
- **Found during:** post-Task-3 ESLint sweep (not part of any task's grep-based verify block)
- **Issue:** The plan's action text said "UNLESS `overlay` is true... skip the hook" — implemented as an early `return` before the `useDraggable()` call. This violates `react-hooks/rules-of-hooks` (hooks must run in the same order on every render) and would throw at runtime the moment `overlay` toggled across renders of the same component instance.
- **Fix:** Moved `useDraggable({ id: ticket.id })` to the top of the component, called unconditionally on every render; the `overlay` branch now simply doesn't attach the returned `ref`/`attributes`/`listeners` to its static clone.
- **Files modified:** `frontend/src/components/tickets/kanban-card.tsx`
- **Verification:** `npx eslint src/components/tickets/kanban-card.tsx` — 0 errors (was 1). `npx tsc --noEmit` clean.
- **Committed in:** `1395505`

**2. [Rule 1 - Bug] Click-only interaction on `KanbanCard` had no keyboard equivalent**
- **Found during:** post-Task-3 ESLint sweep
- **Issue:** `onClick={() => onOpen(ticket)}` on a non-native-interactive `<div>` with no matching `onKeyDown` fails `jsx-a11y/click-events-have-key-events` — keyboard-only users could not open the drill from a card.
- **Fix:** Added an `onKeyDown` handler that forwards to dnd-kit's own `listeners.onKeyDown` (preserving whatever keyboard-drag activation 18-03's `DndContext` wires up) and additionally calls `onOpen(ticket)` on `Enter` — mirroring the existing `tickets-table.tsx` row pattern (Enter/Space → `onRowClick`), restricted to `Enter` only so `Space` stays free for dnd-kit's typical drag-pickup key.
- **Files modified:** `frontend/src/components/tickets/kanban-card.tsx`
- **Verification:** `npx eslint` clean; `npx vitest run src/components/tickets/` 69/69 still green (no existing test exercised this path, so no regression risk).
- **Committed in:** `1395505`

**3. [Rule 1 - Bug] Unsupported `aria-disabled` attribute on `role="region"`**
- **Found during:** post-Task-3 ESLint sweep
- **Issue:** `jsx-a11y/role-supports-aria-props` flagged `aria-disabled` on the column wrapper — the ARIA spec does not define `aria-disabled` as a supported state/property for the `region` role, so assistive tech has no defined behavior for it there.
- **Fix:** Removed the `aria-disabled` attribute. The task's acceptance criteria only require the `opacity-40` dim class (present and unchanged) — no acceptance criterion referenced `aria-disabled`, so removing it does not regress any gate.
- **Files modified:** `frontend/src/components/tickets/kanban-column.tsx`
- **Verification:** `npx eslint src/components/tickets/kanban-column.tsx` — 0 errors (was 1).
- **Committed in:** `1395505`

---

**Total deviations:** 3 auto-fixed (all Rule 1 — lint/correctness bugs surfaced by a project-standard ESLint sweep that ran after the plan's own grep-based `<verify>` blocks, which did not check for these issues)
**Impact on plan:** All three fixes are scoped exclusively to files this plan created; no scope creep, no architectural change, no acceptance-criteria regression. `npx vitest run src/components/tickets/` (69/69), `npx tsc --noEmit` (0 errors in touched files), and `npx eslint src/components/tickets/` (0 errors/warnings) all pass after the fixes.

## Issues Encountered
- The plan's task-level `<verify>` blocks are grep/vitest based and did not run ESLint, so the 3 deviations above were only caught by an additional post-task lint sweep. Recommend future plans in this phase include an ESLint gate in `<verify>` for new interactive/a11y-bearing components (draggable/droppable leaves in particular are prone to rules-of-hooks and click-without-keydown mistakes).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `KanbanCard`, `KanbanColumn`, and `KanbanReasonPrompt` are pure presentational/interaction leaves, ready for 18-03 to assemble into the `DndContext` board container — their prop contracts (`ticket`/`onOpen`/`overlay`; `columnKey`/`label`/`count`/`isValidTarget`/`isDragActive`/`children`/`isEmpty`; `ticketLabel`/`onSave`/`onCancel`) match the plan's `<interfaces>` block exactly, so 18-03 is pure assembly with no further leaf-component changes expected.
- The `data-ticket-id` and `data-column` attributes required by the 18-01 RED e2e spec (`tickets-kanban.spec.ts`) are already emitted by these leaves — 18-03 only needs to render them inside the board's `DndContext`/columns without modification.
- `KanbanReasonPrompt`'s RED unit spec is now fully GREEN (4/4); no remaining Wave 1 unit-test debt.
- No blockers for Wave 2 (18-03: `DndContext` container + page wiring) or Wave 3 (mobile degradation, remaining polish).

---
*Phase: 18-tickets-kanban-board*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created files confirmed present on disk (severity-glyph.ts, kanban-card.tsx, kanban-column.tsx, kanban-reason-prompt.tsx). `tickets-table.tsx` modification confirmed (imports from `./severity-glyph`, no local `SEVERITY_GLYPH` const). All 4 commits (`0c13f9e`, `6fa68e9`, `ab03406`, `1395505`) confirmed present in `git log --oneline`.
