import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type TriageRow = {
  id: string;
  cve_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  host: string;
  cvss_v3_score: number | null;
  cisa_kev: boolean;
  sla_due_at: string | null;
};

export type TopTriageResponse = {
  items: TriageRow[];
  total: number;
};

export function useTopTriage(limit = 5) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.topTriage(limit),
    queryFn: ({ signal }) =>
      api<TopTriageResponse>(`/api/v1/vulnerabilities?sort=triage&limit=${limit}`, {
        signal,
      }),
    staleTime: 60_000,
    retry: 0, // D-D-07: only stats + dashboard-tiles tier retries
  });
}
