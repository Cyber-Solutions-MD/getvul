import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Phase 12 D-D-01 — detail endpoint for /assets/[id].
// Returns asset + vuln_counts + tags + sla_breach + directory_user in a
// single round-trip; vulnerabilities/remediations live on separate hooks so
// each detail-page section degrades independently.

export type DirectoryUser = {
  email: string;
  display_name: string | null;
  department: string | null;
  job_title: string | null;
  avatar_url: string | null;
  groups: string[];
  idp_source: string | null;
  is_active: boolean;
  role: string | null;
};

export type AssetDetail = {
  id: string;
  hostname: string | null;
  os_name: string | null;
  os_version: string | null;
  device_category: string | null;
  risk_score: number | null;
  seen_by_sources: string[] | Record<string, unknown>;
  assigned_user: string | null;
  tags: string[] | null;
  sla_breach: number;
  vuln_counts: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    exploitable: number;
    kev: number;
    sla_breach: number;
  };
  directory_user: DirectoryUser | null;
  ip_addresses: string[] | null;
  mac_addresses: string[] | null;
  serial_number: string | null;
  model: string | null;
  managed_by: string | null;
  last_checkin_at: string | null;
  building: string | null;
  department: string | null;
};

export function useAsset(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.assets.byId(id ?? ''),
    queryFn: ({ signal }) =>
      api<AssetDetail>(`/api/v1/assets/${id}`, { signal }),
    enabled: !!id,
    staleTime: 30_000,
    retry: 1,
  });
}
