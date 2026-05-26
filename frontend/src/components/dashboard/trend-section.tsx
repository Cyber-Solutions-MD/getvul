'use client';
import dynamic from 'next/dynamic';
import type { TrendChartProps, Range } from '@/components/ui/trend-chart';
import { TrendChartSkeleton } from '@/components/ui/trend-chart-skeleton';
import { PartialFailureBanner } from '@/components/states';
import { useUrlState } from '@/hooks/use-url-state';
import { useTrends } from '@/lib/queries/use-trends';
import { microcopy } from './microcopy';

// Phase 11 D-S-06 retrofit: error → <PartialFailureBanner>.
// Loading state stays inline because the shape isn't table-shaped — see
// 11-RESEARCH.md §Phase 10 Retrofit Audit (planner discretion preserved).
// Pattern 9 + D-C-03 + D-D-04: dynamic-import wrapper around TrendChart so
// recharts only loads when /dashboard mounts this section. Plan 04's
// TrendChart primitive intentionally does NOT self-wrap with next/dynamic
// so it stays unit-testable.

const TrendChart = dynamic<TrendChartProps>(
  () => import('@/components/ui/trend-chart').then((m) => m.TrendChart),
  { ssr: false, loading: () => <TrendChartSkeleton /> }
);

const ALLOWED_RANGES = ['7d', '30d', '90d'] as const;

export function TrendSection() {
  const [range, setRange] = useUrlState<Range>('range', ALLOWED_RANGES, '30d');
  const q = useTrends(range);

  if (q.isPending) {
    return (
      <section aria-labelledby="trend-h">
        <h2 id="trend-h" className="sr-only">{microcopy.trend.h2}</h2>
        <TrendChartSkeleton />
      </section>
    );
  }

  if (q.error) {
    const code  = (q.error as { code?: number | string } | null)?.code ?? 'unknown';
    const reqId = (q.error as { requestId?: string } | null)?.requestId ?? 'unknown';
    return (
      <section aria-labelledby="trend-h">
        <h2 id="trend-h" className="sr-only">{microcopy.trend.h2}</h2>
        <PartialFailureBanner
          errors={[{ code, requestId: reqId, message: undefined }]}
          onRetry={() => q.refetch()}
          source="Trend"
        />
      </section>
    );
  }

  // Reshape backend's date-keyed object → ordered TrendDatum[] ascending by date.
  const data = Object.entries(q.data?.severity_trends ?? {})
    .map(([date, v]) => ({ date, ...v }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return (
    <section
      aria-labelledby="trend-h"
      className="rounded-lg border border-border-subtle bg-surface p-5"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 id="trend-h" className="text-lg font-semibold text-text">
          {microcopy.trend.h2}
        </h2>
      </div>
      <TrendChart data={data} range={range} onRangeChange={setRange} />
    </section>
  );
}
