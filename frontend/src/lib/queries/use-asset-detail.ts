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
  // Phase 32 (32-01/32-02/32-03) — exposure-context fields. Precedence:
  // ASSET_OVERRIDE (permanent) > GROUP_OVERRIDE (most-recently-updated group
  // wins on conflict) > AUTO (inferred at upsert/recompute).
  business_criticality: string | null;
  business_criticality_source: 'AUTO' | 'ASSET_OVERRIDE' | 'GROUP_OVERRIDE' | null;
  // Read-side lookup (32-05) — the name of the group currently driving this
  // field when its source is GROUP_OVERRIDE; null otherwise.
  business_criticality_group_name: string | null;
  data_sensitivity: string | null;
  data_sensitivity_source: 'AUTO' | 'ASSET_OVERRIDE' | 'GROUP_OVERRIDE' | null;
  data_sensitivity_group_name: string | null;
  internet_facing: boolean | null;
  internet_facing_source: 'AUTO' | 'ASSET_OVERRIDE' | 'GROUP_OVERRIDE' | null;
  internet_facing_group_name: string | null;
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
