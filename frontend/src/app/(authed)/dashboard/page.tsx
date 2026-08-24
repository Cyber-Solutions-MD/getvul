'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { Hero } from '@/components/dashboard/hero';
import { StatStripWired } from '@/components/dashboard/stat-strip-wired';
import { TrendSection } from '@/components/dashboard/trend-section';
import { Top5Card } from '@/components/dashboard/top5-card';
import { ActivityRail } from '@/components/dashboard/activity-rail';
import { OnboardingPanel } from '@/components/dashboard/onboarding-panel';
import { LensSwitcher } from '@/components/dashboard/lens-switcher';
import { LeadershipHero } from '@/components/dashboard/leadership-hero';
import { MttrByTierTile } from '@/components/dashboard/mttr-by-tier-tile';
import { SlaComplianceTile } from '@/components/dashboard/sla-compliance-tile';
import { FrameworkPostureStrip } from '@/components/dashboard/framework-posture-strip';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { PartialFailureBanner } from '@/components/states';
import { ApiError } from '@/lib/api';
import { useStats } from '@/lib/queries/use-stats';
import { useLens, type Lens } from '@/hooks/use-lens';
import { useAnalytics, type AnalyticsTrendPoint, type VersionBoundary } from '@/lib/queries/use-analytics';
import { useMttrByTier } from '@/lib/queries/use-mttr-by-tier';
import { useSlaMetrics, type SlaMetrics } from '@/lib/queries/use-sla-metrics';
import { useComplianceOverview } from '@/lib/queries/use-compliance';
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
//
// Phase 43 Plan 04 (RPT-02, D-05/D-06/D-07): the onboarding early-return
// below stays the OUTERMOST check, byte-for-byte unchanged — the lens
// switcher only renders once onboarding clears. `analyst`/`it-ops` render
// the EXACT pre-existing block below (D-07 "byte-for-byte"); `leadership`/
// `compliance` render a new trend-and-posture widget composition. Lens
// selection (useLens) is presentation-only and never gated on/derives from
// `User.role` (T-43-13).

// Deferred (next/dynamic) so recharts is never pulled into the default
// (analyst) lens's bundle — only mounted when a user actually switches to
// leadership/compliance. Mirrors trend-section.tsx's own dynamic-import
// convention for the exact same reason.
const RiskTrendChart = dynamic<{ trend: AnalyticsTrendPoint[]; boundaries: VersionBoundary[] }>(
  () => import('@/components/analytics/risk-trend-chart').then((m) => m.RiskTrendChart),
  { ssr: false, loading: () => <TrendChartSkeleton /> }
);

