'use client';
/**
 * ApproverCombobox — Phase 39 Plan 07 (EXC-01 D-08) searchable tenant-user
 * picker for the exception-grant dialog's Approver field.
 *
 * Pitfall 6: this is explicitly NOT a wrapper around reassign-combobox.tsx
 * (that import is grep-gated at 0 occurrences). It copies that component's
 * 250ms debounce effect, useAssignableUsers(debounced) data source,
 * highlightIdx + ArrowUp/ArrowDown/Enter/Escape keyboard handling, and the
 * full WAI-ARIA combobox markup (role=combobox on the input with
 * aria-controls/expanded/autocomplete/activedescendant; role=listbox/option;
 * Avatar + name/email <li>) — but the data-flow is entirely different: this
 * is ONE field inside a larger single-submit form (the grant dialog), so it
 * takes value/onSelect props and fires NO internal mutation on selection —
 * the analog's own per-selection reassign-mutation call (bound to a single
 * asset) is deliberately not reproduced here at all.
 *
 * Loading/error states (39-UI-SPEC.md UI Considerations, grant-form loading/
 * error rows):
 *   loading → once a search is in flight (2+ chars typed, mirroring the
 *             W9 >=2-char gate use-assignable-users.ts already enforces),
 *             the input disables and its placeholder swaps to
 *             "Loading approvers…" until the request resolves.
 *   error   → "Approvers failed to load. Retry." rendered inline below the
 *             input (a distinct scoped string from the grant dialog's own
 *             precondition/expiry/generic submit errors).
 */
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEventHandler } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { useAssignableUsers } from '@/lib/queries/use-assignable-users';
import type { DirectoryUser } from '@/lib/queries/use-asset-detail';
import { cn } from '@/lib/utils';

const DEBOUNCE_MS = 250;

// /users/directory's raw JSON includes `id` (backend/app/users/router.py
// list_directory_users: `"id": str(u.id)`), but the shared DirectoryUser
// type (use-asset-detail.ts, owned by the Phase 12 asset-detail surface)
// never declared it — that consumer only ever needed email/display_name.
// Widened LOCALLY here rather than editing the shared use-asset-detail.ts
// (outside this plan's files_modified): the exception grant payload's
// approver_user_id needs the real user FK, not just an email string.
export type ApproverUser = DirectoryUser & { id: string };

export type SelectedApprover = { id: string; email: string; display_name: string | null };

export type ApproverComboboxProps = {
  value: SelectedApprover | null;
  onSelect: (user: SelectedApprover) => void;
};

export function ApproverCombobox({ value, onSelect }: ApproverComboboxProps) {
  const [input, setInput] = useState(value ? (value.display_name ?? value.email) : '');
  const [debounced, setDebounced] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  // Unlike reassign-combobox (which unmounts entirely on selection via its
  // caller's onDone()), this combobox stays mounted as a persistent form
  // field — so the suggestion area defaults OPEN (matching
  // reassign-combobox's own unconditional listbox rendering, including the
  // "start typing" hint being visible pre-focus) and is only explicitly
  // closed after a commit or Escape, re-opening on the next focus/keystroke.
  const [isOpen, setIsOpen] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const users = useAssignableUsers(debounced);

  // T-12-17-class debounce: hold the value for 250ms before passing to the
  // hook, mirroring reassign-combobox.tsx exactly. The hook's own
  // `enabled: search.length >= 2` gate (W9) trims single-character scans.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(input), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input]);

  // Keep the visible text in sync with an EXTERNAL value reset (the grant
  // dialog clears `approver` back to null every time it re-opens for a new
  // finding) — this is a controlled field embedded in a larger form, not a
  // one-shot inline editor that unmounts on completion like
  // reassign-combobox's caller does. Harmless no-op while the user is
  // actively typing (before any selection, `value` doesn't change).
  useEffect(() => {
    setInput(value ? (value.display_name ?? value.email) : '');
  }, [value]);

  const items = (users.data?.users ?? []) as ApproverUser[];
  const showHint = debounced.trim().length < 2;
  const isLoadingResults = !showHint && users.isLoading;

  const commit = (user: ApproverUser) => {
    onSelect(user);
    setInput(user.display_name ?? user.email);
    setIsOpen(false);
  };

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
      inputRef.current?.blur();
    } else if (e.key === 'Enter') {
      if (!isOpen) return;
      e.preventDefault();
      const target = items[highlightIdx];
      if (!target) return;
      commit(target);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setIsOpen(true);
      setHighlightIdx((i) => Math.min(i + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    }
  };

  const listboxId = 'approver-listbox';
  const activeOptId = isOpen && items[highlightIdx] ? `approver-opt-${highlightIdx}` : undefined;

  return (
    <div
      ref={containerRef}
      onKeyDown={onKeyDown}
      className="space-y-2"
      data-testid="approver-combobox"
    >
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          setHighlightIdx(0);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        disabled={isLoadingResults}
        placeholder={isLoadingResults ? 'Loading approvers…' : 'Search teammates…'}
        className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet disabled:opacity-50"
        role="combobox"
        aria-controls={listboxId}
        aria-expanded={isOpen}
        aria-autocomplete="list"
        aria-activedescendant={activeOptId}
        aria-label="Search approvers"
      />

      {users.isError && (
        <p role="alert" className="text-xs text-danger">
          Approvers failed to load. Retry.
        </p>
      )}

      {isOpen && (
        <ul
          id={listboxId}
          role="listbox"
          className="max-h-48 overflow-y-auto rounded-md border border-border-subtle bg-surface"
          data-testid="approver-list"
        >
          {showHint && (
            <li className="px-3 py-2 text-xs text-text-muted">
              Start typing a name or email to search…
            </li>
          )}
          {!showHint && isLoadingResults && (
            <li className="px-3 py-2 text-xs text-text-muted">Loading approvers…</li>
          )}
          {!showHint && !isLoadingResults && items.length === 0 && (
            <li className="px-3 py-2 text-xs text-text-muted">
              No users match &quot;{debounced}&quot;
            </li>
          )}
          {items.map((u, idx) => (
            <li
              key={u.id}
              id={`approver-opt-${idx}`}
              role="option"
              aria-selected={idx === highlightIdx}
              onMouseEnter={() => setHighlightIdx(idx)}
              onClick={() => commit(u)}
              className={cn(
                'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                idx === highlightIdx ? 'bg-surface-2' : 'hover:bg-surface-2',
              )}
              data-testid={`approver-option-${idx}`}
            >
              <Avatar name={u.display_name ?? undefined} email={u.email} size={24} />
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-text">{u.display_name ?? u.email}</span>
                <span className="truncate text-[10px] font-mono text-text-muted">{u.email}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
