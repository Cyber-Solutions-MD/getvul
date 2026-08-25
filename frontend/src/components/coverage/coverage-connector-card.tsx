'use client';
/**
 * CoverageConnectorCard — one enabled scanner connector's coverage stat
 * (Phase 41 Plan 03, COV-02). Composes ConnectorMark + a display label +
 * SyncStatusPill, exactly like connector-card.tsx's header row — no new
 * primitive invented (must_haves prohibition).
 *
 * % headline (D-05): 40px Display, JetBrains Mono, tabular-nums, colored by
 * the existing SLA 3-tier family (never a new palette):
 *   >= 90%  -> text-success (matches .sla-pill.ok)
 *   50-89%  -> text-warning (matches .sla-pill.soon)
 *   <  50%  -> text-danger  (matches .sla-pill.overdue)
 *   null    -> em-dash, text-faint (D-11 — never 0%, the denominator is zero)
 *
 * Stale badge (D-06): amber "stale · {N}d" pill — reuses the identical
 * amber chrome already established by page.tsx's "No scanner coverage" row
 * badge (border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]).
 * Never red — a stale sync is "hasn't reported recently," a distinct
 * signal from SyncStatusPill's red "failed" state; both can render
 * side-by-side on the same card.
 */
import { ConnectorMark } from '@/components/connectors/connector-mark';
import { SyncStatusPill } from '@/components/connectors/sync-status-pill';
import type { ConnectorProvider } from '@/components/connectors/types';
import { cn } from '@/lib/utils';
import type { CoverageConnectorCard as CoverageConnectorCardData } from '@/lib/queries/use-coverage-summary';

// Literal display-label lookup for the 6 real SCANNER_SOURCES values
// (Pitfall 6 — never special-case vendor names beyond this fixed set).
// Falls through to the raw connector_type string for any unrecognized
// value rather than crashing (defense-in-depth, mirrors connector-mark.tsx's
// undefined-fallback convention).
const CONNECTOR_DISPLAY_LABEL: Record<string, string> = {
  CROWDSTRIKE: 'CrowdStrike',
  NESSUS: 'Nessus',
  DEFENDER: 'Defender',
  WIZ: 'Wiz',
  QUALYS: 'Qualys',
  RAPID7: 'Rapid7',
};

function connectorDisplayLabel(connectorType: string): string {
  return CONNECTOR_DISPLAY_LABEL[connectorType] ?? connectorType;
}

// 3-tier coverage-% color (UI-SPEC Color — reuses the existing SLA tier
// family verbatim, no new palette).
function coveragePctColorClass(pct: number): string {
  if (pct >= 90) return 'text-success';
  if (pct >= 50) return 'text-warning';
  return 'text-danger';
}

export type CoverageConnectorCardProps = {
  card: CoverageConnectorCardData;
  className?: string;
};

export function CoverageConnectorCard({ card, className }: CoverageConnectorCardProps) {
  const provider = card.connector_type.toLowerCase() as ConnectorProvider;
  const label = connectorDisplayLabel(card.connector_type);
  const hasCoverage = card.coverage_pct !== null;

  return (
    <div
      data-coverage-card
      data-connector-type={card.connector_type}
      className="rounded-lg border border-border-subtle bg-surface-2 p-6"
    >
      {/* Header row: mark + display label + sync status pill */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <ConnectorMark provider={provider} className="shrink-0" />
          <span className="truncate text-sm font-semibold text-text">{label}</span>
        </div>
        <SyncStatusPill status={card.last_sync_status} className="shrink-0" />
      </div>

      {/* Coverage % headline — Display size, mono tabular-nums, 3-tier color. */}
      <div className="mt-4 flex items-baseline gap-2">
        <span
          data-coverage-pct
          className={cn(
            'font-mono text-4xl font-semibold leading-tight tabular-nums',
            hasCoverage ? coveragePctColorClass(card.coverage_pct as number) : 'text-text-faint',
          )}
        >
          {hasCoverage ? card.coverage_pct : '—'}
          {hasCoverage && '%'}
        </span>
        <span className="text-xs text-text-muted">covered</span>
      </div>

      {/* Stale badge (D-06) — amber, never red; rendered alongside the
          SyncStatusPill above, not in place of it. */}
      {card.is_stale && (
        <div className="mt-3">
          <span
            data-stale-pill
            className="inline-flex items-center gap-1.5 rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 text-xs font-mono text-[var(--color-amber-on-soft)]"
          >
            stale · {card.stale_days}d
          </span>
        </div>
      )}
    </div>
  );
}
