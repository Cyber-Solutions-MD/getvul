'use client';

// TrendChart — Phase 10 dashboard primitive (Plan 10-04).
//
// Decisions (D-C-01..10, D-Ax-03..04, D-Perf-01):
//   - Stacked recharts BarChart (one stackId across critical/high/medium/low Bars)
//   - Fills routed through CSS variables — survives theme swaps + forced-colors mode
//   - sr-only <table> is the canonical data path for screen readers (SVG is aria-hidden)
//   - Range toggle (7d/30d/90d) uses aria-pressed (accessible toggle pattern)
//   - prefers-reduced-motion gates Bar animations explicitly (belt-and-suspenders
//     alongside recharts' native 'auto' isAnimationActive behavior)
//   - NO dynamic-import wrapper here — Plan 05's dashboard/trend-section.tsx
//     owns the route-split shim so this primitive stays unit-testable.

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { cn } from '@/lib/utils';
import { microcopy } from '@/components/dashboard/microcopy';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';

export type TrendDatum = {
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
};
export type Range = '7d' | '30d' | '90d';
export type TrendChartProps = {
  data: TrendDatum[];
  range: Range;
  onRangeChange: (next: Range) => void;
};

// Exported for test-level contract assertions (jsdom + recharts v2.12 doesn't
// emit the inner <rect> elements, so a DOM-level fill assertion is unreliable —
// we assert the constant directly, plus a grep gate on the source per
// acceptance_criteria. The grep gate + this export together prove the contract.)
export const SEVERITY_FILLS = {
  critical: 'var(--color-severity-critical)',
  high: 'var(--color-severity-high)',
  medium: 'var(--color-severity-medium)',
  low: 'var(--color-severity-low)',
} as const;

const SEVERITY_GLYPHS = {
  critical: '■', // ■
  high: '▲',     // ▲
  medium: '◆',   // ◆
  low: '○',      // ○
} as const;

function fmtTick(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function fmtFullDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function isLatestDay(label: string, lastDate: string): boolean {
  return label === lastDate;
}

// Exported for unit-test isolation (Test 9 + Test 10 render the tooltip directly
// because recharts' hover-fire requires a sized SVG which jsdom doesn't provide).
export type SeverityTooltipPayload = {
  dataKey: 'critical' | 'high' | 'medium' | 'low';
  value: number;
};
export function SeverityTooltip({
  active,
  payload,
  label,
  lastDate,
}: {
  active?: boolean;
  payload?: SeverityTooltipPayload[];
  label?: string;
  lastDate?: string;
}) {
  if (!active || !payload?.length) return null;
  const get = (k: SeverityTooltipPayload['dataKey']) =>
    payload.find(p => p.dataKey === k)?.value ?? 0;
  const total =
    get('critical') + get('high') + get('medium') + get('low');
  const headline =
    label && lastDate && isLatestDay(label, lastDate)
      ? microcopy.trend.todaySoFar
      : label
        ? fmtFullDate(label)
        : '';
  return (
    <div
      role="tooltip"
      className="rounded-md border border-border bg-surface px-3 py-2 shadow-card"
    >
      <p className="text-xs text-text-muted">{headline}</p>
      <p className="font-mono text-sm text-text">{total} open</p>
      <ul className="mt-1 space-y-0.5 font-mono text-xs">
        <li>
          <span className="text-severity-critical" aria-hidden="true">
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

function RangeToggle({
  value,
  onChange,
}: {
  value: Range;
  onChange: (n: Range) => void;
}) {
  const opts: { id: Range; label: string; a11y: string }[] = [
    { id: '7d', label: microcopy.trend.range7d, a11y: microcopy.trend.range7dA11y },
    { id: '30d', label: microcopy.trend.range30d, a11y: microcopy.trend.range30dA11y },
    { id: '90d', label: microcopy.trend.range90d, a11y: microcopy.trend.range90dA11y },
  ];
  return (
    <div
      role="group"
      aria-label="Trend range"
      className="inline-flex rounded-md border border-border-subtle p-0.5"
    >
      {opts.map(o => {
        const active = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={active}
            // Verbose a11y string lives in a sr-only span — the visible
            // compact label '7d' remains the accessible name (no aria-label
            // override) so screen readers + visual users get the same handle.
            onClick={() => onChange(o.id)}
            className={cn(
              'rounded-sm px-3 py-1 text-xs font-mono transition-colors',
              active
                ? 'bg-surface-2 text-text'
                : 'text-text-muted hover:text-text',
            )}
          >
            {o.label}
            <span className="sr-only">{' '}({o.a11y})</span>
          </button>
        );
      })}
    </div>
  );
}

function ChartDataTable({ data }: { data: TrendDatum[] }) {
  return (
    <table className="sr-only" aria-label={microcopy.trend.h2}>
      <caption>Daily counts of open vulnerabilities by severity</caption>
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Critical</th>
          <th scope="col">High</th>
          <th scope="col">Medium</th>
          <th scope="col">Low</th>
          <th scope="col">Total</th>
        </tr>
      </thead>
      <tbody>
        {data.map(d => (
          <tr key={d.date}>
            <th scope="row">{fmtFullDate(d.date)}</th>
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

export function TrendChart({ data, range, onRangeChange }: TrendChartProps) {
  const lastDate = data[data.length - 1]?.date ?? '';
  const reduced = usePrefersReducedMotion();
  // recharts' TS types don't yet expose 'auto'; the runtime accepts it (v2.10+).
  const anim: false | 'auto' = reduced ? false : 'auto';

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="sr-only">{microcopy.trend.h2}</h3>
        <RangeToggle value={range} onChange={onRangeChange} />
      </div>
      <div aria-hidden="true">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
            accessibilityLayer
          >
            <CartesianGrid
              strokeDasharray="2 4"
              vertical={false}
              stroke="var(--color-border-subtle)"
            />
            <XAxis
              dataKey="date"
              tickFormatter={fmtTick}
              stroke="var(--color-text-muted)"
            />
            <YAxis stroke="var(--color-text-muted)" />
            <Tooltip
              content={<SeverityTooltip lastDate={lastDate} />}
              cursor={{ fill: 'var(--color-surface-2)' }}
            />
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
      <ChartDataTable data={data} />
    </div>
  );
}
