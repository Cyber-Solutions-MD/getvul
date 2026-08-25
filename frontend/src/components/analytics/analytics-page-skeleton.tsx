'use client';
/**
 * AnalyticsPageSkeleton — Suspense/loading fallback for /dashboard/
 * analytics (Phase 42 Plan 01). Mirrors TrendChartSkeleton's
 * controls-row-pills + chart-block shape (`components/ui/
 * trend-chart-skeleton.tsx`) — same `aria-busy="true" aria-live="polite"`
 * wrapper convention, never a separate `role="status"` (that's EmptyState's
 * contract, not a loading shimmer's).
 *
 * UI-audit fix (Phase 42 polish, finding #2): the control row now mirrors
 * the CURRENT `ScopeWindowControls` layout (Plan 03) — a scope-dropdown-
 * trigger-sized placeholder on the left plus the 5 window presets on the
 * right (was: 4 generic pills, no dropdown placeholder, stale since Plan
 * 03 added the scope dropdown + the 5th "Custom range" preset) — so the
 * real controls no longer pop/reflow the instant data arrives.
 */
export function AnalyticsPageSkeleton() {
  return (
    <div className="space-y-4 p-6" aria-busy="true" aria-live="polite" data-testid="analytics-page-skeleton">
      <div className="h-9 w-40 rounded-md bg-surface-2 animate-pulse" />
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Scope-dropdown-trigger placeholder — matches the real trigger's
            max-w-[220px] footprint at a representative collapsed width. */}
        <div className="h-7 w-[140px] rounded-md bg-surface-2 animate-pulse" />
        <div className="flex gap-1">
          <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
          <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
          <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
          <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
          {/* "Custom range" preset — wider label than the other 4. */}
          <div className="h-7 w-24 rounded-md bg-surface-2 animate-pulse" />
        </div>
      </div>
      <div className="h-[200px] rounded-md bg-surface-2 animate-pulse" />
    </div>
  );
}
