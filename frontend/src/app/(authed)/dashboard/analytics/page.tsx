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
 * Plan 03 adds the scope dropdown (D-02) and the custom date range (D-03)
 * onto this same page shell. `scope`/`customFrom`/`customTo` are owned
 * HERE as plain component state (NOT threaded through `useUrlState` —
 * RESEARCH Pitfall 3: that hook's enum-clamp shape doesn't fit free-form
 * dates/UUIDs); only the 5-way window PRESET stays URL-state-driven,
 * unchanged from Plan 01/02.
 */
import { Suspense, useState, type ReactNode } from 'react';
import { PartialFailureBanner, EmptyState } from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useUrlState } from '@/hooks/use-url-state';
import {
  useAnalytics,
  isCustomRangeComplete,
  isCustomRangeValid,
  type AnalyticsWindow,
  type Burndown,
} from '@/lib/queries/use-analytics';
import { AnalyticsPageSkeleton } from '@/components/analytics/analytics-page-skeleton';
import { RiskTrendChart } from '@/components/analytics/risk-trend-chart';
import { BacklogAgingChart } from '@/components/analytics/backlog-aging-chart';
import { BurndownTile } from '@/components/analytics/burndown-tile';
import { ScopeWindowControls, type ScopeValue } from '@/components/analytics/scope-window-controls';
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

const ALLOWED_WINDOWS = ['7d', '30d', '90d', '1y', 'custom'] as const;

// D-04 (42-CONTEXT.md): below this many SCORED points, render the guided
// EmptyState instead of a misleading line. Locked at 1 (not the plan
// text's illustrative "e.g. 2") to honor 42-UI-SPEC.md's E2 zero-one-many
// LOCKED user decision — "exactly 1 data point... renders as a single dot
// marker" — which requires a lone point to reach the chart, not the empty
// branch. Gated on the count of non-null (scored) points, never on a falsy
// avg_risk_exposure_score (0 is a legitimate healthy-tenant reading, not
// "empty" — 42-RESEARCH.md Common Pitfalls: "gating the D-04 empty state
// on a score value"). A null score IS "no reading" (a gap), so a series that
// is all-null — e.g. an empty-membership group (G-42-4) — is empty here.
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
  // D-02/D-03 (Plan 03): plain component state, not URL state (Pitfall 3 —
  // a group UUID / free-form date isn't a fixed enum useUrlState can clamp
  // against). Defaults: tenant-wide scope, empty (unpicked) custom range.
  const [scope, setScope] = useState<ScopeValue>({ type: 'all' });
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const isCustomWindow = windowPreset === 'custom';
  // UI-audit fix (Phase 42 polish, finding #1): while the custom window is
  // active but the range is incomplete/invalid, use-analytics.ts sets
  // `enabled: false` — TanStack Query v5 never transitions `isPending` away
  // from true for a query that has never fetched, so this branch must be
  // checked BEFORE q.isPending or the page renders a perpetual loading
  // skeleton stacked under the "End date must be after start date." error.
  // isCustomRangeValid already implies isCustomRangeComplete (see
  // use-analytics.ts), but both are named here to match the branch's own
  // "complete AND valid" framing rather than relying on that implication.
  const isAwaitingValidCustomRange =
    isCustomWindow && !(isCustomRangeComplete(customFrom, customTo) && isCustomRangeValid(customFrom, customTo));
  const q = useAnalytics({
    window: windowPreset,
    scope: scope.type,
    groupId: scope.type === 'group' ? scope.groupId : null,
    from: isCustomWindow ? customFrom : null,
    to: isCustomWindow ? customTo : null,
  });

  const trend = q.data?.trend ?? [];
  const boundaries = q.data?.boundaries ?? [];
  const aging = q.data?.aging ?? [];
  const agingPctOverdue = q.data?.aging_pct_overdue ?? 0;
  const burndown = q.data?.burndown ?? EMPTY_BURNDOWN;
  // G-42-4: gate the D-04 empty state on the count of SCORED points, not raw
  // row count. A null avg_risk_exposure_score is a GAP, not a reading (D-06 —
  // a scored-0 day is a legitimate healthy reading and must NOT be treated as
  // empty; only null counts as "no data"). An empty-membership group returns
  // one null-score row per snapshot day, so a raw-length gate rendered a
  // misleading all-null line instead of the guided EmptyState.
  const scoredPointCount = trend.filter((p) => p.avg_risk_exposure_score !== null).length;
  const isBelowMinHistory = scoredPointCount < MIN_HISTORY_POINTS;
  const scopeLabel = scope.type === 'group' ? scope.groupName : microcopy.scope.allTenantLabel;

  return (
    <div className="p-6">
      {/* 42-UI-SPEC.md Spacing Scale `2xl` (48px, mb-12): the page header
          (title + scope/window controls) reads as ONE block, separated from
          the first chart/state section by 3x the internal xl (32px)
          section rhythm below — UI-audit fix #4b (was a flat space-y-4). */}
      <div className="space-y-4 mb-12">
        <header className="space-y-1">
          {/* 42-UI-SPEC.md Typography: Heading role, 32px (text-3xl), 600
              weight — mirrors coverage/page.tsx's h1 treatment. */}
          <h1 className="text-3xl font-semibold text-text">{microcopy.page.h1}</h1>
        </header>

        <ScopeWindowControls
          scope={scope}
          onScopeChange={setScope}
          window={windowPreset}
          onWindowChange={setWindowPreset}
          customFrom={customFrom}
          customTo={customTo}
          onCustomFromChange={setCustomFrom}
          onCustomToChange={setCustomTo}
        />
      </div>

      {/* WR-13: state branches are mutually exclusive — error >
          awaiting-valid-range > loading > below-min-history empty >
          populated. The awaiting-valid-range branch (UI-audit fix #1) must
          come before q.isPending: while a custom range is incomplete/
          invalid, useAnalytics disables the query, and TanStack Query v5
          never moves `isPending` off `true` for a query that has never
          fetched — without this branch the page would show a permanent
          loading skeleton stacked under the inline order-error text. */}
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
      ) : isAwaitingValidCustomRange ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.customRange.awaitingRangeTitle}</EmptyState.Title>
          <EmptyState.Body>{microcopy.customRange.awaitingRangeBody}</EmptyState.Body>
        </EmptyState>
      ) : q.isPending ? (
        <AnalyticsPageSkeleton />
      ) : isBelowMinHistory ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.insufficientHistory.title}</EmptyState.Title>
          <EmptyState.Body>{microcopy.empty.insufficientHistory.body(scopeLabel)}</EmptyState.Body>
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
