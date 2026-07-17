# Phase 18: Tickets kanban board - Research

**Researched:** 2026-07-17
**Domain:** React 19 / Next.js 15 App Router drag-and-drop (@dnd-kit) over an existing TanStack Query optimistic mutation
**Confidence:** HIGH (codebase + @dnd-kit stable API); MEDIUM on exact gzipped bundle delta (must be verified by `next build`)

## Summary

Phase 18 replaces the copy-only board placeholder in `tickets/page.tsx` with a real four-column kanban derived entirely from the existing `useTickets` list result. No new query, no backend change. The only persisting action is block/unblock, driven by the existing `useMarkBlocked` mutation against `POST /api/v1/tickets/{id}/blocked`. @dnd-kit is the locked DnD library.

The single most important architectural insight: **the board should be a pure projection of the tickets list cache**, and block/unblock re-projection should happen automatically because `useMarkBlocked.onMutate` optimistically flips the `blocked` flag in the list cache. HOWEVER, the current `useMarkBlocked` patches the wrong cache key (`['tickets']` exact) while the real list data lives under `['tickets','list',{filters,page,view}]`. That latent mismatch means the optimistic list patch is a **no-op today** (the list view only updates via the `onSuccess` fuzzy invalidation refetch). For the board to move a card *optimistically* with rollback, `onMutate`/`onError` must be switched from `setQueryData(['tickets'], …)` to `setQueriesData({queryKey:['tickets','list']}, …)` (fuzzy, plural). This is the cleanest wiring and also fixes the latent list-view bug — see Pitfall 1.

Second key insight: the stable, React-19-compatible package is **`@dnd-kit/core@6.3.1`** (peer `react: >=16.8.0`, which React 19 satisfies). Context7's `/websites/dndkit` and `/clauderic/dnd-kit` entries document the **new experimental v2 API** (`@dnd-kit/react` + `@dnd-kit/dom`, `DragDropProvider`, `PointerActivationConstraints`) — do NOT follow those snippets; they are a different, in-development package. The board needs `@dnd-kit/core` only (`DndContext`, `useDraggable`, `useDroppable`, `DragOverlay`, `PointerSensor`/`KeyboardSensor`/`TouchSensor`, `useSensor`/`useSensors`). No `@dnd-kit/sortable` (no intra-column reordering).

**Primary recommendation:** Build a `next/dynamic(..., { ssr:false })`-lazy-loaded `<TicketsKanbanBoard>` client component that renders 4 `useDroppable` columns from `useTickets` data, uses one `DndContext` with distance/delay-gated pointer + touch sensors and a keyboard sensor, gates valid drops in `onDragEnd` (only block/unblock transitions persist), extends `useMarkBlocked` to `setQueriesData` for real optimistic reprojection, and disables `DragOverlay` drop animation under `prefers-reduced-motion`. Lazy-loading keeps @dnd-kit out of the tickets route First-Load JS.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Drag semantics (D-DRAG):**
- **D-DRAG-01 — Blocked-only drop target.** Open / In progress / Completed are read-only groupings mirroring `external_status` (provider-synced). Blocked is the sole interactive drop target. Drag INTO Blocked → `blocked=true`; drag OUT of Blocked (to any read-only lane) → `blocked=false`. Reuses `POST /api/v1/tickets/{id}/blocked` + `useMarkBlocked`. No provider write-back, no new status field.
- **D-DRAG-02 — Reason prompt on drop into Blocked.** Inline popover for an *optional* blocked-reason (Save / Cancel). Cancel snaps back, no mutation. Save commits optimistic block with reason. Whitespace-only reason → null (Phase 13 D-P-02). Unblock needs no prompt — commits immediately.
- **D-DRAG-03 — Read-only lanes dim + not-droppable during drag.** The three provider-mirror lanes render a "not a drop target" cue during an active drag so only Blocked reads interactive. Dropping on a read-only lane snaps back with no mutation. **Exception:** a card dragged *out of* Blocked onto a read-only lane IS a valid unblock (the dim applies to read-only-origin cards dragged toward other read-only lanes).
- **D-DRAG-04 — Keyboard parity.** Space grabs a focused card, arrows move toward Blocked, Space drops → same reason prompt. Only Blocked reachable as a valid target for read-only-origin cards. dnd-kit screen-reader announcements (grabbed / over / dropped) wired. Full pointer parity (UX-D-01-03).
- **D-DRAG-05 — Touch: long-press to drag.** TouchSensor with short press-delay (~200ms); a quick swipe scrolls the board horizontally instead (UX-D-01-05).

**Columns / filter / empty (D-COL):**
- **D-COL-01 — Blocked column wins.** A `blocked=true` ticket lives ONLY in Blocked regardless of `external_status`. Unblocking re-homes it to its `external_status` column. Exactly one column home per card.
- **D-COL-02 — Always render all 4 columns; empty → canonical EmptyState.** Column→`external_status` map uses `STATUS_ALLOW`: `open`→Open, `in_progress`→In progress, `completed`→Completed, plus `blocked` flag → Blocked.
- **D-COL-03 — Chip-bar filters still apply.** The existing chip-bar (status/provider/severity/SLA/search) filters the same `useTickets` result the board renders. Status axis narrows which columns hold cards; other axes filter within all columns.
- **D-COL-04 — Column headers: flow order + status accent + live count.** Order left→right: Open → In progress → Completed → Blocked. Each header carries the Phase 13 D-P-04 status-pill color accent + a live count badge.

**Card / click (D-CARD):**
- **D-CARD-01 — Compact card.** Top line: provider gradient mark + ID (mono, `external_ticket_id`) + truncated title. Bottom line: severity glyph (from `max_severity`) + SLA pill + assignee avatar. NO status pill on the card except a red Blocked accent when applicable. Reuses `ProviderMark`, `SlaPill`, severity glyph, `Avatar`.
- **D-CARD-02 — Click opens DrillPanel.** A click/tap (distinct from a drag via activation distance) opens the same `DrillPanel` + `TicketDrillContent` via the `?ticket=…&open=drill` URL contract. Esc/clickaway inherited (verify still works during/after a drag).

