import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// TileValue.value is a union — `mttr_30d` is formatted server-side as e.g. "4.2d"
// (Plan 01 Open Q2 / Warning 6 in 10-02-PLAN). critical_open / sla_at_risk / kev
// are always numbers; mttr is always string. UI rendering treats the value as
// a display token regardless of underlying type.
export type TileValue = {
  value: number | string;
  delta: number | null;
  delta_direction: 'up' | 'down' | 'flat' | null;
};

export type TopVuln = {
  id: string; // vuln UUID — required for snooze + undo mutations (Blocker 2 fix)
  cve_id: string;
  host: string;
  path: string;
  cvss: number;
  on_kev: boolean;
  exploited: boolean;
};

export type DashboardStatsResponse = {
  dashboard_tiles: {
    critical_open: TileValue;
    sla_at_risk: TileValue;
    kev: TileValue;
    mttr_30d: TileValue;
  };
  top_vuln: TopVuln | null;
  vuln_open_count: number;
  asset_total_count: number;
  ticket_open_count: number;
  onboarding_state: 'no_scanners' | 'no_data_yet' | 'ready';
};

export function useStats() {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.stats(),
    queryFn: ({ signal }) =>
      api<DashboardStatsResponse>('/api/v1/vulnerabilities/stats', { signal }),
    staleTime: 60_000, // D-D-06
    retry: 1, // D-D-07: 1× on 5xx for stats (most-visible tile tier)
    refetchOnWindowFocus: true, // D-D-06 explicit (matches default; documents intent)
  });
}
