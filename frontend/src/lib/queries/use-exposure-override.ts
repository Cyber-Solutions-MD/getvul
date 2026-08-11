'use client';
/**
 * useSetExposureOverride — per-asset exposure-context override mutation for
 * the ExposureContextCard (32-05-PLAN Task 1).
 *
 * Contract:
 *   - PATCH /api/v1/assets/{id}/exposure-context  body { field, value }
 *     (value is always a string — "true"/"false" for internet_facing, the
 *     enum literal for business_criticality/data_sensitivity — mirroring
 *     the backend's `_ExposureOverrideUpdate` Pydantic model exactly).
 *   - Response is the FULL asset-detail dict (same shape as `useAsset`'s
 *     GET), so onSuccess writes it straight into the byId cache instead of
 *     re-fetching — mirrors `useReassignAsset`'s optimistic-cache shape but
 *     doesn't need onMutate optimism since the response IS the new truth.
 *   - onError: error Toast. onSuccess: success Toast naming the field.
 *
 * Threat model anchor (32-05-PLAN <threat_model> T-32-13): this hook sends
 * ONLY {field, value} — never spreads arbitrary form state — mirroring
 * useReassignAsset's T-12-08 mass-assignment guard. The backend's
 * `_ExposureOverrideUpdate` (`extra: "forbid"`) is the real boundary.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';
import type { AssetDetail } from './use-asset-detail';

export type ExposureField = 'business_criticality' | 'data_sensitivity' | 'internet_facing';

const FIELD_LABEL: Record<ExposureField, string> = {
  business_criticality: 'Business criticality',
  data_sensitivity: 'Data sensitivity',
  internet_facing: 'Internet-facing',
};

export type SetExposureOverrideBody = {
  field: ExposureField;
  /** Always a string on the wire — "true"/"false" for internet_facing. */
  value: string;
};

export function useSetExposureOverride(assetId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<AssetDetail, Error, SetExposureOverrideBody>({
    mutationFn: (body) =>
      api<AssetDetail>(`/api/v1/assets/${assetId}/exposure-context`, {
        method: 'PATCH',
        // T-32-13: ONLY {field, value} — never spread arbitrary form state.
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: (data, variables) => {
      // Response is the full asset-detail dict — write it directly rather
      // than re-fetching (the plan's "invalidate" requirement is satisfied
      // by both approaches; this one is instant + avoids a network round trip).
      qc.setQueryData(queryKeys.assets.byId(assetId), data);
      qc.invalidateQueries({ queryKey: queryKeys.assets.byId(assetId) });
      toast({
        variant: 'success',
        message: `${FIELD_LABEL[variables.field]} updated.`,
      });
    },
    onError: (err) => {
      toast({
        variant: 'error',
        message: err.message || 'Could not update exposure context. Try again.',
      });
    },
    retry: 0,
  });
}
