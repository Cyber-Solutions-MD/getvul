'use client';
/**
 * KanbanColumn — droppable column with status-accent header, live count,
 * per-column EmptyState, and a drag-dim cue.
 *
 * D-COL-02: always renders (4 canonical columns) — empty state renders
 * the shared EmptyState instead of cards.
 * D-COL-04: header order is status-accent dot + label + live count badge.
 * D-DRAG-03: read-only lanes (i.e. columns that are not a valid drop target
 * for the ticket currently being dragged) dim during a drag.
 *
 * Per RESEARCH Pattern 3: the droppable stays ENABLED for every column at all
 * times — the "you can't drop here" gate is enforced in `onDragEnd` (18-03),
 * not via dnd-kit's `disabled` option, so `isOver` still fires correctly and
 * the ring/dim cues can coexist.
 *
 * No inline hex — all colors via Tailwind sunset tokens. No position:fixed
 * or sticky (must not collide with the bottom-nav — Pitfall 4).
 */
import type { ReactNode } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { EmptyState } from '@/components/states/empty-state';
import { cn } from '@/lib/utils';
import type { ColumnKey } from './bucket-tickets';

// D-P-04 status-accent classes per column — mirrors status-pill.tsx so
// light+dark AA holds (same -on-soft token pattern).
const COLUMN_ACCENT: Record<ColumnKey, string> = {
  open: 'text-[var(--color-violet-on-soft)] border-violet/40 bg-violet-soft',
  in_progress: 'text-[var(--color-amber-on-soft)] border-amber/40 bg-amber/10',
  completed: 'text-success border-success/40 bg-success/10',
  blocked: 'text-[var(--color-severity-critical-on-soft)] border-severity-critical/40 bg-severity-critical/10',
};

// Peer-voice empty copy per column (copy-voice.md).
const EMPTY_COPY: Record<ColumnKey, string> = {
  open: 'Nothing in this column.',
  in_progress: 'Nothing in this column.',
  completed: 'Nothing in this column.',
  blocked: 'No blockers right now.',
};

export type KanbanColumnProps = {
  columnKey: ColumnKey;
  label: string;
  count: number;
  isValidTarget: boolean;
  isDragActive: boolean;
  children: ReactNode;
  isEmpty: boolean;
};

export function KanbanColumn({
  columnKey,
  label,
  count,
  isValidTarget,
  isDragActive,
  children,
  isEmpty,
}: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: columnKey });

  return (
    <div
      data-column={columnKey}
      role="region"
      aria-label={label}
      className={cn(
        'snap-start shrink-0 basis-[85vw] md:basis-0 md:flex-1 flex flex-col rounded-lg',
        isDragActive && !isValidTarget && 'opacity-40',
        isOver && isValidTarget && 'ring-2 ring-violet',
      )}
    >
      {/* Header: status-accent dot + label + live count badge */}
      <div className="flex items-center gap-2 px-1 pb-2">
        <span
          className={cn(
            'inline-flex size-2.5 shrink-0 rounded-full border',
            COLUMN_ACCENT[columnKey],
          )}
        />
        <span className="text-sm font-semibold text-text">{label}</span>
        <span className="ml-auto rounded-full border border-border-subtle px-2 py-0.5 text-xs text-text-muted">
          {count}
        </span>
      </div>

      {/* Body: droppable region */}
      <div ref={setNodeRef} className="flex flex-col gap-2 min-h-[4rem]">
        {isEmpty ? (
          <EmptyState>
            <EmptyState.Title>Nothing here</EmptyState.Title>
            <EmptyState.Body>{EMPTY_COPY[columnKey]}</EmptyState.Body>
          </EmptyState>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
