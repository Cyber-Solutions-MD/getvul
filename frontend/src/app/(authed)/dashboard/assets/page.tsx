'use client';
/**
 * /assets — UX-04-01 list page.
 *
 * Composes:
 *   - AssetsChipBar (4 axes) — URL-synced via useUrlStateList per axis
 *   - SkeletonTable (loading) — Phase 11 D-S-*; reused verbatim (UX-04-05)
 *   - EmptyState (no results) — Phase 11 compound primitive
 *   - PartialFailureBanner (errors) — Phase 11 hybrid primitive
 *   - AssetsTable (rows) — 6 cols
 *   - Pagination — Phase 11 D-T-03 sunset-styled
 *
 * Row click → router.push(`/assets/${id}`) — drill happens on the detail page,
 * not in a panel on the list (CONTEXT.md D-D-03 — DrillPanel reuse is for
 * IN-context CVE drill on detail).
 *
 * Replaces the 386-line v1 implementation (raw fetch + freehand hex +
 * missing state primitives).
 */
import { Suspense, useCallback, useMemo, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { AssetsChipBar } from '@/components/assets/assets-chip-bar';
import { AssetsTable } from '@/components/assets/assets-table';
import { microcopy } from '@/components/assets/microcopy';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useAssets, type AssetsFilters } from '@/lib/queries/use-assets';

// XSS allow-lists mirror AssetsChipBar (T-12-05). Reflected URL values outside
// the allow-list are silently dropped by useUrlStateList on read+write.
const CATEGORIES = ['WORKSTATION', 'SERVER', 'NETWORK', 'MOBILE', 'OTHER'] as const;
const RISK_BANDS = ['critical', 'high', 'medium', 'low'] as const;
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
const OS_FAMILIES = ['linux', 'windows', 'macos', 'other'] as const;
const ORDERS = ['asc', 'desc'] as const;
type Order = (typeof ORDERS)[number];

// 6-column skeleton shape mirrors AssetsTable. Module-scope = stable reference.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'mono', width: 140 },  // hostname
  { kind: 'text', width: 160 },  // os
  { kind: 'text', width: 180 },  // owner
  { kind: 'mono', width: 40 },   // risk
  { kind: 'badge', width: 120 }, // tags
  { kind: 'badge', width: 120 }, // sources
];

function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">{microcopy.page.h1}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message.slice(0, 40) || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}

function AssetsPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  useDocumentTitle(microcopy.page.h1);

  const [category] = useUrlStateList<string>('category', CATEGORIES, []);
  const [risk_band] = useUrlStateList<string>('risk_band', RISK_BANDS, []);
  const [source] = useUrlStateList<string>('source', SOURCES, []);
  const [os_family] = useUrlStateList<string>('os_family', OS_FAMILIES, []);
  const [order] = useUrlState<Order>('order', ORDERS, 'desc');
  const search = params?.get('search') ?? '';
  const pageNum = Math.max(1, Number(params?.get('page') ?? '1') || 1);

  // useUrlStateList returns a fresh array reference each render; without
  // useMemo, every interaction would re-fetch even when the URL is unchanged.
  // Memoize so the TanStack cache key remains stable across re-renders.
  const filters: AssetsFilters = useMemo(
    () => ({
      category: category.length ? category : undefined,
      risk_band: risk_band.length ? risk_band : undefined,
      source: source.length ? source : undefined,
      os_family: os_family.length ? os_family : undefined,
      search: search || undefined,
    }),
    [category, risk_band, source, os_family, search],
  );

  const q = useAssets({ filters, page: pageNum, sort: 'risk_score', order });

  const onRowOpen = useCallback(
    (id: string) => router.push(`/assets/${id}`),
    [router],
  );

  const handlePageChange = useCallback(
    (next: number) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      if (next <= 1) sp.delete('page');
      else sp.set('page', String(next));
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), {
        scroll: false,
      });
    },
    [router, pathname, params],
  );

  const isLoading = q.isPending;
  const items = q.data?.items ?? [];
  const total = q.data?.total ?? 0;
  // Backend doesn't emit asset facets yet — placeholder. AssetsChipBar's source
  // axis renders nothing until counts arrive; other axes are static enums.
  const facets = useMemo(
    () => ({ source: undefined, category: undefined }),
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          {microcopy.page.eyebrow} · {total} {total === 1 ? 'asset' : 'assets'}
        </div>
        <h1 className="text-2xl font-semibold text-text">{microcopy.page.h1}</h1>
      </header>

      <AssetsChipBar facets={facets} />

      {q.error && (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              requestId: String((q.error as Error).message).slice(0, 40),
            },
          ]}
          onRetry={() => q.refetch()}
        />
      )}

      {isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.noResults.title}</EmptyState.Title>
          <EmptyState.Body>{microcopy.empty.noResults.body}</EmptyState.Body>
        </EmptyState>
      ) : (
        <>
          <AssetsTable rows={items} onRowOpen={onRowOpen} />
          {(q.data?.pages ?? 1) > 1 && (
            <Pagination
              page={pageNum}
              totalPages={q.data?.pages ?? 1}
              total={q.data?.total ?? 0}
              pageSize={q.data?.page_size ?? 25}
              onPageChange={handlePageChange}
            />
          )}
        </>
      )}
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">{microcopy.page.h1}</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function AssetsPage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="AssetsPage">
      <Suspense fallback={PAGE_FALLBACK}>
        <AssetsPageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
