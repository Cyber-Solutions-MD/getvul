'use client';
/**
 * LensSwitcher — RPT-02 (Phase 43 Plan 04). A 4-segment control (Analyst /
 * IT-ops / Compliance / Leadership) rendered top-right of the dashboard
 * header. Mirrors `scope-window-controls.tsx`'s `role="group"` +
 * `aria-pressed` segmented-toggle idiom (itself extending
 * `components/ui/trend-chart.tsx`'s `RangeToggle`).
 *
 * Visual chrome per 43-UI-SPEC.md: inactive = `--color-surface-2` fill +
 * `--color-text-muted` label; active = `--color-pink-soft` fill +
 * `--color-pink` border/label (the existing `.chip`/`ChipBar` active-state
 * convention, reused verbatim — no new tokens invented).
 *
 * E1 (long-text, `covered`): segment labels are a FIXED closed set, not
 * user data — the control never wraps (single row).
 *
 * Lens availability is presentation-only and never depends on
 * `User.role` (T-43-13) — this component takes no role prop at all.
 */
import { cn } from '@/lib/utils';
import { ALLOWED_LENSES, type Lens } from '@/hooks/use-lens';

export type LensSwitcherProps = {
  lens: Lens;
  onLensChange: (next: Lens) => void;
  className?: string;
};

const LENS_LABEL: Record<Lens, string> = {
  analyst: 'Analyst',
  'it-ops': 'IT-ops',
  compliance: 'Compliance',
  leadership: 'Leadership',
};

export function LensSwitcher({ lens, onLensChange, className }: LensSwitcherProps) {
  return (
    <div
      role="group"
      aria-label="Dashboard lens"
      className={cn(
        'inline-flex flex-nowrap items-center rounded-md border border-border-subtle p-0.5',
        className,
      )}
    >
      {ALLOWED_LENSES.map((l) => {
        const active = l === lens;
        return (
          <button
            key={l}
            type="button"
            aria-pressed={active}
            onClick={() => onLensChange(l)}
            className={cn(
              'whitespace-nowrap rounded-sm px-3 py-1 text-xs font-medium transition-colors',
              active
                ? 'border border-pink bg-pink-soft text-[var(--color-pink-on-soft)]'
                : 'border border-transparent text-text-muted hover:text-text',
            )}
          >
            {LENS_LABEL[l]}
          </button>
        );
      })}
    </div>
  );
}