### Claude's Discretion
- **Null / unrecognized `external_status`:** map to the **Open** column (treat unknown as Open). Planner may refine if data shows a meaningful "no status" population.
- **Degrade breakpoint:** use **768px** (Tailwind `md`) to match Phase 15's bottom-nav breakpoint and UX-D-01-05.
- **Column snap width on mobile:** ~85vw per column with CSS scroll-snap.
- **@dnd-kit install:** add `@dnd-kit/core` + `@dnd-kit/sortable` (or `@dnd-kit/core` alone if sortable isn't needed — planner decides) with `--legacy-peer-deps`. → **Research resolves this: `@dnd-kit/core` alone is sufficient (no sortable); `--legacy-peer-deps` is optional, not required — see Standard Stack.**
- **dnd-kit activation constraints** — implementation detail (resolved below).
- **Optimistic column reprojection** — extend `useMarkBlocked` onMutate/onError, or let list-cache patch drive it. Planner picks cleanest wiring. → **Research resolves: extend `onMutate`/`onError` to `setQueriesData` — see Pitfall 1.**

### Deferred Ideas (OUT OF SCOPE)
- Provider status write-back (drag Open↔IP↔Completed → Jira/Asana/GitHub) — locked deferred Phase 13 D-P-01 / D-PROV-02.
- GetVul-internal `workflow_status` field — rejected this phase (dual-status complexity).
- Bulk drag / multi-select on the board.
- WIP limits / column customization / column reordering.
- Single-column mobile switcher — horizontal-scroll chosen instead (fallback if touch-drag proves unreliable in UAT).
- Any backend schema/endpoint change.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-D-01-01 | Four status columns (Open/IP/Completed/Blocked) from `useTickets`, replacing placeholder | Board = pure projection of `useTickets` items; bucketing rules in Architecture Pattern 1. Replaces the `view === 'board'` branch at `page.tsx:247-250`. |
| UX-D-01-02 | Pointer drag (@dnd-kit) persists status via mutation w/ optimistic update + rollback | `DndContext` + `useDraggable`/`useDroppable`; `onDragEnd` gates to block/unblock only; `useMarkBlocked` (extended to `setQueriesData`) supplies optimistic + rollback. Pattern 2/3, Pitfall 1. |
| UX-D-01-03 | Fully keyboard-operable (@dnd-kit keyboard sensor) | `KeyboardSensor` + `closestCorners` collision; announcements API. Pattern 4. |
| UX-D-01-04 | Empty columns render canonical empty-state; status chip filter still applies | Per-column `EmptyState` primitive; chip-bar `status` filter already narrows `useTickets` server-side. Pattern 1, D-COL-02/03. |
| UX-D-01-05 | <768px degrades cleanly (horizontal scroll) without regressing fixed bottom-nav | CSS scroll-snap flex row; `TouchSensor` delay disambiguates long-press-drag vs swipe-scroll. Pattern 5, Pitfall 4. |
| UX-D-01-06 | List/board URL toggle preserved; route ≤250 KB; axe both themes | `useUrlState<View>('view',…)` already wired; `next/dynamic` lazy-load keeps @dnd-kit off First-Load; axe gate `e2e/a11y-routes.spec.ts`. Validation Architecture. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Column bucketing / Blocked-wins projection | Browser / Client (pure fn) | — | Derived client-side from the already-fetched `useTickets` list; no server call |
| Drag interaction (pointer/keyboard/touch) | Browser / Client | — | @dnd-kit is client-only (uses `window`, pointer/keyboard events, `useId`); must live in a `'use client'` component |
| Block/unblock persistence | API / Backend (existing) | Client optimistic cache | Reuses `POST /{id}/blocked`; client applies optimistic patch + rollback via TanStack |
| Reason capture | Browser / Client | — | Optional string, whitespace→null coercion, sent in mutation body |
| Empty / loading / error states | Browser / Client | — | Canonical `states/*` primitives, per-column |
| Bundle budgeting | CDN / Static (build output) | Client | `next build` route chunk; `next/dynamic` splits the board+dnd-kit out of First-Load JS |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@dnd-kit/core` | `6.3.1` | `DndContext`, `useDraggable`, `useDroppable`, `DragOverlay`, sensors, collision detection, accessibility announcements | The locked, mature, accessible React DnD toolkit; keyboard + screen-reader support built in `[VERIFIED: npm view @dnd-kit/core version → 6.3.1, published 2024-12-05]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@dnd-kit/utilities` | `3.2.2` | `CSS.Translate.toString(transform)` helper | Optional — only if applying transform to the source card. With `DragOverlay` you generally don't (source stays; overlay follows), so this can be skipped and the transform inlined as `translate3d(x,y,0)`. `[VERIFIED: npm view @dnd-kit/utilities version → 3.2.2]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@dnd-kit/core` alone | `+ @dnd-kit/sortable@10.0.0` | Sortable adds intra-column reordering + `sortableKeyboardCoordinates`. **Not needed** — the board has no card reordering; cards bucket by status. Adding it inflates bundle for zero feature. `[VERIFIED: npm view @dnd-kit/sortable version → 10.0.0]` |
| stable `@dnd-kit/core` 6.x | new `@dnd-kit/react` + `@dnd-kit/dom` (v2 experimental, `DragDropProvider`) | The v2 rewrite is what Context7 currently indexes, but it is pre-1.0/experimental and a different API surface. Milestone locked "@dnd-kit"; the stable, production-proven package is `@dnd-kit/core@6.3.1`. Do NOT use v2. `[VERIFIED: Context7 /websites/dndkit returns DragDropProvider/PointerActivationConstraints — the v2 API, not v6 core]` |

**Installation:**
```bash
cd frontend
npm install @dnd-kit/core@6.3.1
# @dnd-kit/utilities@3.2.2 optional (only if not using DragOverlay-only rendering)
```

**On `--legacy-peer-deps`:** `@dnd-kit/core@6.3.1` declares `peerDependencies: { react: ">=16.8.0", react-dom: ">=16.8.0" }` `[VERIFIED: npm view]`. React 19 **satisfies** this range, so `--legacy-peer-deps` is **NOT required** for @dnd-kit (unlike Phase 15-01's `lucide-react`, which pinned `peer react@^18` and genuinely needed the flag). Using `--legacy-peer-deps` anyway is harmless and consistent with the existing install convention; the planner may include it for consistency, but should document that @dnd-kit's peer range already accepts React 19. `[VERIFIED]`

**Bundle note:** unpacked size of `@dnd-kit/core` is ~1.04 MB (ESM+CJS+sourcemaps) `[VERIFIED: npm view @dnd-kit/core dist.unpackedSize → 1066148]`; real gzipped First-Load contribution is roughly ~12–15 KB `[ASSUMED — must be verified by next build]`. Route `/dashboard/tickets` is ~166 KB First Load JS with ~84 KB headroom to the 250 KB budget. **Lazy-loading the board via `next/dynamic({ ssr:false })` keeps @dnd-kit out of the route's First-Load JS entirely** (dynamic chunks are not counted in the "First Load JS" column). This makes UX-D-01-06 comfortably safe. `[CITED: check-bundle-all.mjs — measures the First Load JS column, which excludes dynamic imports]`

## Architecture Patterns

### System Architecture Diagram

```
                         URL (?view=board&status=…&ticket=…&open=drill)
                                        │
                                        ▼
                    tickets/page.tsx  (TicketsPageInner, 'use client')
                    useUrlState<View>('view')  ─── view === 'board' ?
                                        │ yes
                                        ▼
        next/dynamic(() => import('./tickets-kanban-board'), { ssr:false })
                                        │
                                        ▼
   ┌──────────────────  <TicketsKanbanBoard rows={q.data.items} …>  ('use client') ──────────────────┐
   │                                                                                                   │
   │  q.isPending → per-column skeletons     q.error → PartialFailureBanner (mirror list branch)       │
   │                                                                                                   │
   │  bucketTickets(rows):  Blocked-wins → { open[], in_progress[], completed[], blocked[] }           │
   │                                                                                                   │
   │  <DndContext sensors={pointer+touch+keyboard} collisionDetection={closestCorners}                 │
   │              accessibility={{announcements, screenReaderInstructions}}                            │
   │              onDragStart={setActive} onDragEnd={gateAndPersist} onDragCancel={clearActive}>       │
   │                                                                                                   │
   │    [Open col]    [In progress col]    [Completed col]    [Blocked col]                            │
   │    useDroppable  useDroppable          useDroppable       useDroppable                            │
   │      │  each card = useDraggable(id=ticket.id)  → onClick opens DrillPanel (distance-gated)       │
   │      │                                                                                            │
   │    during drag: dim read-only lanes / highlight valid target (derived from active card.blocked)  │
   │                                                                                                   │
   │    <DragOverlay dropAnimation={reducedMotion ? null : default}> compact card clone </DragOverlay> │
   │                                                                                                   │
   │  onDragEnd(active, over):                                                                         │
   │    card = rows[active.id]                                                                         │
   │    if !card.blocked && over==='blocked'  → open ReasonPrompt → Save: markBlocked(true, reason)    │
   │    if  card.blocked && over ∈ readOnlyLanes → markBlocked(false, null)  (immediate)               │
   │    else → no-op (snap back)                                                                       │
   └───────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                        ▼
                     useMarkBlocked.mutate({id, blocked, blocked_reason})
                       onMutate: setQueriesData(['tickets','list'], flip blocked)  ← OPTIMISTIC REPROJECT
                       onError:  restore snapshots (rollback → card snaps back)
                       onSuccess: invalidate ['tickets'] (fuzzy) → server reconcile
                                        │
                                        ▼
                          POST /api/v1/tickets/{id}/blocked   (existing backend, unchanged)
```

### Recommended Project Structure
```
frontend/src/
├── app/(authed)/dashboard/tickets/
│   ├── page.tsx                     # EDIT: replace view==='board' placeholder with dynamic <TicketsKanbanBoard>
│   └── tickets-kanban-board.tsx     # NEW: 'use client' — DndContext + 4 columns + reason prompt
├── components/tickets/
│   ├── kanban-card.tsx              # NEW: compact draggable card (ProviderMark + ID + title + severity glyph + SlaPill + Avatar)
│   ├── kanban-column.tsx            # NEW: droppable column (header w/ status accent + count badge + EmptyState when empty)
│   ├── kanban-reason-prompt.tsx     # NEW: inline optional-reason popover (mirror blocked-toggle.tsx save/cancel + whitespace→null)
│   ├── bucket-tickets.ts            # NEW: pure fn + tests (Blocked-wins, unknown→Open) — unit-testable
│   ├── blocked-toggle.tsx           # REUSE: mirror its save/cancel + whitespace-null pattern in reason-prompt
│   ├── provider-mark.tsx sla-pill.tsx  # REUSE as-is
│   └── (severity glyph)             # REUSE the SEVERITY_GLYPH/SEVERITY_CLASS maps from tickets-table.tsx (extract to shared module)
├── lib/queries/
│   └── use-mark-blocked.ts          # EDIT: onMutate/onError → setQueriesData/getQueriesData (Pitfall 1)
└── hooks/
    └── use-prefers-reduced-motion.ts  # REUSE: gate DragOverlay dropAnimation
```

### Pattern 1: Board as a pure projection of the list cache (bucketing)
**What:** Derive the 4 columns synchronously from `useTickets().data.items`. No new query, no local copy of the data. Blocked wins for placement.
**When to use:** Always — this is the board body.
```typescript
// bucket-tickets.ts  — pure, unit-testable (STATUS_ALLOW mirrors use-tickets.ts / chip-bar)
import type { TicketSummary } from '@/lib/queries/use-tickets';

export type ColumnKey = 'open' | 'in_progress' | 'completed' | 'blocked';
export const COLUMN_ORDER: ColumnKey[] = ['open', 'in_progress', 'completed', 'blocked']; // D-COL-04

export function bucketTickets(rows: TicketSummary[]): Record<ColumnKey, TicketSummary[]> {
  const cols: Record<ColumnKey, TicketSummary[]> = { open: [], in_progress: [], completed: [], blocked: [] };
  for (const t of rows) {
    if (t.blocked) { cols.blocked.push(t); continue; }           // D-COL-01: Blocked wins
    const s = t.external_status?.toLowerCase() ?? null;
    if (s === 'in_progress' || s === 'in progress') cols.in_progress.push(t);
    else if (s === 'completed') cols.completed.push(t);
    else cols.open.push(t);                                       // discretion: unknown/null → Open
  }
  return cols;
}
```
Because block/unblock re-projection flows through the list cache (Pitfall 1), **no board-local state mirrors the data** — the board re-renders from `useTickets` and re-buckets automatically when `useMarkBlocked.onMutate` flips the flag.

### Pattern 2: DndContext + sensor configuration (stable @dnd-kit/core 6.x API)
**What:** One `DndContext` wrapping the columns, with three sensors. Distance gates click-vs-drag; touch delay gates long-press vs scroll; keyboard gives parity.
```typescript
// tickets-kanban-board.tsx  — 'use client'
import {
  DndContext, DragOverlay, closestCorners,
  PointerSensor, KeyboardSensor, TouchSensor,
  useSensor, useSensors,
  type DragStartEvent, type DragEndEvent,
} from '@dnd-kit/core';

const sensors = useSensors(
  useSensor(PointerSensor, {
    // D-CARD-02: <8px movement = click (opens DrillPanel); >=8px = drag.
    activationConstraint: { distance: 8 },
  }),
  useSensor(TouchSensor, {
    // D-DRAG-05: ~200ms long-press starts drag; a quick swipe (moves >5px before delay) scrolls.
    activationConstraint: { delay: 200, tolerance: 5 },
  }),
  useSensor(KeyboardSensor), // D-DRAG-04: default coordinateGetter + closestCorners is adequate (no sortable)
);
```
**Note on keyboard `coordinateGetter`:** the default `KeyboardSensor` coordinate getter (25px arrow nudge) combined with `collisionDetection={closestCorners}` is sufficient for a column board — there is essentially one meaningful valid target (Blocked) for read-only-origin cards. A custom column-snapping `coordinateGetter` is optional polish, not required. `sortableKeyboardCoordinates` (from `@dnd-kit/sortable`) is designed for sortable lists and is **not** appropriate here. `[ASSUMED — based on @dnd-kit/core 6.x behavior; verify keyboard reachability of Blocked in the e2e keyboard-drag test]`

### Pattern 3: Single-drop-target gating in `onDragEnd`
**What:** All 4 columns are `useDroppable`, but only block/unblock transitions persist. Everything else snaps back (a no-op — since we never optimistically move until a valid mutation fires, "snap back" is automatic).
```typescript
const readOnlyLanes = new Set<ColumnKey>(['open', 'in_progress', 'completed']);

function onDragEnd(e: DragEndEvent) {
  setActiveId(null);
  const over = e.over?.id as ColumnKey | undefined;
  const card = rowsById.get(String(e.active.id));
  if (!over || !card) return;                                   // dropped outside → snap back

  if (!card.blocked && over === 'blocked') {
    // D-DRAG-02: open the reason prompt; DO NOT mutate yet.
    setPendingBlock({ ticketId: card.id });                     // Save → markBlocked(true, reason); Cancel → clear (snap back)
    return;
  }
  if (card.blocked && readOnlyLanes.has(over)) {
    // D-DRAG-01/03 exception: unblock, commit immediately (no prompt).
    markBlocked.mutate({ id: card.id, blocked: false, blocked_reason: null });
    return;
  }
  // read-only → read-only, or blocked → blocked: no-op (snap back).
}
```
**Read-only-lane dim cue (D-DRAG-03):** derive per-column `isValidTarget` in render from the active card. During a drag of a read-only-origin card, only Blocked is valid → dim the 3 read-only lanes. During a drag of a Blocked-origin card, the 3 read-only lanes are valid (unblock) → dim Blocked. Read `active` from `DndContext` via `onDragStart` state (store `activeId`), or `useDndContext()`. Do NOT toggle `useDroppable({ disabled })` conditionally per-render for the dim — keep droppables enabled and gate in `onDragEnd`; use the derived flag only for the visual dim + `aria-disabled`.

### Pattern 4: Accessibility announcements + instructions
**What:** Wire `DndContext.accessibility` so screen readers announce grab / over / drop / cancel, and provide keyboard instructions. Keeps the keyboard path (UX-D-01-03) usable and helps axe stay green.
```typescript
const announcements = {
  onDragStart: ({ active }) => `Picked up ticket ${labelFor(active.id)}.`,
  onDragOver:  ({ active, over }) =>
    over ? `Ticket ${labelFor(active.id)} is over the ${colLabel(over.id)} column.`
         : `Ticket ${labelFor(active.id)} is no longer over a column.`,
  onDragEnd:   ({ active, over }) =>
    over ? `Dropped ticket ${labelFor(active.id)} on the ${colLabel(over.id)} column.`
         : `Ticket ${labelFor(active.id)} was dropped.`,
  onDragCancel:({ active }) => `Cancelled dragging ticket ${labelFor(active.id)}.`,
};
const screenReaderInstructions = {
  draggable:
    'To pick up a ticket, press Space or Enter. Use arrow keys to move toward the Blocked column. Press Space or Enter again to drop, or Escape to cancel.',
};
// <DndContext accessibility={{ announcements, screenReaderInstructions }} …>
```
`[ASSUMED — @dnd-kit/core 6.x `accessibility` prop shape from training knowledge; the v2 docs on Context7 differ. Verify against the installed 6.3.1 types after install.]`

### Pattern 5: <768px horizontal-scroll degradation
**What:** Columns in a flex row with CSS scroll-snap; each column ~85vw on mobile, fixed width on desktop. Touch delay (Pattern 2) lets a quick swipe scroll instead of dragging.
```tsx
<div className="flex gap-4 overflow-x-auto snap-x snap-mandatory md:overflow-visible md:snap-none">
  {COLUMN_ORDER.map((key) => (
    <div key={key} className="snap-start shrink-0 basis-[85vw] md:basis-0 md:flex-1">…</div>
  ))}
</div>
```
Do not use `position: fixed`/`sticky` that could collide with the Phase 15 bottom-nav (`nav[aria-label="Mobile navigation"]`, `min-[768px]:hidden`). The board scrolls horizontally within the page body only.

### Anti-Patterns to Avoid
- **Board holding its own copy of ticket state.** Re-project from `useTickets` — a local `useState<TicketSummary[]>` would diverge from the optimistic cache and break rollback.
- **Making all 4 columns interactive drop targets.** Only block/unblock persists (D-DRAG-01). Do not fake status transitions on the read-only lanes.
- **Adding `@dnd-kit/sortable`.** No reordering → dead weight (Alternatives table).
- **Following Context7's `DragDropProvider`/`PointerActivationConstraints` snippets.** Those are the v2 experimental API; the project uses `@dnd-kit/core` 6.x (`DndContext` + `useSensor`).
- **Mutating on drop into Blocked before the reason prompt resolves** (D-DRAG-02 requires Cancel to be a true no-op).
- **Applying a status pill on the card** (D-CARD-01 — the column conveys status; only a Blocked accent).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pointer/keyboard/touch drag | HTML5 `draggable` + custom event math | `@dnd-kit/core` sensors | HTML5 DnD has no keyboard support, poor touch, and no a11y announcements — fails UX-D-01-03/05 and the axe gate |
| Click-vs-drag disambiguation | Manual mousedown/mouseup distance tracking | `PointerSensor` `activationConstraint.distance` | dnd-kit already suppresses the click after a drag; hand-rolling races with the DrillPanel open handler |
| Long-press vs scroll on touch | `setTimeout` + `touchmove` cancellation | `TouchSensor` `activationConstraint.delay + tolerance` | Battle-tested against iOS/Android scroll quirks |
| Screen-reader drag announcements | ARIA live region wiring by hand | `DndContext.accessibility.announcements` | Built-in, debounced, and correct for AT |
| Optimistic move + rollback | Board-local state + manual revert | Existing `useMarkBlocked` (extended to `setQueriesData`) | Rollback, cache reconciliation, and toast already implemented — Pitfall 1 |
| Reason capture / whitespace coercion | New form component | Mirror `blocked-toggle.tsx` (save/cancel, `trim() || null`, maxLength 500) | Phase 13 D-P-02 rule + backend Pydantic bound already exist |

**Key insight:** Almost everything the board needs already exists (data, mutation, primitives, empty/loading/error, URL toggle). The genuinely new code is thin: a `DndContext` wrapper, `useDraggable` cards, `useDroppable` columns, a reason prompt, and a bucketing pure function.

## Common Pitfalls

### Pitfall 1: `useMarkBlocked` optimistic list patch targets the WRONG cache key (latent bug + blocks board reprojection)
**What goes wrong:** `use-mark-blocked.ts` calls `qc.setQueryData(queryKeys.tickets.all, …)` where `tickets.all === ['tickets']` (exact). But list data lives under `queryKeys.tickets.list({filters,page,view}) === ['tickets','list',{…}]`. `setQueryData` uses **exact** key matching, so the list rows are never patched. Today the list view only updates via the `onSuccess` `invalidateQueries({queryKey:['tickets']})` (which IS fuzzy/prefix and does trigger a refetch). For the **board**, that means a dropped card would NOT move until the server round-trip completes — not optimistic, and rollback-on-error would have nothing to revert visually.
**Why it happens:** `setQueryData` (singular) = exact key; `invalidateQueries`/`setQueriesData` (plural) = fuzzy/prefix. The original hook conflated the two.
**How to avoid:** In `onMutate`, replace the single `setQueryData(['tickets'], …)` with `qc.setQueriesData({ queryKey: ['tickets','list'] }, updater)` (patches every cached tickets list — list AND board views, all filter/page permutations). Snapshot with `qc.getQueriesData({ queryKey: ['tickets','list'] })` (returns `Array<[QueryKey, data]>`); in `onError`, iterate and restore each via `setQueryData(key, data)`. Keep the byId patch as-is. Keep `onSuccess` invalidation as-is. `[VERIFIED: TanStack Query v5 (^5.100.10) — setQueriesData/getQueriesData exist and use fuzzy matching]`
**Warning signs:** dropped card doesn't move until a spinner/refetch; error rollback appears to "do nothing"; the list-view BlockedToggle appears laggy (updates only on refetch).
**Regression guard:** this change also improves the existing list/detail path (optimistic now actually applies). Cover with a unit test asserting the list cache flips in `onMutate` and restores in `onError`.

### Pitfall 2: `DragOverlay` drop animation ignores the globals.css reduced-motion blanket
**What goes wrong:** `globals.css` forces `animation-duration: 0.01ms !important` under `prefers-reduced-motion` (lines 117, 194) — but that only catches **CSS** animations. `@dnd-kit`'s `DragOverlay` drop animation uses the **Web Animations API** (`element.animate()`), which the CSS blanket does NOT touch. A drop tween will still play under reduce, violating the reduced-motion requirement.
**How to avoid:** Read `usePrefersReducedMotion()` (existing hook at `src/hooks/use-prefers-reduced-motion.ts`) and pass `dropAnimation={reduced ? null : undefined}` to `<DragOverlay>`. Also ensure any transform transition on the card is behind Tailwind `motion-safe:` (matches Phase 15-03 belt-and-suspenders precedent).
**Warning signs:** `e2e/reduced-motion.spec.ts` extended assertion fails; visible card fly-back under reduce.

### Pitfall 3: DrillPanel clickaway/Esc racing with an active drag
**What goes wrong:** `DrillPanel` (`drill-panel.tsx`) attaches a document `mousedown` clickaway listener and an `Escape` listener **while open**. If a drag begins while the panel is open, the card `mousedown` is outside the panel → panel closes mid-drag; and Esc during a keyboard drag both cancels the drag (KeyboardSensor) and closes the panel.
**Why it happens:** two independent global listeners on the same events.
**How to avoid:** This is acceptable behavior in most cases (closing the peek panel when you start rearranging is fine), but verify explicitly per D-CARD-02. Since `PointerSensor` distance-gates, a click (<8px) opens the panel and does NOT start a drag; a drag (>=8px) starts a drag and dnd-kit suppresses the trailing click. The realistic race is only "drag a card while a panel is already open." Verify: (a) no layout shift, (b) no stuck drag, (c) Esc cancels drag cleanly. Mirror the Phase 17 DrillPanel-during-transition verification note. `[CITED: drill-panel.tsx:60-88]`

### Pitfall 4: TouchSensor delay vs. the mobile bottom-nav focus behavior
**What goes wrong:** UX-D-01-05 requires the fixed bottom-nav focus behavior (Phase 15) not to regress. A too-aggressive touch drag or a `touch-action` override on the board could swallow vertical scroll or trap focus near the bottom-nav.
**How to avoid:** Scope `touch-action`/drag to the board columns only; horizontal scroll-snap on the column row; do not set `overflow:hidden` on ancestors of the bottom-nav. The 200ms `TouchSensor` delay lets a swipe scroll. Re-run the Phase 15 bottom-nav e2e assertions (already in `a11y-routes.spec.ts` at 360px). `[CITED: routes.ts MOBILE_NAV; a11y-routes.spec.ts:137-163]`

### Pitfall 5: dnd-kit `useId` / hydration in App Router
**What goes wrong:** dnd-kit uses React `useId` and injects ARIA/live-region DOM; rendering it during SSR can produce hydration warnings.
**How to avoid:** The board is a `'use client'` component AND lazy-loaded via `next/dynamic(..., { ssr:false })`, so it never renders on the server. This eliminates the hydration surface and keeps @dnd-kit out of First-Load JS. `[CITED: next/dynamic precedent — trend-section.tsx, showcase-client-loader.tsx]`

### Pitfall 6: Reason-prompt focus timing after a keyboard drop
**What goes wrong:** After a keyboard drop, dnd-kit restores focus to the dragged element. Immediately focusing the reason-prompt input can race with that restoration, dropping focus.
**How to avoid:** Open the prompt in `onDragEnd`, then focus the input on the next frame (`requestAnimationFrame` / `setTimeout(…,0)`) — matching the `blocked-toggle.tsx` pattern (`setTimeout(() => inputRef.current?.focus(), 0)`). On Cancel/Save, return focus to the origin card. `[CITED: blocked-toggle.tsx:51-55]`

## Code Examples

### Compact draggable kanban card (D-CARD-01 + D-CARD-02 click-vs-drag)
```tsx
// kanban-card.tsx — 'use client'
import { useDraggable } from '@dnd-kit/core';
import { ProviderMark } from './provider-mark';
import { SlaPill } from './sla-pill';
import { Avatar } from '@/components/ui/Avatar';
import type { TicketSummary } from '@/lib/queries/use-tickets';
// reuse SEVERITY_GLYPH / SEVERITY_CLASS extracted from tickets-table.tsx

export function KanbanCard({ ticket, onOpen }: { ticket: TicketSummary; onOpen: (t: TicketSummary) => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: ticket.id });
  const sev = ticket.max_severity?.toLowerCase() ?? '';
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={() => onOpen(ticket)}          // distance-gated: fires only on click, not drag (D-CARD-02)
      className={cn(
        'cursor-grab rounded-lg border border-border-subtle bg-surface p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
        ticket.blocked && 'border-l-2 border-l-severity-critical',   // D-CARD-01 red Blocked accent
        isDragging && 'opacity-40',
      )}
    >
      <div className="flex items-center gap-2">
        {isTicketProvider(ticket.provider) && <ProviderMark provider={ticket.provider} />}
        <span className="font-mono text-xs text-text shrink-0">{ticket.external_ticket_id}</span>
        <span className="truncate text-sm text-text" title={ticket.title}>{ticket.title}</span>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className={cn('text-sm', SEVERITY_CLASS[sev] ?? 'text-text-faint')} aria-label={ticket.max_severity ?? 'unknown'}>
          {SEVERITY_GLYPH[sev] ?? '○'}
        </span>
        <SlaPill dueAt={ticket.sla_due_at} />
        {ticket.assignee && <Avatar name={ticket.assignee} email={ticket.assignee} size={20} />}
      </div>
    </div>
  );
}
```
`[CITED: patterns extracted from tickets-table.tsx severity map + provider-mark.tsx + sla-pill.tsx]`

### Wiring in page.tsx (replace the placeholder branch)
```tsx
// page.tsx — replace lines 247-250 (the view==='board' placeholder)
const TicketsKanbanBoard = dynamic(
  () => import('./tickets-kanban-board').then((m) => m.TicketsKanbanBoard),
  { ssr: false, loading: () => <BoardSkeleton /> },
);
// …
{view === 'board' ? (
  <TicketsKanbanBoard
    rows={items}
    isLoading={isLoading}
    error={q.error as Error | null}
    onOpen={onRowClick}          // reuse existing ?ticket=&open=drill handler (D-CARD-02)
  />
) : ( /* existing list branch */ )}
```
The `DrillPanel`/`DrillPanelMobile` at the bottom of `page.tsx` already read `?ticket`/`?open=drill` and render regardless of view — no change needed there. `[CITED: page.tsx:315-407 DrillPanel already view-agnostic]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-beautiful-dnd` | `@dnd-kit` | rbd deprecated/unmaintained ~2022 | Explicitly rejected in this milestone's REQUIREMENTS "Out of scope" |
| HTML5 native DnD | @dnd-kit sensors | — | Native DnD lacks keyboard/a11y; fails the axe + keyboard requirements |
| `@dnd-kit/core` 6.x (`DndContext`) | `@dnd-kit/react`/`@dnd-kit/dom` v2 (`DragDropProvider`) — experimental | v2 in development (indexed by Context7) | **Do NOT adopt v2** — 6.3.1 is the stable, React-19-compatible, production choice |

**Deprecated/outdated:**
- Context7 `/websites/dndkit` + `/clauderic/dnd-kit` snippets reflect the v2 API (`DragDropProvider`, `PointerActivationConstraints`, `KeyboardSensor.configure`) — not applicable to `@dnd-kit/core@6.3.1`. Rely on the 6.x API (`useSensor(PointerSensor, { activationConstraint })`, `DndContext`, `useDraggable`, `useDroppable`, `DragOverlay`) and verify against the installed TypeScript types.

## Runtime State Inventory

Not a rename/refactor/migration phase — greenfield board feature over existing data. Section omitted per template guidance. (No stored data, service config, OS state, secrets, or build artifacts carry an old identifier that this phase changes.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | @dnd-kit/core 6.x `accessibility={{ announcements, screenReaderInstructions }}` prop shape | Pattern 4 | Low — announcements are additive; verify against installed 6.3.1 types; if the shape differs, adjust (feature still works, just announcement wiring changes) |
| A2 | Default `KeyboardSensor` coordinateGetter + `closestCorners` makes Blocked reachable by keyboard for read-only-origin cards | Pattern 2 | Medium — if arrow-key navigation can't reach Blocked reliably, add a custom column-snapping `coordinateGetter`. Caught by the e2e keyboard-drag test (UX-D-01-03) |
| A3 | ~12–15 KB gzipped First-Load contribution of @dnd-kit/core; route stays ≤250 KB | Standard Stack | Low — mitigated by `next/dynamic` lazy-load (excluded from First-Load JS entirely). MUST be confirmed by `next build` + `check-bundle-all.mjs` |
| A4 | Closing the DrillPanel when a drag starts while it's open is acceptable UX | Pitfall 3 | Low — behavioral; confirm in human/e2e verification; if not, gate the clickaway during active drag |

## Open Questions

1. **Keyboard target reachability for Blocked**
   - What we know: `KeyboardSensor` + `closestCorners` moves the drag by arrow keys; collision picks the nearest droppable.
   - What's unclear: whether the default 25px nudge reliably lands on the Blocked column across viewport widths without a custom `coordinateGetter`.
   - Recommendation: implement with the default first; the UX-D-01-03 e2e keyboard-drag test is the gate. If it fails, add a `coordinateGetter` that snaps to the next column's droppable rect.

2. **Does dragging a Blocked card need a target-lane highlight, or just "any read-only lane unblocks"?**
   - What we know: D-DRAG-03 says a Blocked-origin card dropped on any read-only lane unblocks.
   - What's unclear: whether the unblocked card should visibly preview its destination column (its `external_status` home) during hover.
   - Recommendation: keep it simple — highlight all 3 read-only lanes as valid during a Blocked-card drag; on unblock, `bucketTickets` re-homes it to its `external_status` column automatically. Refine only if UAT flags confusion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `@dnd-kit/core` | drag interactions | ✗ (to install) | target 6.3.1 | none — locked library |
| Node/npm | install + build | ✓ | project toolchain | — |
| `next build` + `check-bundle-all.mjs` | UX-D-01-06 budget gate | ✓ | present | — |
| Playwright + `@axe-core/playwright` | axe both-themes + keyboard e2e | ✓ | `@playwright/test 1.61.1`, axe 4.12.1 | — |
| Existing `POST /{id}/blocked` backend | persistence | ✓ (running locally per MEMORY) | — | none needed (no backend change) |

**Missing dependencies with no fallback:** `@dnd-kit/core` — must be installed (this is the phase's premise; locked, so no fallback sought).
**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.6 (unit) + Playwright 1.61.1 (e2e) + `@axe-core/playwright` 4.12.1 (a11y) |
| Config file | `frontend/vitest` (package.json `test`), `frontend/e2e/playwright.config.ts` |
| Quick run command | `cd frontend && npx vitest run src/components/tickets/bucket-tickets.test.ts src/lib/queries/use-mark-blocked.test.ts` |
| Full suite command | `cd frontend && npm run test && npm run test:e2e && npm run perf:budget` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-D-01-01 | 4 columns render from `useTickets`; toggle preserved | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "renders four columns"` | ❌ Wave 0 |
| UX-D-01-01 | `bucketTickets` Blocked-wins + unknown→Open + order | unit | `npx vitest run src/components/tickets/bucket-tickets.test.ts` | ❌ Wave 0 |
| UX-D-01-02 | pointer drag into Blocked persists w/ optimistic + rollback | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "drag into Blocked persists"` | ❌ Wave 0 |
| UX-D-01-02 | `useMarkBlocked` onMutate flips list cache; onError restores (Pitfall 1) | unit | `npx vitest run src/lib/queries/use-mark-blocked.test.ts` | ❌ Wave 0 (extend if exists) |
| UX-D-01-02 | reason whitespace→null coercion | unit | `npx vitest run src/components/tickets/kanban-reason-prompt.test.tsx` | ❌ Wave 0 |
| UX-D-01-03 | keyboard grab/move/drop changes status (Space+arrows+Space) | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "keyboard drag"` | ❌ Wave 0 |
| UX-D-01-04 | empty column shows canonical EmptyState; status chip narrows columns | e2e | `npx playwright test e2e/tickets-kanban.spec.ts -g "empty column"` | ❌ Wave 0 |
| UX-D-01-05 | <768px horizontal scroll; bottom-nav still visible/focusable at 360px | e2e | `npx playwright test e2e/a11y-routes.spec.ts -g "Bottom-nav"` (existing) + new board-mobile case | ⚠️ partial (existing bottom-nav test) |
| UX-D-01-06 | route ≤250 KB First Load JS | build gate | `cd frontend && npm run perf:budget` (asserts `/dashboard/tickets` ≤250 KB) | ✅ `scripts/check-bundle-all.mjs` |
| UX-D-01-06 | axe WCAG 2.1 AA green on `/dashboard/tickets` in BOTH themes (incl. active drag state) | e2e | `npx playwright test e2e/a11y-routes.spec.ts` | ✅ (route already swept; extend to assert board view + mid-drag overlay) |
| UX-D-01-06 | reduced-motion: DragOverlay drop animation suppressed (Pitfall 2) | e2e | `npx playwright test e2e/reduced-motion.spec.ts` | ✅ (extend with board drop assertion) |

