# Phase 18: Tickets kanban board - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the board-view *placeholder* on `/dashboard/tickets` (currently copy-only, rendered when `?view=board`) with a real, keyboard-accessible four-column status kanban (Open / In progress / Completed / Blocked) populated from the existing `useTickets` query, where dragging a card into or out of the **Blocked** column persists via a mutation with optimistic update + rollback.

**In scope:**
- Board body: 4 status columns rendered from `useTickets` data, replacing the placeholder branch in `page.tsx`
- @dnd-kit drag-and-drop (pointer + keyboard + touch sensors), Blocked as the only interactive drop target
- Reason-prompt on drop into Blocked; optimistic block/unblock via existing `POST /{id}/blocked` + `useMarkBlocked`
- Per-column canonical EmptyState; chip-bar filters continue to apply on the board
- Compact kanban card that opens the existing DrillPanel on click
- <768px horizontal-scroll degradation; axe AA in both themes; route ≤250 KB

**Explicitly out of scope (deferred / locked elsewhere):**
- Provider status write-back (drag between Open/IP/Completed → Jira/Asana/GitHub) — locked deferred in Phase 13 D-P-01 + D-PROV-02
- A new GetVul-internal `workflow_status` field/endpoint — considered and rejected this phase (dual-status complexity)
- Any backend schema/endpoint changes — this phase reuses the Phase 13 backend surface as-is
- Bulk drag / multi-card selection on the board
- Column customization / reordering / WIP limits

</domain>

<decisions>
## Implementation Decisions

### Drag semantics — what persists (D-DRAG)

- **D-DRAG-01:** **Blocked-only drop target.** Open / In progress / Completed lanes are **read-only groupings** mirroring `external_status` (provider-synced, per Phase 13 D-P-01). The **Blocked** column is the sole interactive drop target. Dragging a card INTO Blocked sets `blocked=true`; dragging OUT of Blocked (to any read-only lane) sets `blocked=false` (unblock). No provider write-back, no new status field. Reuses the existing `POST /api/v1/tickets/{id}/blocked` endpoint and `useMarkBlocked` hook (already optimistic on both byId and list caches, with rollback on error).

- **D-DRAG-02:** **Reason prompt on drop into Blocked.** Dropping a card into the Blocked column opens a small inline prompt/popover for an *optional* blocked-reason (Save / Cancel), mirroring Phase 13's inline blocked-reason editor. **Cancel snaps the card back** to its origin column and issues no mutation. Save commits the optimistic block with the reason. Whitespace-only reason coerces to null (Phase 13 D-P-02 rule). Unblock (drag OUT of Blocked) needs no prompt — it commits immediately.

- **D-DRAG-03:** **Read-only lanes dim + not-droppable.** While a drag is active, the three provider-mirror lanes (Open/IP/Completed) render a visual "not a drop target" cue (dim / no-drop affordance) so only Blocked reads as interactive. Dropping on a read-only lane snaps the card back with no mutation. (Exception: a card being dragged *out of* Blocked is dropped onto a read-only lane to unblock — that IS a valid unblock action; the "not-droppable" dim applies to cards originating from read-only lanes being dragged toward other read-only lanes.)

- **D-DRAG-04:** **Keyboard parity via @dnd-kit keyboard sensor.** Space grabs a focused card, arrow keys move focus toward the Blocked column, Space drops → same reason prompt as pointer. Only the Blocked column is reachable as a valid target for read-only-origin cards. dnd-kit screen-reader announcements (grabbed / over / dropped) are wired. Full parity with the pointer path (UX-D-01-03).

- **D-DRAG-05:** **Touch: long-press to drag.** dnd-kit TouchSensor with a short press-delay (~200ms) initiates drag; a quick swipe scrolls the board horizontally instead. Disambiguates drag from scroll on phones (UX-D-01-05).

### Columns, filter interplay, empty states (D-COL)

