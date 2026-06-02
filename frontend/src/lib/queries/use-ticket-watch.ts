'use client';
/**
 * useTicketWatch — optimistic POST/DELETE watch toggle with rollback.
 *
 * Contract (13-08-PLAN Task 2):
 *   toggle(true)  → POST  /api/v1/tickets/{id}/watch  (idempotent, no body)
 *   toggle(false) → DELETE /api/v1/tickets/{id}/watch  (idempotent, no body)
 *
 *   - onMutate: snapshot tickets.byId(id), optimistically flip the current-user
 *     watcher membership so the Watch/Watching button flips BEFORE network resolves.
 *   - onError: restore snapshot + error toast (peer voice, no "Please").
 *     PITFALL 6: never leave the button stuck in the wrong state — snapshot mandatory.
 *   - onSuccess: invalidate tickets.byId(id) + tickets.watchers(id).
 *   - retry: 0.
 *
 * Threat model:
 *   T-13-26 (mass assignment): watch carries no payload (method only, {} body is fine).
 *   T-13-30 (optimistic integrity): onMutate snapshot + onError restore prevents the UI
 *     asserting a state the server never committed (D-W-03).
 *
 * Pitfall 6: snapshot is MANDATORY — onError must restore it or the button stays
 * "Watching" even though the server rejected the POST. Tests assert this path.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';
import type { TicketDetail } from './use-ticket-detail';

type WatchCtx = { snapshot: unknown };

export function useTicketWatch(id: string, currentUserId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<unknown, Error, boolean, WatchCtx>({
    // T-13-26: no body payload — method only. Watch endpoint carries no data fields.
    mutationFn: (next: boolean) =>
      api(`/api/v1/tickets/${id}/watch`, {
        method: next ? 'POST' : 'DELETE',
      }),

    onMutate: async (next) => {
      const key = queryKeys.tickets.byId(id);
      await qc.cancelQueries({ queryKey: key });

      // PITFALL 6: snapshot is mandatory — restoring on error keeps button correct.
      const snapshot = qc.getQueryData(key);

      // Optimistically flip current-user watcher membership in the detail cache.
      qc.setQueryData(key, (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev;
        const detail = prev as TicketDetail;
        let watchers: TicketDetail['watchers'];

        if (next) {
          // Add current user as watcher if not already present
          const alreadyWatching = detail.watchers.some(
            (w) => w.userId === currentUserId,
          );
          if (alreadyWatching) {
            watchers = detail.watchers;
          } else {
            watchers = [
              ...detail.watchers,
              {
                userId: currentUserId,
                displayName: 'You',
                role: 'watcher' as const,
                createdAt: new Date().toISOString(),
              },
            ];
          }
        } else {
          // Remove current user from watchers
          watchers = detail.watchers.filter((w) => w.userId !== currentUserId);
        }

        return { ...detail, watchers };
      });

      return { snapshot };
    },

    onError: (_err, _next, ctx) => {
      // PITFALL 6: restore snapshot so the Watch/Watching button is never stuck.
      if (ctx && ctx.snapshot !== undefined) {
        qc.setQueryData(queryKeys.tickets.byId(id), ctx.snapshot);
      }
      // Peer voice — no "Please", no "Unable to".
      toast({ variant: 'error', message: "Couldn't update watch. Try again." });
    },

    onSuccess: () => {
      // Reconcile against server truth.
      qc.invalidateQueries({ queryKey: queryKeys.tickets.byId(id) });
      qc.invalidateQueries({ queryKey: queryKeys.tickets.watchers(id) });
    },

    retry: 0,
  });
}
