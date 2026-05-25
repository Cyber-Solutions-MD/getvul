'use client';
import { cn } from '@/lib/utils';

// D-S-01: column-aware skeleton mirroring real table column shape.
// Phase 12+ describe their columns once when calling.
//
// motion-safe:animate-shimmer consumes the alias from tailwind.config.ts.
// The motion-safe: variant means prefers-reduced-motion: reduce strips the
// animation but the gradient remains. Forced-colors mode: the bordered
// placeholder shape survives because the pill kind carries an explicit
// border; mono/text/badge fall back to the row border-b.
//
// Test contract (11-02): rows carry `data-skeleton-row`; cells carry
// `data-skeleton-cell` so test assertions can target the shimmer placeholders
// directly (the <td> wrappers are layout chrome only — the cell with chrome,
// width, and shimmer is what tests measure).

export type SkeletonColumnKind = 'pill' | 'mono' | 'text' | 'badge';
export type SkeletonColumn = { kind: SkeletonColumnKind; width: number };

type Props = { rows?: number; columns: SkeletonColumn[]; className?: string };

const KIND_BG: Record<SkeletonColumnKind, string> = {
  // Sunset-tinted pill shimmer (state-patterns.md `.skel-pill`)
  pill: 'rounded-full bg-gradient-to-r from-pink-soft via-violet-soft to-pink-soft border border-border-subtle',
  // Neutral mono-block shimmer
  mono: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
  text: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
  badge: 'rounded bg-gradient-to-r from-surface-2 via-border to-surface-2',
};

export function SkeletonTable({ rows = 8, columns, className }: Props) {
  return (
    <table
      className={cn('w-full', className)}
      aria-busy="true"
      aria-label="Loading vulnerabilities"
    >
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr
            key={r}
            data-skeleton-row=""
            className="border-b border-border-subtle"
          >
            {columns.map((col, c) => (
              <td key={c} className="px-3 py-3">
                <span
                  data-skeleton-cell=""
                  className={cn(
                    'inline-block h-4 bg-[length:200%_100%] motion-safe:animate-shimmer',
                    KIND_BG[col.kind]
                  )}
                  style={{ width: col.width }}
                />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
