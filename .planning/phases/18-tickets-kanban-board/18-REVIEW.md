---
phase: 18-tickets-kanban-board
reviewed: 2026-07-17T14:59:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - frontend/e2e/a11y-routes.spec.ts
  - frontend/e2e/reduced-motion.spec.ts
  - frontend/e2e/tickets-kanban.spec.ts
  - frontend/src/app/(authed)/dashboard/tickets/page.tsx
  - frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx
  - frontend/src/components/tickets/bucket-tickets.test.ts
  - frontend/src/components/tickets/bucket-tickets.ts
  - frontend/src/components/tickets/kanban-card.tsx
  - frontend/src/components/tickets/kanban-column.tsx
  - frontend/src/components/tickets/kanban-reason-prompt.test.tsx
  - frontend/src/components/tickets/kanban-reason-prompt.tsx
  - frontend/src/components/tickets/severity-glyph.ts
  - frontend/src/components/tickets/tickets-table.tsx
  - frontend/src/lib/queries/use-mark-blocked.test.ts
  - frontend/src/lib/queries/use-mark-blocked.ts
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-07-17T14:59:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the Tickets kanban board (Phase 18): the @dnd-kit `DndContext` container, the pure-projection bucketing helper, the draggable card / droppable column / reason-prompt leaf components, the optimistic `useMarkBlocked` mutation, the list-page wiring, and the associated unit + e2e specs.

The board's core architecture is sound — the "board-as-pure-projection" pattern (no board-local row state, re-bucket on every render, optimistic re-project via the fuzzy `['tickets','list']` cache patch) is coherent and the `useMarkBlocked` optimistic/rollback logic is well-tested. `bucketTickets` is pure and correctly covered.