### Sampling Rate
- **Per task commit:** `npx vitest run src/components/tickets/bucket-tickets.test.ts src/lib/queries/use-mark-blocked.test.ts` (quick, <5s)
- **Per wave merge:** `cd frontend && npm run test && npx playwright test e2e/tickets-kanban.spec.ts`
- **Phase gate:** `npm run test && npm run test:e2e && npm run perf:budget` all green before `/gsd-verify-work` (axe both themes + bundle + keyboard drag).

### Wave 0 Gaps
- [ ] `src/components/tickets/bucket-tickets.ts` + `bucket-tickets.test.ts` — pure bucketing (UX-D-01-01): Blocked-wins, `in_progress`/`in progress` alias, unknown/null→Open, `COLUMN_ORDER`.
- [ ] `src/lib/queries/use-mark-blocked.test.ts` — assert `onMutate` `setQueriesData` flips the `['tickets','list',*]` caches and `onError` restores (Pitfall 1 regression guard). (Create if absent; extend if present.)
- [ ] `src/components/tickets/kanban-reason-prompt.test.tsx` — Save with reason, Cancel = no mutation, whitespace→null (UX-D-01-02, mirror blocked-toggle behavior).
- [ ] `e2e/tickets-kanban.spec.ts` — NEW: four-columns render, pointer drag→Blocked persists (optimistic + rollback on injected error), keyboard drag, empty-column EmptyState, status-chip narrowing, board+overlay axe.
- [ ] EXTEND `e2e/a11y-routes.spec.ts` — sweep `/dashboard/tickets?view=board` (+ mid-drag) in both themes.
- [ ] EXTEND `e2e/reduced-motion.spec.ts` — assert no drop tween under `reducedMotion: 'reduce'`.
- [ ] Framework install: `npm install @dnd-kit/core@6.3.1` (no test framework install needed — Vitest/Playwright present).

