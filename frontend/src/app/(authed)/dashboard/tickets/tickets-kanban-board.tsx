'use client';
/**
 * TicketsKanbanBoard — the DndContext container for the tickets kanban board
 * (UX-D-01-01..05). Assembles the 18-02 leaf components (KanbanCard,
 * KanbanColumn, KanbanReasonPrompt) into one `DndContext` with pointer +
 * touch + keyboard sensors, the block/unblock `onDragEnd` gating, a
 * reduced-motion-safe `DragOverlay`, screen-reader announcements, and the
 * mobile horizontal scroll-snap layout (D-COL-04, D-DRAG-01..05).
 *
 * Board-as-pure-projection (RESEARCH Pattern 1): this component holds NO
 * local copy of ticket rows. `bucketTickets(rows)` re-derives the 4 columns
 * on every render; `useMarkBlocked`'s optimistic `onMutate` flips `blocked`
 * in the shared `useTickets` list cache, so the board re-buckets and moves
 * the card automatically — rollback on error is likewise automatic (no
 * board-local state to revert).
 *
 * Gating (D-DRAG-01/02/03, RESEARCH Pattern 3): only two transitions ever
 * call `markBlocked.mutate` — read-only→Blocked (after the reason prompt's
 * Save) and Blocked→read-only (immediate unblock). Every other drop is a
 * no-op (snap back, since no optimistic move happens until a mutation
 * fires). T-18-09.
 *
 * Reduced motion (Pitfall 2 / T-18-10): the WAAPI `DragOverlay` drop tween is
 * NOT caught by the globals.css CSS-animation blanket, so `dropAnimation` is
 * explicitly nulled under `prefers-reduced-motion`.
 *
 * This module is dynamically imported via `next/dynamic({ ssr:false })` from
 * page.tsx (Task 2) so @dnd-kit never enters the route's First-Load JS
 * (Pitfall 5, UX-D-01-06).
 *
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { useMemo, useRef, useState, type MutableRefObject } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  KeyboardSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type KeyboardCoordinateGetter,
} from '@dnd-kit/core';
import { KanbanCard } from '@/components/tickets/kanban-card';
import { KanbanColumn } from '@/components/tickets/kanban-column';
import { KanbanReasonPrompt } from '@/components/tickets/kanban-reason-prompt';
import { bucketTickets, COLUMN_ORDER, COLUMN_LABELS, type ColumnKey } from '@/components/tickets/bucket-tickets';
import { useMarkBlocked } from '@/lib/queries/use-mark-blocked';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';
import { PartialFailureBanner } from '@/components/states';
import type { TicketSummary } from '@/lib/queries/use-tickets';

// D-DRAG-01/03: only Blocked is an interactive drop target; the other 3
// lanes are read-only groupings mirroring `external_status`.
const READ_ONLY_LANES = new Set<ColumnKey>(['open', 'in_progress', 'completed']);

// 18-04 gate fix (RESEARCH Open Question 1 fallback, flagged as an open item
// in 18-03-SUMMARY.md): the default KeyboardSensor coordinateGetter moves the
// drag position by a flat 25px per arrow-key press, which cannot cross a
// ~300-400px-wide column in the 6 ArrowRight presses the e2e keyboard-drag
// spec allows (reproduced live: 6 presses moved the card 0px). The board
// needs a COLUMN-SNAPPING getter, not a pixel-incremental one.
//
// `columnIndexRef` (not `context.over`) tracks the current column: `over` is
// only recomputed once collision detection re-runs against the PREVIOUS
// keypress's coordinates, so on rapid back-to-back presses (no inter-press
// render/collision-detection settle time — exactly how a real user or an
// e2e spec fires ArrowRight in a tight loop) `over` lags by a press and the
// getter would otherwise re-derive the same "next" index every time,
// stalling one column short of Blocked (reproduced live). A ref-based
// counter advances deterministically on every keypress regardless of
// collision-detection timing; `handleDragStart` resets it to 0 (Open) so
// each new drag starts from the picked-up card's actual column.
function makeKanbanColumnCoordinateGetter(
  columnIndexRef: MutableRefObject<number>,
): KeyboardCoordinateGetter {
  return (event, { currentCoordinates, context }) => {
    const { code } = event;
    if (code !== 'ArrowRight' && code !== 'ArrowLeft') {
      return undefined;
    }
    event.preventDefault();

    const direction = code === 'ArrowRight' ? 1 : -1;
    columnIndexRef.current = Math.min(
      Math.max(columnIndexRef.current + direction, 0),
      COLUMN_ORDER.length - 1,
    );
    const nextColumnId = COLUMN_ORDER[columnIndexRef.current];

    const rect = context.droppableContainers.get(nextColumnId)?.rect.current;
    if (!rect) return undefined;

    // 22-01 gate fix (WR-02 test discovery): target the CENTER of the target
    // column's own rect, not the y carried over from the origin column.
    // KanbanColumn's droppable ref sits on its inner card-list div (min-h-[4rem]),
    // which collapses to a short EmptyState height for a column with 0 cards.
    // Keeping `currentCoordinates.y` (the y of the card being dragged FROM)
    // could fall outside a short empty intermediate column's rect, causing
    // closestCorners collision detection to skip past it entirely (reproduced
    // live: one ArrowRight from Open jumped straight to Completed when
    // In progress was empty). Re-centering vertically on every keypress keeps
    // the virtual position inside the intended column regardless of its
    // height, so each ArrowRight/ArrowLeft reliably lands exactly one column over.
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
  };
}

export type TicketsKanbanBoardProps = {
  rows: TicketSummary[];
  isLoading: boolean;
  error: Error | null;
  onOpen: (ticket: TicketSummary) => void;
  /** WR-04: retry a transient board fetch failure (wired to q.refetch()). */
  onRetry?: () => void;
};

