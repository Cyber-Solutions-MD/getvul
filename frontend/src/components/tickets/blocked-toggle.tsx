/**
 * BlockedToggle — shared inline blocked-reason editor.
 *
 * D-P-03 / D-P-02: Shared by drill footer (Plan 05) and detail right-rail (Plan 08).
 * This component is a controlled UI shell — the actual TanStack mutation lives in the consumer.
 *
 * Behavior:
 * - Not-blocked: renders microcopy.markBlocked button.
 *   Click → inline text input (max 500 chars, microcopy.blockedPrompt) + Save/Cancel.
 *   Save → onToggle({ blocked: true, blockedReason: trimmedReason || null })
 *   Cancel → collapse without calling onToggle.
 * - Blocked: renders Unblock button.
 *   Click → onToggle({ blocked: false, blockedReason: null }) immediately (no reason prompt).
 * - pending=true → disable all controls (optimistic in-flight).
 *
 * Keyboard: Esc cancels the inline editor; Enter saves.
 * No inline hex — all colors via Tailwind sunset tokens.
 *
 * T-13-20: maxLength=500 mirrors backend Pydantic bound.
 * T-13-21: whitespace-only reason coerces to null before onToggle.
 */
'use client';

import { useState, useCallback, useRef } from 'react';
import { microcopy } from './microcopy';

export type BlockedToggleChange = {
  blocked: boolean;
  blockedReason: string | null;
};

export type BlockedToggleProps = {
  blocked: boolean;
  blockedReason: string | null;
  onToggle: (next: BlockedToggleChange) => void;
  pending?: boolean;
};

const MAX_REASON = 500;

export function BlockedToggle({
  blocked,
  blockedReason,
  onToggle,
  pending = false,
}: BlockedToggleProps) {
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const openEditor = useCallback(() => {
    setReason('');
    setEditing(true);
    // Focus the input on next tick
    setTimeout(() => inputRef.current?.focus(), 0);
  }, []);

  const closeEditor = useCallback(() => {
    setEditing(false);
    setReason('');
  }, []);

  const handleSave = useCallback(() => {
    const trimmed = reason.trim();
    onToggle({ blocked: true, blockedReason: trimmed || null });
    closeEditor();
  }, [reason, onToggle, closeEditor]);

  const handleUnblock = useCallback(() => {
    onToggle({ blocked: false, blockedReason: null });
  }, [onToggle]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeEditor();
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSave();
      }
    },
    [closeEditor, handleSave],
  );

  // Blocked state: show Unblock button
  if (blocked) {
    return (
      <div className="flex items-center gap-2">
        {/* Blocked indicator */}
        <span className="inline-flex items-center gap-1.5 rounded-full border border-severity-critical/40 bg-severity-critical/10 px-2 py-0.5 text-xs text-[var(--color-severity-critical-on-soft)]">
          <span className="size-1.5 rounded-full bg-current" />
          Blocked
          {blockedReason && (
            // Intentionally full-opacity: the prior `/80` de-emphasis is dropped.
            // Light mode needs the full-strength on-soft token (#991B1B) to clear AA
            // contrast, and Tailwind 3.4 does not reliably emit an alpha modifier
            // (`/80`) on a `var()` arbitrary value. Dark mode is a deliberate no-op
            // token, so it also renders at 100% — accepted; no a11y regression.
            <span className="font-normal text-[var(--color-severity-critical-on-soft)]">— {blockedReason}</span>
          )}
        </span>
        <button
          type="button"
          onClick={handleUnblock}
          disabled={pending}
          className="text-xs text-text-muted underline-offset-2 hover:text-text hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40"
        >
          {microcopy.unblock}
        </button>
      </div>
    );
  }

  // Not-blocked + editor closed: show Mark blocked button
  if (!editing) {
    return (
      <button
        type="button"
        onClick={openEditor}
        disabled={pending}
        className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-muted hover:border-severity-critical/40 hover:text-[var(--color-severity-critical-on-soft)] focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40"
      >
        {microcopy.markBlocked}
      </button>
    );
  }

  // Inline editor — Phase 12 reassign-combobox shape
  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={microcopy.blockedPrompt}
        maxLength={MAX_REASON}
        disabled={pending}
        className="min-w-0 flex-1 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:opacity-50"
        aria-label="Blocked reason"
      />
      <button
        type="button"
        onClick={handleSave}
        disabled={pending}
        className="rounded-lg bg-severity-critical/10 px-3 py-1.5 text-xs font-medium text-[var(--color-severity-critical-on-soft)] hover:bg-severity-critical/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40"
      >
        {microcopy.blockedSave}
      </button>
      <button
        type="button"
        onClick={closeEditor}
        disabled={pending}
        className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-muted hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:cursor-not-allowed disabled:opacity-40"
      >
        {microcopy.blockedCancel}
      </button>
    </div>
  );
}
