/**
 * use-cspm-detail.ts — TanStack hook for CSPM finding detail.
 *
 * useCspmDetail(id) — useQuery(queryKeys.cspm.detail(id), GET /api/v1/cspm/{id}), enabled: !!id.
 *
 * MisconfigResponse adds to MisconfigSummary:
 *   rule_description, frameworks[], resource_region, cloud_account_id, cloud_account_name,
 *   remediation_info, remediation_url, remediated_at, details.
 *
 * Plan 14-03.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import type { MisconfigSummary } from './use-cspm-findings';

export type FrameworkMapping = {
  name: string;
  control_id: string;
  compliance_status: string;
};

export type MisconfigResponse = MisconfigSummary & {
  rule_description: string | null;
  frameworks: FrameworkMapping[];
  resource_region: string | null;
  cloud_account_id: string | null;
  cloud_account_name: string | null;
  remediation_info: string | null;
  remediation_url: string | null;
  remediated_at: string | null;
  details: Record<string, unknown> | null;
};

export function useCspmDetail(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.cspm.detail(id ?? ''),
    queryFn: ({ signal }) =>
      api<MisconfigResponse>(`/api/v1/cspm/${id}`, { signal }),
    enabled: !!id,
    staleTime: 60_000,
    retry: 1,
  });
}
