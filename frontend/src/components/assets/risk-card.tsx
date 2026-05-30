'use client';
/**
 * RiskCard — UX-04-03 right-rail card composing RiskRing + 4 breakdown rows.
 *
 * 4 rows in this exact order (12-07-PLAN D-R-04):
 *   1. Critical exposures  → vuln_counts.critical (severity-critical tint)
 *   2. SLA breaches        → sla_breach          (severity-high tint, amber)
 *   3. KEV count           → vuln_counts.kev     (severity-medium tint, pink)
 *   4. 7-day delta         → "—" + "Trend unavailable" (history table deferred,
 *                            locked_decisions item 2)
 *
 * Token note: the plan referenced `text-text-subtle` which is NOT defined in
 * tailwind.config.ts (only text-text-muted + text-text-faint). All "subtle"
 * uses below resolve to `text-text-muted` per CLAUDE.md ui-guardrails.
 */
import { RiskRing } from '@/components/ui/RiskRing';
import type { AssetDetail } from '@/lib/queries/use-asset-detail';
import { cn } from '@/lib/utils';

function BreakdownRow({
  count,
  label,
  tintClass,
  testId,
}: {
  count: number | string;
  label: string;
  tintClass?: string;
  testId?: string;
}) {
  return (
    <div
      className="flex items-center justify-between border-t border-border-subtle py-2 text-sm"
      data-testid={testId}
    >
      <span className="text-text-muted">{label}</span>
      <span className={cn('font-mono tabular-nums', tintClass)}>{count}</span>
    </div>
  );
}

export function RiskCard({ asset }: { asset: AssetDetail }) {
  const counts = asset.vuln_counts;
  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-2 p-4"
      aria-label="Risk score"
      data-testid="risk-card"
    >
      <div className="flex justify-center pb-3">
        <RiskRing score={asset.risk_score} />
      </div>
      <div className="space-y-0">
        <BreakdownRow
          testId="risk-row-critical"
          count={counts?.critical ?? 0}
          label="Critical"
          tintClass="text-severity-critical"
        />
        <BreakdownRow
          testId="risk-row-sla"
          count={asset.sla_breach ?? 0}
          label="SLA breach"
          tintClass="text-severity-high"
        />
        <BreakdownRow
          testId="risk-row-kev"
          count={counts?.kev ?? 0}
          label="KEV"
          tintClass="text-severity-medium"
        />
        <BreakdownRow
          testId="risk-row-delta"
          count="—"
          label="Trend unavailable"
          tintClass="text-text-muted"
        />
      </div>
    </section>
  );
}
