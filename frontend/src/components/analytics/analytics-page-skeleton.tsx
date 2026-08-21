'use client';
/**
 * AnalyticsPageSkeleton — Suspense/loading fallback for /dashboard/
 * analytics (Phase 42 Plan 01). Mirrors TrendChartSkeleton's
 * controls-row-pills + chart-block shape (`components/ui/
 * trend-chart-skeleton.tsx`) — same `aria-busy="true" aria-live="polite"`
 * wrapper convention, never a separate `role="status"` (that's EmptyState's
 * contract, not a loading shimmer's). Extended with a 4th pill so the
 * control-row shimmer already matches this page's 4-preset window toggle
 * (Coverage's analog only needed 3 for the vuln dashboard's Range control).
 */
export function AnalyticsPageSkeleton() {
  return (
    <div className="space-y-4 p-6" aria-busy="true" aria-live="polite">
      <div className="h-9 w-40 rounded-md bg-surface-2 animate-pulse" />
      <div className="flex justify-end gap-1">
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
      </div>
      <div className="h-[200px] rounded-md bg-surface-2 animate-pulse" />
    </div>
  );
}
