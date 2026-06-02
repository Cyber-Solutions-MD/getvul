'use client';
/**
 * useMarkBlocked — optimistic mutation hook for toggling the blocked state on a ticket.
 *
 * Contract (13-07-PLAN Task 1):
 *   - POST /api/v1/tickets/{id}/blocked with body { blocked, blocked_reason }
 *   - onMutate: cancel byId + all, snapshot, optimistically flip blocked/blockedReason
 *   - onError: rollback snapshot + error toast
 *   - onSuccess: invalidate tickets.byId(id) + tickets.all + predicate-invalidate
 *     any ['assets', *, 'remediations'] that may embed ticket state (Pattern 4)
 *
 * Threat model:
 *   T-13-23 (mass assignment): ONLY {blocked, blocked_reason} are sent — never
 *   spread arbitrary form data into the body. Backend Pydantic model rejects extras.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
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

type SnapshotCtx = { snapshot: unknown };

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
      const allKey = queryKeys.tickets.all;

      // Cancel any in-flight queries for this ticket to prevent race conditions.
      await qc.cancelQueries({ queryKey: byIdKey });
      await qc.cancelQueries({ queryKey: allKey });

      // Snapshot both the detail cache and the list cache for rollback.
      const snapshot = {
        byId: qc.getQueryData(byIdKey),
        all: qc.getQueryData(allKey),
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

      // Optimistically update the list cache if it exists.
      // Pattern 4: also patch the list so the table row updates immediately.
      qc.setQueryData(allKey, (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev;
        const typed = prev as { items?: unknown[] };
        if (!typed.items) return prev;
        return {
          ...typed,
          items: typed.items.map((item) => {
            if (!item || typeof item !== 'object') return item;
            const ticket = item as Record<string, unknown>;
            if (ticket.id !== id) return item;
            return { ...ticket, blocked, blockedReason: blocked_reason };
          }),
        };
      });

      return { snapshot };
    },

    onError: (_err, _vars, ctx) => {
      // Roll back to the snapshot so the UI shows the previous state.
      if (ctx) {
        const { snapshot } = ctx as { snapshot: { byId: unknown; all: unknown } };
        if (snapshot.byId !== undefined) {
          qc.setQueryData(
            queryKeys.tickets.byId((_vars as MarkBlockedVars).id),
            snapshot.byId
          );
        }
        if (snapshot.all !== undefined) {
          qc.setQueryData(queryKeys.tickets.all, snapshot.all);
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
