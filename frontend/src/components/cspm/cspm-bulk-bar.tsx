'use client';
/**
 * CspmBulkBar — bulk actions bar for the CSPM findings list.
 *
 * Mirrors ticket-bulk-bar shape. Bottom-anchored, slide-up animation.
 * Returns null when selectedCount === 0.
 *
 * Actions:
 *   Resolve → onBulkAction('REMEDIATED')
 *   Ignore  → onBulkAction('SUPPRESSED')
 *   Reopen  → onBulkAction('OPEN')
 *
 * D-CSPM-03 bulk mapping: Resolve→REMEDIATED, Ignore→SUPPRESSED, Reopen→OPEN.
 * Sunset tokens only. No raw palette.
 * data-cspm-bulk-bar attribute for test hooks.
 *
 * Plan 14-03.
 */
import { cn } from '@/lib/utils';

export type BulkCspmStatus = 'REMEDIATED' | 'SUPPRESSED' | 'OPEN';

export type CspmBulkBarProps = {
  selectedCount: number;
  onBulkAction: (status: BulkCspmStatus) => void;
  onClearSelection: () => void;
  isPending?: boolean;
};

export function CspmBulkBar({
  selectedCount,
  onBulkAction,
  onClearSelection,
  isPending,
}: CspmBulkBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      role="toolbar"
      aria-label="Bulk actions"
      data-cspm-bulk-bar
      className={cn(
        'fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t border-border-subtle bg-surface px-6 py-3 shadow-lg',
        'animate-in slide-in-from-bottom-2',
      )}
    >
      <span className="text-sm font-medium text-text">
        {selectedCount} selected
      </span>

      <div className="ml-4 flex items-center gap-2">
        {/* Resolve → REMEDIATED */}
        <button
          type="button"
          onClick={() => onBulkAction('REMEDIATED')}
          disabled={isPending}
          className="rounded-md border border-severity-low/30 bg-severity-low/10 px-3 py-1.5 text-sm font-medium text-severity-low hover:bg-severity-low/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
        >
          Resolve
        </button>

        {/* Ignore → SUPPRESSED */}
        <button
          type="button"
          onClick={() => onBulkAction('SUPPRESSED')}
          disabled={isPending}
          className="rounded-md border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm font-medium text-text-muted hover:bg-surface hover:border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ignore
        </button>

        {/* Reopen → OPEN */}
        <button
          type="button"
          onClick={() => onBulkAction('OPEN')}
          disabled={isPending}
          className="rounded-md border border-violet/30 bg-violet/10 px-3 py-1.5 text-sm font-medium text-[var(--color-violet-on-soft)] hover:bg-violet/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
        >
          Reopen
        </button>
      </div>

      <button
        type="button"
        onClick={onClearSelection}
        className="ml-auto text-sm text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        aria-label="Clear selection"
      >
        ×
      </button>
    </div>
  );
}
