'use client';
/**
 * useMarkBlocked — optimistic mutation hook for toggling the blocked state on a ticket.
 *
 * Contract (13-07-PLAN Task 1, patched 18-00 Task 3 — Pitfall 1):
 *   - POST /api/v1/tickets/{id}/blocked with body { blocked, blocked_reason }
 *   - onMutate: cancel byId + every ['tickets','list',*] query, snapshot both,
 *     optimistically flip blocked/blocked_reason in each
 *   - onError: rollback the byId snapshot + every captured list snapshot + error toast
 *   - onSuccess: invalidate tickets.byId(id) + tickets.all + predicate-invalidate
 *     any ['assets', *, 'remediations'] that may embed ticket state (Pattern 4)
 *
 * Pitfall 1 (18-RESEARCH.md): list data lives under the FUZZY key
 * ['tickets','list',{filters,page,view}] — one query per filter/page/view
 * permutation — not the exact ['tickets'] prefix. `setQueryData`/`getQueryData`
 * use EXACT key matching, so patching `queryKeys.tickets.all` was a no-op
 * against real list caches. Fixed here via `setQueriesData`/`getQueriesData`
 * with `{ queryKey: ['tickets','list'] }`, which matches every cached list
 * query (list view AND the kanban board — both are pure projections of the
 * same cache) regardless of its filter/page/view permutation.
 *
 * Threat model:
 *   T-13-23 (mass assignment): ONLY {blocked, blocked_reason} are sent — never
 *   spread arbitrary form data into the body. Backend Pydantic model rejects extras.
 */
import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

type MarkBlockedVars = {
  id: string;
  blocked: boolean;
  blocked_reason: string | null;
};

type MarkBlockedResponse = {
  blocked: boolean;
  blocked_reason: string | null;
};

type SnapshotCtx = {
  snapshot: {
    byId: unknown;
    listSnapshots: Array<[QueryKey, unknown]>;
  };
};

export function useMarkBlocked() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<MarkBlockedResponse, Error, MarkBlockedVars, SnapshotCtx>({
    mutationFn: ({ id, blocked, blocked_reason }) =>
      api<MarkBlockedResponse>(`/api/v1/tickets/${id}/blocked`, {
        method: 'POST',
        // T-13-23: ONLY {blocked, blocked_reason} — never spread arbitrary vars.
        body: JSON.stringify({ blocked, blocked_reason }),
        headers: { 'Content-Type': 'application/json' },
      }),

    onMutate: async ({ id, blocked, blocked_reason }) => {
      const byIdKey = queryKeys.tickets.byId(id);
      const listPrefix = { queryKey: ['tickets', 'list'] as const };

      // Cancel any in-flight queries for this ticket (byId) and every cached
      // tickets list query (fuzzy — list view + kanban board share this cache)
      // to prevent race conditions with the optimistic patch below.
      await qc.cancelQueries({ queryKey: byIdKey });
      await qc.cancelQueries(listPrefix);

      // Snapshot the detail cache and EVERY cached list query for rollback.
      const snapshot = {
        byId: qc.getQueryData(byIdKey),
        listSnapshots: qc.getQueriesData<{ items?: unknown[] }>(listPrefix),
      };

      // Optimistically flip the blocked state in the detail cache.
      qc.setQueryData(byIdKey, (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev;
        return {
          ...(prev as Record<string, unknown>),
          blocked,
          blocked_reason,
        };
      });

      // Optimistically flip the blocked state in EVERY cached tickets list
      // query (fuzzy match — Pitfall 1 fix). `setQueryData` (exact) missed
      // the real ['tickets','list',{filters,page,view}] key shape; the board
      // (a pure projection of this same cache) needs this to reproject
      // optimistically too.
      qc.setQueriesData(listPrefix, (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev;
        const typed = prev as { items?: unknown[] };
        if (!typed.items) return prev;
        return {
          ...typed,
          items: typed.items.map((item) => {
            if (!item || typeof item !== 'object') return item;
            const ticket = item as Record<string, unknown>;
            if (ticket.id !== id) return item;
            // WR-07: snake_case to match TicketSummary/TicketDetail (CR-04).
            return { ...ticket, blocked, blocked_reason };
          }),
        };
      });

      return { snapshot };
    },

    onError: (_err, vars, ctx) => {
      // Roll back to the snapshot so the UI shows the previous state.
      if (ctx) {
        const { snapshot } = ctx;
        if (snapshot.byId !== undefined) {
          qc.setQueryData(queryKeys.tickets.byId(vars.id), snapshot.byId);
        }
        for (const [key, data] of snapshot.listSnapshots) {
          qc.setQueryData(key, data);
        }
      }
      toast({ variant: 'error', message: 'Could not update blocked status. Try again.' });
    },

    onSuccess: (_data, { id }) => {
      // Reconcile against server truth.
      qc.invalidateQueries({ queryKey: queryKeys.tickets.byId(id) });
      qc.invalidateQueries({ queryKey: queryKeys.tickets.all });

      // Pattern 4 (RESEARCH §Pattern 4): predicate-invalidate any asset
      // remediations list that may embed ticket state. Ticket blocked status
      // can surface in the asset detail right-rail remediation card.
      qc.invalidateQueries({
        predicate: (q) =>
          Array.isArray(q.queryKey) &&
          q.queryKey[0] === 'assets' &&
          q.queryKey[2] === 'remediations',
      });
    },

    retry: 0,
  });
}
