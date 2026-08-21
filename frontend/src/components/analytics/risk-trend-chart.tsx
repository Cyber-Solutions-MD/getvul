'use client';
/**
 * RiskTrendChart — the tenant risk-exposure trend line (Phase 42 Plan 01,
 * TREND-01/03 tracer slice). This is a genuinely new chart primitive: no
 * existing component in this codebase uses recharts' `Line`,
 * `ReferenceLine`, or `connectNulls` in any form — `components/ui/
 * trend-chart.tsx` is a stacked `BarChart`. See 42-RESEARCH.md Architecture
 * Patterns Pattern 4 (the only source for this logic, verified against
 * recharts docs, not a codebase precedent).
 *
 * Segments (never interpolates) across a detected risk-model-version
 * boundary (D-11) via the "pivot by version" approach: one `<Line>` per
 * detected version, with `null` outside that version's own dates, so
 * recharts' default `connectNulls={false}` naturally breaks the line at
 * the boundary — no synthetic null row inserted into the x-axis domain
 * (42-RESEARCH.md Pitfall 4). A single-version series (every real tenant
 * today — RISK_MODEL_VERSION has never been bumped past "v1") yields
 * exactly one `<Line>` and zero `<ReferenceLine>`s: one continuous segment,
 * byte-identical to a plain single-series line chart.
 *
 * A window with exactly one point renders a single dot (`dot={{ r: 3 }}`)
 * — recharts renders per-point dots independently of whether a connecting
 * path segment exists, so one point never draws a misleading zero-length
 * line (UI-SPEC E2 zero-one-many, locked user decision).
 *
 * Scaffolding (ResponsiveContainer/aria-hidden wrapper, reduced-motion
 * gating, sr-only ChartDataTable) is copied from
 * `components/ui/trend-chart.tsx` — the violet accent and the
 * segment/boundary logic are the only genuinely new pieces. The
 * version-boundary marker is deliberately NEUTRAL chrome (never violet or
 * a severity/success color) — coloring it would itself bias the reader
 * toward reading a model change as "important/good/bad" (D-11/D-12's whole
 * point is that it is neither).
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { usePrefersReducedMotion } from '@/hooks/use-prefers-reduced-motion';
import type { AnalyticsTrendPoint, VersionBoundary } from '@/lib/queries/use-analytics';
import { microcopy } from './microcopy';

export type RiskTrendChartProps = {
  trend: AnalyticsTrendPoint[];
  boundaries: VersionBoundary[];
};

// A plain intersection of `{ date: string }` with `Record<string, number |
// null>` conflicts (the index signature would also apply to `date`,
// demanding `string` be assignable to `number | null`) — widen the index
// signature's value type to include `string` so `date` satisfies it too.
type PivotedPoint = {
  date: string;
  [scoreKey: string]: string | number | null;
};

// 42-RESEARCH.md Code Examples §4 — one dataKey per detected version, null
// outside that version's own date range.
function pivotByVersion(trend: AnalyticsTrendPoint[]): { data: PivotedPoint[]; versions: string[] } {
  const versions = Array.from(
    new Set(trend.map((p) => p.risk_model_version).filter((v): v is string => v !== null)),
  );
  const data = trend.map((p) => {
    const row: PivotedPoint = { date: p.date };
    for (const v of versions) {
      row[`score_${v}`] = p.risk_model_version === v ? p.avg_risk_exposure_score : null;
    }
    return row;
  });
  return { data, versions };
}

function fmtTick(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function fmtFullDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

// The canonical accessible data path (the SVG chart is aria-hidden) — the
// version boundary must be readable here too, not only visually via
// <ReferenceLine> (plan <action>: "boundary readable in the table, not
// only visually").
function ChartDataTable({ trend, boundaries }: { trend: AnalyticsTrendPoint[]; boundaries: VersionBoundary[] }) {
  const boundaryDates = new Set(boundaries.map((b) => b.date));
  return (
    <table className="sr-only" aria-label={microcopy.trend.h2}>
      <caption>Daily tenant risk-exposure score, by date and model version</caption>
      <thead>
        <tr>
          <th scope="col">Date</th>
          <th scope="col">Score</th>
          <th scope="col">Model version</th>
        </tr>
      </thead>
      <tbody>
        {trend.map((p) => (
          <tr key={p.date}>
            <th scope="row">{fmtFullDate(p.date)}</th>
            <td>{p.avg_risk_exposure_score ?? '—'}</td>
            <td>
              {p.risk_model_version ?? '—'}
              {boundaryDates.has(p.date) ? ` — ${microcopy.trend.versionBoundaryTooltip}` : ''}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Custom <ReferenceLine label> render — a small neutral mono "chip"
// (bg-surface-2 / text-text-muted / border-border-subtle per 42-UI-SPEC.md
// Color), never the default plain SVG text. recharts clones this element
// and injects `viewBox`/`value` at render time.
function VersionBoundaryLabel(props: { viewBox?: { x?: number; y?: number }; value?: string | number }) {
  const x = props.viewBox?.x ?? 0;
  const y = props.viewBox?.y ?? 0;
  const text = String(props.value ?? '');
  const paddingX = 6;
  const charWidth = 6.2;
  const width = Math.max(28, text.length * charWidth + paddingX * 2);
  return (
    <g>
      <rect
        x={x - width / 2}
        y={y - 8}
        width={width}
        height={18}
        rx={4}
        fill="var(--color-surface-2)"
        stroke="var(--color-border-subtle)"
      />
      <text
        x={x}
        y={y + 4}
        textAnchor="middle"
        fontSize={11}
        fontFamily="var(--font-mono)"
        fill="var(--color-text-muted)"
      >
        {text}
      </text>
    </g>
  );
}

export function RiskTrendChart({ trend, boundaries }: RiskTrendChartProps) {
  const reduced = usePrefersReducedMotion();
  // recharts' TS types don't yet expose 'auto'; the runtime accepts it (v2.10+).
  const anim: false | 'auto' = reduced ? false : 'auto';
  const { data, versions } = pivotByVersion(trend);

  return (
    <div className="space-y-3">
      <h3 className="sr-only">{microcopy.trend.h2}</h3>
      <div aria-hidden="true">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }} accessibilityLayer>
            <CartesianGrid strokeDasharray="2 4" vertical={false} stroke="var(--color-border-subtle)" />
            <XAxis dataKey="date" tickFormatter={fmtTick} stroke="var(--color-text-muted)" />
            <YAxis stroke="var(--color-text-muted)" />
            <Tooltip
              labelFormatter={(label) => fmtFullDate(String(label))}
              contentStyle={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 6,
              }}
            />
            {/* One Line per detected version — the ONLY primary series on
                this page, so violet (not a severity palette). */}
            {versions.map((v) => (
              <Line
                key={v}
                type="monotone"
                dataKey={`score_${v}`}
                name={v}
                stroke="var(--color-violet)"
                connectNulls={false}
                dot={{ r: 3 }}
                isAnimationActive={anim as unknown as boolean}
              />
            ))}
            {/* One neutral (never accent/severity/success) marker per
                detected boundary — D-11/D-12: a model-version change is
                neither good nor bad, so its chrome must not imply either. */}
            {boundaries.map((b) => (
              <ReferenceLine
                key={b.date}
                x={b.date}
                stroke="var(--color-border-strong)"
                strokeDasharray="4 4"
                label={<VersionBoundaryLabel value={microcopy.trend.versionBoundaryLabel(b.old_version, b.new_version)} />}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable trend={trend} boundaries={boundaries} />
    </div>
  );
}
