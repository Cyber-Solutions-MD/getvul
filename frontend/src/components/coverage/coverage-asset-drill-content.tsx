'use client';
/**
 * CoverageAssetDrillContent — D-D-02 slot content for the shared DrillPanel
 * chrome, paired with `idKey="asset"` (Phase 41 Plan 05, COV-03). Mirrors
 * `ticket-drill-content.tsx`'s exact 3-region shape (header / body sections
 * / sticky footer) and its `!data` loading branch — see
 * 41-PATTERNS.md's analog for this file.
 *
 * Presentational only — no data fetching. The caller (coverage page) passes
 * the blind-spot asset summary from the list row and owns the "Route to
 * owner" mutation + confirm dialog (single shared dialog/mutation instance
 * at the page level, per the plan — this component only triggers it via
 * `onRouteToOwner`).
 */
import { X } from 'lucide-react';
import type { BlindSpotAsset } from '@/lib/queries/use-blind-spot-assets';
import { microcopy } from './microcopy';

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

// Day-count copy, no date library — mirrors page.tsx's own formatLastSeen /
// exceptions-table.tsx's `grantedAgo` (copy-voice.md's "Nd ago" format).
function formatLastSeen(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const days = Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
  return days <= 0 ? 'Today' : `${days}d ago`;
}

const H4_CLASS = 'mb-2 text-xs uppercase tracking-wide text-text-muted';

// Secondary-weight footer button — NEVER bg-gradient-sunset (UI-SPEC Color:
// this page has no page-level primary CTA). Violet focus ring is the
// reserved accent for this exact action.
const ROUTE_TO_OWNER_BTN_CLASS =
  'inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:pointer-events-none disabled:opacity-50';

export type CoverageAssetDrillContentProps = {
  /** Pre-fetched summary from the list row — presentational only, no fetch. */
  asset?: BlindSpotAsset;
  /** D-08 asymmetric RBAC — analyst+ can invoke "Route to owner"; a viewer sees it disabled. */
  canRouteToOwner: boolean;
  /** Opens the caller's shared RouteToOwnerDialog for this asset. */
  onRouteToOwner: () => void;
  onClose: () => void;
};

export function CoverageAssetDrillContent({
  asset,
  canRouteToOwner,
  onRouteToOwner,
  onClose,
}: CoverageAssetDrillContentProps) {
  if (!asset) {
    return (
      <div aria-busy="true" className="p-6 text-text-muted text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ── */}
      <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
        <div className="min-w-0">
          <span className="font-mono text-sm font-semibold text-text">{asset.hostname}</span>
          <p className="mt-0.5 truncate text-sm text-text-muted">{categoryLabel(asset.category)}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="ml-2 shrink-0 rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* ── Body ── */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        <section aria-labelledby="cadrill-coverage-h">
          <h4 id="cadrill-coverage-h" className={H4_CLASS}>
            Coverage
          </h4>
          {/* Amber, never red — a blind spot is a coverage gap, not a
              severity finding (41-UI-SPEC.md Color). */}
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 text-xs text-[var(--color-amber-on-soft)]">
            {microcopy.badge.noScannerCoverage}
          </span>
        </section>

        <section aria-labelledby="cadrill-source-h">
          <h4 id="cadrill-source-h" className={H4_CLASS}>
            In inventory via
          </h4>
          <p className="text-sm text-text">
            {asset.seen_by_sources.length > 0 ? asset.seen_by_sources.join(', ') : '—'}
          </p>
        </section>

        <section aria-labelledby="cadrill-lastseen-h">
          <h4 id="cadrill-lastseen-h" className={H4_CLASS}>
            Last seen
          </h4>
          <p className="font-mono text-sm text-text-muted">{formatLastSeen(asset.last_seen_at)}</p>
        </section>
      </div>

      {/* ── Footer (sticky bottom) ── */}
      <div className="border-t border-border-subtle p-4">
        <button
          type="button"
          onClick={onRouteToOwner}
          disabled={!canRouteToOwner}
          title={canRouteToOwner ? undefined : microcopy.routeToOwner.disabledHint}
          className={ROUTE_TO_OWNER_BTN_CLASS}
        >
          {microcopy.routeToOwner.rowAction}
        </button>
      </div>
    </div>
  );
}
