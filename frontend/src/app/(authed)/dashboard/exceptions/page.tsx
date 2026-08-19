'use client';
/**
 * /dashboard/exceptions — EXC-02/EXC-03 manage-only exceptions list view.
 *
 * Composition mirrors campaigns/page.tsx (Phase 38):
 *   ErrorBoundary > Suspense > ExceptionsPageInner
 *
 * State branches (mutually exclusive, WR-13):
 *   q.error                          -> PartialFailureBanner
 *   isLoading                        -> SkeletonTable
 *   never granted (q.data.length===0)-> EmptyState "No exceptions granted yet"
 *   filtered to zero                 -> EmptyState "Nothing matches this filter"
 *   else                             -> ExceptionsTable + Pagination
 *
 * Filtering (type/scope_type chips + free-text search) is CLIENT-SIDE: GET
 * /api/v1/exceptions has no server-side filter/pagination params (mirrors
 * campaigns' D-07 always-returns-the-full-tenant-list precedent; see
 * backend/app/exceptions/service.py::list_exceptions). Pagination is also
 * client-side local component state (not URL-synced) — the sitewide 25-row
 * page size, sliced over the filtered+sorted array.
 *
 * Row click never navigates — ExceptionsTable owns its own inline-accordion
 * expand state internally; this page never calls useRouter for row
 * interaction (only for the "Clear all filters" URL reset).
 */
import { Suspense, useCallback, useMemo, useState, type ReactNode } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ExceptionsChipBar } from '@/components/exceptions/exceptions-chip-bar';
import { ExceptionsTable } from '@/components/exceptions/exceptions-table';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import Pagination from '@/components/ui/Pagination';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useExceptions } from '@/lib/queries/use-exceptions';

// Mirrors ExceptionsChipBar's TYPE_ALLOW/SCOPE_ALLOW (T-39-22 allow-list
// clamp) — duplicated locally per the campaigns/page.tsx precedent (that
// page also redeclares STATUS_ALLOW rather than importing
// CAMPAIGNS_STATUS_ALLOW from its chip-bar).
const TYPE_ALLOW = ['FALSE_POSITIVE', 'ACCEPTED_RISK'] as const;
const TYPE_LABEL: Record<(typeof TYPE_ALLOW)[number], string> = {
  FALSE_POSITIVE: 'False positive',
  ACCEPTED_RISK: 'Accept risk',
};

const SCOPE_ALLOW = ['FINDING', 'ASSET', 'ASSET_GROUP'] as const;
const SCOPE_LABEL: Record<(typeof SCOPE_ALLOW)[number], string> = {
  FINDING: 'Finding',
  ASSET: 'Asset',
  ASSET_GROUP: 'Asset group',
};

// Sitewide default page size (tickets/assets/remediations Pagination usage).
const PAGE_SIZE = 25;

// 7-column skeleton shape mirrors ExceptionsTable.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'pill', width: 90 }, // type
  { kind: 'mono', width: 130 }, // cve/target
  { kind: 'text', width: 70 }, // scope
  { kind: 'text', width: 120 }, // approver
  { kind: 'mono', width: 60 }, // granted
  { kind: 'pill', width: 70 }, // expires
  { kind: 'badge', width: 34 }, // revoke
];

const CTA_PRIMARY =
  'inline-flex items-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';
const CTA_SECONDARY =
  'inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

