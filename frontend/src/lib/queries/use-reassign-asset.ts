'use client';
/**
 * useReassignAsset — owner mutation hook for the /assets/[id] right rail (UX-04-04).
 *
 * Contract (12-07-PLAN Task 1):
 *   - POST /api/v1/assets/{id}/owner with body { assigned_user_email }
 *   - onMutate: cancel byId queries, snapshot cache, optimistically patch
 *     `assigned_user` so the owner card flips to the new name BEFORE the
 *     network resolves (honors VALIDATION manual-only #3).
 *   - onError: roll back snapshot, emit an error Toast.
 *   - onSuccess: invalidate `queryKeys.assets.byId(id)` + `queryKeys.assets.all`
 *     and emit a success Toast naming the new owner (ROADMAP SC-6).
 *
 * Threat model anchor (12-07-PLAN <threat_model>):
 *   T-12-08 (mass assignment): we send ONLY {assigned_user_email}; the
 *   backend `_AssetOwnerUpdate` Pydantic model from Plan 12-02 rejects extras.
 *   This file MUST NOT spread arbitrary form data into the body.
 *   T-12-09 (audit miss): backend writes `asset.owner_changed`. Frontend has
 *   no role here.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

export type ReassignResponse = {
  id: string;
  hostname: string | null;
  assigned_user: string | null;
  directory_user: {
    email: string;
    display_name: string | null;
    idp_source: string | null;
    role: string | null;
  } | null;
};

type SnapshotCtx = { snapshot: unknown };

export function useReassignAsset(assetId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<ReassignResponse, Error, string, SnapshotCtx>({
    mutationFn: (email) =>
      api<ReassignResponse>(`/api/v1/assets/${assetId}/owner`, {
        method: 'POST',
        // T-12-08: ONLY the email field — never spread arbitrary form state.
        body: JSON.stringify({ assigned_user_email: email }),
        headers: { 'Content-Type': 'application/json' },
      }),
    // Optimistic update: combobox closes immediately on commit and the cache
    // is patched ahead of network. Tracks VALIDATION manual-only #3.
    onMutate: async (email) => {
      const key = queryKeys.assets.byId(assetId);
      await qc.cancelQueries({ queryKey: key });
      const snapshot = qc.getQueryData(key);
      qc.setQueryData(key, (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev;
        return { ...(prev as Record<string, unknown>), assigned_user: email };
      });
      return { snapshot };
    },
    onError: (_err, _email, ctx) => {
      // Roll back the optimistic patch so the rail re-shows the previous owner.
      if (ctx && ctx.snapshot !== undefined) {
        qc.setQueryData(queryKeys.assets.byId(assetId), ctx.snapshot);
      }
      toast({ variant: 'error', message: 'Could not reassign owner. Try again.' });
    },
    onSuccess: (data) => {
      // Reconcile against server truth + emit confirmation toast (SC-6).
      qc.invalidateQueries({ queryKey: queryKeys.assets.byId(assetId) });
      qc.invalidateQueries({ queryKey: queryKeys.assets.all });
      const newOwner = data.assigned_user ?? 'new owner';
      toast({ variant: 'success', message: `Owner reassigned to ${newOwner}` });
    },
    // BL-06 inheritance (Phase 10): api.ts surfaces 401 on mutations as a
    // thrown error; do NOT retry — audit attribution > convenience.
    retry: 0,
  });
}
