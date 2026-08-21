'use client';
/**
 * /dashboard/coverage — Phase 41 Plan 01 (COV-01) tracer slice + Plan 03
 * (COV-02) coverage strip: the per-connector coverage strip (top) plus the
 * blind-spot asset list (authoritative MDM/HR inventory that no scanner
 * has ever touched, below). Lives under `(authed)/dashboard` so the
 * existing auth guard + persistent shell apply (Pitfall 2 — never
 * `/coverage`).
 *
 * Composition mirrors exceptions/page.tsx (Phase 39) and assets/page.tsx
 * (Phase 12):
 *   ErrorBoundary > Suspense > CoveragePageInner
 *
 * State branches (mutually exclusive, WR-13 — error checked FIRST since
 * `items` defaults to `[]` on error, so item-based branches would
 * otherwise ALSO render). Plan 03 adds a second read (useCoverageSummary)
 * feeding into the SAME branch machine rather than a parallel one:
 *   error (either query)                      -> PartialFailureBanner
 *   isLoading (either query)                  -> skeleton strip + SkeletonTable
 *   !has_authoritative_inventory               -> EmptyState "No inventory
 *     source connected" (D-11 — never a misleading 0%/100%, never a
 *     total-assets fallback)
 *   has_authoritative_inventory && !has_scanner_connector -> EmptyState
 *     "No scanner connected" (UI-SPEC E4 backstop — inventory exists, but
 *     nothing scans it; distinct from the D-11 case above)
 *   total === 0 (inventory exists, zero blind spots) -> EmptyState "Every
 *     device is covered" (quiet win, no CTA)
 *   else                                       -> coverage strip + blind-spot
 *     table + Pagination (D-04 top-to-bottom "see the gap, then see the
 *     assets" order, xl gap between the two halves)
 *
 * DrillPanel + the "Route to owner" action are Plan 04/05 (COV-03)
 * concerns. Plan 05 wires both: row click opens `DrillPanel` (generalized
 * `idKey="asset"`, the tickets-page precedent — NOT `/assets`'s full-page
 * `router.push`, Pitfall 8) rendering `CoverageAssetDrillContent`; the
 * per-row action AND the drill footer's action share ONE
 * `RouteToOwnerDialog` + ONE `useRouteToOwner(assetId)` instance at this
 * page level (`routeToOwnerTarget` state below), rather than each owning an
 * independent dialog/mutation pair.
 */
import { Suspense, useCallback, useMemo, useState, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { microcopy } from '@/components/coverage/microcopy';
import { CoverageConnectorCard } from '@/components/coverage/coverage-connector-card';
import { CoverageAssetDrillContent } from '@/components/coverage/coverage-asset-drill-content';
import { RouteToOwnerDialog } from '@/components/coverage/route-to-owner-dialog';
import {
  SkeletonTable,
  EmptyState,
  PartialFailureBanner,
  type SkeletonColumn,
} from '@/components/states';
import { StatStrip } from '@/components/ui/stat-strip';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { DrillPanel } from '@/components/vulnerabilities/drill-panel';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useBlindSpotAssets, type BlindSpotAsset } from '@/lib/queries/use-blind-spot-assets';
import { useCoverageSummary } from '@/lib/queries/use-coverage-summary';
import { useRouteToOwner } from '@/lib/queries/use-route-to-owner';

// 5-column skeleton shape mirrors the blind-spot table below.
const SKELETON_COLUMNS: SkeletonColumn[] = [
  { kind: 'mono', width: 140 }, // hostname
  { kind: 'text', width: 100 }, // category
  { kind: 'text', width: 140 }, // os
  { kind: 'text', width: 70 }, // last seen
  { kind: 'badge', width: 150 }, // never-scanned badge
];

const CATEGORY_LABEL: Record<string, string> = {
  WORKSTATION: 'Workstation',
  SERVER: 'Server',
  NETWORK: 'Network',
  MOBILE: 'Mobile',
  OTHER: 'Other',
};

