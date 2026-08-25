'use client';
/**
 * SlaComplianceTile — RPT-02 leadership/compliance-lens widget (Phase 43
 * Plan 04). Display-size (40px/600) mono % + a thin 3-segment bar
 * (on-track / approaching-breach / breached), reusing the existing SLA
 * 3-tier color family verbatim (`--color-success`/`-warning`/`-danger` —
 * `.sla-pill` chrome). Analog: `analytics/burndown-tile.tsx`.
 *
 * E8 (★ `covered`, mandatory): `remediated_total === 0` (the metric's own
 * zero-denominator signal per `use-sla-metrics.ts`'s `SlaMetrics` type)
 * renders "Not yet measured" — NEVER `0%`, which the SLA function's own
 * documented `compliance_pct` fallback (100.0) would otherwise misrepresent
 * as a perfect score to a board audience (43-RESEARCH.md Pitfall 1).
 *
 * `compact` renders the smaller Compliance-lens variant (item 2 of 4);
 * default (hero) renders the Leadership-lens variant (item 4 of 5).
 */
import { cn } from '@/lib/utils';
import type { SlaMetrics } from '@/lib/queries/use-sla-metrics';

export type SlaComplianceTileProps = {
  metrics: SlaMetrics;
  compact?: boolean;
  className?: string;
};

export function SlaComplianceTile({ metrics, compact = false, className }: SlaComplianceTileProps) {
  // D-11 zero-denominator discipline: gate on remediated_total, never on
  // compliance_pct itself (the service's own fallback returns 100.0 when
  // remediated_total is 0 — a fake-perfect number, not a real reading).
  const hasData = metrics.remediated_total > 0;

  const onTrack = metrics.within_sla;
  const approaching = metrics.at_risk;
  const breached = metrics.breached;
  const openTotal = onTrack + approaching + breached;

  return (
    <section
      aria-label="SLA compliance"
      data-testid="sla-compliance-tile"
      className={cn('rounded-lg border border-border-subtle bg-surface-2', compact ? 'p-3' : 'p-4', className)}
    >
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">SLA compliance</h3>

      <div className="flex flex-col items-center gap-1 pb-3">
        {hasData ? (
          <span
            data-testid="sla-compliance-pct"
            className={cn(
              'font-mono font-semibold leading-tight tabular-nums text-text',
              compact ? 'text-2xl' : 'text-4xl',
            )}
          >
            {metrics.compliance_pct}%
          </span>
        ) : (
          <span data-testid="sla-compliance-pct" className="text-sm italic text-text-faint">
            Not yet measured
          </span>
        )}
      </div>

      {openTotal > 0 && (
        <div className="flex h-2 w-full overflow-hidden rounded-full border border-border-subtle">
          <div
            data-testid="sla-bar-on-track"
            className="bg-success"
            style={{ width: `${(onTrack / openTotal) * 100}%` }}
          />
          <div
            data-testid="sla-bar-approaching"
            className="bg-warning"
            style={{ width: `${(approaching / openTotal) * 100}%` }}
          />
          <div
            data-testid="sla-bar-breached"
            className="bg-danger"
            style={{ width: `${(breached / openTotal) * 100}%` }}
          />
        </div>
      )}
    </section>
  );
}
