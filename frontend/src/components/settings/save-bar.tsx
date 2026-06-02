'use client';
/**
 * SaveBar — D-SET-04 per-category sticky save bar.
 *
 * Invisible until a settings pane is dirty (isDirty=true). Slides in from the
 * bottom as a fixed bar above the viewport floor when it appears.
 *
 * Pattern mirrors TicketBulkBar (Phase 13):
 *   fixed inset-x-0 bottom-0 z-30 + animate-in slide-in-from-bottom-2
 *
 * Copy (copy-voice.md):
 *   - "Save changes" (not "Submit" / "OK")
 *   - "Discard" (not "Cancel" / "Reset")
 *   - "Saving…" while pending (not "Loading…")
 *
 * No inline hex — all colors via sunset Tailwind tokens.
 */

import { cn } from '@/lib/utils';
import { SAVE_BAR } from './microcopy';

export type SaveBarProps = {
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
};

export function SaveBar({ isDirty, isSaving, onSave, onDiscard }: SaveBarProps) {
  // Returns null when not dirty — invisible by default.
  if (!isDirty) return null;

  return (
    <div
      data-save-bar
      role="toolbar"
      aria-label="Unsaved changes"
      className={cn(
        'fixed inset-x-0 bottom-0 z-30',
        'flex items-center justify-between',
        'border-t border-border-subtle bg-surface-2/95 backdrop-blur',
        'px-6 py-3',
        'animate-in slide-in-from-bottom-2',
      )}
    >
      {/* Left: note copy */}
      <span className="text-sm text-text-muted">
        {SAVE_BAR.unsavedNote}
      </span>

      {/* Right: Discard + Save actions */}
      <div className="flex items-center gap-2">
        {/* Discard — ghost button */}
        <button
          type="button"
          onClick={onDiscard}
          disabled={isSaving}
          className="rounded-md px-3 py-1.5 text-sm font-medium text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
        >
          {SAVE_BAR.discard}
        </button>

        {/* Save changes — gradient CTA */}
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className={cn(
            'rounded-md px-4 py-1.5 text-sm font-medium',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            'disabled:cursor-not-allowed disabled:opacity-50',
            // Gradient CTA — uses the gradient-brand/gradient-sunset variable; no raw hex.
            'bg-gradient-to-r from-pink to-violet text-white',
          )}
          style={{ background: 'var(--gradient-brand, var(--gradient-sunset, linear-gradient(135deg, #EC4899 0%, #A78BFA 50%, #F59E0B 100%)))' }}
        >
          {isSaving ? SAVE_BAR.saving : SAVE_BAR.save}
        </button>
      </div>
    </div>
  );
}
