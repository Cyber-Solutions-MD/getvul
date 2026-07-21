'use client';
/**
 * TicketBulkBar — D-S-03 bulk actions bar for the /tickets list page.
 *
 * Appears when one or more tickets are selected (bottom-anchored, slide-up animation).
 * Actions:
 *   1. Close — ConfirmModal (no input), calls onBulkAction('close')
 *   2. Mark blocked — modal collecting shared blocked_reason, calls onBulkAction('block', reason)
 *   3. Unblock — ConfirmModal, calls onBulkAction('unblock')
 *
 * Bulk actions fire against POST /tickets/bulk-action on the backend (Plan 03).
 * The page owns the mutation; this component only renders the UI and callbacks.
 *
 * D-S-03: BulkActionBar bottom-anchored, appears on row selection.
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import ConfirmModal from '@/components/ui/ConfirmModal';

export type BulkAction = 'close' | 'block' | 'unblock';

export type TicketBulkBarProps = {
  selectedCount: number;
  onBulkAction: (action: BulkAction, blockedReason?: string | null) => void;
  onClearSelection: () => void;
  isPending?: boolean;
};

type ModalState =
  | null
  | { kind: 'close' }
  | { kind: 'unblock' }
  | { kind: 'block'; reason: string };

const MAX_REASON = 500;

export function TicketBulkBar({
  selectedCount,
  onBulkAction,
  onClearSelection,
  isPending,
}: TicketBulkBarProps) {
  const [modal, setModal] = useState<ModalState>(null);
  const [blockReason, setBlockReason] = useState('');

  const openBlock = useCallback(() => {
    setBlockReason('');
    setModal({ kind: 'block', reason: '' });
  }, []);

  const closeModal = useCallback(() => {
    setModal(null);
    setBlockReason('');
  }, []);

  const confirmClose = useCallback(() => {
    onBulkAction('close');
    closeModal();
  }, [onBulkAction, closeModal]);

  const confirmBlock = useCallback(() => {
    const trimmed = blockReason.trim();
    onBulkAction('block', trimmed || null);
    closeModal();
  }, [blockReason, onBulkAction, closeModal]);

  const confirmUnblock = useCallback(() => {
    onBulkAction('unblock');
    closeModal();
  }, [onBulkAction, closeModal]);

  if (selectedCount === 0) return null;

  return (
    <>
      {/* Bottom-anchored bulk bar */}
      <div
        role="toolbar"
        aria-label="Bulk actions"
        className={cn(
          'fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t border-border-subtle bg-surface px-6 py-3 shadow-lg',
          'animate-in slide-in-from-bottom-2',
        )}
      >
        <span className="text-sm font-medium text-text">
          {selectedCount} {selectedCount === 1 ? 'ticket' : 'tickets'} selected
        </span>

        <div className="ml-4 flex items-center gap-2">
          {/* Close action */}
          <button
            type="button"
            onClick={() => setModal({ kind: 'close' })}
            disabled={isPending}
            className="rounded-md border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm font-medium text-text hover:bg-surface hover:border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
          >
            Close
          </button>

          {/* Mark blocked */}
          <button
            type="button"
            onClick={openBlock}
            disabled={isPending}
            className="rounded-md border border-severity-critical/30 bg-severity-critical/10 px-3 py-1.5 text-sm font-medium text-[var(--color-severity-critical-on-soft)] hover:bg-severity-critical/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
          >
            Mark blocked
          </button>

          {/* Unblock */}
          <button
            type="button"
            onClick={() => setModal({ kind: 'unblock' })}
            disabled={isPending}
            className="rounded-md border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm font-medium text-text hover:bg-surface hover:border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:cursor-not-allowed disabled:opacity-50"
          >
            Unblock
          </button>
        </div>

        <button
          type="button"
          onClick={onClearSelection}
          className="ml-auto text-sm text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
        >
          Clear
        </button>
      </div>

      {/* Close confirmation modal */}
      {modal?.kind === 'close' && (
        <ConfirmModal
          open
          title="Close tickets"
          message={`Close ${selectedCount} selected ${selectedCount === 1 ? 'ticket' : 'tickets'}? This will mark them as closed in GetVul.`}
          confirmLabel="Close tickets"
          variant="warning"
          onConfirm={confirmClose}
          onCancel={closeModal}
        />
      )}

      {/* Unblock confirmation modal */}
      {modal?.kind === 'unblock' && (
        <ConfirmModal
          open
          title="Unblock tickets"
          message={`Unblock ${selectedCount} selected ${selectedCount === 1 ? 'ticket' : 'tickets'}? The blocked reason will be cleared.`}
          confirmLabel="Unblock"
          variant="info"
          onConfirm={confirmUnblock}
          onCancel={closeModal}
        />
      )}

      {/* Mark blocked modal — collects shared reason */}
      {modal?.kind === 'block' && (
        // Backdrop: role="presentation" removes landmark semantics from the overlay;
        // click or Esc on the backdrop dismisses the modal (keyboard parity).
        <div
          role="presentation"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeModal();
          }}
          onKeyDown={(e) => { if (e.key === 'Escape') closeModal(); }}
        >
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="block-modal-title"
          tabIndex={-1}
          className="w-full max-w-md rounded-xl border border-border-subtle bg-surface p-6 shadow-xl"
        >
            <h2 id="block-modal-title" className="text-lg font-semibold text-text">
              Mark tickets as blocked
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {selectedCount} {selectedCount === 1 ? 'ticket' : 'tickets'} will be marked blocked.
              Optionally add a shared reason.
            </p>
            <div className="mt-4">
              <label
                htmlFor="bulk-block-reason"
                className="block text-xs font-medium text-text-muted uppercase tracking-wide"
              >
                Reason (optional)
              </label>
              <input
                id="bulk-block-reason"
                type="text"
                value={blockReason}
                onChange={(e) => setBlockReason(e.target.value)}
                placeholder="What's blocking these tickets?"
                maxLength={MAX_REASON}
                className="mt-1.5 w-full rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
              />
              <div className="mt-1 text-right text-xs text-text-faint">
                {MAX_REASON - blockReason.length} left
              </div>
            </div>
            <div className="mt-5 flex gap-2 justify-end">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-md border border-border-subtle px-4 py-2 text-sm font-medium text-text-muted hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmBlock}
                className="rounded-md bg-severity-critical/10 border border-severity-critical/30 px-4 py-2 text-sm font-medium text-[var(--color-severity-critical-on-soft)] hover:bg-severity-critical/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                Mark blocked
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
