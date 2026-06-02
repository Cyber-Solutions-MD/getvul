/**
 * use-cspm-findings.ts — TanStack hooks for the CSPM surface.
 *
 * Hooks:
 *   useCspmFindings — paginated finding list GET /api/v1/cspm
 *   useCspmStats    — stats GET /api/v1/cspm/stats
 *   useComplianceFrameworks — frameworks GET /api/v1/cspm/compliance
 *   useBulkCspmStatus — mutation POST /api/v1/cspm/bulk-status
 *
 * T-14-10: filter values reflected into URL params are clamped upstream by
 * ChipBar allowList → useUrlStateList. This hook adds no additional transform
 * (CSPM filters are already clamped before they reach here).
 *
 * Plan 14-03.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import { useToast } from '@/components/ui/ToastProvider';
import { CSPM_MICROCOPY } from '@/components/cspm/microcopy';

// ── Types ────────────────────────────────────────────────────────────────────

export type MisconfigSummary = {
  id: string;
  rule_id: string;
  rule_name: string;
  category: string;
  severity: string;
  source: string;
  status: string;
  resource_id: string;
  resource_name: string;
  resource_type: string;
  cloud_provider: string;
  first_detected_at: string;
  last_seen_at: string;
};

export type CspmFilters = {
  severity?: readonly string[];
  source?: readonly string[];
  status?: readonly string[];
  cloud_provider?: string;
  resource_type?: string;
  search?: string;
};

export type CspmListResponse = {
  items: MisconfigSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type CspmCloudCount = {
  cloud_provider: string;
  count: number;
};

export type CspmStatsResponse = {
  total_findings: number;
  open_findings: number;
  compliance_pass_rate: number | null;
  by_cloud_provider: CspmCloudCount[];
  by_category: Array<{ category: string; count: number }>;
  by_severity: Array<{ severity: string; count: number }>;
};

export type ComplianceFramework = {
  name: string;
  total_controls: number;
  passed: number;
  failed: number;
  suppressed: number;
  pass_rate: number;
};

export type BulkCspmStatus = 'REMEDIATED' | 'SUPPRESSED' | 'OPEN';

// ── URL param builder ─────────────────────────────────────────────────────────

export function buildCspmParams(opts: {
  filters: CspmFilters;
  page: number;
}): URLSearchParams {
  const sp = new URLSearchParams();
  const { filters } = opts;

  filters.severity?.forEach((s) => sp.append('severity', s));
  filters.source?.forEach((s) => sp.append('source', s));
  filters.status?.forEach((s) => sp.append('status', s));
  if (filters.cloud_provider) sp.set('cloud_provider', filters.cloud_provider);
  if (filters.resource_type) sp.set('resource_type', filters.resource_type);
  if (filters.search) sp.set('search', filters.search);
  sp.set('page', String(opts.page));
  sp.set('page_size', '25');

  return sp;
}

// ── Hooks ────────────────────────────────────────────────────────────────────

export function useCspmFindings(opts: { filters: CspmFilters; page: number }) {
  return useQuery({
    queryKey: queryKeys.cspm.list({ filters: opts.filters, page: opts.page }),
    queryFn: ({ signal }) =>
      api<CspmListResponse>(
        `/api/v1/cspm?${buildCspmParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useCspmStats() {
  return useQuery({
    queryKey: queryKeys.cspm.stats(),
    queryFn: ({ signal }) =>
      api<CspmStatsResponse>('/api/v1/cspm/stats', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useComplianceFrameworks() {
  return useQuery({
    queryKey: queryKeys.cspm.compliance(),
    queryFn: ({ signal }) =>
      api<ComplianceFramework[]>('/api/v1/cspm/compliance', { signal }),
    staleTime: 120_000,
    retry: 1,
  });
}

export function useBulkCspmStatus() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: BulkCspmStatus }) =>
      api('/api/v1/cspm/bulk-status', {
        method: 'POST',
        body: JSON.stringify({ ids, status }),
      }),
    onSuccess: (_data, { ids, status }) => {
      const n = ids.length;
      // Invalidate entire cspm subtree
      queryClient.invalidateQueries({ queryKey: queryKeys.cspm.all });

      // Toast per D-CSPM-03 mapping
      if (status === 'REMEDIATED') toast({ message: CSPM_MICROCOPY.toasts.resolved(n), variant: 'success' });
      else if (status === 'SUPPRESSED') toast({ message: CSPM_MICROCOPY.toasts.suppressed(n), variant: 'success' });
      else toast({ message: CSPM_MICROCOPY.toasts.reopened(n), variant: 'success' });
    },
    onError: () => {
      toast({ message: CSPM_MICROCOPY.toasts.error, variant: 'error' });
    },
  });
}
