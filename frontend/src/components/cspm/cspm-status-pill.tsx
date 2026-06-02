'use client';
/**
 * CspmStatusPill — status pill for CSPM findings.
 *
 * Uses CSPM-specific status-to-color mapping (Pitfall 4 — distinct from ticket statuses).
 * Status colors do NOT reuse ticket status tokens — CSPM has its own vocabulary.
 *
 * Mapping (per plan spec):
 *   OPEN         → violet
 *   IN_PROGRESS  → amber
 *   REMEDIATED   → severity-low (lavender/green)
 *   SUPPRESSED   → text-muted gray
 *   FALSE_POSITIVE → text-muted gray italic
 *
 * Shape: same as SyncStatusPill — `inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium`.
 * data-cspm-status={status} attribute for test hooks.
 *
 * Plan 14-03.
 */
import { cn } from '@/lib/utils';

export type CspmStatusPillProps = {
  status: string;
  className?: string;
};

const STATUS_CLASSES: Record<string, string> = {
  OPEN:           'border-violet/40 bg-violet/10 text-violet',
  IN_PROGRESS:    'border-amber/40 bg-amber/10 text-amber',
  REMEDIATED:     'border-severity-low/40 bg-severity-low/10 text-severity-low',
  SUPPRESSED:     'border-border-subtle bg-surface-2 text-text-muted',
  FALSE_POSITIVE: 'border-border-subtle bg-surface-2 text-text-muted italic',
};

const STATUS_LABEL: Record<string, string> = {
  OPEN:           'Open',
  IN_PROGRESS:    'In progress',
  REMEDIATED:     'Remediated',
  SUPPRESSED:     'Suppressed',
  FALSE_POSITIVE: 'False positive',
};

// Fallback for unknown statuses
const FALLBACK_CLASS = 'border-border-subtle bg-surface-2 text-text-muted';

export function CspmStatusPill({ status, className }: CspmStatusPillProps) {
  const classes = STATUS_CLASSES[status] ?? FALLBACK_CLASS;
  const label = STATUS_LABEL[status] ?? status;

  return (
    <span
      data-cspm-status={status}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        classes,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'inline-block size-1.5 rounded-full bg-current',
          status === 'IN_PROGRESS' ? 'motion-safe:animate-pulse' : '',
        )}
      />
      {label}
    </span>
  );
}