function categoryLabel(category: string | null): string {
  if (!category) return '—';
  return CATEGORY_LABEL[category] ?? category;
}

// Day-count copy, no date library (mirrors exceptions-table.tsx's
// `grantedAgo` — copy-voice.md's "Nd ago" quantity format).
function formatLastSeen(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const days = Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
  return days <= 0 ? 'Today' : `${days}d ago`;
}

// CTA_SECONDARY mirrors exceptions/page.tsx's constant verbatim — this
// reconciliation-first page has no page-level primary CTA (41-UI-SPEC.md
// Design System / Color: "No pink accent usage on this page"), so every
// action here uses the bordered secondary chrome, never `bg-gradient-sunset`.
const CTA_SECONDARY =
  'inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet';

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

// Secondary-weight row action — NEVER bg-gradient-sunset (UI-SPEC Color:
// this page has no page-level primary CTA). Mirrors CTA_SECONDARY's chrome
// at a row-scale (smaller padding).
const ROW_ACTION_BTN_CLASS =
  'inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-2 px-2.5 py-1 text-xs font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:pointer-events-none disabled:opacity-50';

function BlindSpotTable({
  rows,
  canRouteToOwner,
  onRowClick,
  onRouteToOwner,
}: {
  rows: BlindSpotAsset[];
  canRouteToOwner: boolean;
  onRowClick: (asset: BlindSpotAsset) => void;
  onRouteToOwner: (asset: BlindSpotAsset) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
            <th scope="col" className="px-3 py-2" data-col="hostname">
              {microcopy.columns.hostname}
            </th>
            <th scope="col" className="px-3 py-2" data-col="category">
              {microcopy.columns.category}
            </th>
            <th scope="col" className="px-3 py-2" data-col="os">
              {microcopy.columns.os}
            </th>
            <th scope="col" className="px-3 py-2" data-col="last-seen">
              {microcopy.columns.lastSeen}
            </th>
            <th scope="col" className="px-3 py-2" data-col="never-scanned">
              {microcopy.columns.neverScanned}
            </th>
            <th scope="col" className="px-3 py-2" data-col="actions">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              tabIndex={0}
              onClick={() => onRowClick(r)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onRowClick(r);
                }
              }}
              className="cursor-pointer border-b border-border-subtle hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
            >
              <td className="px-3 py-3 font-mono text-text">{r.hostname}</td>
              <td className="px-3 py-3 text-text-muted">{categoryLabel(r.category)}</td>
              <td className="px-3 py-3 text-text-muted">{r.os ?? '—'}</td>
              <td className="px-3 py-3 font-mono text-text-muted">
                {formatLastSeen(r.last_seen_at)}
              </td>
              <td className="px-3 py-3">
                {/* Amber, never red — a blind spot is a coverage gap, not a
                    severity finding (41-UI-SPEC.md Color). Exact chrome
                    mirrors exceptions-table.tsx's ACCEPTED_RISK pill. */}
                <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 text-xs text-[var(--color-amber-on-soft)]">
                  {microcopy.badge.noScannerCoverage}
                </span>
              </td>
              <td className="px-3 py-3">
                <button
                  type="button"
                  onClick={(e) => {
                    // Row itself opens the drill on click — the row action
                    // must not also trigger that (D-04's two independent
                    // entry points into the same dialog).
                    e.stopPropagation();
                    onRouteToOwner(r);
                  }}
                  disabled={!canRouteToOwner}
                  title={canRouteToOwner ? undefined : microcopy.routeToOwner.disabledHint}
                  className={ROW_ACTION_BTN_CLASS}
                >
                  {microcopy.routeToOwner.rowAction}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Skeleton strip cards (state-patterns.md — subtle animate-pulse block,
// mirrors dashboard/hero.tsx's isPending shape) shown while useCoverageSummary
// resolves. 3 is an arbitrary placeholder count (StatStrip's real column
// ladder takes over once actual cards render); no data shape is implied.
function CoverageStripSkeleton() {
  return (
    <StatStrip aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-[168px] rounded-lg border border-border-subtle bg-surface-2 p-6 animate-pulse"
        />
      ))}
    </StatStrip>
  );
}

