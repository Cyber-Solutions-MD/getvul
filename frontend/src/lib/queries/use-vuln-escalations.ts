'use client';
/**
 * useVulnEscalations — GET /api/v1/vulnerabilities/{id}/escalations (Phase 36
 * / SLA-03, D-07). Tenant-scoped, IDOR-safe escalation-fire history for a
 * single finding, consumed by the drill panel's escalation-history list
 * (36-06). Mirrors useVulnerabilityDetail's shape (signal-aware queryFn,
 * enabled-gate on a non-empty id).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type VulnEscalationEvent = {
  id: string;
  from_state: string;
  to_state: string;
  channel: string;
  fired_at: string;
  delivery_status: string;
  error_message: string | null;
};

export function useVulnEscalations(id: string | null) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.escalations(id ?? ''),
    queryFn: ({ signal }) =>
      api<VulnEscalationEvent[]>(
        `/api/v1/vulnerabilities/${encodeURIComponent(id!)}/escalations`,
        { signal },
      ),
    enabled: id !== null && id !== '',
    staleTime: 30_000,
    retry: 1,
  });
}