function SectionErrorFallback(section: string) {
  function SectionFallback(err: Error, reset: () => void): ReactNode {
    return (
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
  return SectionFallback;
}

// E8 (★ `covered`): with <2 scored data points, the risk-trend hero renders
// a neutral centered "not enough history" note rather than a misleading
// line — applies to both the leadership (full-width) and compliance
// (compact) trend widgets.
function RiskTrendWidget({ compact = false }: { compact?: boolean }) {
  const q = useAnalytics({ window: '90d' });

  if (q.error) {
    return (
      <PartialFailureBanner
        errors={[{ code: 'http_error', requestId: String((q.error as Error).message) || 'unknown' }]}
        onRetry={() => q.refetch()}
        source="Risk trend"
      />
    );
  }
  if (q.isPending) {
    return <TrendChartSkeleton />;
  }

  const trend = q.data?.trend ?? [];
  const boundaries = q.data?.boundaries ?? [];
  const scoredPointCount = trend.filter((p) => p.avg_risk_exposure_score !== null).length;

  if (scoredPointCount < 2) {
    return (
      <div
        role="status"
        data-testid="risk-trend-no-history"
        className="flex h-[140px] items-center justify-center rounded-lg border border-border-subtle bg-surface-2 p-6 text-center text-sm text-text-muted"
      >
        Not enough history to plot a trend yet — check back after a few more days.
      </div>
    );
  }

  return (
    <div className={compact ? 'max-w-lg' : undefined}>
      <RiskTrendChart trend={trend} boundaries={boundaries} />
    </div>
  );
}

// WR-01 (43-REVIEW.md): shared ApiError → PartialFailureBanner `errors` row
// shape, mirroring finding-drill-content.tsx's existing conversion so the
// banner always gets a real HTTP code + request ID instead of "unknown".
function toErrorRow(error: unknown): { code: number | string; requestId: string; message?: string } {
  return error instanceof ApiError
    ? { code: error.code, requestId: error.requestId, message: error.message }
    : { code: 'ERR', requestId: 'unknown', message: error instanceof Error ? error.message : undefined };
}

const ZERO_SLA_METRICS: SlaMetrics = {
  sla_config: {},
  open_with_sla: 0,
  breached: 0,
  at_risk: 0,
  within_sla: 0,
  compliance_pct: 0,
  remediated_within_sla: 0,
  remediated_total: 0,
  breach_by_severity: {},
  avg_days_remaining: null,
};

function LeadershipMttrTile() {
  const q = useMttrByTier();
  if (q.error) {
    // Admin-gated route (unchanged, out of this plan's scope): a non-admin
    // viewer's 403 here is an existing, intentional RBAC-floor decision —
    // keep treating it the same as an honestly-empty tenant ("Not yet
    // measured"), NOT as a failure banner. Any OTHER error (500, network)
    // is a distinct, genuine failure mode and deserves its own signal +
    // retry, matching RiskTrendWidget on the same lens (WR-01).
    if (q.error instanceof ApiError && q.error.code === 403) {
      return <MttrByTierTile rows={[]} />;
    }
    return (
      <PartialFailureBanner errors={[toErrorRow(q.error)]} onRetry={() => q.refetch()} source="MTTR by tier" />
    );
  }
  if (q.isPending || !q.data) {
    return <MttrByTierTile rows={[]} />;
  }
  return <MttrByTierTile rows={q.data} />;
}

function LeadershipSlaTile({ compact = false }: { compact?: boolean }) {
  const q = useSlaMetrics();
  if (q.error) {
    // require_viewer-gated (unlike MTTR's require_admin) — a 403 here would
    // itself indicate a real bug, so every error is treated as a genuine
    // failure (WR-01), never collapsed into the honest-empty rendering.
    return (
      <PartialFailureBanner errors={[toErrorRow(q.error)]} onRetry={() => q.refetch()} source="SLA compliance" />
    );
  }
  if (q.isPending || !q.data) {
    return <SlaComplianceTile compact={compact} metrics={ZERO_SLA_METRICS} />;
  }
  return <SlaComplianceTile compact={compact} metrics={q.data} />;
}

function LeadershipPostureStrip({ variant = 'compact' }: { variant?: 'compact' | 'hero' }) {
  const q = useComplianceOverview();
  if (q.error) {
    // require_viewer-gated — same rationale as LeadershipSlaTile above.
    return (
      <PartialFailureBanner errors={[toErrorRow(q.error)]} onRetry={() => q.refetch()} source="Framework posture" />
    );
  }
  if (q.isPending || !q.data) {
    return <FrameworkPostureStrip controls={[]} variant={variant} />;
  }
  return <FrameworkPostureStrip controls={q.data.controls} variant={variant} />;
}

// Leadership lens (43-UI-SPEC.md items 1-5) — trend-and-posture widgets
// only, NO triage widgets (no hero action list, no top5-card, no
// activity-rail).
function LeadershipLens() {
  return (
    <div className="flex flex-col gap-6">
      <ErrorBoundary fallback={SectionErrorFallback('Leadership hero')}>
        <LeadershipHero />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('Risk trend')}>
        <RiskTrendWidget />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('MTTR by tier')}>
        <LeadershipMttrTile />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('SLA compliance')}>
        <LeadershipSlaTile />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('Framework posture')}>
        <LeadershipPostureStrip variant="compact" />
      </ErrorBoundary>
    </div>
  );
}

// Compliance lens (43-UI-SPEC.md items 1-4) — posture-first: hero-sized
// framework-posture strip, then compact SLA/trend, then a link to the full
// compliance page.
function ComplianceLens() {
  return (
    <div className="flex flex-col gap-6">
      <ErrorBoundary fallback={SectionErrorFallback('Framework posture')}>
        <LeadershipPostureStrip variant="hero" />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('SLA compliance')}>
        <LeadershipSlaTile compact />
      </ErrorBoundary>
      <ErrorBoundary fallback={SectionErrorFallback('Risk trend')}>
        <RiskTrendWidget compact />
      </ErrorBoundary>
      <Link
        href="/dashboard/compliance"
        className="inline-flex w-fit items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      >
        View full compliance page
      </Link>
    </div>
  );
}

function DashboardHeader({ lens, onLensChange }: { lens: Lens; onLensChange: (next: Lens) => void }) {
  return (
    <div className="mb-4 flex items-center justify-end">
      <LensSwitcher lens={lens} onLensChange={onLensChange} />
    </div>
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

      {/* useLens wraps useSearchParams (via useUrlState) — Suspense required
          by Next 15 for CSR-bailout during static generation, mirroring
          TrendSection's own wrapping comment below. */}
      <Suspense fallback={null}>
        <LensAwareBody />
      </Suspense>
    </>
  );
}

function LensAwareBody() {
  const [lens, setLens] = useLens();

  if (lens === 'leadership') {
    return (
      <>
        <DashboardHeader lens={lens} onLensChange={setLens} />
        <LeadershipLens />
      </>
    );
  }

  if (lens === 'compliance') {
    return (
      <>
        <DashboardHeader lens={lens} onLensChange={setLens} />
        <ComplianceLens />
      </>
    );
  }

  // analyst / it-ops — the exact pre-existing widget composition, unchanged
  // (D-07 "byte-for-byte").
  return (
    <>
      <DashboardHeader lens={lens} onLensChange={setLens} />
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <ErrorBoundary fallback={SectionErrorFallback('Hero')}>
            <Hero />
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Stats')}>
            <StatStripWired />
          </ErrorBoundary>
          <ErrorBoundary fallback={SectionErrorFallback('Trend')}>
            {/* Suspense wraps useSearchParams (via useUrlState) — required
                by Next 15 for CSR-bailout during static generation. */}
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
