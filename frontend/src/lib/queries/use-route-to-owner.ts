'use client';
/**
 * useRouteToOwner — mutation hook for the Plan 04 (COV-03) backend endpoint
 * `POST /api/v1/coverage/assets/{asset_id}/route-to-owner`. Mirrors
 * use-reassign-asset.ts's toast + targeted-invalidate + `retry: 0` shape
 * (41-PATTERNS.md's "Mutation hook: toast + query invalidate" pattern).
 *
 * No request body (the endpoint resolves the owner server-side via
 * `get_directory_user`, D-07/D-09) — the mutation fn takes no variables.
 *
 * `retry: 0` — this mutation has audit + notification side effects
 * (T-41-16): a mutation with real-world side effects is never auto-retried,
 * matching every other v5.0 write hook (`use-reassign-asset.ts`,
 * `use-exception-mutations.ts`).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { microcopy } from '@/components/coverage/microcopy';
import { queryKeys } from './keys';

export type RouteToOwnerResponse = {
  hostname: string;
  routed_to: string;
};

export function useRouteToOwner(assetId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<RouteToOwnerResponse, Error, void>({
    mutationFn: () =>
      api<RouteToOwnerResponse>(`/api/v1/coverage/assets/${assetId}/route-to-owner`, {
        method: 'POST',
      }),
    onError: () => {
      toast({ variant: 'error', message: microcopy.routeToOwner.errorToast });
    },
    onSuccess: (data) => {
      // Coverage is compute-on-read (D-10) — a successful route-to-owner
      // changes nothing on the server's blind-spot reconciliation itself,
      // but invalidating queryKeys.coverage.all keeps the whole domain
      // (list + summary) consistent with the mutation-hook convention every
      // other v5.0 write path follows.
      qc.invalidateQueries({ queryKey: queryKeys.coverage.all });
      // UI-SPEC Copywriting Contract's exact success-toast template:
      // "{hostname} routed to {routed_to}" — routed_to is already either
      // the resolved owner's display name/email or the literal "your
      // admins" fallback string (D-09), computed server-side.
      toast({ variant: 'success', message: `${data.hostname} routed to ${data.routed_to}` });
    },
    retry: 0,
  });
}
