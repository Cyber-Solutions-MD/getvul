'use client';
/**
 * /dashboard/compliance — Phase 43 Plan 01 (RPT-03 tracer slice): per-
 * framework control-status cards (SOC 2 / ISO 27001 / PCI DSS / NIST CSF)
 * evidenced by the tenant's own posture metrics (D-08/D-09/D-12/D-13).
 * Lives under `(authed)/dashboard` so the existing auth guard + persistent
 * shell apply (Coverage/Analytics precedent).
 *
 * Composition mirrors dashboard/analytics/page.tsx:
 *   ErrorBoundary > Suspense > CompliancePageInner
 *
 * State branches (mutually exclusive, WR-13 order — error checked FIRST):
 *   error (either query)                       -> PartialFailureBanner
 *   isLoading (either query)                    -> skeleton control cards
 *   overview has zero controls OR every control
 *     is not_measured                           -> two-branch EmptyState,
 *     branch selected from useCoverageSummary()'s has_scanner_connector
 *     signal (43-RESEARCH.md Pattern 3 — reuse the existing "has this
 *     tenant even started scanning" source of truth, never re-derive it)
 *   else                                         -> framework chip bar +
 *     control-card grid, grouped by framework, 2-col desktop / 1-col
 *     mobile (43-UI-SPEC.md Layout)
 *
 * The framework chip bar is a single-select ("All" is a real default
 * state, not "nothing selected") — the shared, generic `ChipBar` primitive
 * is multi-select (useUrlStateList) and doesn't fit that shape, so this
 * page renders its own small single-select control using the identical
 * active/inactive chip chrome (visual-language.md `.chip`/`.chip.active`,
 * `border-pink bg-pink-soft text-[var(--color-pink-on-soft)]` — the same
 * classes Pagination.tsx's active page number already uses).
 */
import { Suspense, useMemo, type ReactNode } from 'react';
import Link from 'next/link';
import { PartialFailureBanner, EmptyState } from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { ControlCard } from '@/components/compliance/control-card';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useUrlState } from '@/hooks/use-url-state';
import { useComplianceOverview, type ControlStatus } from '@/lib/queries/use-compliance';
import { useCoverageSummary } from '@/lib/queries/use-coverage-summary';
import { cn } from '@/lib/utils';

const PAGE_TITLE = 'Compliance';

const FRAMEWORK_FILTERS = ['all', 'soc2', 'iso27001', 'pci_dss', 'nist_csf'] as const;
type FrameworkFilter = (typeof FRAMEWORK_FILTERS)[number];

const FRAMEWORK_ORDER = ['soc2', 'iso27001', 'pci_dss', 'nist_csf'] as const;

const FRAMEWORK_LABEL: Record<string, string> = {
  all: 'All',
  soc2: 'SOC 2',
  iso27001: 'ISO 27001',
  pci_dss: 'PCI DSS',
  nist_csf: 'NIST CSF',
};

// Mirrors coverage/page.tsx's CTA_SECONDARY constant verbatim — every
// empty-state action on this page is bordered secondary chrome, never
// bg-gradient-sunset (this page has no page-level primary CTA).
const CTA_SECONDARY =
  'inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">{PAGE_TITLE}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

// Shimmer recipe mirrors components/states/skeleton-table.tsx's real
// Tailwind implementation of the state-patterns.md `.skeleton`/`.skel-pill`
// shimmer (motion-safe:animate-shimmer + bg-[length:200%_100%]).
const SKELETON_BAR = 'inline-block rounded bg-gradient-to-r from-surface-2 via-border to-surface-2 bg-[length:200%_100%] motion-safe:animate-shimmer';
const SKELETON_PILL = 'inline-block rounded-full border border-border-subtle bg-gradient-to-r from-pink-soft via-violet-soft to-pink-soft bg-[length:200%_100%] motion-safe:animate-shimmer';

function ControlCardSkeleton() {
  return (
    <div data-skeleton-card="" className="rounded-lg border border-border-subtle bg-surface-2 p-6">
      <div className="flex items-center justify-between gap-3">
        <span className={cn(SKELETON_BAR, 'h-4 w-40')} />
        <span data-skeleton-pill="" className={cn(SKELETON_PILL, 'h-5 w-20')} />
      </div>
      <span className={cn(SKELETON_BAR, 'mt-3 block h-4 w-56')} />
      <span className={cn(SKELETON_BAR, 'mt-2 block h-3 w-72')} />
    </div>
  );
}

