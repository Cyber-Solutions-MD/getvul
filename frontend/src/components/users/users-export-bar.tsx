'use client';
/**
 * UsersExportBar — export-only bulk bar for /dashboard/users (Plan 14-04).
 *
 * D-USR-02: export-only — no write actions here; writable RBAC actions live
 * in Workspace settings (Plan 14-05).
 *
 * Appears when selectedIds.length > 0 (bottom-anchored, slide-up animation).
 * Returns null when no selection.
 */
import { cn } from '@/lib/utils';
import ExportButton from '@/components/ui/ExportButton';
import { microcopy } from './microcopy';

export type UsersExportBarProps = {
  selectedIds: string[];
  onClearSelection: () => void;
};

export function UsersExportBar({ selectedIds, onClearSelection }: UsersExportBarProps) {
  if (selectedIds.length === 0) return null;

  return (
    <div
      role="toolbar"
      aria-label="Bulk export"
      data-users-export-bar
      className={cn(
        'fixed inset-x-0 bottom-0 z-30 flex items-center gap-3',
        'border-t border-border-subtle bg-surface px-6 py-3 shadow-lg',
        'animate-in slide-in-from-bottom-2',
      )}
    >
      <span className="text-sm font-medium text-text">
        {microcopy.selected(selectedIds.length)}
      </span>

      <div className="ml-4 flex items-center gap-2">
        <ExportButton
          resource="users"
          label={microcopy.exportSelected}
          filters={{ ids: selectedIds }}
        />
      </div>

      <button
        type="button"
        onClick={onClearSelection}
        className="ml-auto text-sm text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        aria-label="Clear selection"
      >
        Clear
      </button>
    </div>
  );
}
