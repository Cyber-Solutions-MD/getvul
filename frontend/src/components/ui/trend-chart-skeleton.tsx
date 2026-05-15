'use client';

// D-C-03 loading state — shown by next/dynamic during recharts chunk fetch.
// Plan 05's dashboard/trend-section.tsx wraps the import:
//   next/dynamic(() => import('@/components/ui/trend-chart').then(m => m.TrendChart),
//                 { ssr: false, loading: () => <TrendChartSkeleton /> })

export function TrendChartSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      <div className="flex justify-end gap-1">
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
      </div>
      <div className="h-[200px] rounded-md bg-surface-2 animate-pulse" />
    </div>
  );
}
