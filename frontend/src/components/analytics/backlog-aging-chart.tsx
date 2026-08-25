'use client';
/**
 * BacklogAgingChart — Phase 42 Plan 02 (TREND-02/D-08): current open
 * findings bucketed into 3 SLA-tier-aligned buckets (Within SLA / Recently
 * breached / Long overdue), stacked by severity. A point-in-time snapshot
 * (D-08) — ignores the page's window preset entirely (scope only); the
 * parent page always passes the same `data`/`pctOverdue` regardless of the
 * selected trend window.
 *
 * Reuses `trend-chart.tsx`'s stacked-BarChart scaffolding verbatim
 * (ResponsiveContainer + aria-hidden wrapper, prefers-reduced-motion
 * gating, sr-only data table as the canonical accessible path) and its
 * exported `SEVERITY_FILLS` constant — bars are colored by SEVERITY only,
 * never by SLA tier (mixing both encodings would double-encode "urgency").
 * Bucket labels on the x-axis are plain TEXT (locked strings from
 * `microcopy.aging.buckets`), never SLA-tier colored chrome.
 *
 * The "% of open backlog is overdue" headline tile (UI-SPEC E3
 * zero-one-many) renders the full locked sentence at Display size (40px/
 * 600, mono/tabular-nums per foundation.md's "anything copy-pasteable"
 * rule for percentages) — explicit at zero, never blank or omitted.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { SEVERITY_FILLS } from '@/components/ui/trend-chart';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';
import type { AgingBucket, AgingBucketId } from '@/lib/queries/use-analytics';
import { microcopy } from './microcopy';

export type BacklogAgingChartProps = {
  data: AgingBucket[];
  pctOverdue: number;
};

const SEVERITY_GLYPHS = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
} as const;

function fmtBucketTick(bucketId: string): string {
  return microcopy.aging.buckets[bucketId as AgingBucketId] ?? bucketId;
}

// Exported for unit-test isolation, mirrors trend-chart.tsx's
// SeverityTooltipPayload/SeverityTooltip precedent — the per-severity
// breakdown shape is the same, only the "headline" derivation differs (a
// bucket label, never a "today so far" date concept).
export type AgingTooltipPayload = {
  dataKey: 'critical' | 'high' | 'medium' | 'low';
  value: number;
};
export function AgingTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: AgingTooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const get = (k: AgingTooltipPayload['dataKey']) => payload.find(p => p.dataKey === k)?.value ?? 0;
  const total = get('critical') + get('high') + get('medium') + get('low');
  const bucketLabel = label ? fmtBucketTick(label) : '';
  return (
    <div role="tooltip" className="rounded-md border border-border bg-surface px-3 py-2 shadow-card">
      <p className="text-xs text-text-muted">{bucketLabel}</p>
      <p className="font-mono text-sm text-text">{total} open</p>
      <ul className="mt-1 space-y-0.5 font-mono text-xs">
        <li>
          <span className="text-[var(--color-severity-critical-on-soft)]" aria-hidden="true">
            {SEVERITY_GLYPHS.critical}
          </span>{' '}
          Critical: {get('critical')}
        </li>
        <li>
          <span className="text-[var(--color-severity-high-on-soft)]" aria-hidden="true">
            {SEVERITY_GLYPHS.high}
          </span>{' '}
          High: {get('high')}
        </li>
        <li>
          <span className="text-severity-medium" aria-hidden="true">
            {SEVERITY_GLYPHS.medium}
          </span>{' '}
          Medium: {get('medium')}
        </li>
        <li>
          <span className="text-severity-low" aria-hidden="true">
            {SEVERITY_GLYPHS.low}
          </span>{' '}
          Low: {get('low')}
        </li>
      </ul>
    </div>
  );
}

function AgingDataTable({ data }: { data: AgingBucket[] }) {
  return (
    <table className="sr-only" aria-label={microcopy.aging.h2}>
      <caption>Open findings by SLA-tier aging bucket and severity</caption>
      <thead>
        <tr>
          <th scope="col">Bucket</th>
          <th scope="col">Critical</th>
          <th scope="col">High</th>
          <th scope="col">Medium</th>
          <th scope="col">Low</th>
          <th scope="col">Total</th>
        </tr>
      </thead>
      <tbody>
        {data.map(d => (
          <tr key={d.bucket}>
            <th scope="row">{fmtBucketTick(d.bucket)}</th>
            <td>{d.critical}</td>
            <td>{d.high}</td>
            <td>{d.medium}</td>
            <td>{d.low}</td>
            <td>{d.critical + d.high + d.medium + d.low}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function BacklogAgingChart({ data, pctOverdue }: BacklogAgingChartProps) {
  const reduced = usePrefersReducedMotion();
  // recharts' TS types don't yet expose 'auto'; the runtime accepts it (v2.10+).
  const anim: false | 'auto' = reduced ? false : 'auto';

  return (
    <div className="space-y-3">
      {/* Display-size (40px/600) headline tile — UI-SPEC E3: renders the
          FULL locked sentence explicitly at zero, never blank/omitted. */}
      <p
        data-testid="aging-overdue-tile"
        className="font-mono text-4xl font-semibold leading-tight tabular-nums text-text"
      >
        {microcopy.aging.overdueTile(pctOverdue)}
      </p>
      <div aria-hidden="true">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }} accessibilityLayer>
            <CartesianGrid strokeDasharray="2 4" vertical={false} stroke="var(--color-border-subtle)" />
            <XAxis dataKey="bucket" tickFormatter={fmtBucketTick} stroke="var(--color-text-muted)" />
            <YAxis stroke="var(--color-text-muted)" allowDecimals={false} />
            <Tooltip content={<AgingTooltip />} cursor={{ fill: 'var(--color-surface-2)' }} />
            {/* Same stackId="s" → all 4 stack. Paint order = stack order: low at base. */}
            <Bar
              dataKey="low"
              stackId="s"
              fill={SEVERITY_FILLS.low}
              isAnimationActive={anim as unknown as boolean}
            />
            <Bar
              dataKey="medium"
              stackId="s"
              fill={SEVERITY_FILLS.medium}
              isAnimationActive={anim as unknown as boolean}
            />
            <Bar
              dataKey="high"
              stackId="s"
              fill={SEVERITY_FILLS.high}
              isAnimationActive={anim as unknown as boolean}
            />
            <Bar
              dataKey="critical"
              stackId="s"
              fill={SEVERITY_FILLS.critical}
              isAnimationActive={anim as unknown as boolean}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <AgingDataTable data={data} />
    </div>
  );
}
