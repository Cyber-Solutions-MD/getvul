'use client';
/**
 * useAnalytics — GET /api/v1/analytics/overview (Phase 42 Plan 01, tracer
 * slice: TREND-01/03; Plan 02 extends the response type additively with
 * TREND-02's aging/burndown keys; Plan 03 wires D-02 group scope + D-03
 * custom date range fully through — no response shape change either time).
 * Merges use-trends.ts's range-param-in-key shape with
 * use-coverage-summary.ts's single-combined-payload shape: one query, one
 * loading/error state for the whole /dashboard/analytics page (D-13's
 * "single compute pass").
 *
 * Plan 03: the hook now takes a params OBJECT (not a bare window string) so
 * the page can pass scope/groupId/from/to alongside the window preset.
 * `enabled` lets the page gate the request itself while a custom range is
 * incomplete/invalid (RESEARCH Pitfall 3 — "fires no query until valid").
 * The cache key's `scope` stays a single string (`'all'` or
 * `'group:<id>'`) — Plan 01's `queryKeys.analytics.overview(opts)` shape is
 * NOT reshaped (its own "extend without a shape change" precedent);
 * `group_id` is only ever a fetch-URL concern, not a new key field.
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

export type AnalyticsWindow = '7d' | '30d' | '90d' | '1y' | 'custom';

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
  // Plan 03 (D-02/D-06) — scope echo + the group's display name, mirroring
  // backend/app/analytics/schemas.py::AnalyticsOverviewResponse. `null`
  // when scope === 'all'.
  scope: string;
  group_name: string | null;
};

// `Partial` (not a full Record) so indexing stays legal even when `window`
// is statically typed as the full AnalyticsWindow union (including
// 'custom', which never actually reaches this lookup — see the `!isCustom`
// guard below) without a narrowing cast.
const WINDOW_DAYS: Partial<Record<AnalyticsWindow, number>> = {
  '7d': 7,
  '30d': 30,
  '90d': 90,
  '1y': 365,
};

// Single source of truth for the custom-range validity rule (RESEARCH
// Pitfall 3) — `scope-window-controls.tsx` imports these SAME functions
// (rather than re-deriving the rule) so the "show the order error" render
// check and the "fire no query" enabled-gate below can never drift apart.
// ISO (YYYY-MM-DD) strings compare lexicographically identically to date
// order, so a plain string compare is correct here — no Date parsing.
export function isCustomRangeComplete(from: string, to: string): boolean {
  return !!from && !!to;
}

export function isCustomRangeValid(from: string, to: string): boolean {
  return isCustomRangeComplete(from, to) && to >= from;
}

export type UseAnalyticsParams = {
  window: AnalyticsWindow;
  /** D-02 — defaults to tenant-wide. */
  scope?: 'all' | 'group';
  /** Required (and validated by the caller) when scope === 'group'. */
  groupId?: string | null;
  /** ISO dates (YYYY-MM-DD) — only read when window === 'custom'. */
  from?: string | null;
  to?: string | null;
  /**
   * Plan 03 / RESEARCH Pitfall 3: the page gates this `false` while a
   * custom range is incomplete or invalid (to < from) so NO request is
   * ever attempted with a malformed range — "fires no query until valid."
   * Defaults to `true` (every non-custom window is always valid).
   */
  enabled?: boolean;
};

export function useAnalytics({
  window,
  scope = 'all',
  groupId = null,
  from = null,
  to = null,
  enabled = true,
}: UseAnalyticsParams) {
  const isCustom = window === 'custom';
  const isGroupScoped = scope === 'group' && !!groupId;
  const rangeValid = isCustomRangeValid(from ?? '', to ?? '');

  const params = new URLSearchParams();
  if (isGroupScoped) {
    params.set('scope', 'group');
    params.set('group_id', groupId as string);
  }
  if (isCustom && rangeValid) {
    params.set('from', from as string);
    params.set('to', to as string);
  } else if (!isCustom) {
    params.set('days', String(WINDOW_DAYS[window] ?? 30));
  }

  // Cache-key `scope` stays a single string — Plan 01's opts-object shape
  // ({scope, window, from?, to?}) is NOT reshaped; a composite `group:<id>`
  // value differentiates one group's cached series from another's.
  const cacheScope = isGroupScoped ? `group:${groupId}` : 'all';

  return useQuery({
    queryKey: queryKeys.analytics.overview({
      scope: cacheScope,
      window,
      from: from ?? undefined,
      to: to ?? undefined,
    }),
    queryFn: ({ signal }) =>
      api<AnalyticsOverviewResponse>(`/api/v1/analytics/overview?${params.toString()}`, { signal }),
    // Custom range: only fire once both dates are present AND in order.
    enabled: enabled && (!isCustom || rangeValid),
    staleTime: 0,
    retry: 1,
    refetchOnWindowFocus: false, // chart redraw on alt-tab is jarring (mirrors use-trends.ts)
  });
}