However, the review surfaced one BLOCKER in the keyboard interaction path (Enter simultaneously starts a drag and opens the drill panel — on a path the component's own screen-reader instructions advertise), plus a functional gap where the board silently renders only the first page of tickets. Several a11y/UX consistency warnings and maintainability items follow.

No secrets, injection, or unsafe-DOM issues were found; user data renders as React text children throughout and the mutation body is mass-assignment-guarded.

## Critical Issues

### CR-01: Enter key on a kanban card starts a drag AND opens the drill panel simultaneously

**File:** `frontend/src/components/tickets/kanban-card.tsx:97-102`
**Issue:** `handleKeyDown` first forwards the event to dnd-kit's listener (`listeners?.onKeyDown?.(e)`) and then unconditionally calls `onOpen(ticket)` on `Enter`. dnd-kit's `KeyboardSensor` treats **Enter** as both a drag *start* and drag *drop/end* activator (its default start/end keys are `Space` and `Enter`). Two consequences:

1. **Pick-up:** Pressing Enter on a focused card begins a keyboard drag *and* fires `onOpen`, which does `router.replace(?ticket=…&open=drill)` and opens the DrillPanel. The panel steals/traps focus, breaking the drag that was just initiated.
2. **Drop:** While a keyboard drag is in flight, the card retains focus, so pressing Enter to *drop* also re-enters `handleKeyDown` → `onOpen` fires again, re-opening the drill.

This is a correctness defect on a documented interaction path: the board's own `screenReaderInstructions.draggable` literally tells users "To pick up a ticket, press Space or **Enter**." Following that instruction produces broken, ambiguous behavior. (Space happens to work because `handleKeyDown` only special-cases `Enter`, which is why the e2e keyboard-drag spec — which uses Space — stays green and masks this.)

**Fix:** Disambiguate by respecting whether dnd-kit consumed the key. The `KeyboardSensor` calls `preventDefault()` when it activates/drops/cancels a drag, so:
```tsx
const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
  listeners?.onKeyDown?.(e);
  // dnd-kit consumed this key for drag start/drop/cancel — don't also open the drill.
  if (e.defaultPrevented) return;
  if (e.key === 'Enter') {
    onOpen(ticket);
  }
};
```

## Warnings

### WR-01: Board view renders only the current page of tickets, with no pagination

**File:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:253-259`, `frontend/src/lib/queries/use-tickets.ts:53-98,111-115`
**Issue:** The board receives `rows={items}` where `items = q.data?.items` — a single paginated page (`page_size` ~25). Unlike the list branch, the board branch renders **no `Pagination` control**. Worse, `buildSearchParams` (use-tickets.ts) never consumes `view`, so a `view=board` query fetches the identical paginated payload as the list. Result: any ticket beyond page 1 is invisible and unreachable in board view — the analyst cannot see or drag it. For a triage board this is a real functional gap (a "Blocked" ticket on page 2 simply never appears in the Blocked column).
**Fix:** Either fetch an unpaginated/large-page dataset for the board (have the backend/`buildSearchParams` honor `view=board` with a higher page size or a distinct endpoint), or add pagination affordance to the board branch. At minimum, surface that the board is showing only the current page.

### WR-02: Screen-reader "Dropped on {column}" announcement fires even for gated no-op drops

**File:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:225-234`
**Issue:** `announcements.onDragEnd` announces `Dropped ticket X on the {column} column.` whenever `over` is set. But most drops are gated no-ops in `handleDragEnd` (read-only→read-only and blocked→blocked snap back with no mutation, lines 196-202). A screen-reader user who drags a card between two read-only lanes hears a success announcement for a move that never happened, contradicting the visual snap-back. This defeats the a11y intent.
**Fix:** Mirror the gating logic in the announcement — only announce a committed move when the drop is a valid transition; otherwise announce that the ticket returned to its column, e.g.:
```ts
onDragEnd: ({ active, over }) => {
  const card = rowsById.get(String(active.id));
  const committed = over && card && (
    (!card.blocked && over.id === 'blocked') ||
    (card.blocked && READ_ONLY_LANES.has(over.id as ColumnKey))
  );
  return committed
    ? `Moved ticket ${labelFor(active.id)} to the ${colLabel(over!.id)} column.`
    : `Ticket ${labelFor(active.id)} returned to its column.`;
},
```

### WR-03: `asana_not_configured` error is handled in list view but not board view

**File:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:205,253-259` vs `282-292`
**Issue:** In list view, `asanaUnconfigured` routes an expected "connector not configured" signal to the connector-deep-link `EmptyState` (D-S-02). In board view, the code unconditionally renders `<TicketsKanbanBoard error={q.error} />`, whose error branch (tickets-kanban-board.tsx:244-250) shows a generic `PartialFailureBanner`. So the same backend condition produces a helpful "Set up connectors" CTA in one view and an opaque error banner in the other — inconsistent UX and a lost remediation path.
**Fix:** Apply the `asanaUnconfigured` branch before choosing list vs board, or pass an `asanaUnconfigured` flag into the board so it can render the same connector EmptyState.

### WR-04: Board error state has no retry affordance

**File:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:244-250`
**Issue:** The board's error branch renders `PartialFailureBanner` without an `onRetry`, whereas the list branch passes `onRetry={() => q.refetch()}` (page.tsx:291). A transient fetch failure in board view leaves the user with a dead-end banner and no way to recover short of a full reload.
**Fix:** Thread a retry callback into the board (e.g. add an `onRetry?: () => void` prop wired to `q.refetch()`) and pass it to `PartialFailureBanner`.

### WR-05: `KanbanReasonPrompt` uses `role="dialog"` but is neither modal nor dismissible outside its buttons

**File:** `frontend/src/components/tickets/kanban-reason-prompt.tsx:52-57`; container `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:296-307`
**Issue:** The prompt declares `role="dialog"` but has no `aria-modal`, no focus trap, and no backdrop/outside-click dismissal — the board behind it remains fully interactive and Tab can leave the dialog. A `role="dialog"` that doesn't behave like one is misleading to assistive tech, and a user can start another drag while the pending-block prompt is open, leaving `pendingBlock` referencing a stale card. Escape only fires while the input is focused (handler is on the `<input>`, not the dialog), so if focus leaves the input there is no keyboard dismiss.
**Fix:** Either drop `role="dialog"` and treat it as an inline popover (moving the `onKeyDown` Escape handler to the container so Escape works regardless of focus), or make it a real dialog: add `aria-modal="true"`, trap focus, and dismiss on outside click / Escape at the container level. Also consider suppressing drag while `pendingBlock` is set.

## Info

### IN-01: `isTicketProvider` type guard duplicated across three files

**File:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:62-64`, `frontend/src/components/tickets/kanban-card.tsx:33-35`, `frontend/src/components/tickets/tickets-table.tsx:28-30`
**Issue:** The identical `provider is 'jira'|'asana'|'github'` narrowing guard is copy-pasted in three places (one returns `TicketProvider`, one returns the inline union). Divergence risk if the provider set changes.
**Fix:** Export a single `isTicketProvider` from `components/tickets/types.ts` and import it in all three consumers.

### IN-02: Drill-panel render block duplicated verbatim for desktop and mobile

**File:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:325-416`
**Issue:** The `renderContent`/`TicketDrillContent`/`renderBlockedToggle` block (~40 lines, including the CR-06 provider-narrowing comment) is duplicated identically for `DrillPanel` and `DrillPanelMobile`. Any change must be made twice.
**Fix:** Extract a single `renderTicketDrill = ({ id, onClose }) => (…)` callback and pass it to both panels.

### IN-03: e2e drag specs rely on fixed `waitForTimeout` sleeps

**File:** `frontend/e2e/tickets-kanban.spec.ts:102,112,151` (and `reduced-motion.spec.ts` polling)
**Issue:** The drag tests use arbitrary `page.waitForTimeout(200|300)` to settle deferred autofocus and column reflow. Fixed sleeps are a known source of e2e flakiness — they under-wait on slow CI and over-wait otherwise. The inline comments acknowledge the races they paper over.
**Fix:** Replace with condition-based waits where possible (e.g. `await expect(saveButton).toBeEnabled()` / `await saveButton.focus()` before click; wait for the specific card locator to settle rather than a raw timeout).

---

_Reviewed: 2026-07-17T14:59:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