## Security Domain

`security_enforcement` default (enabled). This is a client-only feature reusing an existing, already-hardened endpoint. No new backend surface.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface; existing session/JWT unchanged |
| V3 Session Management | no | Unchanged |
| V4 Access Control | no (reused) | `POST /{id}/blocked` already tenant-scoped server-side; board sends only `{id, blocked, blocked_reason}` |
| V5 Input Validation | yes | Blocked-reason `maxLength=500` (T-13-20) + whitespace→null (T-13-21) mirrored from `blocked-toggle.tsx`; backend Pydantic bound already enforces. Column/status values clamped via existing `STATUS_ALLOW`. All ticket fields rendered as React text nodes (T-12-07) — no `dangerouslySetInnerHTML` |
| V6 Cryptography | no | None |

### Known Threat Patterns for React/Next.js client board
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via ticket title/id/reason in card or overlay | Tampering | React text-node escaping (existing pattern); provider via literal `isTicketProvider` narrowing (no `as` launder) |
| Mass assignment on blocked mutation | Tampering | `useMarkBlocked` sends ONLY `{blocked, blocked_reason}` (T-13-23); backend rejects extras — unchanged |
| Reflected URL param injection (`?view`, `?ticket`, `?status`) | Tampering | `useUrlState`/`useUrlStateList` allow-list clamp already applied (`VIEW_ALLOW`, `STATUS_ALLOW`) |

