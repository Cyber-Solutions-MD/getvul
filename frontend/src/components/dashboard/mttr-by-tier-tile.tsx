'use client';
/**
 * MttrByTierTile — RPT-02 leadership-lens widget (Phase 43 Plan 04). Three
 * tier cells (Critical / High / Moderate), Display-size (40px/600) mono
 * days, tier-hued per the existing severity-tier family. Analog:
 * `analytics/burndown-tile.tsx`'s stat-tile-with-states shape.
 *
 * E8 (★ `covered`, mandatory): a tier with zero remediation history
 * (`avg_seconds === null`) renders "Not yet measured" — NEVER `0 days`,
 * which would read as a real (good!) number to a board audience. Gated on
 * the metric's own null signal, never on a falsy/zero value (0 days IS a
 * legitimate — if implausible — reading and must not be confused with "no
 * data"), mirroring `use-analytics.ts`'s scored-point-count discipline.
 */
import { cn } from '@/lib/utils';
import type { MttrByTierRow } from '@/lib/queries/use-mttr-by-tier';

export type MttrByTierTileProps = {
  rows: MttrByTierRow[];
  className?: string;
};

const TIER_ORDER = ['critical', 'high', 'moderate'] as const;
type TierId = (typeof TIER_ORDER)[number];

const TIER_LABEL: Record<TierId, string> = {
  critical: 'Critical',
  high: 'High',
  moderate: 'Moderate',
};

// Tier-hued per the existing severity family (visual-language.md) — never
// a new palette. "moderate" maps to the medium severity hue.
const TIER_COLOR_CLASS: Record<TierId, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  moderate: 'text-severity-medium',
};

function daysFromSeconds(avgSeconds: number): string {
  const days = avgSeconds / 86400;
  return days.toFixed(1);
}

export function MttrByTierTile({ rows, className }: MttrByTierTileProps) {
  const byTier = new Map(rows.map((r) => [r.tier_at_remediation, r]));

  return (
    <section
      aria-label="MTTR by risk tier"
      data-testid="mttr-by-tier-tile"
      className={cn('rounded-lg border border-border-subtle bg-surface-2 p-4', className)}
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">MTTR by tier</h3>
      <div className="grid grid-cols-3 gap-3">
        {TIER_ORDER.map((tier) => {
          const row = byTier.get(tier);
          const hasData = row != null && row.avg_seconds !== null;
          return (
            <div key={tier} className="flex flex-col items-center gap-1 text-center">
              {hasData ? (
                <span
                  data-testid={`mttr-tier-value-${tier}`}
                  className={cn(
                    'font-mono text-4xl font-semibold leading-tight tabular-nums',
                    TIER_COLOR_CLASS[tier],
                  )}
                >
                  {daysFromSeconds(row!.avg_seconds as number)}
                  <span className="text-sm text-text-muted"> d</span>
                </span>
              ) : (
                <span
                  data-testid={`mttr-tier-value-${tier}`}
                  className="text-sm italic text-text-faint"
                >
                  Not yet measured
                </span>
              )}
              <span className="text-xs text-text-muted">{TIER_LABEL[tier]}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
