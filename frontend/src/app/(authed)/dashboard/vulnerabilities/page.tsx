'use client';
// Phase 11-06 — composes Wave 1 hooks + Wave 2 components into the redesigned
// /dashboard/vulnerabilities surface (UX-03-01..06 + UX-S-01..05). Glue + state
// branching only. Phase 10 deep-link contract honored: ?cve=…&open=drill.
import { Suspense, useCallback, useMemo, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Lightbulb } from 'lucide-react';
import { ChipBar } from '@/components/vulnerabilities/chip-bar';
import { ViewToggle } from '@/components/vulnerabilities/view-toggle';
import { VulnTable, type VulnTableRow, type VulnTableSortField } from '@/components/vulnerabilities/vuln-table';
import { DrillPanel } from '@/components/vulnerabilities/drill-panel';
import { DrillPanelMobile } from '@/components/vulnerabilities/drill-panel-mobile';
import { microcopy } from '@/components/vulnerabilities/microcopy';
import { SkeletonTable, EmptyState, PartialFailureBanner, PerSourceStatusStrip, type SkeletonColumn } from '@/components/states';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useVulnerabilities, type VulnerabilitiesFilters } from '@/lib/queries/use-vulnerabilities';
import { useConnectors } from '@/lib/queries/use-connectors';
import { queryKeys } from '@/lib/queries/keys';

// XSS allow-lists mirror chip-bar.tsx (T-11-17 / WR-04). Reflected URL values
// outside the allow-list are silently dropped by useUrlStateList on read+write.
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const;
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
const STATUSES = ['OPEN', 'IN_PROGRESS', 'RESOLVED', 'SUPPRESSED'] as const;
const SORT_FIELDS = ['severity', 'cve_id', 'cvss_v3_score', 'sla_due_at', ''] as const;
const ORDERS = ['asc', 'desc'] as const;
const GROUPS = ['cve', 'host'] as const;
type Severity = (typeof SEVERITIES)[number];
type Source = (typeof SOURCES)[number];
type Status = (typeof STATUSES)[number];
type SortField = (typeof SORT_FIELDS)[number];
type Order = (typeof ORDERS)[number];
type Group = (typeof GROUPS)[number];

// 7-column skeleton shape mirrors VulnTable. Module-scope = stable reference.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'pill', width: 90 }, { kind: 'mono', width: 130 }, { kind: 'text', width: 220 },
  { kind: 'mono', width: 120 }, { kind: 'mono', width: 40 }, { kind: 'badge', width: 80 },
  { kind: 'mono', width: 60 },
];

// Banner subscribes to both list + connectors — either can degrade independently.
const WATCH_KEYS = [queryKeys.vulnerabilities.all, queryKeys.connectors.all] as const;

const CTA_PRIMARY = 'rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';
const CTA_SECONDARY = 'rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

