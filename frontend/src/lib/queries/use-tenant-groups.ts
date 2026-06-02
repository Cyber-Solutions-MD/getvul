import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Plan 14-04 — tenant groups hook.
// GET /api/v1/tenant/groups (Admin) → array of group objects.

export type TenantGroupMember = {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  department: string | null;
};

export type TenantGroup = {
  name: string;
  member_count: number;
  members: TenantGroupMember[];
};

export function useTenantGroups() {
  return useQuery({
    queryKey: queryKeys.settings.groups(),
    queryFn: ({ signal }) =>
      api<TenantGroup[]>('/api/v1/tenant/groups', { signal }),
    staleTime: 60_000,
  });
}