function CoveragePageInner() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  useDocumentTitle(microcopy.page.h1);

  // D-08 asymmetric RBAC — analyst+ can invoke "Route to owner"; a viewer
  // sees it disabled, never a raw 403 to react to (the backend
  // `require_analyst` gate is defense-in-depth only). Mirrors
  // connectors/page.tsx:98-99's role-check convention.
  const { user } = useAuth();
  const canRouteToOwner =
    user?.role === 'OWNER' || user?.role === 'ADMIN' || user?.role === 'ANALYST';

  const pageNum = Math.max(1, Number(params?.get('page') ?? '1') || 1);
  const q = useBlindSpotAssets({ page: pageNum });
  const summaryQ = useCoverageSummary();

  const isLoading = q.isPending || summaryQ.isPending;
  const queryError = q.error ?? summaryQ.error;
  const items = useMemo(() => q.data?.items ?? [], [q.data]);
  const total = q.data?.total ?? 0;
  const hasAuthoritativeInventory = q.data?.has_authoritative_inventory ?? false;
  const totalAuthoritativeAssets = q.data?.total_authoritative_assets ?? 0;
  const hasScannerConnector = summaryQ.data?.has_scanner_connector ?? false;
  const coverageCards = summaryQ.data?.cards ?? [];

  // UI-SPEC E4 backstop: inventory exists but zero scanner connectors —
  // distinct from the D-11 !hasAuthoritativeInventory case below.
  const isScannerAbsent = hasAuthoritativeInventory && !hasScannerConnector;
  const isPopulated = hasAuthoritativeInventory && hasScannerConnector && total > 0;

  // Subtitle only makes sense once we know the real, populated-with-blind-
  // spots state (41-UI-SPEC.md Copywriting Contract: "populated, has blind
  // spots") — the loading/error/empty branches below carry their own copy.
  const showSubtitle = !queryError && !isLoading && isPopulated;

  const handlePageChange = (next: number) => {
    const sp = new URLSearchParams(params?.toString() ?? '');
    if (next <= 1) sp.delete('page');
    else sp.set('page', String(next));
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
  };

  // Asset id from URL for the drill panel (D-D-02, idKey="asset" — the
  // tickets-page precedent, NOT `/assets`'s full-page navigation, Pitfall 8).
  const assetIdFromUrl = params?.get('asset') ?? null;
  const selectedAsset: BlindSpotAsset | undefined = useMemo(
    () => items.find((a) => a.id === assetIdFromUrl) ?? undefined,
    [items, assetIdFromUrl],
  );

  // Row click → set ?asset=<id>&open=drill (D-D-02).
  const onRowClick = useCallback(
    (asset: BlindSpotAsset) => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      sp.set('asset', asset.id);
      sp.set('open', 'drill');
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
    },
    [router, pathname, params],
  );

  // "Route to owner" — a single shared dialog + mutation instance for BOTH
  // the row action and the drill footer action (not one pair each).
  const [routeToOwnerTarget, setRouteToOwnerTarget] = useState<BlindSpotAsset | null>(null);
  const routeToOwnerMutation = useRouteToOwner(routeToOwnerTarget?.id ?? '');
  const handleRouteToOwnerConfirm = useCallback(() => {
    routeToOwnerMutation.mutate(undefined, {
      onSuccess: () => setRouteToOwnerTarget(null),
    });
  }, [routeToOwnerMutation]);

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        {/* 41-UI-SPEC.md Typography: Heading role, 32px (text-3xl), 600
            weight — mirrors exceptions/page.tsx's h1 treatment. */}
        <h1 className="text-3xl font-semibold text-text">{microcopy.page.h1}</h1>
        {showSubtitle && (
          <p className="text-sm text-text-muted">{microcopy.page.subtitle(total)}</p>
        )}
      </header>

      {/* WR-13: state branches are mutually exclusive — error > loading >
          the three empty variants (D-11 no-inventory, E4 scanner-absent,
          quiet-win all-covered — branched on has_authoritative_inventory/
          has_scanner_connector/total, never on items.length alone) >
          populated. */}
      {queryError ? (
        <PartialFailureBanner
          errors={[
            {
              code: 'http_error',
              // WR-10: pass full message; banner truncates visually.
              requestId: String((queryError as Error).message) || 'unknown',
            },
          ]}
          onRetry={() => {
            q.refetch();
            summaryQ.refetch();
          }}
        />
      ) : isLoading ? (
        <div className="space-y-8">
          <CoverageStripSkeleton />
          <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
        </div>
      ) : !hasAuthoritativeInventory ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.noInventory.title}</EmptyState.Title>
          <EmptyState.Body>{microcopy.empty.noInventory.body}</EmptyState.Body>
          <EmptyState.Actions>
            <Link href="/dashboard/connectors" className={CTA_SECONDARY}>
              {microcopy.empty.noInventory.action}
            </Link>
          </EmptyState.Actions>
        </EmptyState>
      ) : isScannerAbsent ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.scannerAbsent.title}</EmptyState.Title>
          <EmptyState.Body>{microcopy.empty.scannerAbsent.body}</EmptyState.Body>
          <EmptyState.Actions>
            <Link href="/dashboard/connectors" className={CTA_SECONDARY}>
              {microcopy.empty.scannerAbsent.action}
            </Link>
          </EmptyState.Actions>
        </EmptyState>
      ) : total === 0 ? (
        <EmptyState>
          <EmptyState.Title>{microcopy.empty.allCovered.title}</EmptyState.Title>
          <EmptyState.Body>{microcopy.empty.allCovered.body(totalAuthoritativeAssets)}</EmptyState.Body>
        </EmptyState>
      ) : (
        <div className="space-y-8">
          {/* D-04: coverage strip (the "see the gap %" half) renders above
              the blind-spot list (the "see the assets behind it" half),
              xl gap (32px) between them. */}
          <StatStrip>
            {coverageCards.map((card) => (
              <CoverageConnectorCard key={card.connector_type} card={card} />
            ))}
          </StatStrip>
          <BlindSpotTable
            rows={items}
            canRouteToOwner={canRouteToOwner}
            onRowClick={onRowClick}
            onRouteToOwner={setRouteToOwnerTarget}
          />
          {(q.data?.pages ?? 1) > 1 && (
            <Pagination
              page={pageNum}
              totalPages={q.data?.pages ?? 1}
              total={q.data?.total ?? 0}
              pageSize={q.data?.page_size ?? 50}
              onPageChange={handlePageChange}
            />
          )}
        </div>
      )}

      {/* Drill panel (D-D-02, idKey="asset" — tickets-page precedent,
          Pitfall 8: never the /assets full-page navigation). */}
      <DrillPanel
        idKey="asset"
        id={assetIdFromUrl}
        ariaLabel="Device detail"
        renderContent={({ onClose }) => (
          <CoverageAssetDrillContent
            asset={selectedAsset}
            canRouteToOwner={canRouteToOwner}
            onRouteToOwner={() => {
              if (selectedAsset) setRouteToOwnerTarget(selectedAsset);
            }}
            onClose={onClose}
          />
        )}
      />

      {/* Single shared confirm dialog for BOTH the row action and the
          drill footer action (D-07/D-09). No per-row owner signal exists
          today (see microcopy.ts's doc comment) — every call site renders
          the unresolvable (D-09) branch. */}
      <RouteToOwnerDialog
        open={routeToOwnerTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRouteToOwnerTarget(null);
        }}
        hostname={routeToOwnerTarget?.hostname ?? ''}
        ownerResolved={false}
        onConfirm={handleRouteToOwnerConfirm}
        isPending={routeToOwnerMutation.isPending}
      />
    </div>
  );
}

const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">{microcopy.page.h1}</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function CoveragePage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="CoveragePage">
      <Suspense fallback={PAGE_FALLBACK}>
        <CoveragePageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