function CompliancePageSkeleton() {
  return (
    <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading compliance posture">
      <h1 className="sr-only">{PAGE_TITLE}</h1>
      <span className={cn(SKELETON_BAR, 'h-8 w-48')} />
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <ControlCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

function FrameworkChipBar({
  value,
  onChange,
}: {
  value: FrameworkFilter;
  onChange: (next: FrameworkFilter) => void;
}) {
  return (
    <div role="group" aria-label="Filter by framework" className="flex flex-wrap items-center gap-2">
      {FRAMEWORK_FILTERS.map((f) => {
        const active = value === f;
        return (
          <button
            key={f}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(f)}
            className={cn(
              'inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
              active
                ? 'border-pink bg-pink-soft text-[var(--color-pink-on-soft)]'
                : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
            )}
          >
            {FRAMEWORK_LABEL[f]}
          </button>
        );
      })}
    </div>
  );
}

function CompliancePageInner() {
  useDocumentTitle(PAGE_TITLE);
  const [frameworkFilter, setFrameworkFilter] = useUrlState<FrameworkFilter>(
    'framework',
    FRAMEWORK_FILTERS,
    'all',
  );

  const complianceQ = useComplianceOverview();
  const coverageSummaryQ = useCoverageSummary();

  const isLoading = complianceQ.isPending || coverageSummaryQ.isPending;
  const queryError = complianceQ.error ?? coverageSummaryQ.error;
  const controls = complianceQ.data?.controls ?? [];
  const hasScannerConnector = coverageSummaryQ.data?.has_scanner_connector ?? false;

  // The empty condition itself never needs a backend schema change (D-11
  // precedent) — "no measurable posture yet" is entirely derivable from
  // the controls array already returned; useCoverageSummary only picks
  // WHICH cause-specific empty-state branch to show.
  //
  // `has_active_scanning` is excluded from this check: it evidences off a
  // plain boolean (has_scanner_connector) that is ALWAYS defined (true or
  // false, never null) — a fresh tenant's "no scanner" answer is a real,
  // honest "fail," not an absent-denominator "not_measured" (unlike every
  // percentage-based metric, which has a genuine zero-denominator case).
  // Counting it here would make the empty branch unreachable: even a
  // brand-new tenant always has exactly one non-not_measured control.
  const measurableControls = controls.filter((c) => c.metric_key !== 'has_active_scanning');
  const isEmpty = controls.length === 0 || measurableControls.every((c) => c.status === 'not_measured');

  const groupedControls = useMemo(() => {
    const groups = new Map<string, ControlStatus[]>();
    for (const c of complianceQ.data?.controls ?? []) {
      if (frameworkFilter !== 'all' && c.framework !== frameworkFilter) continue;
      const existing = groups.get(c.framework);
      if (existing) existing.push(c);
      else groups.set(c.framework, [c]);
    }
    return groups;
    // complianceQ.data is a stable TanStack Query cache reference (unlike
    // the `controls` local, which is a fresh `?? []` array on every render
    // when data is undefined) -- depending on it directly avoids an
    // exhaustive-deps warning without changing behavior.
  }, [complianceQ.data, frameworkFilter]);

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        {/* 43-UI-SPEC.md Typography: Heading role, 32px (text-3xl), 600
            weight — mirrors coverage/analytics page h1 treatment. */}
        <h1 className="text-3xl font-semibold text-text">{PAGE_TITLE}</h1>
      </header>

      {queryError ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              requestId: String((queryError as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => {
            complianceQ.refetch();
            coverageSummaryQ.refetch();
          }}
        />
      ) : isLoading ? (
        <CompliancePageSkeleton />
      ) : isEmpty ? (
        !hasScannerConnector ? (
          <EmptyState>
            <EmptyState.Title>Not enough posture data yet</EmptyState.Title>
            <EmptyState.Body>
              Framework controls are evidenced by your SLA compliance and coverage metrics — connect a
              scanner to start measuring posture.
            </EmptyState.Body>
            <EmptyState.Actions>
              <Link href="/dashboard/connectors" className={CTA_SECONDARY}>
                Connect a scanner
              </Link>
            </EmptyState.Actions>
          </EmptyState>
        ) : (
          <EmptyState>
            <EmptyState.Title>Not enough posture data yet</EmptyState.Title>
            <EmptyState.Body>
              Controls are evidenced by SLA compliance — configure a risk-tier SLA policy to start
              measuring posture.
            </EmptyState.Body>
            <EmptyState.Actions>
              <Link href="/dashboard/settings?category=sla" className={CTA_SECONDARY}>
                Configure SLA policy
              </Link>
            </EmptyState.Actions>
          </EmptyState>
        )
      ) : (
        <div className="space-y-8">
          <FrameworkChipBar value={frameworkFilter} onChange={setFrameworkFilter} />

          {FRAMEWORK_ORDER.filter((fw) => groupedControls.has(fw)).map((fw) => (
            <section key={fw} aria-labelledby={`framework-${fw}-h`} className="space-y-3">
              <h2 id={`framework-${fw}-h`} className="text-sm font-semibold uppercase tracking-wide text-text-muted">
                {FRAMEWORK_LABEL[fw]}
              </h2>
              {/* Overflow: grid reflows to 1-col on mobile; long control
                  name/evidencing text wraps freely and the card grows to
                  fit (43-UI-SPEC.md E2/E3 long-text) — never clipped. */}
              <div className="grid gap-4 md:grid-cols-2">
                {(groupedControls.get(fw) ?? []).map((c) => (
                  <ControlCard key={`${c.framework}-${c.control_id}`} control={c} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

const PAGE_FALLBACK = <CompliancePageSkeleton />;

export default function CompliancePage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="CompliancePage">
      <Suspense fallback={PAGE_FALLBACK}>
        <CompliancePageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
