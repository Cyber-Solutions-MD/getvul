/**
 * WatcherStack — avatar stack with +N overflow chip and popover.
 *
 * UX-05-05 / D-W-04:
 * - Sort: assignee → reporter → watchers (chronological by createdAt)
 * - Dedupe by userId; prefer strongest role (assignee > reporter > watcher)
 * - Render first 3 as Avatar (28px, overlapping -ml-2 ring)
 * - If >3 entries: render a <button> +N chip that toggles a popover
 *   listing all watchers (displayName + role tag)
 * - Popover opens on click/focus, closes on blur/Esc — keyboard accessible
 * - Empty → microcopy.watchersEmpty
 *
 * T-13-19 (XSS): displayNames rendered as Avatar text nodes (XSS-safe).
 */
'use client';

import { useState, useRef, useCallback } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';

export type Watcher = {
  userId: string;
  displayName: string | null;
  email?: string | null;
  role?: 'assignee' | 'reporter' | 'watcher';
  createdAt?: string;
};

// Role priority: lower number = stronger (assignee wins)
const ROLE_PRIORITY: Record<NonNullable<Watcher['role']>, number> = {
  assignee: 0,
  reporter: 1,
  watcher: 2,
};

function roleOf(r: Watcher['role']): NonNullable<Watcher['role']> {
  return r ?? 'watcher';
}

function dedupeAndSort(watchers: Watcher[]): Watcher[] {
  // Dedupe by userId, preferring the strongest role.
  const map = new Map<string, Watcher>();
  for (const w of watchers) {
    const existing = map.get(w.userId);
    if (!existing) {
      map.set(w.userId, w);
    } else {
      // Keep whichever has the stronger (lower-priority-number) role.
      if (ROLE_PRIORITY[roleOf(w.role)] < ROLE_PRIORITY[roleOf(existing.role)]) {
        map.set(w.userId, { ...w });
      }
    }
  }

  // Sort: assignee first, reporter second, then watchers ascending by createdAt.
  return Array.from(map.values()).sort((a, b) => {
    const pa = ROLE_PRIORITY[roleOf(a.role)];
    const pb = ROLE_PRIORITY[roleOf(b.role)];
    if (pa !== pb) return pa - pb;
    // Same role → sort chronologically by createdAt (ascending = oldest first)
    const ta = a.createdAt ?? '';
    const tb = b.createdAt ?? '';
    return ta.localeCompare(tb);
  });
}

const VISIBLE_COUNT = 3;
const MAX_POPOVER = 50;

export function WatcherStack({ watchers }: { watchers: Watcher[] }) {
  const [open, setOpen] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);

  const sorted = dedupeAndSort(watchers).slice(0, MAX_POPOVER);
  const visible = sorted.slice(0, VISIBLE_COUNT);
  const overflow = sorted.length - VISIBLE_COUNT;

  const toggle = useCallback(() => setOpen((v) => !v), []);
  const close = useCallback(() => setOpen(false), []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
      }
    },
    [close],
  );

  if (sorted.length === 0) {
    return (
      <span className="text-xs text-text-faint">{microcopy.watchersEmpty}</span>
    );
  }

  return (
    // onKeyDown on the wrapper (no role) captures Escape bubbled from within the popup
    // without attaching handlers to the non-interactive dialog element (jsx-a11y compliant)
    <div className="relative inline-flex items-center gap-1" onKeyDown={handleKeyDown}>
      {/* Avatar stack — overlapping avatars with negative margin ring */}
      <div className="flex items-center">
        {visible.map((w, i) => (
          <span
            key={w.userId}
            className={cn('ring-2 ring-surface rounded-full', i > 0 && '-ml-2')}
            title={w.displayName ?? w.email ?? 'Unknown'}
          >
            <Avatar
              name={w.displayName ?? undefined}
              email={w.email ?? undefined}
              size={28}
            />
          </span>
        ))}
      </div>

      {/* Overflow chip — keyboard accessible button */}
      {overflow > 0 && (
        <button
          ref={chipRef}
          type="button"
          aria-label={`+${overflow} more watchers`}
          aria-expanded={open}
          aria-haspopup="listbox"
          onClick={toggle}
          className="ml-1 inline-flex items-center justify-center rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs font-medium text-text-muted hover:border-border hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-violet"
        >
          +{overflow}
        </button>
      )}

      {/* Popover — all watchers list */}
      {open && (
        <div
          role="dialog"
          aria-label="All watchers"
          tabIndex={-1}
          className="absolute left-0 top-full z-50 mt-2 min-w-[200px] rounded-xl border border-border-subtle bg-surface-2 p-2 shadow-lg"
        >
          <ul role="list" className="space-y-1">
            {sorted.map((w) => (
              <li
                key={w.userId}
                className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-text"
              >
                <Avatar
                  name={w.displayName ?? undefined}
                  email={w.email ?? undefined}
                  size={20}
                />
                <span className="flex-1 truncate">
                  {w.displayName ?? w.email ?? 'Unknown'}
                </span>
                {w.role && w.role !== 'watcher' && (
                  <span className="rounded-full border border-border-subtle bg-surface px-1.5 py-0.5 text-xs text-text-muted capitalize">
                    {w.role}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
