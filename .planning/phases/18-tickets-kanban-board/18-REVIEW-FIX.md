---
phase: 18-tickets-kanban-board
fixed_at: 2026-07-18T13:25:00Z
review_path: .planning/phases/18-tickets-kanban-board/18-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 18: Code Review Fix Report

**Fixed at:** 2026-07-18T13:25:00Z
**Source review:** .planning/phases/18-tickets-kanban-board/18-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01 + WR-01..WR-05)
- Fixed: 6
- Skipped: 0

**Verification (run once, post-fix, from `frontend/`):**
- `tsc --noEmit` → exit 0 (clean)
- `eslint` on the 4 touched files → exit 0 (clean)
- `vitest run src/components/tickets/` → 13 files, 69 tests passed

_Note: the full Playwright e2e / axe / Lighthouse gate was intentionally NOT run (needs a prod build + running server). CR-01 in particular exercises a keyboard-drag path the unit suite cannot cover — see its human-verification note below._

## Fixed Issues

### CR-01: Enter key on a kanban card starts a drag AND opens the drill panel simultaneously

**Files modified:** `frontend/src/components/tickets/kanban-card.tsx`
**Commit:** eee55de
**Status:** fixed: requires human verification
**Applied fix:** Added `if (e.defaultPrevented) return;` in `handleKeyDown` immediately after forwarding the event to dnd-kit's `listeners.onKeyDown`. dnd-kit's `KeyboardSensor` calls `preventDefault()` when it consumes Enter for a drag start/drop/cancel, so the drill (`onOpen`) now only fires for an Enter that dnd-kit did NOT claim. Matches the reviewer's suggested fix.

_Human-verification note: this is a behavioral fix on a keyboard-interaction path. The existing e2e keyboard-drag spec uses **Space**, so it does not exercise this branch (it masked the bug originally). Recommend a manual keyboard-drag-with-Enter check, or extending `tickets-kanban.spec.ts` to press Enter, before the phase proceeds — the fix relies on dnd-kit actually setting `defaultPrevented` on its Enter activation, which unit tests do not assert._

### WR-01: Board view renders only the current page of tickets, with no pagination

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx`
**Commit:** 7faa111
**Status:** fixed (partial mitigation — see note)
**Applied fix:** Wrapped the board branch in a fragment and rendered the same `Pagination` control the list branch uses (gated on `q.data.pages > 1`, wired to the existing `pageNum` / `handlePageChange`). Tickets beyond page 1 (e.g. a Blocked ticket on page 2) are now reachable and draggable via the pager.

_Note: I took the lower-risk of the reviewer's two options — surfacing a pagination affordance — rather than changing the fetch contract (having `buildSearchParams`/the backend honor `view=board` with a larger page size or a distinct endpoint). The latter touches the wire contract and backend and was out of scope for a safe auto-fix. The board still shows one page at a time; it is no longer a dead end, but a follow-up could fetch an unpaginated dataset for a true single-screen board._

### WR-02: Screen-reader "Dropped on {column}" announcement fires even for gated no-op drops

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`
**Commit:** 6c25f73
**Status:** fixed: requires human verification
**Applied fix:** Rewrote `announcements.onDragEnd` to mirror `handleDragEnd`'s gating: it looks up the dragged card via `rowsById`, computes `committed` for only the two valid transitions (read-only→`blocked`, `blocked`→read-only lane), and announces `"Moved ticket X to the {column} column."` only when committed, otherwise `"Ticket X returned to its column."`. This stops announcing success for snap-back no-ops.

_Human-verification note: flagged for human verification because the gating logic must stay in lockstep with `handleDragEnd`, and screen-reader announcement text is not asserted by the unit suite. Recommend a manual VoiceOver/NVDA pass (or an e2e live-region assertion) on a read-only→read-only drag to confirm the "returned to its column" wording fires._

### WR-03: `asana_not_configured` error is handled in list view but not board view

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx`
**Commit:** 34592aa
**Applied fix:** Hoisted the `asanaUnconfigured` check above the list/board switch. The connector deep-link `EmptyState` (D-S-02, "Set up connectors →") now renders before either view is chosen, so board view gets the same remediation CTA instead of the generic `PartialFailureBanner`. Removed the now-redundant `asanaUnconfigured` branch from inside the list section (no behavior change for list). Copy/CTA reuse the existing connector EmptyState verbatim.

### WR-04: Board error state has no retry affordance

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`, `frontend/src/app/(authed)/dashboard/tickets/page.tsx`
**Commit:** 23921d0
**Applied fix:** Added an optional `onRetry?: () => void` prop to `TicketsKanbanBoardProps`, destructured it, and passed it to the error branch's `PartialFailureBanner`. Wired `onRetry={() => q.refetch()}` from page.tsx — matching the list branch's retry behavior — so a transient board fetch failure is now recoverable in-place.

### WR-05: `KanbanReasonPrompt` uses `role="dialog"` but is neither modal nor dismissible outside its buttons

**Files modified:** `frontend/src/components/tickets/kanban-reason-prompt.tsx`
**Commit:** b8ff253
**Applied fix:** Took the reviewer's "inline popover" route. Changed `role="dialog"` → `role="group"` with the existing accessible name (honest labeling for a non-modal cluster). Split the input's Enter-to-save into `handleInputKeyDown`, and moved Escape-to-cancel into a document-level `keydown` listener (added/removed in a `useEffect`) so Escape works regardless of whether the input or a button holds focus.

_Implementation note: the reviewer suggested moving the Escape handler onto the container. Attaching `onKeyDown` to the `role="group"` div tripped `jsx-a11y/no-noninteractive-element-interactions` (verified via eslint), so I used a document-level listener instead — same behavior (dismiss regardless of focus), no lint violation, no handler on a non-interactive element. The reviewer's optional "consider suppressing drag while `pendingBlock` is set" was left out: sensors are created via top-level `useSensors` hooks and cannot be conditionally disabled without a larger refactor; it is a defensive nicety, not part of the core dialog-semantics defect, so it is deferred._

---

_Fixed: 2026-07-18T13:25:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
