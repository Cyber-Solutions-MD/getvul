/**
 * VulnCount — T·C·H vulnerability count cell.
 *
 * D-L-02: total text-text, critical text-severity-critical, high text-[var(--color-severity-high-on-soft)].
 * Zeros are explicit (shown, not hidden). Edge cases:
 *   total === 0 → em dash "—" (no breakdown)
 *   total > 99  → "99+" (cap)
 *
 * No inline hex — colors via Tailwind tokens.
 * Middot `·` separator per spec.
 */
import { cn } from '@/lib/utils';

export type VulnCountProps = {
  total: number;
  critical: number;
  high: number;
  className?: string;
};

export function VulnCount({ total, critical, high, className }: VulnCountProps) {
  if (total === 0) {
    return (
      <span className={cn('text-text-faint', className)}>
        {/* em dash for total 0 — no breakdown */}
        —
      </span>
    );
  }

  const displayTotal = total > 99 ? '99+' : total;

  return (
    <span className={cn('inline-flex items-baseline gap-0.5 font-mono', className)}>
      <span className="text-text">{displayTotal}</span>
      <span className="text-severity-critical">·{critical}</span>
      <span className="text-[var(--color-severity-high-on-soft)]">·{high}</span>
    </span>
  );
}
