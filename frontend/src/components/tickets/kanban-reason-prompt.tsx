'use client';
/**
 * KanbanReasonPrompt — inline optional-reason popover (D-DRAG-02).
 *
 * Shown after a card is dropped into the Blocked column: lets the analyst
 * optionally record why the ticket is blocked before the mutation fires.
 * Mirrors blocked-toggle.tsx's inline editor exactly:
 * - Save → onSave(reason.trim() || null) (whitespace-only → null).
 * - Cancel → onCancel() (never calls onSave — no mutation).
 * - Enter → Save; Escape → Cancel.
 * - maxLength=500 mirrors the backend Pydantic bound (T-18-05).
 * - Autofocus is deferred to the next tick (Pitfall 6) to avoid racing
 *   dnd-kit's post-drop focus restore.
 *
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { microcopy } from './microcopy';

const MAX_REASON = 500;

export type KanbanReasonPromptProps = {
  ticketLabel: string;
  onSave: (reason: string | null) => void;
  onCancel: () => void;
};

export function KanbanReasonPrompt({ ticketLabel, onSave, onCancel }: KanbanReasonPromptProps) {
  const [reason, setReason] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, []);

  const handleSave = () => {
    onSave(reason.trim() || null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  };

  return (
    <div
      role="dialog"
      aria-label={`Blocked reason for ${ticketLabel}`}
      className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface p-3"
    >
      <input
        ref={inputRef}
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={microcopy.blockedPrompt}
        maxLength={MAX_REASON}
        className="min-w-0 flex-1 rounded-lg border border-border-subtle bg-surface-2 px-3 py-1.5 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
        aria-label="Blocked reason"
      />
      <button
        type="button"
        onClick={handleSave}
        className="rounded-lg bg-severity-critical/10 px-3 py-1.5 text-xs font-medium text-severity-critical hover:bg-severity-critical/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
      >
        {microcopy.blockedSave}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-muted hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
      >
        {microcopy.blockedCancel}
      </button>
    </div>
  );
}
