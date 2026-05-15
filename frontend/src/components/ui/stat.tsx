'use client';
import type { HTMLAttributes, ReactNode } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

// D-P-02 + D-S-03..05: Stat tile with direction-aware delta color.
// - delta > 0 with deltaIsGood='down'  → "up is bad" → text-danger + TrendingUp
// - delta < 0 with deltaIsGood='down'  → "down is good" → text-success + TrendingDown
// - delta === 0                        → flat — no arrow rendered
// - delta === null|undefined           → "Δ —" (Pitfall 8 — first-week tenants without
//                                          snapshot history; backend returns null,
//                                          frontend MUST render this glyph not a spinner)

export type StatProps = HTMLAttributes<HTMLDivElement> & {
  label: string;
  value: number | string;
  delta?: number | null;
  /** When the delta direction is "good for the user". E.g., critical_open: down=good. */
  deltaIsGood?: 'up' | 'down';
  /** Suffix appended after the delta number. Default 'from yesterday' (D-S-04). */
  deltaSuffix?: string;
  hint?: string;
  icon?: ReactNode;
};

export function Stat({
  label,
  value,
  delta,
  deltaIsGood = 'down',
  deltaSuffix = 'from yesterday',
  hint,
  icon,
  className,
  ...rest
}: StatProps) {
  let body: ReactNode = null;
  if (delta === null || delta === undefined) {
    // Pitfall 8 / D-S-04: render 'Δ —' for tenants without 7d of snapshot history.
    body = (
      <span className="font-mono text-xs text-text-muted">Δ —</span>
    );
  } else if (delta === 0) {
    // Flat — no arrow, no row content. T-10-19: don't fabricate motion.
    body = null;
  } else {
    const direction = delta > 0 ? 'up' : 'down';
    const isGood = direction === deltaIsGood;
    const Arrow = direction === 'up' ? TrendingUp : TrendingDown;
    body = (
      <span
        className={cn(
          'inline-flex items-center gap-1 font-mono text-xs',
          isGood ? 'text-success' : 'text-danger'
        )}
      >
        <Arrow className="h-3 w-3" aria-hidden="true" />
        {delta > 0 ? '+' : ''}
        {delta} {deltaSuffix}
      </span>
    );
  }

  return (
    <div
      className={cn(
        'relative rounded-lg border border-border-subtle bg-surface p-5',
        className
      )}
      {...rest}
    >
      {icon && (
        <div
          className="absolute right-3 top-3 grid h-6 w-6 place-items-center rounded-md text-text-muted"
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <div className="mb-2 text-xs uppercase tracking-wide text-text-muted">
        {label}
      </div>
      <div className="font-mono text-4xl font-bold leading-none tabular-nums text-text">
        {value}
      </div>
      {body !== null && <div className="mt-2">{body}</div>}
      {hint && delta === undefined && (
        <div className="mt-2 text-xs text-text-faint">{hint}</div>
      )}
      {/* When delta is provided (incl. null) and hint is also provided, surface hint below the delta row.
          This supports tiles like "MTTR — 4.2d / Δ — / vs goal 7d". */}
      {hint && delta !== undefined && (
        <div className="mt-1 text-xs text-text-faint">{hint}</div>
      )}
    </div>
  );
}
