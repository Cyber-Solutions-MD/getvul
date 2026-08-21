'use client';
/**
 * useAnalytics — GET /api/v1/analytics/overview (Phase 42 Plan 01, tracer
 * slice: TREND-01/03). Merges use-trends.ts's range-param-in-key shape with
 * use-coverage-summary.ts's single-combined-payload shape: one query, one
 * loading/error state for the whole /dashboard/analytics page (D-13's
 * "single compute pass"). `scope` is a placeholder this plan always passes
 * as `'all'`; Plan 03 wires group scoping through fully.
 *
 * Backend contract: backend/app/analytics/schemas.py::AnalyticsOverviewResponse
 * (snake_case end-to-end, CR-04 precedent — api() does no casing transform).
 *
 * `staleTime: 0` (not use-trends.ts's 60_000) — D-13 is explicitly
 * live-compute-on-read; a stale client cache could hide a just-captured
 * snapshot or a just-detected version boundary.
 *
 * Type named `AnalyticsWindow` (not the plan-prose's bare "Window") to avoid
 * shadowing the DOM lib's global `Window` interface.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type AnalyticsWindow = '7d' | '30d' | '90d' | '1y';

export type AnalyticsTrendPoint = {
  date: string;
  /** null = a real gap (reserved for Plan 03's zero-scored-group case). */
  avg_risk_exposure_score: number | null;
  risk_model_version: string | null;
};

export type VersionBoundary = {
  date: string;
  old_version: string;
  new_version: string;
};

export type AnalyticsOverviewResponse = {
  trend: AnalyticsTrendPoint[];
  boundaries: VersionBoundary[];
};

const WINDOW_DAYS: Record<AnalyticsWindow, number> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
  '1y': 365,
};

export function useAnalytics(window: AnalyticsWindow = '30d') {
  const days = WINDOW_DAYS[window];
  return useQuery({
    queryKey: queryKeys.analytics.overview({ scope: 'all', window }),
    queryFn: ({ signal }) =>
      api<AnalyticsOverviewResponse>(`/api/v1/analytics/overview?days=${days}`, { signal }),
    staleTime: 0,
    retry: 1,
    refetchOnWindowFocus: false, // chart redraw on alt-tab is jarring (mirrors use-trends.ts)
  });
}
