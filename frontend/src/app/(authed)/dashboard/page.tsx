'use client';

import { Hero } from '@/components/dashboard/hero';
import { StatStripWired } from '@/components/dashboard/stat-strip-wired';
import { TrendSection } from '@/components/dashboard/trend-section';
import { Top5Card } from '@/components/dashboard/top5-card';
import { ActivityRail } from '@/components/dashboard/activity-rail';
import { OnboardingPanel } from '@/components/dashboard/onboarding-panel';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useStats } from '@/lib/queries/use-stats';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { microcopy } from '@/components/dashboard/microcopy';
import { Suspense, type ReactNode } from 'react';
import { TrendChartSkeleton } from '@/components/ui/trend-chart-skeleton';

// D-R-01: client component (own data-fetching, document.title side-effect).
// D-E-01: per-section <ErrorBoundary> — a crash in Hero MUST NOT unmount
// the rest. D-Ax-01: sr-only h1 sits above the section h2s.
// D-Tab-01: tab title flips between '(N) Dashboard · GetVul' and base.
// D-M-01: 2-column grid at ≥1280px (`xl:grid-cols-[1fr_340px]`); rail stacks
// below at <1280px.

function SectionErrorFallback(section: string) {
  return (err: Error, reset: () => void): ReactNode => (
    <section
      role="alert"
      className="rounded-lg border border-danger bg-danger-soft p-5"
    >
      <p className="text-sm">
        {microcopy.error.inline(section, 'crash', err.message.slice(0, 40))}
      </p>
      <button
        onClick={reset}
        className="mt-2 font-mono text-xs underline"
        type="button"
      >
        Retry now
      </button>
    </section>
  );
}

export default function DashboardPage() {
  const stats = useStats();
  const critical = (stats.data?.dashboard_tiles?.critical_open?.value as number) ?? 0;
  useDocumentTitle(
    critical > 0 ? microcopy.tabTitle.withCount(critical) : microcopy.tabTitle.base
  );

  const onboarding = stats.data?.onboarding_state;
  if (!stats.isPending && (onboarding === 'no_scanners' || onboarding === 'no_data_yet')) {
    return (
      <>
        <h1 className="sr-only">Dashboard</h1>
        <OnboardingPanel state={onboarding} lastSyncAt={null} onRefresh={() => stats.refetch()} />
      </>
    );
  }

  return (
    <>
      <h1 className="sr-only">Dashboard</h1>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <ErrorBoundary fallback={SectionErrorFallback('Hero')}>
            <Hero />
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Stats')}>
            <StatStripWired />
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Trend')}>
            {/* Suspense wraps useSearchParams (via useUrlState) — required by Next 15
                for CSR-bailout during static generation. */}
            <Suspense fallback={<TrendChartSkeleton />}>
              <TrendSection />
            </Suspense>
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Top 5')}>
            <Top5Card />
          </ErrorBoundary>
        </div>
        <ErrorBoundary fallback={SectionErrorFallback('Activity')}>
          <ActivityRail />
        </ErrorBoundary>
      </div>
    </>
  );
}
