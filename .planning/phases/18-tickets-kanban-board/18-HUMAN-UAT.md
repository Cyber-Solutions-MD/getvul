---
status: partial
phase: 18-tickets-kanban-board
source: [18-VERIFICATION.md, 18-REVIEW-FIX.md]
started: "2026-07-18"
updated: "2026-07-18"
---

## Current Test

[awaiting human testing]

## Tests

### 1. CR-01 — Enter key: drag vs. drill (keyboard a11y)
expected: On `/dashboard/tickets?view=board`, Tab to focus a card, press Space to pick it up, use arrows to move to the Blocked column, press Enter to drop → the reason prompt opens and the DrillPanel does NOT open. Separately, pressing Enter on a focused card when NOT mid-drag opens the DrillPanel. (Fix: `handleKeyDown` bails on `e.defaultPrevented` so the drill only opens when dnd-kit did not consume Enter for the drag.)
result: [pending]

### 2. WR-02 — Screen-reader announcement on a no-op drop
expected: With a screen reader (or the a11y live-region inspector) active, drag a card from a read-only lane and drop it back on a read-only lane (a gated no-op). The announcement reads "…returned to its column" (or equivalent), NOT a false "Dropped … on the {column}". A real committed move into/out of Blocked still announces the move.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