function BoardSkeletonColumn({ columnKey }: { columnKey: ColumnKey }) {
  return (
    <div
      data-column={columnKey}
      className="snap-start shrink-0 basis-[85vw] md:basis-0 md:flex-1 flex flex-col rounded-lg"
    >
      <div className="flex items-center gap-2 px-1 pb-2">
        <span className="inline-flex size-2.5 shrink-0 rounded-full border border-border-subtle bg-surface-2" />
        <span className="text-sm font-semibold text-text">{COLUMN_LABELS[columnKey]}</span>
      </div>
      <div className="flex flex-col gap-2 min-h-[4rem]">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-[4.5rem] rounded-lg motion-safe:animate-shimmer bg-gradient-to-r from-surface-2 via-border to-surface-2"
          />
        ))}
      </div>
    </div>
  );
}

export function TicketsKanbanBoard({ rows, isLoading, error, onOpen, onRetry }: TicketsKanbanBoardProps) {
  const reduced = usePrefersReducedMotion();
  const markBlocked = useMarkBlocked();

  // RESEARCH anti-pattern: NO board-local copy of ticket rows — pure
  // projection from the shared useTickets cache, re-buckets on every render.
  const cols = useMemo(() => bucketTickets(rows), [rows]);
  const rowsById = useMemo(() => new Map(rows.map((t) => [t.id, t])), [rows]);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [pendingBlock, setPendingBlock] = useState<{ ticketId: string } | null>(null);

  // 18-04 gate fix: backs the column-snapping keyboard coordinateGetter (see
  // makeKanbanColumnCoordinateGetter comment above) — reset in handleDragStart
  // to the card's actual starting column so Left/Right stay correctly
  // anchored regardless of which lane the drag began in.
  const columnIndexRef = useRef(0);
  const keyboardCoordinateGetter = useMemo(
    () => makeKanbanColumnCoordinateGetter(columnIndexRef),
    [],
  );

  const sensors = useSensors(
    // D-CARD-02: <8px movement = click (opens DrillPanel); >=8px = drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    // D-DRAG-05: ~200ms long-press starts drag; a quick swipe scrolls instead.
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 5 } }),
    // D-DRAG-04: column-snapping coordinateGetter + closestCorners collision
    // detection (RESEARCH Open Question 1 fallback — see comment above).
    useSensor(KeyboardSensor, { coordinateGetter: keyboardCoordinateGetter }),
  );

  const activeCard = activeId ? (rowsById.get(activeId) ?? null) : null;

  function isValidTargetFor(columnKey: ColumnKey): boolean {
    if (!activeCard) return false;
    if (!activeCard.blocked) return columnKey === 'blocked';
    return READ_ONLY_LANES.has(columnKey);
  }

  function handleDragStart(e: DragStartEvent) {
    const id = String(e.active.id);
    setActiveId(id);
    const startColumn = COLUMN_ORDER.find((key) => cols[key].some((t) => t.id === id));
    columnIndexRef.current = startColumn ? COLUMN_ORDER.indexOf(startColumn) : 0;
  }

  function handleDragCancel() {
    setActiveId(null);
  }

  function handleDragEnd(e: DragEndEvent) {
    setActiveId(null);
    const over = e.over?.id as ColumnKey | undefined;
    const card = rowsById.get(String(e.active.id));
    if (!over || !card) return; // dropped outside any column → snap back

    if (!card.blocked && over === 'blocked') {
      // D-DRAG-02: open the reason prompt; DO NOT mutate yet — Cancel must
      // be a true no-op (no optimistic move has happened).
      setPendingBlock({ ticketId: card.id });
      return;
    }
    if (card.blocked && READ_ONLY_LANES.has(over)) {
      // D-DRAG-01/03 exception: unblock, commit immediately (no prompt).
      markBlocked.mutate({ id: card.id, blocked: false, blocked_reason: null });
      return;
    }
    // read-only → read-only, or blocked → blocked: no-op (snap back).
  }

  function labelFor(id: string | number): string {
    return rowsById.get(String(id))?.external_ticket_id ?? String(id);
  }

  function colLabel(id: string | number): string {
    return COLUMN_LABELS[id as ColumnKey] ?? String(id);
  }

  const announcements = {
    onDragStart: ({ active }: { active: { id: string | number } }) =>
      `Picked up ticket ${labelFor(active.id)}.`,
    onDragOver: ({
      active,
      over,
    }: {
      active: { id: string | number };
      over: { id: string | number } | null;
    }) =>
      over
        ? `Ticket ${labelFor(active.id)} is over the ${colLabel(over.id)} column.`
        : `Ticket ${labelFor(active.id)} is no longer over a column.`,
    onDragEnd: ({
      active,
      over,
    }: {
      active: { id: string | number };
      over: { id: string | number } | null;
    }) => {
      // WR-02: mirror handleDragEnd's gating so we only announce a committed
      // move for the two valid transitions (read-only→Blocked, Blocked→read-only).
      // Every other drop is a gated no-op that snaps back — announcing a
      // "Dropped on {column}" success for those contradicts the visual snap-back.
      const card = rowsById.get(String(active.id));
      const overKey = over?.id as ColumnKey | undefined;
      const committed = !!(
        over &&
        card &&
        overKey &&
        ((!card.blocked && overKey === 'blocked') ||
          (card.blocked && READ_ONLY_LANES.has(overKey)))
      );
      return committed
        ? `Moved ticket ${labelFor(active.id)} to the ${colLabel(over!.id)} column.`
        : `Ticket ${labelFor(active.id)} returned to its column.`;
    },
    onDragCancel: ({ active }: { active: { id: string | number } }) =>
      `Cancelled dragging ticket ${labelFor(active.id)}.`,
  };

  const screenReaderInstructions = {
    draggable:
      'To pick up a ticket, press Space or Enter. Use arrow keys to move toward the Blocked column. Press Space or Enter again to drop, or Escape to cancel.',
  };

  if (error) {
    return (
      <PartialFailureBanner
        errors={[{ code: 'http_error', requestId: String(error.message) || 'unknown' }]}
        onRetry={onRetry}
      />
    );
  }

  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="flex gap-4 overflow-x-auto snap-x snap-mandatory md:overflow-visible md:snap-none"
      >
        {COLUMN_ORDER.map((key) => (
          <BoardSkeletonColumn key={key} columnKey={key} />
        ))}
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      accessibility={{ announcements, screenReaderInstructions }}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="flex gap-4 overflow-x-auto snap-x snap-mandatory md:overflow-visible md:snap-none">
        {COLUMN_ORDER.map((key) => (
          <KanbanColumn
            key={key}
            columnKey={key}
            label={COLUMN_LABELS[key]}
            count={cols[key].length}
            isEmpty={cols[key].length === 0}
            isValidTarget={isValidTargetFor(key)}
            isDragActive={activeId !== null}
          >
            {cols[key].map((t) => (
              <KanbanCard key={t.id} ticket={t} onOpen={onOpen} />
            ))}
          </KanbanColumn>
        ))}
      </div>

      <DragOverlay dropAnimation={reduced ? null : undefined}>
        {activeCard ? <KanbanCard ticket={activeCard} onOpen={() => {}} overlay /> : null}
      </DragOverlay>

      {pendingBlock && (
        <div className="fixed inset-x-0 top-20 z-50 flex justify-center px-4">
          <KanbanReasonPrompt
            ticketLabel={rowsById.get(pendingBlock.ticketId)?.external_ticket_id ?? ''}
            onSave={(reason) => {
              markBlocked.mutate({ id: pendingBlock.ticketId, blocked: true, blocked_reason: reason });
              setPendingBlock(null);
            }}
            onCancel={() => setPendingBlock(null)}
          />
        </div>
      )}
    </DndContext>
  );
}
