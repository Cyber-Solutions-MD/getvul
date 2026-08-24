'use client';
/**
 * useSlaMetrics — GET /api/v1/vulnerabilities/sla/metrics (Phase 43 Plan
 * 04, RPT-02). Mirrors use-coverage-summary.ts's no-arg, `staleTime: 0`
 * shape.
 *
 * T-43-15 / D-15 (exception-consistency, Pitfall 2): ALWAYS requests
 * `?exclude_exceptions=true` — the additive query param this plan's
 * router.py extension threads into `get_sla_metrics`. This makes the
 * leadership/compliance-lens SLA-compliance tile read the SAME
 * `compliance_pct` the compliance page (Plan 01) and the board PDF (Plan
 * 02) already compute, rather than the route's own default (`false`,
 * preserved for every pre-existing consumer of this route).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type SlaMetrics = {
  sla_config: Record<string, number>;
  open_with_sla: number;
  breached: number;
  at_risk: number;
  within_sla: number;
  compliance_pct: number;
  remediated_within_sla: number;
  /** D-11 zero-denominator discipline: 0 means "not yet measured", never a real 100%. */
  remediated_total: number;
  breach_by_severity: Record<string, number>;
  avg_days_remaining: number | null;
};

export function useSlaMetrics() {
  return useQuery({
    queryKey: queryKeys.slaMetrics.get({ excludeExceptions: true }),
    queryFn: ({ signal }) =>
      api<SlaMetrics>('/api/v1/vulnerabilities/sla/metrics?exclude_exceptions=true', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
