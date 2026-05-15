import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type Range = '7d' | '30d' | '90d';

export type TrendsResponse = {
  // D-C-09 severity-stacked daily counts.
  severity_trends: Record<
    string,
    { critical: number; high: number; medium: number; low: number }
  >;
};

export function useTrends(range: Range = '30d') {
  const days = range === '7d' ? 7 : range === '90d' ? 90 : 30;
  return useQuery({
    queryKey: queryKeys.vulnerabilities.trends(range), // key carries range param per D-D-03
    queryFn: ({ signal }) =>
      api<TrendsResponse>(`/api/v1/vulnerabilities/trends?days=${days}`, { signal }),
    staleTime: 60_000, // D-D-06
    retry: 1, // D-D-07 dashboard-tiles tier
    refetchOnWindowFocus: false, // chart redraw on alt-tab is jarring
  });
}
