/**
 * SeverityRibbon — UX-04-02 main column header. ■2 · ▲3 · ◆1 · ○1 · □0 ribbon.
 *
 * Glyph + count render inside a single text node per entry (Phase 11 chip-bar
 * lesson — testing-library's deep-text matching prefers a single child node so
 * `expect(...textContent).toBe('■2')` works without whitespace fudging).
 *
 * Zero-count entries are dimmed via text-text-faint (text-text-subtle is NOT a
 * configured tailwind token; convention from RiskRing.tsx + Breadcrumb.tsx +
 * assets-table.tsx is to substitute text-text-faint).
 */
import { cn } from '@/lib/utils';

const GLYPHS = [
  { key: 'critical', glyph: '■', tint: 'text-severity-critical', label: 'Critical' },
  { key: 'high', glyph: '▲', tint: 'text-[var(--color-severity-high-on-soft)]', label: 'High' },
  { key: 'medium', glyph: '◆', tint: 'text-severity-medium', label: 'Medium' },
  { key: 'low', glyph: '○', tint: 'text-severity-low', label: 'Low' },
  { key: 'info', glyph: '□', tint: 'text-severity-info', label: 'Info' },
] as const;

export type SeverityCounts = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info?: number;
};

export function SeverityRibbon({ counts }: { counts: SeverityCounts }) {
  return (
    <div className="flex items-center gap-3 text-sm" data-testid="severity-ribbon">
      {GLYPHS.map(({ key, glyph, tint, label }) => {
        const n = (counts[key as keyof SeverityCounts] ?? 0) as number;
        const dimmed = n === 0;
        return (
          <span
            key={key}
            role="img"
            className={cn(
              'inline-flex items-center font-mono tabular-nums',
              dimmed ? 'text-text-faint' : tint,
            )}
            aria-label={`${n} ${label}`}
            data-testid={`ribbon-${key}`}
          >
            {`${glyph}${n}`}
          </span>
        );
      })}
    </div>
  );
}
