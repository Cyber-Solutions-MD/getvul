'use client';
/**
 * /dashboard/analytics — Phase 42 Plan 01 (TREND-01/03 tracer slice): the
 * tenant risk-exposure trend line over a selectable window, with mandatory
 * loading/empty/error states and version-boundary-aware segmentation.
 * Plan 02 (TREND-02) adds the backlog aging distribution + burndown rate
 * sections onto this SAME shell, additively. Composition mirrors
 * `dashboard/coverage/page.tsx`:
 *   ErrorBoundary > Suspense > AnalyticsPageInner
 *
 * This page has ONE combined query (D-13/A2 — single compute pass), so
 * there is exactly one isLoading/error branch pair, simpler than Coverage's
 * two-independent-query chain. Plan 02's aging/burndown sections
 * deliberately share this SAME loading/error/empty branch chain (no
 * independent fetch, no separate empty condition) — the plan's own Task 3
 * checkpoint verifies "loading (skeleton) and error (PartialFailureBanner)
 * still cover all three sections as one compute pass."
 *
 * Plan 03 adds the scope dropdown and the custom date range onto this same
 * page shell.
 */
import { Suspense, type ReactNode } from 'react';
import { PartialFailureBanner, EmptyState } from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useUrlState } from '@/hooks/use-url-state';
import { useAnalytics, type AnalyticsWindow, type Burndown } from '@/lib/queries/use-analytics';
import { AnalyticsPageSkeleton } from '@/components/analytics/analytics-page-skeleton';
import { RiskTrendChart } from '@/components/analytics/risk-trend-chart';
import { BacklogAgingChart } from '@/components/analytics/backlog-aging-chart';
import { BurndownTile } from '@/components/analytics/burndown-tile';
import { ScopeWindowControls } from '@/components/analytics/scope-window-controls';
import { microcopy } from '@/components/analytics/microcopy';

// Fallback shape for the populated branch's destructure below — the
// branch is only reachable once q.data is defined (not pending, no
// error), but TS can't narrow that across the JSX conditional, so this
// mirrors trend/boundaries' own `?? []` guard for the burndown object.
const EMPTY_BURNDOWN: Burndown = {
  status: 'no_change',
  net_per_week: 0,
  open_backlog: 0,
  days_to_clear: null,
  capped: false,
};

const ALLOWED_WINDOWS = ['7d', '30d', '90d', '1y'] as const;

// D-04 (42-CONTEXT.md): below this many snapshot points, render the guided
// EmptyState instead of a misleading line. Locked at 1 (not the plan
// text's illustrative "e.g. 2") to honor 42-UI-SPEC.md's E2 zero-one-many
// LOCKED user decision — "exactly 1 data point... renders as a single dot
// marker" — which requires a lone point to reach the chart, not the empty
// branch. Gated on the snapshot ROW COUNT, never on a falsy
// avg_risk_exposure_score (0 is a legitimate healthy-tenant reading, not
// "empty" — 42-RESEARCH.md Common Pitfalls: "gating the D-04 empty state
// on a score value").
const MIN_HISTORY_POINTS = 1;

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">{microcopy.page.h1}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function AnalyticsPageInner() {
  useDocumentTitle(microcopy.page.h1);
  // Named windowPreset/setWindowPreset (not "window") to avoid shadowing
  // the global browser `window` object within this component's scope.
  const [windowPreset, setWindowPreset] = useUrlState<AnalyticsWindow>('window', ALLOWED_WINDOWS, '30d');
  const q = useAnalytics(windowPreset);

  const trend = q.data?.trend ?? [];
  const boundaries = q.data?.boundaries ?? [];
  const aging = q.data?.aging ?? [];
  const agingPctOverdue = q.data?.aging_pct_overdue ?? 0;
  const burndown = q.data?.burndown ?? EMPTY_BURNDOWN;
  const isBelowMinHistory = trend.length < MIN_HISTORY_POINTS;

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        {/* 42-UI-SPEC.md Typography: Heading role, 32px (text-3xl), 600
            weight — mirrors coverage/page.tsx's h1 treatment. */}
        <h1 className="text-3xl font-semibold text-text">{microcopy.page.h1}</h1>
      </header>

      <ScopeWindowControls value={windowPreset} onChange={setWindowPreset} />

      {/* WR-13: state branches are mutually exclusive — error > loading >
          below-min-history empty > populated. */}
      {q.error ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              requestId: String((q.error as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => q.refetch()}
        />
      ) : q.isPending ? (
        <AnalyticsPageSkeleton />
      ) : isBelowMinHistory ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.insufficientHistory.title}</EmptyState.Title>
          <EmptyState.Body>
            {microcopy.empty.insufficientHistory.body(microcopy.scope.allTenantLabel)}
          </EmptyState.Body>
        </EmptyState>
      ) : (
        // xl (32px) gap between the trend/aging/burndown sections, per
        // 42-UI-SPEC.md's visual hierarchy (trend line -> aging -> burndown,
        // top to bottom, same rhythm as Phase 41's strip-to-list gap).
        <div className="space-y-8">
          <section aria-labelledby="risk-trend-h" className="space-y-3">
            <h2 id="risk-trend-h" className="sr-only">
              {microcopy.trend.h2}
            </h2>
            <RiskTrendChart trend={trend} boundaries={boundaries} />
          </section>
          <section aria-labelledby="aging-h" className="space-y-3">
            <h2 id="aging-h" className="sr-only">
              {microcopy.aging.h2}
            </h2>
            <BacklogAgingChart data={aging} pctOverdue={agingPctOverdue} />
          </section>
          <section aria-labelledby="burndown-h" className="space-y-3">
            <h2 id="burndown-h" className="sr-only">
              {microcopy.burndown.h2}
            </h2>
            <BurndownTile
              status={burndown.status}
              netPerWeek={burndown.net_per_week}
              daysToClear={burndown.days_to_clear}
              capped={burndown.capped}
            />
          </section>
        </div>
      )}
    </div>
  );
}

const PAGE_FALLBACK = <AnalyticsPageSkeleton />;

export default function AnalyticsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="AnalyticsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <AnalyticsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