// Generalizes the UI-SPEC's literal 2-chip "both X and Y" template (39-06
// Copywriting Contract) to 1 or 3+ active filter dimensions (type chip,
// scope chip, free-text search) — the verbatim template is preserved
// exactly for the demonstrated 2-chip case.
function joinConjunction(labels: string[]): string {
  if (labels.length === 0) return 'matching this filter';
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `both ${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(', ')}, and ${labels[labels.length - 1]}`;
}

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">Exceptions</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function ExceptionsPageInner() {
  useDocumentTitle('Exceptions');
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const [type] = useUrlStateList<string>('type', TYPE_ALLOW, []);
  const [scopeType] = useUrlStateList<string>('scope_type', SCOPE_ALLOW, []);
  const search = (params?.get('search') ?? '').trim().toLowerCase();

  const [page, setPage] = useState(1);

  const q = useExceptions();

  const filtered = useMemo(() => {
    const all = q.data ?? [];
    return all.filter((row) => {
      if (type.length > 0 && !type.includes(row.type)) return false;
      if (scopeType.length > 0 && !scopeType.includes(row.scope_type)) return false;
      if (search && !row.cve_id.toLowerCase().includes(search)) return false;
      return true;
    });
  }, [q.data, type, scopeType, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  // Derived clamp (not a stored reset) — if a filter narrows the set while
  // parked on a later page, this always renders a valid page without
  // needing an effect to rewrite `page` itself.
  const currentPage = Math.min(page, totalPages);

  const pageItems = useMemo(
    () => filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [filtered, currentPage],
  );

  const clearAllFilters = useCallback(() => {
    setPage(1);
    router.replace(pathname ?? '/dashboard/exceptions', { scroll: false });
  }, [router, pathname]);

  const isLoading = q.isPending;
  const totalUnfiltered = q.data?.length ?? 0;
  const isNeverGranted = !isLoading && !q.error && totalUnfiltered === 0;
  const isEmptyFiltered = !isLoading && !q.error && totalUnfiltered > 0 && filtered.length === 0;

  const activeChipLabels = useMemo(() => {
    const labels: string[] = [];
    if (type.length > 0) labels.push(type.map((t) => TYPE_LABEL[t as keyof typeof TYPE_LABEL] ?? t).join('/'));
    if (scopeType.length > 0) {
      labels.push(scopeType.map((s) => SCOPE_LABEL[s as keyof typeof SCOPE_LABEL] ?? s).join('/'));
    }
    if (search) labels.push(`"${search}"`);
    return labels;
  }, [type, scopeType, search]);

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          Exceptions · {filtered.length} {filtered.length === 1 ? 'exception' : 'exceptions'}
        </div>
        {/* 39-UI-SPEC.md Typography: Display role, 32px (text-3xl), 600
            weight — mirrors dashboard/hero.tsx's h2 headline treatment. */}
        <h1 className="text-3xl font-semibold text-text">Exceptions</h1>
      </header>

      <ExceptionsChipBar />

      {/* WR-13: state branches are mutually exclusive — error > loading >
          empty (never-granted) > empty (filtered-to-zero) > data. */}
      {q.error ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              // WR-10: pass full message; banner truncates visually.
              requestId: String((q.error as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => q.refetch()}
        />
      ) : isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={8} />
      ) : isNeverGranted ? (
        <EmptyState>
          <EmptyState.Title>No exceptions granted yet</EmptyState.Title>
          <EmptyState.Body>
            False-positive and accept-risk decisions show up here once an analyst grants one
            from a finding&apos;s drill panel — with justification, approver, and expiry
            tracked automatically.
          </EmptyState.Body>
          <EmptyState.Actions>
            <Link href="/dashboard/vulnerabilities" className={CTA_SECONDARY}>
              View vulnerabilities
            </Link>
          </EmptyState.Actions>
        </EmptyState>
      ) : isEmptyFiltered ? (
        <EmptyState>
          <EmptyState.Title>Nothing matches this filter</EmptyState.Title>
          <EmptyState.Body>
            No exceptions are {joinConjunction(activeChipLabels)} right now. Clear a filter or
            broaden the window.
          </EmptyState.Body>
          <EmptyState.Actions>
            <button type="button" onClick={clearAllFilters} className={CTA_PRIMARY}>
              Clear all filters
            </button>
          </EmptyState.Actions>
        </EmptyState>
      ) : (
        <>
          <ExceptionsTable rows={pageItems} />
          {totalPages > 1 && (
            <Pagination
              page={currentPage}
              totalPages={totalPages}
              total={filtered.length}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">Exceptions</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={8} />
  </div>
);

export default function ExceptionsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="ExceptionsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <ExceptionsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
