# Phase 18: Tickets kanban board - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 18-tickets-kanban-board
**Areas discussed:** Drag semantics / what persists, Columns + filter + empty states, Mobile <768px degradation, Card content + click behavior

---

## Drag semantics / what persists

| Option | Description | Selected |
|--------|-------------|----------|
| Blocked-only drop target | Only Blocked accepts drops; reuses /blocked + useMarkBlocked; Open/IP/Completed read-only | ✓ |
| New internal workflow status | New column + endpoint so all 4 draggable; dual-status model | |
| Provider status write-back | Drag → Jira/Asana/GitHub transition; contradicts P13 locked deferrals | |

**User's choice:** Blocked-only drop target.

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt for reason on drop | Inline popover for optional reason (Save/Cancel); Cancel snaps back | ✓ |
| Block immediately, edit later | Instant block, reason edited afterward | |

**User's choice:** Prompt for reason on drop.

| Option | Description | Selected |
|--------|-------------|----------|
| Dim + not-droppable, snap back | Read-only lanes dim / show no-drop cue during drag | ✓ |
| Look normal, silently snap back | No visual differentiation | |

**User's choice:** Dim + not-droppable, snap back.

| Option | Description | Selected |
|--------|-------------|----------|
| Same flow, keyboard-driven | Space grab, arrows to Blocked, Space drop → same reason prompt; SR announcements | ✓ |
| Keyboard toggles Blocked directly | Enter/menu action instead of drag metaphor | |

**User's choice:** Same flow, keyboard-driven.

---

## Columns + filter + empty states

| Option | Description | Selected |
|--------|-------------|----------|
| Blocked column wins | blocked=true card lives only in Blocked; unblock re-homes to provider column | ✓ |
| Provider column with blocked accent | Card stays in provider column with red accent | |

**User's choice:** Blocked column wins.

| Option | Description | Selected |
|--------|-------------|----------|
| Always show all 4, empty → EmptyState | Stable layout; empty columns render canonical EmptyState; chip filter still applies | ✓ |
| Hide unselected-status columns | Render only selected-status columns | |

**User's choice:** Always show all 4, empty → EmptyState.

| Option | Description | Selected |
|--------|-------------|----------|
| Flow order + live count | Open → IP → Completed → Blocked; header status accent + live count badge | ✓ |
| Order only, no counts | Same order, no count badge | |

**User's choice:** Flow order + live count.

---

## Mobile <768px degradation

| Option | Description | Selected |
|--------|-------------|----------|
| Horizontal-scroll columns | Keep 4 columns, scroll-snap ~85vw each; bottom-nav stays fixed | ✓ |
| Single-column switcher | Segmented control to switch one column at a time | |
| Fall back to list view | Force list, hide board toggle below 768px | |

**User's choice:** Horizontal-scroll columns.

| Option | Description | Selected |
|--------|-------------|----------|
| Long-press to drag | TouchSensor press-delay (~200ms) drags; quick swipe scrolls | ✓ |
| Tap-action fallback on mobile | Card 'Block/Unblock' action instead of touch-drag | |

**User's choice:** Long-press to drag.

---

## Card content + click behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Compact card | Provider mark + ID + title / severity + SLA + assignee; no status pill (column conveys it) | ✓ |
| Full-detail card | All list-row fields incl. vuln-count + status pill; taller cards | |

**User's choice:** Compact card.

| Option | Description | Selected |
|--------|-------------|----------|
| Open the DrillPanel | Click opens same DrillPanel as list row (?ticket=...&open=drill) | ✓ |
| Navigate to /tickets/[id] | Click goes to full detail page | |
| No click action | Drag-only cards | |

**User's choice:** Open the DrillPanel.

---

## Claude's Discretion

- Null/unrecognized `external_status` → Open column
- Degrade breakpoint = 768px (Tailwind md, matches Phase 15 bottom-nav)
- Mobile column snap width ~85vw with CSS scroll-snap
- @dnd-kit install with --legacy-peer-deps (React 19 peer)
- dnd-kit activation constraints (click-vs-drag distance, keyboard coordinate getter)
- Optimistic column reprojection wiring on block/unblock

## Deferred Ideas

- Provider status write-back (locked deferred P13 D-P-01 / D-PROV-02)
- GetVul-internal workflow_status field (considered, rejected — dual-status complexity)
- Bulk drag / multi-select on board
- WIP limits / column customization / reordering
- Single-column mobile switcher (fallback if touch-drag proves unreliable)