## Sources

### Primary (HIGH confidence)
- Codebase (read this session): `tickets/page.tsx`, `use-tickets.ts`, `use-mark-blocked.ts`, `keys.ts`, `blocked-toggle.tsx`, `provider-mark.tsx`, `sla-pill.tsx`, `status-pill.tsx`, `vuln-count.tsx`, `tickets-table.tsx`, `tickets-chip-bar.tsx`, `drill-panel.tsx`, `drill-panel-mobile.tsx`, `empty-state.tsx`, `states/index.ts`, `routes.ts`, `a11y-routes.spec.ts`, `check-bundle-all.mjs`, `globals.css` (reduced-motion), `package.json`.
- `npm view @dnd-kit/core` → version 6.3.1, peer `react >=16.8.0`, published 2024-12-05; `@dnd-kit/sortable` 10.0.0; `@dnd-kit/utilities` 3.2.2; `@dnd-kit/accessibility` 3.1.1 (all VERIFIED via npm registry).
- Sketch skill references: `interaction-patterns.md` (§Drag-to-update status — 006 variant C), `state-patterns.md` (empty/loading/error mandatory).
- CONTEXT.md D-DRAG/D-COL/D-CARD decisions; REQUIREMENTS.md UX-D-01-01..06; ROADMAP Phase 18.

