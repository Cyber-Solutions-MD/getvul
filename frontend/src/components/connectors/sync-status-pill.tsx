/**
 * SyncStatusPill — 4-state connector sync health pill.
 *
 * D-CONN-05: driven by `last_sync_status` (backend raw values).
 * Reuses the Phase 13 D-P-04 color token family:
 *   ok      → severity-low (green)
 *   failed  → severity-critical (red)
 *   syncing → amber (animated dot)
 *   null    → text-faint (gray, never-synced)
 *
 * Sunset-tokenized: no raw gray-*, indigo-*, or emerald-* utilities.
 */
import { cn } from '@/lib/utils';

type SyncStatus = 'ok' | 'failed' | 'syncing' | null;

export type SyncStatusPillProps = {
  status: SyncStatus;
  className?: string;
};

type StateConfig = {
  label: string;
  pillClass: string;
  dotClass: string;
};

// Map each backend status value to visual config.
// Reuses Phase 13 D-P-04 border/bg/text token triad.
const STATUS_CONFIG: Record<NonNullable<SyncStatus> | '__never', StateConfig> = {
  ok: {
    label: 'Synced',
    pillClass: 'border-severity-low/40 bg-severity-low/10 text-severity-low',
    dotClass: 'size-1.5 rounded-full bg-current',
  },
  failed: {
    label: 'Failed',
    pillClass: 'border-severity-critical/40 bg-severity-critical/10 text-[var(--color-severity-critical-on-soft)]',
    dotClass: 'size-1.5 rounded-full bg-current',
  },
  syncing: {
    label: 'Syncing',
    pillClass: 'border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]',
    dotClass: 'size-1.5 rounded-full bg-current motion-safe:animate-pulse',
  },
  __never: {
    label: 'Never synced',
    pillClass: 'border-border-subtle bg-surface-2 text-text-faint',
    dotClass: 'size-1.5 rounded-full bg-current',
  },
};

export function SyncStatusPill({ status, className }: SyncStatusPillProps) {
  const key = status ?? '__never';
  // Total lookup: an unexpected/un-normalized value (e.g. a raw backend
  // "SUCCESS"/"FAILED" that bypassed the service.py wire normalization)
  // degrades gracefully to the __never config instead of crashing the
  // destructure — belt-and-suspenders alongside the backend fix.
  const { label, pillClass, dotClass } = STATUS_CONFIG[key] ?? STATUS_CONFIG['__never'];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        pillClass,
        className,
      )}
      data-sync-status={status ?? 'never'}
    >
      <span className={dotClass} />
      {label}
    </span>
  );
}