// ErrorBoundary fallback for the whole page. Synthesizes a `crash` code so the
// banner's HTTP-code shape (Phase 10 D-E-02) renders without raw stack leakage.
function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4">
      <h1 className="sr-only">{microcopy.page.h1}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message.slice(0, 40) || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function VulnerabilitiesPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // Multi-value filters. Setters surfaced so EmptyState 3-tier CTAs can call them.
  const [severity, setSeverity, toggleSeverity] = useUrlStateList<Severity>('severity', SEVERITIES, []);
  const [source, setSource] = useUrlStateList<Source>('source', SOURCES, []);
  const [status] = useUrlStateList<Status>('status', STATUSES, []);
  const [group] = useUrlState<Group>('group', GROUPS, 'cve');
  const [sort, setSort] = useUrlState<SortField>('sort', SORT_FIELDS, '');
  const [order, setOrder] = useUrlState<Order>('order', ORDERS, 'desc');

  // Search is free-text — chip-bar owns the debounce. Page reads the flushed value.
  const search = params?.get('search') ?? '';
  const pageNum = Math.max(1, Number(params?.get('page') ?? '1') || 1);
  // Phase 10 deep-link contract (top5-card.tsx:82): `?cve=<id>&open=drill`.
  const cveDeepLink = params?.get('cve') ?? null;
  const drillOpen = params?.get('open') === 'drill';

  // Empty arrays → undefined so backend QS stays clean (Wave 1 contract).
  const filters: VulnerabilitiesFilters = useMemo(() => ({
    severity: severity.length > 0 ? severity : undefined,
    source: source.length > 0 ? source : undefined,
    status: status.length > 0 ? status : undefined,
    search: search || undefined,
  }), [severity, source, status, search]);

  const q = useVulnerabilities({ filters, group, page: pageNum, sort, order });
  const connectorsQ = useConnectors();

  // D-V-04 — failed connectors drive both stale-row tinting AND strip visibility.
  const failedSources = useMemo<string[]>(
    () => (connectorsQ.data ?? []).filter((c) => c.last_sync_status === 'failed').map((c) => c.connector_type),
    [connectorsQ.data],
  );

  // D-Tab-01 — tab title reflects filtered count.
  useDocumentTitle(q.data?.total ? microcopy.tabTitle.withCount(q.data.total) : microcopy.tabTitle.base);

  const handleSortChange = useCallback(
    (field: VulnTableSortField, nextOrder: 'asc' | 'desc' | null) => {
      setSort((field ?? '') as SortField);
      setOrder((nextOrder ?? 'desc') as Order);
    },
    [setSort, setOrder],
  );

  // Row open writes ?cve= + ?open=drill atomically — deep-link round-trips.
  // router.replace (not push) so back-button escapes panel cleanly.
  const handleRowOpen = useCallback((idOrCve: string) => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.set('cve', idOrCve);
    sp.set('open', 'drill');
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
  }, [router, pathname, params]);

  const handlePageChange = useCallback((next: number) => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    if (next <= 1) sp.delete('page'); else sp.set('page', String(next));
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
  }, [router, pathname, params]);

  const hasActiveFilters = severity.length > 0 || source.length > 0 || status.length > 0 || search.length > 0;

  // Normalize facets per-key (Rule 1 defensive) — backend may return `{}` in
  // the empty-filtered branch; ChipBar's index access (facets.severity[…]) NPEs without this.
  const rawFacets = q.data?.facets;
  const facets = useMemo(() => ({
    severity: rawFacets?.severity ?? {},
    source: rawFacets?.source ?? {},
    status: rawFacets?.status ?? {},
  }), [rawFacets]);

  const isEmptyFiltered = !!q.data && q.data.items.length === 0 && hasActiveFilters;

  return (
    <>
      <h1 className="sr-only">{microcopy.page.h1}</h1>
      <div className="space-y-4">
        {/* UX-S-03 — partial-failure banner; renders null when no errors. */}
        <PartialFailureBanner watchKeys={WATCH_KEYS} onRetry={() => q.refetch()} />

        {/* UX-S-03 — per-source health row when ANY connector is failed. */}
        {failedSources.length > 0 && q.data?.facets && (
          <PerSourceStatusStrip facets={facets.source} />
        )}

        {/* ChipBar hidden in empty-filtered branch — the EmptyState's 3 CTAs are
            the unambiguous chrome there, and this avoids a "Clear all" button
            name collision with EmptyState's "Clear all filters" CTA. */}
        {!isEmptyFiltered && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ChipBar facets={facets} />
            <ViewToggle />
          </div>
        )}

        {q.isPending ? (
          <SkeletonTable rows={8} columns={SKELETON_COLUMNS} />
        ) : q.error ? (
          /* UX-S-04 — total failure: EmptyState shell + retry CTA. */
          <EmptyState>
            <EmptyState.Title>{microcopy.totalFailure.title}</EmptyState.Title>
            <EmptyState.Body>{microcopy.totalFailure.body}</EmptyState.Body>
            <EmptyState.Actions>
              <button type="button" onClick={() => q.refetch()} className={CTA_PRIMARY}>
                {microcopy.totalFailure.retry}
              </button>
            </EmptyState.Actions>
          </EmptyState>
        ) : isEmptyFiltered ? (
          /* UX-S-02 — empty-filtered: 3-tier CTAs + violet lightbulb suggestion. */
          <EmptyState>
            <EmptyState.Title>{microcopy.empty.title}</EmptyState.Title>
            <EmptyState.Body>{microcopy.empty.body}</EmptyState.Body>
            <EmptyState.Actions>
              <button type="button" onClick={() => { setSeverity([]); setSource([]); }} className={CTA_PRIMARY}>
                {microcopy.empty.clearAll}
              </button>
              <button type="button" onClick={() => toggleSeverity('medium')} className={CTA_SECONDARY}>
                {microcopy.empty.broadenSeverity}
              </button>
              <button type="button" onClick={() => setSource([])} className={CTA_SECONDARY}>
                {microcopy.empty.searchAll}
              </button>
            </EmptyState.Actions>
            <EmptyState.Suggestion>
              <Lightbulb size={16} aria-hidden="true" className="mt-0.5 shrink-0" />
              <span>{microcopy.empty.suggestion}</span>
            </EmptyState.Suggestion>
          </EmptyState>
        ) : q.data && q.data.items.length > 0 ? (
          <>
            <VulnTable
              rows={q.data.items as VulnTableRow[]}
              sort={(sort || null) as VulnTableSortField}
              order={(order || null) as 'asc' | 'desc' | null}
              onSort={handleSortChange}
              onRowOpen={handleRowOpen}
              failedSources={failedSources}
            />
            {q.data.total_pages > 1 && (
              <Pagination
                page={q.data.page}
                totalPages={q.data.total_pages}
                total={q.data.total}
                pageSize={q.data.page_size}
                onPageChange={handlePageChange}
              />
            )}
          </>
        ) : null}
      </div>

      {/* Drill panels share the URL contract (?cve=…&open=drill). Only one
          mounts at a time: desktop covers ≥900px, mobile gates on <900px via
          useMediaQuery internally. cveDeepLink + drillOpen passed inline so the
          deep-link wiring stays greppable in this file. */}
      <DrillPanel cveId={drillOpen ? cveDeepLink : null} />
      <DrillPanelMobile cveId={drillOpen ? cveDeepLink : null} />
    </>
  );
}

// Suspense bailout for useSearchParams during prerender (Next 15) — fallback
// renders the same SkeletonTable shape the loading branch uses post-hydration.
const PAGE_FALLBACK = (
  <div className="space-y-4">
    <h1 className="sr-only">{microcopy.page.h1}</h1>
    <SkeletonTable rows={8} columns={SKELETON_COLUMNS} />
  </div>
);

export default function VulnerabilitiesPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="VulnerabilitiesPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <VulnerabilitiesPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
