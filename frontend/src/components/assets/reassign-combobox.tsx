'use client';
/**
 * ReassignCombobox — UX-04-04 inline combobox bound to /users/directory.
 *
 * D-A-01 contract (12-CONTEXT.md):
 *   Esc          → onDone() (cancel, no mutation)
 *   Enter        → mutate(highlighted.email), then onDone() on success
 *   Click outside → onDone() (cancel, no mutation)
 *   ArrowUp/Down → move highlight inside the visible options
 *
 * Threat anchors:
 *   T-12-04 (XSS via reflected user fields): all reflected backend strings
 *     (display_name, email) are rendered as React text children — never via
 *     dangerouslySetInnerHTML.
 *   T-12-17 (per-keystroke DoS): the input is debounced 250ms before the
 *     query fires; combined with useAssignableUsers' `enabled: search.length >= 2`
 *     gate this caps the directory call rate.
 *
 * W9 hint: when the input is empty, the listbox shows a "start typing"
 * hint instead of paging the entire directory on first focus.
 */
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEventHandler } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { useAssignableUsers } from '@/lib/queries/use-assignable-users';
import { useReassignAsset } from '@/lib/queries/use-reassign-asset';
import { cn } from '@/lib/utils';

const DEBOUNCE_MS = 250;

export type ReassignComboboxProps = {
  assetId: string;
  initialEmail: string | null;
  onDone: () => void;
};

export function ReassignCombobox({ assetId, initialEmail, onDone }: ReassignComboboxProps) {
  const [input, setInput] = useState(initialEmail ?? '');
  const [debounced, setDebounced] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const users = useAssignableUsers(debounced);
  const mutation = useReassignAsset(assetId);

  // Auto-focus the input the moment the card flips into edit mode.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // T-12-17 debounce: hold the value for 250ms before passing to the hook.
  // The hook itself adds an `enabled: search.length >= 2` gate, so single-
  // character scans still produce zero network traffic.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(input), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  // D-A-01: click-outside cancels (no mutation). Listen on document, not
  // window — Toast portal lives at document level and clicks inside it
  // would otherwise cancel the in-flight UX.
  useEffect(() => {
    const onMouseDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        onDone();
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [onDone]);

  const items = users.data?.users ?? [];

  const commit = (email: string) => {
    if (!email) return;
    mutation.mutate(email, {
      onSuccess: () => onDone(),
    });
  };

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onDone();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = items[highlightIdx];
      commit(target?.email ?? input);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    }
  };

  // W9: empty input → hint only. >=2 chars triggers the network call
  // (gate lives in useAssignableUsers).
  const showHint = debounced.trim().length < 2;

  return (
    <div
      ref={containerRef}
      onKeyDown={onKeyDown}
      className="space-y-2"
      role="combobox"
      aria-expanded="true"
      aria-haspopup="listbox"
      data-testid="reassign-combobox"
    >
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          setHighlightIdx(0);
        }}
        disabled={mutation.isPending}
        placeholder="Search by name or email..."
        className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:opacity-50"
        aria-label="Search assignable users"
      />

      {mutation.error && (
        <div
          role="alert"
          className="rounded-md border border-severity-critical bg-surface px-3 py-2 text-xs text-severity-critical"
        >
          {(mutation.error as Error).message || 'Reassign failed'}
        </div>
      )}

      <ul role="listbox" className="max-h-48 overflow-y-auto" data-testid="reassign-list">
        {showHint && (
          <li className="px-3 py-2 text-xs text-text-muted">
            Start typing a name or email to search...
          </li>
        )}
        {!showHint && users.isLoading && (
          <li className="px-3 py-2 text-xs text-text-muted">Loading...</li>
        )}
        {!showHint && !users.isLoading && items.length === 0 && (
          <li className="px-3 py-2 text-xs text-text-muted">
            No users match &quot;{debounced}&quot;
          </li>
        )}
        {items.map((u, idx) => (
          <li
            key={u.email}
            role="option"
            aria-selected={idx === highlightIdx}
            onMouseEnter={() => setHighlightIdx(idx)}
            onClick={() => commit(u.email)}
            className={cn(
              'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
              idx === highlightIdx ? 'bg-surface' : 'hover:bg-surface',
            )}
            data-testid={`reassign-option-${idx}`}
          >
            <Avatar
              name={u.display_name ?? undefined}
              email={u.email}
              size={24}
            />
            <span className="flex flex-col">
              <span className="text-text">{u.display_name ?? u.email}</span>
              <span className="text-[10px] font-mono text-text-muted">{u.email}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