### Secondary (MEDIUM confidence)
- @dnd-kit/core 6.x API (DndContext, sensors, useDraggable/useDroppable, DragOverlay, accessibility announcements) — training knowledge, corroborated by the npm-verified version/peer range. To be confirmed against installed TypeScript types.
- TanStack Query v5 `setQueriesData`/`getQueriesData` fuzzy semantics — v5 (^5.100.10 in package.json).

### Tertiary (LOW confidence)
- Context7 `/websites/dndkit` + `/clauderic/dnd-kit` — returned the **v2 experimental API** (`DragDropProvider`, `PointerActivationConstraints`), which is NOT the stable package this phase uses. Recorded as a pitfall, not as guidance.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions/peer ranges npm-verified; @dnd-kit/core-only decision justified (no reordering).
- Architecture (board-as-projection, single-drop gating, sensor config): HIGH — grounded in read source + established 6.x API.
- `useMarkBlocked` cache-key fix (Pitfall 1): HIGH — verified by reading the hook + keys.ts; exact vs fuzzy matching is standard TanStack v5 behavior.
- Exact bundle delta / keyboard reachability / announcements prop shape: MEDIUM — flagged in Assumptions Log; gated by build + e2e.

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (stable stack; @dnd-kit/core 6.x has been stable since 2024. Re-check only if @dnd-kit v2 reaches stable before implementation.)
