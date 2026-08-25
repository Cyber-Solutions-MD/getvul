'use client';
/**
 * useRemediationsGrouped — GET /api/v1/vulnerabilities/remediations/grouped
 * (Phase 38 Plan 05, CAMP-01 entry point). This is a brand-new frontend
 * consumer of an already-shipped backend endpoint (38-RESEARCH.md Pitfall
 * 8 — zero prior frontend callers), so the response shape below is read
 * directly off `backend/app/vulnerabilities/remediation_service.py::
 * get_remediations_grouped()` rather than an existing frontend type.
 *
 * Mirrors use-vuln-escalations.ts's shape (signal-aware queryFn); unlike
 * the compute-on-read campaigns hooks (staleTime: 0), a 30s staleTime is
 * used here — this is a raw vulnerability aggregation, not a campaign's
 * live progress snapshot, so brief caching is safe (same rationale as
 * use-vuln-escalations.ts's own 30_000).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type RemediationGroup = {
  remediation_id: string;
  remediation_action: string | null;
  affected_product: string | null;
  affected_hosts: number;
  vuln_count: number;
  max_severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  is_suppressed: boolean;
  suppressed_count: number;
};

export type RemediationsGroupedResponse = {
  items: RemediationGroup[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export function useRemediationsGrouped(page = 1, pageSize = 25) {
  return useQuery({
    queryKey: queryKeys.remediationsGrouped.list({ page, pageSize }),
    queryFn: ({ signal }) =>
      api<RemediationsGroupedResponse>(
        `/api/v1/vulnerabilities/remediations/grouped?page=${page}&page_size=${pageSize}`,
        { signal },
      ),
    staleTime: 30_000,
    retry: 1,
  });
}
