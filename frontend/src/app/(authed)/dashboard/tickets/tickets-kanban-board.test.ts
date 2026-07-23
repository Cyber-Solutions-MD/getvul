// Unit coverage for the two kanban paths the e2e suite cannot reach on the
// default dev seed (the Open lane is empty, so the keyboard-drag specs skip):
//   - WR-01: dragEndAnnouncement — pending vs. committed vs. no-op wording.
//   - 22-IN-02: makeKanbanColumnCoordinateGetter — the ref advances ONLY after
//     the target column's rect is confirmed measured.
// Strings here are the same ones tickets-kanban.spec.ts asserts byte-for-byte.
import { describe, it, expect, vi } from 'vitest';
import type { MutableRefObject } from 'react';
import {
  dragEndAnnouncement,
  makeKanbanColumnCoordinateGetter,
} from './tickets-kanban-board';
import { COLUMN_ORDER, COLUMN_LABELS, type ColumnKey } from '@/components/tickets/bucket-tickets';

const colLabel = (id: string | number): string =>
  COLUMN_LABELS[id as ColumnKey] ?? String(id);

describe('dragEndAnnouncement (WR-01)', () => {
  it('read-only → Blocked announces a PENDING state (mutation fires on Save, not at drop)', () => {
    const msg = dragEndAnnouncement({ blocked: false }, { id: 'blocked' }, 'T-1', colLabel);
    expect(msg).toBe('Ticket T-1 ready to block — confirm the reason to finish.');
    // Must NOT claim a completed move at drop.
    expect(msg).not.toMatch(/^Moved ticket/);
  });

  it('Blocked → read-only is the only immediate commit — announces the completed move', () => {
    expect(dragEndAnnouncement({ blocked: true }, { id: 'open' }, 'T-2', colLabel)).toBe(
      'Moved ticket T-2 to the Open column.',
    );
    expect(dragEndAnnouncement({ blocked: true }, { id: 'in_progress' }, 'T-2', colLabel)).toBe(
      'Moved ticket T-2 to the In progress column.',
    );
  });

  it('read-only → read-only is a gated no-op (returned to its column)', () => {
    expect(dragEndAnnouncement({ blocked: false }, { id: 'in_progress' }, 'T-3', colLabel)).toBe(
      'Ticket T-3 returned to its column.',
    );
  });

  it('Blocked → Blocked is a gated no-op (returned to its column)', () => {
    expect(dragEndAnnouncement({ blocked: true }, { id: 'blocked' }, 'T-4', colLabel)).toBe(
      'Ticket T-4 returned to its column.',
    );
  });

  it('dropped outside any column → returned to its column', () => {
    expect(dragEndAnnouncement({ blocked: false }, null, 'T-5', colLabel)).toBe(
      'Ticket T-5 returned to its column.',
    );
  });

  it('unknown card (no row) → returned to its column, never a false move', () => {
    const msg = dragEndAnnouncement(undefined, { id: 'blocked' }, 'T-6', colLabel);
    expect(msg).toBe('Ticket T-6 returned to its column.');
    expect(msg).not.toMatch(/^Moved ticket/);
  });
});

type RectLike = { left: number; top: number; width: number; height: number };

/** Mock dnd-kit context whose droppableContainers only knows the given columns. */
function makeContext(present: Partial<Record<ColumnKey, RectLike | null>>) {
  return {
    context: {
      droppableContainers: {
        get(key: ColumnKey) {
          if (key in present) return { rect: { current: present[key] } };
          return undefined;
        },
      },
    },
  } as unknown as Parameters<ReturnType<typeof makeKanbanColumnCoordinateGetter>>[1];
}

function arrowEvent(code: 'ArrowRight' | 'ArrowLeft' | 'Tab') {
  return { code, preventDefault: vi.fn() } as unknown as KeyboardEvent;
}

const RECTS: Record<ColumnKey, RectLike> = {
  open: { left: 0, top: 10, width: 100, height: 40 },
  in_progress: { left: 200, top: 10, width: 100, height: 40 },
  completed: { left: 400, top: 10, width: 100, height: 40 },
  blocked: { left: 600, top: 10, width: 100, height: 40 },
};

function center(key: ColumnKey) {
  const r = RECTS[key];
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

describe('makeKanbanColumnCoordinateGetter (22-IN-02)', () => {
  it('ignores non-arrow keys without touching the index', () => {
    const ref = { current: 0 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    expect(getter(arrowEvent('Tab'), makeContext(RECTS))).toBeUndefined();
    expect(ref.current).toBe(0);
  });

  it('ArrowRight advances one column and re-centers on the TARGET rect', () => {
    const ref = { current: 0 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    const coords = getter(arrowEvent('ArrowRight'), makeContext(RECTS));
    expect(ref.current).toBe(1); // open → in_progress
    expect(coords).toEqual(center('in_progress'));
  });

  it('does NOT advance the ref when the target rect is unmeasured (the IN-02 fix)', () => {
    const ref = { current: 0 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    // in_progress absent from the map → target rect missing.
    const coords = getter(arrowEvent('ArrowRight'), makeContext({ open: RECTS.open }));
    expect(coords).toBeUndefined();
    expect(ref.current).toBe(0); // stayed put — next ArrowRight retries from 0, no skip

    // A container that exists but whose rect.current is null is also gated.
    const coords2 = getter(
      arrowEvent('ArrowRight'),
      makeContext({ open: RECTS.open, in_progress: null }),
    );
    expect(coords2).toBeUndefined();
    expect(ref.current).toBe(0);
  });

  it('ArrowLeft clamps at Open (index 0) and stays there', () => {
    const ref = { current: 0 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    const coords = getter(arrowEvent('ArrowLeft'), makeContext(RECTS));
    expect(ref.current).toBe(0);
    expect(coords).toEqual(center('open'));
  });

  it('ArrowRight clamps at Blocked (last index) and stays there', () => {
    const ref = { current: COLUMN_ORDER.length - 1 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    const coords = getter(arrowEvent('ArrowRight'), makeContext(RECTS));
    expect(ref.current).toBe(COLUMN_ORDER.length - 1);
    expect(coords).toEqual(center('blocked'));
  });

  it('crosses Open → Blocked in successive presses when all rects are present', () => {
    const ref = { current: 0 } as MutableRefObject<number>;
    const getter = makeKanbanColumnCoordinateGetter(ref);
    getter(arrowEvent('ArrowRight'), makeContext(RECTS)); // → in_progress
    getter(arrowEvent('ArrowRight'), makeContext(RECTS)); // → completed
    const last = getter(arrowEvent('ArrowRight'), makeContext(RECTS)); // → blocked
    expect(ref.current).toBe(3);
    expect(last).toEqual(center('blocked'));
  });
});
