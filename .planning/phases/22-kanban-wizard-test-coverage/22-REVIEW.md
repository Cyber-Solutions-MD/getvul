---
phase: 22-kanban-wizard-test-coverage
reviewed: 2026-07-22T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - frontend/e2e/connector-wizard-a11y.spec.ts
  - frontend/e2e/tickets-kanban.spec.ts
  - frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx
  - frontend/src/components/tickets/kanban-column.tsx
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-07-22
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 22 is a test-coverage phase: two e2e specs were extended and two production
files received small keyboard-accessibility fixes surfaced by the new tests. I
reviewed both production changes for regression risk and both specs for
correctness (vacuous passes, selectors, timing).

**Production changes are sound.** The `kanban-column.tsx` `min-w-0` addition is a
correct, low-risk flexbox fix (`min-width:auto` → `0` so `flex-1` columns share
width equally regardless of content), and its rationale — keeping the
coordinateGetter's per-column center-point away from a boundary — is accurate.
The `tickets-kanban-board.tsx` coordinateGetter change (targeting the target
column's own vertical center instead of the dragged card's carried-over `y`) is
well-reasoned and fixes a real collision-detection skip past short/empty
intermediate columns. Verified against the git diff — those are the only two
production hunks in this phase.

**Both new tests are non-vacuous.** I confirmed the CR-01 Enter-drag test's
`[data-drill-panel]` assertion is meaningful: `DrillPanel` returns `null` when
closed (so the element is genuinely absent), and the board branch wires
`onOpen={onRowClick}` (page.tsx:278) to a handler that flips the URL to
`?open=drill` and mounts the panel — so a broken `e.defaultPrevented` guard would
mount `data-drill-panel` and fail the test. The gated-no-op test's interim
"is over the In progress column" assertion is a genuine anti-vacuous gate.

The findings below are one real a11y correctness concern (pre-existing, but now
codified by the new WR-02 assertion) plus minor robustness/cleanliness items.

## Warnings

### WR-01: "Moved to Blocked" is announced at drop, before the reason prompt is confirmed

**File:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:238-261`
**Issue:** The `announcements.onDragEnd` gating treats read-only→Blocked as a
`committed` move and announces `"Moved ticket X to the Blocked column."`. But
`handleDragEnd` does NOT mutate for that transition — it only opens
`KanbanReasonPrompt` (`setPendingBlock(...)`, line 203-207); the move is committed
only when the user clicks Save. dnd-kit fires the `onDragEnd` announcement
synchronously at drop, so the screen reader hears "Moved to Blocked" *before* the
Save/Cancel decision. If the user then Cancels, `onCancel` just clears
`pendingBlock` with no correcting announcement — the card visibly snaps back while
the SR was already told it moved. This is the same false-success class the WR-02
gating was written to eliminate, applied incompletely: read-only→read-only is
correctly gated, but read-only→Blocked is announced as done while still pending.
The new `keyboard drag` test (tickets-kanban.spec.ts:201) now asserts and thereby
locks in this premature wording.

Note: this is pre-existing behavior (the announcements block is not part of this
phase's production diff — only the coordinateGetter `y` and `min-w-0` changed).
Flagging because the new test enshrines it and a11y is a first-class concern here.

**Fix:** Announce the pending state for the read-only→Blocked case rather than a
completed move, and only announce "Moved…" after Save. For example, treat only
Blocked→read-only (the immediate-commit path) as `committed` in the announcement,
and give read-only→Blocked its own message:
```ts
// read-only -> Blocked opens the reason prompt (not yet committed)
if (!card.blocked && overKey === 'blocked') {
  return `Ticket ${labelFor(active.id)} ready to block — confirm the reason to finish.`;
}
// Blocked -> read-only commits immediately
if (card.blocked && READ_ONLY_LANES.has(overKey)) {
  return `Moved ticket ${labelFor(active.id)} to the ${colLabel(over!.id)} column.`;
}
return `Ticket ${labelFor(active.id)} returned to its column.`;
```
Then emit the confirmed "Moved…" announcement from the prompt's `onSave` (e.g. via
a polite live region) so Cancel leaves no stale success. Update the WR-02 test
assertion (spec:201) to match the confirmed-on-Save wording.

## Info

### IN-01: `currentCoordinates` is now an unused destructured binding

**File:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:80`
**Issue:** This phase's change replaced the getter's only use of
`currentCoordinates` (`y: currentCoordinates.y` → `y: rect.top + rect.height / 2`),
but the parameter is still destructured at line 80, leaving it dead. It slipped the
lint gate because `next/core-web-vitals` treats `no-unused-vars` as a warning, but
it's now genuinely unreferenced (only the surrounding comment mentions it).
**Fix:** Drop it from the destructure: `return (event, { context }) => {`.

### IN-02: coordinateGetter advances `columnIndexRef` before the rect-availability check

**File:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx:88-95`
**Issue:** `columnIndexRef.current` is incremented (lines 88-91) *before*
`const rect = ...; if (!rect) return undefined;` (lines 94-95). If a target column's
`rect.current` is momentarily unmeasured, the getter returns `undefined` (no move)
but the ref has already advanced — so the next ArrowRight increments from the
wrong index and skips a column, desyncing the tracked index from the drag's actual
position. Low probability in practice (droppable rects are populated mid-drag), and
pre-existing (not changed this phase), but the ordering is fragile.
**Fix:** Resolve the rect first and only advance the ref when a valid target exists:
```ts
const target = Math.min(Math.max(columnIndexRef.current + direction, 0), COLUMN_ORDER.length - 1);
const rect = context.droppableContainers.get(COLUMN_ORDER[target])?.rect.current;
if (!rect) return undefined;
columnIndexRef.current = target;
```

### IN-03: keyboard-drag tests pick `cards.first()` without ensuring a non-Blocked source

**File:** `frontend/e2e/tickets-kanban.spec.ts:175, 219`
**Issue:** The `keyboard drag` and `keyboard drag with Enter` tests grab
`cards.first()` (DOM order = first non-empty column). If seed data ever placed the
first DOM card in the Blocked column, `handleDragStart` sets `columnIndexRef` to 3,
the six ArrowRight presses clamp there, and the Space/Enter drop becomes a
blocked→blocked no-op — no reason prompt appears and the `waitFor` Save button
times out (a confusing false *failure*, not a false pass). The sibling gated-no-op
test correctly scopes to `[data-column="open"] [data-ticket-id]`; these two do not.
Low probability with current seeds, but the tests would be more robust scoped the
same way.
**Fix:** Source the card from a read-only lane explicitly, e.g.
`page.locator('[data-column="open"] [data-ticket-id]').first()`, mirroring the
gated-no-op test.

### IN-04: connector wizard `driveToTestStep` fills every input with the literal `'test-value'`

**File:** `frontend/e2e/connector-wizard-a11y.spec.ts:234-240`
**Issue:** The provider-agnostic loop fills all `input`s with `'test-value'`. This
assumes no rendered credential field applies client-side format validation (URL,
port/number, etc.) that would keep the "Next" button disabled — if a provider adds
such a field, `driveToTestStep` would stall at the click. The `connectors/test`
call is mocked so the *value* never matters server-side; the only risk is
client-side gating. Acceptable given the current field set, but worth a comment so
a future provider addition doesn't silently break the sweep.
**Fix:** Note the assumption in the helper's docstring, or fill by input `type`
(e.g. a valid `https://…` for `type=url`, a digit for `type=number`) if any wizard
field gains format validation.

---

_Reviewed: 2026-07-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
