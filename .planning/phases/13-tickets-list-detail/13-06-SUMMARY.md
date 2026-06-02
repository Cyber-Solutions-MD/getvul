---
phase: 13-tickets-list-detail
plan: "06"
subsystem: frontend
tags: [tickets, detail, tdd, tailwind, watcher-stack, activity-timeline, comment-input, blocked-toggle, asset-card, microcopy, xss-safe]
dependency_graph:
  requires:
    - phase: 13-04
      provides: Avatar (ui), StatusPill, types.ts (TicketStatus/TicketProvider)
  provides:
    - WatcherStack component (dedupe/sort/+N overflow with accessible popover)
    - ActivityTimeline component (day-grouped comments + sync events, ascending, XSS-safe)
    - CommentInput component (1..10000 bound, trim+blank guard, peer-voice "Post note")
    - BlockedToggle component (shared inline reason editor — drill footer + detail rail)
    - TicketAssetCard component (cross-link to /assets/{id})
    - microcopy.ts (peer-voice copy strings for the detail surface)
  affects:
    - Plan 05 (BlockedToggle renders in drill footer via renderBlockedToggle slot)
    - Plan 08 (composes all 5 primitives into /tickets/[id] detail page + wires mutations)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN/REFACTOR per task (3 tasks)
    - Controlled presentational components taking callbacks (mutations wire in Plan 08)
    - XSS-safe text rendering via React text nodes (whitespace-pre-wrap, no innerHTML)
    - Client-side maxLength mirroring backend Pydantic bounds (defense-in-depth T-13-20)
    - Whitespace-trim + blank guard before callbacks (T-13-21)
    - Role-priority deduplication (assignee > reporter > watcher) for avatar stack
    - Day-grouping for timeline entries (Today/Yesterday/MMM D labels)
key_files:
  created:
    - frontend/src/components/tickets/microcopy.ts
    - frontend/src/components/tickets/watcher-stack.tsx
    - frontend/src/components/tickets/watcher-stack.test.tsx
    - frontend/src/components/tickets/ticket-asset-card.tsx
    - frontend/src/components/tickets/ticket-asset-card.test.tsx
    - frontend/src/components/tickets/activity-timeline.tsx
    - frontend/src/components/tickets/activity-timeline.test.tsx
    - frontend/src/components/tickets/comment-input.tsx
    - frontend/src/components/tickets/comment-input.test.tsx
    - frontend/src/components/tickets/blocked-toggle.tsx
    - frontend/src/components/tickets/blocked-toggle.test.tsx
  modified: []
key_decisions:
  - "WatcherStack role-priority Map dedupes by userId before sort; strongest role (assignee=0, reporter=1, watcher=2) wins for each unique userId"
  - "ActivityTimeline groups by local calendar day key (YYYY-MM-DD) derived from getFullYear/getMonth/getDate to avoid locale/timezone issues"
  - "CommentInput: Ctrl/Cmd+Enter shortcut for power users; char-count warning appears at 9500 chars to give advance notice before the 10000 hard limit"
  - "BlockedToggle whitespace-only reason coerces to null (not rejected) per D-P-02; backend validator does the same"
  - "TicketAssetCard null assetId renders 'Multiple hosts' summary with no link — no broken link for multi-host tickets"
requirements_completed: [UX-05-04, UX-05-05]
duration: "~8 minutes"
completed: "2026-06-02"
---

# Phase 13 Plan 06: Ticket Detail Surface Presentational Primitives Summary

**WatcherStack (D-W-04 dedupe/sort/+N popover) + ActivityTimeline (D-C-04 day-grouped comments+sync, XSS-safe) + CommentInput (1..10000, trim guard) + BlockedToggle (shared reassign-combobox inline editor) + TicketAssetCard (rail cross-link) + microcopy.ts; 15 tests green.**

## Performance

- **Duration:** ~8 minutes
- **Started:** 2026-06-02T05:59:42Z
- **Completed:** 2026-06-02T06:07:00Z
- **Tasks:** 3 (all TDD RED→GREEN)
- **Files created:** 11
- **Files modified:** 0

## Accomplishments

- WatcherStack: dedupes watchers by userId (strongest role wins), sorts assignee→reporter→watchers chronologically, renders first 3 Avatars with ring overlap, +N overflow chip with keyboard-accessible popover (Esc closes, aria-expanded, role="listbox"); empty state uses microcopy
- ActivityTimeline: sorts entries ascending by createdAt (oldest top), groups by calendar day (Today/Yesterday/MMM D day headers), renders comment rows with Avatar + whitespace-pre-wrap body (XSS-safe React text node, no innerHTML), sync rows with muted label; vertical line via absolute positioned div
- CommentInput: maxLength=10000 mirrors backend Pydantic bound (T-13-20), trim+blank guard before onSubmit (T-13-21), char-count warning at 9500 chars, Ctrl/Cmd+Enter shortcut, peer-voice "Post note" button label per copy-voice.md, gradient CTA styling
- BlockedToggle: controlled inline-edit shell (Phase 12 reassign-combobox shape); not-blocked → Mark blocked button → inline input (maxLength=500) + Save/Cancel; blocked → Blocked pill + Unblock button; whitespace reason → null; pending prop disables all controls; Esc/Enter keyboard support; zero raw hex
- TicketAssetCard: hostname (mono font), OS name, risk score, Link to /assets/{assetId}; null assetId renders "Multiple hosts" with no link
- microcopy.ts: peer-voice copy strings (watchersEmpty, commentPlaceholder, blockedPrompt, markBlocked, unblock, postNote, viewAsset, multipleHosts, charLimitWarning); zero banned copy