- **D-COL-01:** **Blocked column wins.** A ticket with `blocked=true` lives **only** in the Blocked column, regardless of its `external_status`. Unblocking returns the card to the column matching its `external_status`. Each card has exactly one column home. (This is the board projection of Phase 13 D-P-04's "Blocked renders alongside provider status" — on the board, Blocked takes precedence for placement.)

- **D-COL-02:** **Always render all 4 columns; empty → canonical EmptyState.** All four columns always render (stable layout). Any column with no matching cards shows the canonical `EmptyState` primitive (UX-D-01-04). Column-to-`external_status` mapping uses the existing `STATUS_ALLOW` values: `open` → Open, `in_progress` → In progress, `completed` → Completed, plus the `blocked` flag → Blocked.

- **D-COL-03:** **Chip-bar filters still apply on the board.** The existing tickets chip-bar (status / provider / severity / SLA / search) filters the same `useTickets` result set the board renders. The **status** axis narrows which columns hold cards (selecting status=Open empties the other three, which then show EmptyState) — redundant but harmless, satisfying "the status chip filter still applies." The other axes (provider / severity / SLA / search) filter cards *within* all columns.

- **D-COL-04:** **Column headers: flow order + status accent + live count.** Order left-to-right: **Open → In progress → Completed → Blocked** (workflow order; Blocked last as the exception lane). Each header carries the Phase 13 D-P-04 status-pill color accent and a live count badge of cards currently in that column.

### Card content + click behavior (D-CARD)

- **D-CARD-01:** **Compact card.** Top line: provider gradient mark + ID (mono, `external_ticket_id`) + truncated title. Bottom line: severity glyph (from `max_severity`) + SLA pill + assignee avatar. **No status pill on the card** (the column conveys status) except a red **Blocked** accent when applicable. Reuses `ProviderMark`, `SlaPill`, the severity glyph, and `Avatar` primitives. Kept narrow to fit column width and maximize cards-per-column.

- **D-CARD-02:** **Click opens the DrillPanel.** A click/tap (distinct from a drag, via dnd-kit activation distance) opens the same `DrillPanel` + `TicketDrillContent` as a list row, using the existing `?ticket=...&open=drill` URL contract. Consistent with the list view; analyst peeks vulns + actions without leaving the board. Esc / clickaway close behavior inherited (verify it still works during/after a drag, mirroring the Phase 17 DrillPanel-during-transition concern).

### Claude's Discretion

- **Null / unrecognized `external_status`:** map to the **Open** column (treat unknown as Open) rather than dropping the card or adding a fifth bucket — the requirement fixes exactly four columns. Planner may refine if data shows a meaningful "no status" population.
- **Degrade breakpoint:** use **768px** (Tailwind `md`) to match Phase 15's bottom-nav breakpoint and UX-D-01-05.
- **Column snap width on mobile:** ~85vw per column with CSS scroll-snap — standard; no user input needed.
- **@dnd-kit install:** add `@dnd-kit/core` + `@dnd-kit/sortable` (or `@dnd-kit/core` alone if sortable isn't needed — planner decides) with `--legacy-peer-deps` (React 19 peer, consistent with Phase 15-01 lucide install decision).
- **dnd-kit activation constraints** (pointer distance to distinguish click vs drag; keyboard coordinate getter) — implementation detail for research/planning.
- **Optimistic column reprojection:** on block/unblock, the card should visually move columns immediately (optimistic) and roll back on mutation error — extend the `useMarkBlocked` onMutate/onError to also reflect column placement, or let the list-cache patch drive re-projection. Planner picks the cleanest wiring.

### Folded Todos

None — `gsd-tools todo match-phase 18` returned zero matches.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 18 scope authorities
- `.planning/ROADMAP.md` §Phase 18 (lines ~223–232) — Goal + 4 Success Criteria
- `.planning/milestones/v2.2-ROADMAP.md` §Phase 18 — milestone-level goal + success criteria
- `.planning/REQUIREMENTS.md` §"Phase 18 — Tickets kanban board" (UX-D-01-01 … UX-D-01-06, lines 28–35) — testable acceptance units

### Inherited from Phase 13 (LOAD-BEARING — do not redecide)
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md` §D-P-01 (status model: Open/IP/Completed display-only; Blocked GetVul-interactive) — the constraint that drives D-DRAG-01
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md` §D-P-02 (blocked/blocked_reason schema + whitespace coercion) and §D-P-04 (status pill visual contract + "Blocked alongside provider status")
- `.planning/phases/13-tickets-list-detail/13-CONTEXT.md` §D-L-03 (`?view=list|board` URL toggle — preserved) and §D-D (DrillPanel reuse contract)

### Design system (auto-load via CLAUDE.md routing)
- `.claude/skills/sketch-findings-getvul/sources/006-tickets-sunset/` — sketch 006; **variant C is the deferred kanban sketch** (the visual reference this phase realizes)
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — mandatory loading/empty/error coverage (per-column EmptyState)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — drill-down panel chrome + interaction conventions
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — status pill / SLA pill / provider mark / severity glyph conventions
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — color tokens (status accents, both themes)

### Frontend code to reuse / extend
- `frontend/src/app/(authed)/dashboard/tickets/page.tsx` — the `view === 'board'` branch to replace (currently placeholder copy)
- `frontend/src/lib/queries/use-tickets.ts` — board's data source; `TicketSummary` shape (`external_status`, `blocked`, `blocked_reason`, snake_case wire contract)
- `frontend/src/lib/queries/use-mark-blocked.ts` — optimistic block/unblock mutation (byId + list cache patch, rollback) — the persisting mutation for D-DRAG-01
- `frontend/src/components/tickets/blocked-toggle.tsx` — blocked-reason capture UX to mirror in the drop prompt
- `frontend/src/components/tickets/{provider-mark,sla-pill,status-pill,vuln-count}.tsx` — card primitives
- `frontend/src/components/tickets/ticket-drill-content.tsx` — DrillPanel content for card click
- `frontend/src/components/vulnerabilities/drill-panel.tsx` + `drill-panel-mobile.tsx` — DrillPanel chrome (desktop + vaul mobile)
- `frontend/src/components/states/*` — SkeletonTable / EmptyState (per-column empty)
- `frontend/src/components/tickets/tickets-table.tsx` + `tickets-chip-bar.tsx` — list-row field reference + chip-bar the board shares

### Backend (reused as-is — no changes expected)
- `backend/app/ticketing/router.py:551` — `POST /{ticket_id}/blocked` (the only mutation the board needs)

### Quality gate (both hold from Phase 15/16/17)
- `frontend/e2e/a11y-routes.spec.ts` — axe AA per route in both themes (Phase 16)
- Phase 15 bottom-nav <768px focus behavior must not regress (UX-D-01-05)

### Project-level
- `CLAUDE.md` — UI work routes to `sketch-findings-getvul` skill (auto-loads on frontend implementation)
- `.planning/PROJECT.md` — milestone state

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets (carry forward)
- **`useTickets`** (`use-tickets.ts`) — already returns the full `TicketSummary[]` the board needs; no new query. Board buckets client-side by `external_status` + `blocked`.
- **`useMarkBlocked`** (`use-mark-blocked.ts`) — optimistic block/unblock already patches byId AND list caches with rollback (STATE decision). This IS the drag-persist mutation; extend its optimistic patch to reflect column re-projection.
- **DrillPanel + TicketDrillContent** — card click reuses the exact list-row drill (chrome + `?ticket=...&open=drill`).
- **State primitives** (`components/states/*`) — `EmptyState` per empty column; `SkeletonTable`/skeleton for board loading.
- **Ticket card primitives** — `ProviderMark`, `SlaPill`, severity glyph, `Avatar`, `vuln-count` all exist and are theme-correct.
- **`?view` URL state** — `useUrlState<View>('view', ['list','board'], 'list')` already wired in `page.tsx`; board branch just needs a real body.

### Established patterns (cannot deviate)
- **Sunset CSS variables only** — status accents from `foundation.md`; no raw hex; Inter + JetBrains Mono locked.
- **snake_case wire contract** — `TicketSummary` fields are snake_case end-to-end (CR-04); board accessors match.
- **Mandatory state coverage** — every column renders EmptyState when empty; board renders loading + error states.
- **Reduced-motion + axe-both-themes gate** — any drag/drop animation must be reduced-motion-safe; route stays ≤250 KB.

### Integration points
- **`@dnd-kit`** — NOT yet in `frontend/package.json`; add with `--legacy-peer-deps` (React 19 peer). First DnD dependency in the project.
- **Bundle budget** — `/dashboard/tickets` is currently ~166 KB First Load JS (Phase 17 build). @dnd-kit adds weight; verify the route stays ≤250 KB (UX-D-01-06).
- **DrillPanel-during-drag** — mirror the Phase 17 concern: Esc/clickaway close must still work during/after a drag; no layout shift.

</code_context>

<specifics>
## Specific Ideas

- **"Blocked is the one lane you own."** The board's honesty is the point: three provider-driven lanes you can read but not rewrite, and one workflow signal (Blocked = "waiting on patch vendor") you drag into and out of. Read-only lanes visibly dim during drag so the interactive boundary is discoverable, not surprising.
- **Blocked column wins for placement** — a blocked-but-Open ticket appears in Blocked, not Open. Drag it back out to unblock and it re-homes to its provider column.
- **Card = compact, column = status.** Don't repeat the status pill on the card; the column already says it. Card carries severity + SLA + who owns it.
- **@dnd-kit is locked** (milestone constraint) — no alternative DnD library.

</specifics>

<deferred>
## Deferred Ideas

- **Provider status write-back** (drag Open↔IP↔Completed → Jira/Asana/GitHub transition) — locked deferred in Phase 13 D-P-01 / D-PROV-02; a future phase if analysts want GetVul-driven transitions.
- **GetVul-internal `workflow_status` field** — considered as a way to make all 4 columns draggable; rejected this phase to avoid a dual-status model. Revisit only if the display-only lanes prove too limiting in use.
- **Bulk drag / multi-select on the board** — single-card drag only in Phase 18.
- **WIP limits / column customization / column reordering** — not in scope.
- **Single-column mobile switcher** — considered for <768px; horizontal-scroll chosen instead. Available as a fallback if touch-drag proves unreliable in UAT.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 18` returned zero matches.

</deferred>

---

*Phase: 18-tickets-kanban-board*
*Context gathered: 2026-07-17*
