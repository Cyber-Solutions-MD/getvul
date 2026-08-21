'use client';
/**
 * useAnalytics — GET /api/v1/analytics/overview (Phase 42 Plan 01, tracer
 * slice: TREND-01/03; Plan 02 extends the response type additively with
 * TREND-02's aging/burndown keys — no shape change, same single query).
 * Merges use-trends.ts's range-param-in-key shape with
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

// Plan 02 (TREND-02/D-08) — one SLA-tier-aligned aging bucket, stacked by
// severity. Always 3 buckets present, in this fixed order, even at zero
// (UI-SPEC E3 — "nothing overdue" is a valid state, never an error).
export type AgingBucketId = 'within_sla' | 'recently_breached' | 'long_overdue';
export type AgingBucket = {
  bucket: AgingBucketId;
  critical: number;
  high: number;
  medium: number;
  low: number;
};

// Plan 02 (TREND-02/D-09) — net backlog velocity + a projected clear-date.
// `status` carries direction; `net_per_week` is always a non-negative
// MAGNITUDE (no sign, no client-side abs() needed).
export type BurndownStatus = 'shrinking' | 'growing' | 'no_change';
export type Burndown = {
  status: BurndownStatus;
  net_per_week: number;
  open_backlog: number;
  /** null for growing/no_change (UI-SPEC: "no clear date at this rate"). */
  days_to_clear: number | null;
  /** true when days_to_clear was capped at MAX_PROJECTION_DAYS (UI-SPEC E4). */
  capped: boolean;
};

export type AnalyticsOverviewResponse = {
  trend: AnalyticsTrendPoint[];
  boundaries: VersionBoundary[];
  aging: AgingBucket[];
  aging_pct_overdue: number;
  burndown: Burndown;
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
