'use client';
/**
 * useComplianceOverview — GET /api/v1/compliance/overview (Phase 43 Plan
 * 01, RPT-03 tracer slice): per-framework control-status rows evidenced
 * by posture metrics (D-08/D-13). Mirrors use-coverage-summary.ts's
 * no-arg-shape exactly.
 *
 * staleTime: 0 (D-10/coverage precedent) — every control is compute-on-
 * read over Phase 36/41/42 services, so a stale client cache could show
 * an out-of-date status.
 *
 * Backend contract: backend/app/compliance/schemas.py::ComplianceOverviewResponse
 * / ControlStatusResponse (snake_case end-to-end — CR-04 precedent, api()
 * does no casing transform). The browser NEVER re-derives `status` — it
 * renders exactly what this endpoint returns.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type ControlStatus = {
  framework: string; // "soc2" | "iso27001" | "pci_dss" | "nist_csf"
  control_id: string;
  title: string;
  metric_key: string;
  value: number | null;
  status: 'pass' | 'partial' | 'fail' | 'not_measured';
};

export type ComplianceOverviewResponse = {
  controls: ControlStatus[];
};

export function useComplianceOverview() {
  return useQuery({
    queryKey: queryKeys.compliance.overview(),
    queryFn: ({ signal }) => api<ComplianceOverviewResponse>('/api/v1/compliance/overview', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
