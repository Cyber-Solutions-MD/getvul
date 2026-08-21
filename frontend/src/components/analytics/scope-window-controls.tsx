'use client';
/**
 * ScopeWindowControls — the top-of-page selector row for /dashboard/
 * analytics (Phase 42 Plan 01 — TREND-01 D-03). This plan ships the WINDOW
 * preset toggle only (7d/30d/90d/1y). Plan 03 adds the scope dropdown ("All
 * (tenant)" + each AssetGroup, D-02) and a 5th "Custom range" preset with
 * inline native date inputs onto this SAME file/component (D-03) — do not
 * rename this file or its export when that lands.
 *
 * Extends `components/ui/trend-chart.tsx`'s RangeToggle (`role="group"` +
 * `aria-pressed` accessible-toggle idiom) from 3 options to 4. Owned state
 * lives in the page (mirrors `dashboard/trend-section.tsx`'s TrendSection
 * owning `useUrlState` and handing `range`/`onRangeChange` down to
 * TrendChart's internal dumb RangeToggle) — this component is presentational.
 */
import { cn } from '@/lib/utils';
import type { AnalyticsWindow } from '@/lib/queries/use-analytics';
import { microcopy } from './microcopy';

export type ScopeWindowControlsProps = {
  value: AnalyticsWindow;
  onChange: (next: AnalyticsWindow) => void;
};

const WINDOW_OPTIONS: { id: AnalyticsWindow; label: string; a11y: string }[] = [
  { id: '7d', label: microcopy.window.d7, a11y: microcopy.window.d7A11y },
  { id: '30d', label: microcopy.window.d30, a11y: microcopy.window.d30A11y },
  { id: '90d', label: microcopy.window.d90, a11y: microcopy.window.d90A11y },
  { id: '1y', label: microcopy.window.y1, a11y: microcopy.window.y1A11y },
];

export function ScopeWindowControls({ value, onChange }: ScopeWindowControlsProps) {
  return (
    <div className="flex items-center justify-end">
      <div
        role="group"
        aria-label={microcopy.window.groupLabel}
        className="inline-flex rounded-md border border-border-subtle p-0.5"
      >
        {WINDOW_OPTIONS.map((o) => {
          const active = o.id === value;
          return (
            <button
              key={o.id}
              type="button"
              aria-pressed={active}
              // Verbose a11y string lives in a sr-only span — the visible
              // compact label ('7d') remains the accessible name.
              onClick={() => onChange(o.id)}
              className={cn(
                'rounded-sm px-3 py-1 text-xs font-mono transition-colors',
                active ? 'bg-surface-2 text-text' : 'text-text-muted hover:text-text',
              )}
            >
              {o.label}
              <span className="sr-only">{' '}({o.a11y})</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