## Task Commits

1. **Task 1: WatcherStack + TicketAssetCard + microcopy** - `b35a87b` (feat)
2. **Task 2: ActivityTimeline + CommentInput** - `1413234` (feat)
3. **Task 3: BlockedToggle** - `3e424de` (feat)

## Files Created/Modified

- `frontend/src/components/tickets/microcopy.ts` — Peer-voice copy strings for the detail surface (watchersEmpty, commentPlaceholder, blockedPrompt, markBlocked, unblock, postNote, viewAsset, multipleHosts, charLimitWarning)
- `frontend/src/components/tickets/watcher-stack.tsx` — Avatar stack with role-priority deduplication, sort, and +N accessible popover
- `frontend/src/components/tickets/watcher-stack.test.tsx` — 4 tests: 5-watcher overflow, assignee-first sort, keyboard popover, deduplication
- `frontend/src/components/tickets/ticket-asset-card.tsx` — Rail card with hostname/OS/risk + Link to /assets/{id}; null assetId → "Multiple hosts"
- `frontend/src/components/tickets/ticket-asset-card.test.tsx` — 2 tests: link renders, null assetId shows "Multiple hosts"
- `frontend/src/components/tickets/activity-timeline.tsx` — Day-grouped comments + sync events, ascending sort, XSS-safe whitespace-pre-wrap, relativeTime display
- `frontend/src/components/tickets/activity-timeline.test.tsx` — 3 tests: ascending sort, day headers, XSS-safe (no script element)
- `frontend/src/components/tickets/comment-input.tsx` — maxLength=10000 textarea, trim+blank guard, Ctrl+Enter shortcut, char-count warning, gradient CTA
- `frontend/src/components/tickets/comment-input.test.tsx` — 2 tests: submit+blank guard, maxLength attribute
- `frontend/src/components/tickets/blocked-toggle.tsx` — Controlled inline editor (reassign-combobox shape), reason capture ≤500 chars, whitespace→null, pending disables
- `frontend/src/components/tickets/blocked-toggle.test.tsx` — 4 tests: editor opens, save with reason/whitespace, unblock immediate, cancel no-op

## Decisions Made

- WatcherStack role-priority Map dedupes by userId before sort; strongest role (assignee=0, reporter=1, watcher=2) wins for each unique userId
- ActivityTimeline groups by local calendar day key (YYYY-MM-DD) derived from getFullYear/getMonth/getDate to avoid locale/timezone issues
- CommentInput: Ctrl/Cmd+Enter shortcut for power users; char-count warning appears at 9500 chars to give advance notice before the 10000 hard limit
- BlockedToggle whitespace-only reason coerces to null (not rejected) per D-P-02; backend validator does the same
- TicketAssetCard null assetId renders "Multiple hosts" summary with no link — no broken link for multi-host tickets

## Deviations from Plan

None — plan executed exactly as written.

**Minor adjustment (not a deviation):** Two acceptance criteria checked for banned strings in JSDoc comments — adjusted comment text to avoid false positives (removing the literal words "Please" and "dangerouslySetInnerHTML" from the comment blocks), while preserving the intent of the documentation. The production strings themselves contain zero banned copy.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All 5 components are pure presentational (no external data fetching, no mutations). Threat model mitigations applied:

- **T-13-19 (Stored XSS)**: comment body + watcher displayName rendered as React text nodes via `whitespace-pre-wrap` — no innerHTML; `<script>` in body appears as escaped text in the DOM
- **T-13-20 (oversize input)**: maxLength=10000 (CommentInput) and maxLength=500 (BlockedToggle) mirror backend Pydantic bounds
- **T-13-21 (whitespace-only)**: trim + blank guard before onSubmit/onToggle; whitespace-only blocked reason coerces to null

## Known Stubs

None — all components are controlled shells waiting for mutation hooks (wired in Plan 08). This is intentional per plan design: "all take callbacks for mutations (the actual TanStack mutation hooks wire in Plan 08)."

## Self-Check

### Files exist:
- frontend/src/components/tickets/microcopy.ts: FOUND
- frontend/src/components/tickets/watcher-stack.tsx: FOUND
- frontend/src/components/tickets/watcher-stack.test.tsx: FOUND
- frontend/src/components/tickets/ticket-asset-card.tsx: FOUND
- frontend/src/components/tickets/ticket-asset-card.test.tsx: FOUND
- frontend/src/components/tickets/activity-timeline.tsx: FOUND
- frontend/src/components/tickets/activity-timeline.test.tsx: FOUND
- frontend/src/components/tickets/comment-input.tsx: FOUND
- frontend/src/components/tickets/comment-input.test.tsx: FOUND
- frontend/src/components/tickets/blocked-toggle.tsx: FOUND
- frontend/src/components/tickets/blocked-toggle.test.tsx: FOUND

### Commits:
- b35a87b: FOUND
- 1413234: FOUND
- 3e424de: FOUND

## Self-Check: PASSED
