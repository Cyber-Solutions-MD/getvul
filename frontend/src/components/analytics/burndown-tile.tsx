'use client';
/**
 * BurndownTile — Phase 42 Plan 02 (TREND-02/D-09): net backlog velocity
 * (findings/week, resolved minus new) plus a projected days-to-clear.
 * Reuses `campaign-burndown-card.tsx`'s card chrome (`rounded-lg border
 * border-border-subtle bg-surface-2 p-4`) but deliberately omits that
 * card's center-ring visual (asset-detail's risk-ring primitive) — this
 * is a RATE, not a percentage (UI-SPEC's explicit prohibition).
 *
 * Every value here arrives as an already-computed plain prop from the
 * backend (`get_burndown_rate`) — this component never divides by a
 * denominator itself (mirrors campaign-burndown-card.tsx's Pitfall-5
 * zero-denominator-guard discipline). `status` carries direction;
 * `netPerWeek` is always a non-negative magnitude, so no sign-check or
 * `Math.abs()` is needed here either — only a copy-branch switch on
 * `status`.
 *
 * Directional color reuses the existing SLA/status convention verbatim
 * (text-success for shrinking, text-danger for growing, muted for the
 * distinct no-change branch) — never a new invented palette.
 */
import { cn } from '@/lib/utils';
import type { BurndownStatus } from '@/lib/queries/use-analytics';
import { microcopy } from './microcopy';

export type BurndownTileProps = {
  status: BurndownStatus;
  netPerWeek: number;
  daysToClear: number | null;
  capped: boolean;
  className?: string;
};

function directionalCopy(status: BurndownStatus, netPerWeek: number): string {
  if (status === 'shrinking') return microcopy.burndown.netVelocity.shrinking(netPerWeek);
  if (status === 'growing') return microcopy.burndown.netVelocity.growing(netPerWeek);
  return microcopy.burndown.netVelocity.noChange;
}

// UI-SPEC only defines a projected-clear line for shrinking/growing — the
// no_change status has nothing to project (the rate is exactly flat), so
// this returns null rather than inventing a 3rd copy variant.
function projectedClearCopy(status: BurndownStatus, daysToClear: number | null, capped: boolean): string | null {
  if (status === 'growing') return microcopy.burndown.projectedClear.growing;
  if (status === 'shrinking') {
    if (capped) return microcopy.burndown.projectedClear.capped;
    return microcopy.burndown.projectedClear.shrinking(daysToClear ?? 0);
  }
  return null;
}

export function BurndownTile({ status, netPerWeek, daysToClear, capped, className }: BurndownTileProps) {
  const clearCopy = projectedClearCopy(status, daysToClear, capped);

  return (
    <section
      className={cn('rounded-lg border border-border-subtle bg-surface-2 p-4', className)}
      aria-label="Burndown"
      data-testid="burndown-tile"
    >
      <div className="flex flex-col items-center gap-1 pb-3">
        {/* Display-size (40px/600) headline number, mono/tabular-nums. */}
        <span
          data-testid="burndown-net-per-week"
          className="font-mono text-4xl font-semibold leading-tight tabular-nums text-text"
        >
          {netPerWeek}
        </span>
        <span
          className={cn(
            'text-sm',
            status === 'shrinking' && 'text-success',
            status === 'growing' && 'text-danger',
            status === 'no_change' && 'text-text-muted',
          )}
        >
          {directionalCopy(status, netPerWeek)}
        </span>
      </div>

      {clearCopy !== null && (
        <div className="border-t border-border-subtle pt-3 text-sm text-text-muted">{clearCopy}</div>
      )}
    </section>
  );
}
