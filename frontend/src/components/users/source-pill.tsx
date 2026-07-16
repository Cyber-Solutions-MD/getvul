'use client';
/**
 * SourcePill — enrichment-source pill for directory rows (Plan 14-04).
 *
 * Maps idp_source to sunset token classes (D-USR-01):
 *   google  → text-info / border-info/40 / bg-info/10
 *   azure   → text-info / border-info/40 / bg-info/10
 *   okta    → text-[var(--color-violet-on-soft)] / border-violet/40 / bg-violet-soft (WR-04: AA on cream)
 *   humaans → text-info / border-info/40 / bg-info/10  (cyan analog via --color-info)
 *   local   → text-text-faint / border-border-subtle / bg-surface-2
 *
 * T-14-13: source value used only for class lookup (Record), never injected into
 * CSS as a raw string. Only the class string is rendered — no inline style.
 *
 * No raw palette utilities (no indigo-*, blue-*, cyan-*, gray-*).
 */
import { cn } from '@/lib/utils';

// Literal Record lookup — injection guard (T-14-01/T-13-14 pattern).
const SOURCE_CLASSES: Record<string, string> = {
  google:  'text-info border-info/40 bg-info/10',
  azure:   'text-info border-info/40 bg-info/10',
  okta:    'text-[var(--color-violet-on-soft)] border-violet/40 bg-violet-soft',
  humaans: 'text-info border-info/40 bg-info/10',
  local:   'text-text-faint border-border-subtle bg-surface-2',
};

const FALLBACK_CLASSES = 'text-text-faint border-border-subtle bg-surface-2';

export type SourcePillProps = {
  source: string;
  className?: string;
};

export function SourcePill({ source, className }: SourcePillProps) {
  const classes = SOURCE_CLASSES[source] ?? FALLBACK_CLASSES;
  return (
    <span
      data-source-pill={source}
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-mono',
        classes,
        className
      )}
    >
      {source}
    </span>
  );
}
