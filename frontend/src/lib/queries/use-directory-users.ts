import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Plan 14-04 — directory users hook + stats.
// D-X-02: snake_case throughout (no camelCase transform).
// Pitfall 7: role is NOT exposed in this module — job_title/department are the
// display fields; role is the RBAC role shown only in Workspace settings.

export type DirectoryUsersFilters = {
  status?: string;
  department?: string;
  source?: string;
  search?: string;
};

export type DirectoryUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: string;            // RBAC role — fetched but NOT rendered in directory
  department: string | null;
  job_title: string | null;
  idp_source: string;
  is_active: boolean;
  groups: string[];
  avatar_url: string | null;
  last_login_at: string | null;
  device_count: number;
  devices: Array<{
    id: string;
    hostname: string;
    os_name: string | null;
    device_category: string | null;
    risk_score: number;
    model: string | null;
    serial_number: string | null;
    host_status: string | null;
    last_seen_at: string | null;
  }>;
  max_risk_score: number;
  total_vulns: number;
  critical_vulns: number;
  high_vulns: number;
  exploitable_vulns: number;
};

export type DirectoryUsersResponse = {
  items: DirectoryUser[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type DirectoryStatsResponse = {
  total_users: number;
  active: number;
  suspended: number;
  by_source: Record<string, number>;
  has_department: number;
  has_groups: number;
  departments: Array<{ name: string; count: number }>;
  assigned_assets: number;
  unassigned_assets: number;
};

// buildDirectorySearchParams is co-located + exported so URL-shape tests can
// assert the wire contract without spinning up TanStack (Phase 11 D-D-03 pattern).
export function buildDirectorySearchParams(opts: {
  filters: DirectoryUsersFilters;
  page: number;
  sort: string;
  order: string;
}): URLSearchParams {
  const sp = new URLSearchParams();
  sp.set('page', String(opts.page));
  if (opts.filters.status) sp.set('status', opts.filters.status);
  if (opts.filters.department) sp.set('department', opts.filters.department);
  if (opts.filters.source) sp.set('source', opts.filters.source);
  if (opts.filters.search) sp.set('search', opts.filters.search);
  if (opts.sort) {
    sp.set('sort_by', opts.sort);
    sp.set('sort_dir', opts.order);
  }
  return sp;
}

export function useDirectoryUsers(opts: {
  filters: DirectoryUsersFilters;
  page: number;
  sort: string;
  order: string;
}) {
  return useQuery({
    queryKey: queryKeys.directoryUsers.list({
      filters: opts.filters,
      page: opts.page,
      sort: opts.sort,
      order: opts.order,
    }),
    queryFn: ({ signal }) =>
      api<DirectoryUsersResponse>(
        `/api/v1/users/directory?${buildDirectorySearchParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useDirectoryStats() {
  return useQuery({
    queryKey: queryKeys.directoryUsers.stats(),
    queryFn: ({ signal }) =>
      api<DirectoryStatsResponse>('/api/v1/users/stats', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}
