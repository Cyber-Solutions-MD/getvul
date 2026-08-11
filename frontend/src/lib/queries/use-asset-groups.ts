'use client';
/**
 * use-asset-groups.ts — TanStack query + mutation hooks for the AssetGroup
 * management surface (32-05-PLAN Task 2).
 *
 * Endpoints (backend/app/assets/groups_router.py, mounted at
 * /api/v1/asset-groups — Plan 03, extended read endpoints Plan 05):
 *   GET    /api/v1/asset-groups                        any authed tenant member → AssetGroupResponse[] (+ member_count)
 *   POST   /api/v1/asset-groups                         admin  body { name, description? }
 *   PATCH  /api/v1/asset-groups/{id}                     admin  body { name?, description? }
 *   DELETE /api/v1/asset-groups/{id}                     admin
 *   GET    /api/v1/asset-groups/{id}/members             any authed tenant member → AssetGroupMember[]
 *   POST   /api/v1/asset-groups/{id}/members/{asset_id}  admin  (idempotent)
 *   DELETE /api/v1/asset-groups/{id}/members/{asset_id}  admin
 *   GET    /api/v1/asset-groups/{id}/exposure-context     any authed tenant member → Record<field, value>
 *   PATCH  /api/v1/asset-groups/{id}/exposure-context     admin  body { field, value }
 *
 * Snake_case fields: no transform layer (mirrors use-connectors-admin.ts:15).
 * Mutations invalidate queryKeys.assetGroups.all (list mutations) or the
 * per-group members/exposureContext key (membership/override mutations) —
 * mirrors use-connectors-admin.ts's toast-on-settle shape exactly.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

// ——— Types ———

export type AssetGroupResponse = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type AssetGroupMember = {
  id: string;
  hostname: string | null;
};

export type GroupExposureOverrides = Record<string, string>;

export type CreateAssetGroupBody = {
  name: string;
  description?: string | null;
};

export type UpdateAssetGroupBody = {
  name?: string;
  description?: string | null;
};

export type SetGroupExposureOverrideBody = {
  field: 'business_criticality' | 'data_sensitivity' | 'internet_facing';
  value: string;
};

// ——— Queries ———

export function useAssetGroupsList() {
  return useQuery({
    queryKey: queryKeys.assetGroups.list(),
    queryFn: ({ signal }) =>
      api<AssetGroupResponse[]>('/api/v1/asset-groups', { signal }),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useGroupMembers(groupId: string | null) {
  return useQuery({
    queryKey: queryKeys.assetGroups.members(groupId ?? ''),
    queryFn: ({ signal }) =>
      api<AssetGroupMember[]>(`/api/v1/asset-groups/${groupId}/members`, { signal }),
    enabled: !!groupId,
    staleTime: 15_000,
    retry: 1,
  });
}

export function useGroupExposureOverrides(groupId: string | null) {
  return useQuery({
    queryKey: queryKeys.assetGroups.exposureContext(groupId ?? ''),
    queryFn: ({ signal }) =>
      api<GroupExposureOverrides>(`/api/v1/asset-groups/${groupId}/exposure-context`, { signal }),
    enabled: !!groupId,
    staleTime: 15_000,
    retry: 1,
  });
}

// ——— Mutations ———

export function useCreateAssetGroup() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (body: CreateAssetGroupBody) =>
      api<AssetGroupResponse>('/api/v1/asset-groups', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.all });
      toast({ variant: 'success', message: 'Asset group created.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not create the asset group.' });
    },
  });
}

export function useUpdateAssetGroup() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateAssetGroupBody }) =>
      api<AssetGroupResponse>(`/api/v1/asset-groups/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.all });
      toast({ variant: 'success', message: 'Asset group updated.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not update the asset group.' });
    },
  });
}

export function useDeleteAssetGroup() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (id: string) =>
      api<{ message: string }>(`/api/v1/asset-groups/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.all });
      toast({ variant: 'success', message: 'Asset group deleted.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not delete the asset group.' });
    },
  });
}

export function useAddGroupMember(groupId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (assetId: string) =>
      api<{ message: string }>(`/api/v1/asset-groups/${groupId}/members/${assetId}`, {
        method: 'POST',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.members(groupId) });
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.list() });
      toast({ variant: 'success', message: 'Member added.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not add member.' });
    },
  });
}

export function useRemoveGroupMember(groupId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (assetId: string) =>
      api<{ message: string }>(`/api/v1/asset-groups/${groupId}/members/${assetId}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.members(groupId) });
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.list() });
      toast({ variant: 'success', message: 'Member removed.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not remove member.' });
    },
  });
}

export function useSetGroupExposureOverride(groupId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation({
    mutationFn: (body: SetGroupExposureOverrideBody) =>
      api<{ group_id: string; field: string; value: string }>(
        `/api/v1/asset-groups/${groupId}/exposure-context`,
        {
          method: 'PATCH',
          body: JSON.stringify(body),
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assetGroups.exposureContext(groupId) });
      toast({ variant: 'success', message: 'Group exposure override updated.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Could not update the group override.' });
    },
  });
}
