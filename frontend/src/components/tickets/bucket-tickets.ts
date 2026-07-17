// Phase 18 (18-00 Task 2) — pure projection of the tickets list cache into
// kanban columns. No React, no side effects, no local copy of ticket state:
// the board re-renders from useTickets and re-buckets automatically when
// useMarkBlocked.onMutate flips the `blocked` flag (RESEARCH Pattern 1).
import type { TicketSummary } from '@/lib/queries/use-tickets';

export type ColumnKey = 'open' | 'in_progress' | 'completed' | 'blocked';

// D-COL-04 — flow order left→right.
export const COLUMN_ORDER: ColumnKey[] = ['open', 'in_progress', 'completed', 'blocked'];

// D-COL-04 — column header display labels.
export const COLUMN_LABELS: Record<ColumnKey, string> = {
  open: 'Open',
  in_progress: 'In progress',
  completed: 'Completed',
  blocked: 'Blocked',
};

/**
 * Buckets a TicketSummary[] into the 4 canonical kanban columns.
 *
 * - D-COL-01: `blocked === true` wins — the ticket lives ONLY in the
 *   Blocked column regardless of `external_status`.
 * - STATUS_ALLOW mirrors use-tickets.ts: 'open' | 'in_progress' | 'completed'.
 *   'in_progress' and 'in progress' (space variant) both map to in_progress.
 * - Claude's Discretion (RESEARCH): null, '', or any unrecognized
 *   `external_status` value maps to Open.
 * - Matching is case-insensitive.
 */
export function bucketTickets(rows: TicketSummary[]): Record<ColumnKey, TicketSummary[]> {
  const cols: Record<ColumnKey, TicketSummary[]> = {
    open: [],
    in_progress: [],
    completed: [],
    blocked: [],
  };

  for (const t of rows) {
    if (t.blocked) {
      cols.blocked.push(t);
      continue;
    }
    const s = t.external_status?.toLowerCase() ?? null;
    if (s === 'in_progress' || s === 'in progress') {
      cols.in_progress.push(t);
    } else if (s === 'completed') {
      cols.completed.push(t);
    } else {
      cols.open.push(t);
    }
  }

  return cols;
}
