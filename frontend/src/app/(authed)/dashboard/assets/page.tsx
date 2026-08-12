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
// Phase 35 SRC-03/06: reconciled to the real 6-value VulnSource enum,
// partitioned from the non-scanner enrichment facet (mirrors
// AssetsChipBar's SCANNER_SOURCES/ENRICHMENT_SOURCES split).
const SCANNER_SOURCES = ['CROWDSTRIKE', 'NESSUS', 'DEFENDER', 'WIZ', 'QUALYS', 'RAPID7'] as const;
const ENRICHMENT_SOURCES = ['JAMF', 'HUMAANS', 'INTUNE'] as const;
const SOURCE_MODES = ['or', 'and'] as const;
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
  // WR-10: pass the full err.message — PartialFailureBanner truncates
  // visually with ellipsis. Slicing here silently drops request IDs / JSON
  // payloads past char 40 and loses analyst traceability.
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

function AssetsPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  useDocumentTitle(microcopy.page.h1);

  const [category] = useUrlStateList<string>('category', CATEGORIES, []);
  const [risk_band] = useUrlStateList<string>('risk_band', RISK_BANDS, []);
  // Phase 35 SRC-02/03/04/06 — scanner/enrichment partition + OR/AND toggle.
  // URL keys align with AssetsChipBar's axis keys (`?scanner=`,
  // `?enrichment_source=`, `?source_mode=`) so the chip UI and the fetch
  // read/write the same params.
  const [scanner] = useUrlStateList<string>('scanner', SCANNER_SOURCES, []);
  const [enrichmentSource] = useUrlStateList<string>('enrichment_source', ENRICHMENT_SOURCES, []);
  const [sourceMode] = useUrlState<(typeof SOURCE_MODES)[number]>('source_mode', SOURCE_MODES, 'or');
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
      scanner: scanner.length ? scanner : undefined,
      source_mode: sourceMode,
      enrichment_source: enrichmentSource.length ? enrichmentSource : undefined,
      os_family: os_family.length ? os_family : undefined,
      search: search || undefined,
    }),
    [category, risk_band, scanner, sourceMode, enrichmentSource, os_family, search],
  );

  const q = useAssets({ filters, page: pageNum, sort: 'risk_score', order });

  const onRowOpen = useCallback(
    (id: string) => router.push(`/dashboard/assets/${id}`),
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
  // Backend doesn't emit asset facets yet — placeholder. AssetsChipBar's
  // scanner/enrichment_source axes render nothing until counts arrive
  // (derivedFromCounts); other axes are static enums.
  const facets = useMemo(
    () => ({ scanner: undefined, enrichment_source: undefined, category: undefined }),
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

      {/* WR-13: state branches are mutually exclusive. Without this guard,
          q.error AND items.length === 0 both rendered (because items defaults
          to [] on error) → analyst saw "Something failed, retry" plus
          "No assets match these filters" stacked, which is contradictory. */}
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
