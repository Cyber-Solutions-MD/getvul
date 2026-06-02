/**
 * ActivityTimeline — day-grouped comments + provider sync events.
 *
 * D-C-01 / D-C-04:
 * - Sort entries ascending by createdAt (oldest top).
 * - Group by calendar day with headers: "Today" / "Yesterday" / "MMM D".
 * - Comment rows: author + body in <p class="whitespace-pre-wrap"> (plain text, newlines preserved).
 * - Sync rows: muted label ("Synced from Jira — moved to In progress").
 * - Plain-text only — React text nodes escape user content (no innerHTML tricks).
 *
 * T-13-19 (Stored XSS): comment body and author displayed as React text nodes only.
 * T-13-20/21: body is validated server-side (Pydantic); client renders as-is (no re-validation needed).
 */
'use client';

import { Avatar } from '@/components/ui/Avatar';

export type TimelineEntry =
  | {
      kind: 'comment';
      id: string;
      author: string | null;
      body: string;
      createdAt: string;
    }
  | {
      kind: 'sync';
      id: string;
      label: string;
      createdAt: string;
    };

// Day header label: "Today", "Yesterday", or "MMM D" (e.g. "Jan 15")
function dayLabel(isoDate: string): string {
  const entryDate = new Date(isoDate);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(entryDate, today)) return 'Today';
  if (sameDay(entryDate, yesterday)) return 'Yesterday';

  // "Jan 15" style — locale-aware short format
  return entryDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Group entries by calendar day key (YYYY-MM-DD in UTC)
function groupByDay(entries: TimelineEntry[]): Array<{ dayKey: string; label: string; entries: TimelineEntry[] }> {
  const groups: Map<string, { label: string; entries: TimelineEntry[] }> = new Map();
  for (const entry of entries) {
    const date = new Date(entry.createdAt);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    if (!groups.has(key)) {
      groups.set(key, { label: dayLabel(entry.createdAt), entries: [] });
    }
    groups.get(key)!.entries.push(entry);
  }
  return Array.from(groups.entries()).map(([dayKey, v]) => ({ dayKey, ...v }));
}

// Relative timestamp display (e.g., "12m ago", "2h ago")
function relativeTime(isoDate: string): string {
  const ms = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function CommentRow({ entry }: { entry: Extract<TimelineEntry, { kind: 'comment' }> }) {
  return (
    <li className="flex gap-3">
      {/* Timeline dot — violet per interaction-patterns.md (comments) */}
      <div className="relative flex flex-col items-center">
        <div className="flex size-7 items-center justify-center rounded-full border-2 border-violet/40 bg-violet-soft text-violet z-10">
          <Avatar
            name={entry.author ?? undefined}
            size={20}
          />
        </div>
      </div>
      <div className="flex-1 pb-4">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-text">
            {entry.author ?? 'Unknown'}
          </span>
          <span className="font-mono text-xs text-text-faint">
            {relativeTime(entry.createdAt)}
          </span>
        </div>
        {/* T-13-19: whitespace-pre-wrap + React text node = XSS-safe, newlines preserved */}
        <p className="whitespace-pre-wrap mt-1 text-sm text-text-muted">{entry.body}</p>
      </div>
    </li>
  );
}

function SyncRow({ entry }: { entry: Extract<TimelineEntry, { kind: 'sync' }> }) {
  return (
    <li className="flex gap-3">
      {/* Timeline dot — default (system event) */}
      <div className="relative flex flex-col items-center">
        <div className="flex size-7 items-center justify-center rounded-full border-2 border-border-subtle bg-surface z-10">
          <span className="size-1.5 rounded-full bg-text-muted" />
        </div>
      </div>
      <div className="flex-1 pb-4">
        <p className="text-sm text-text-muted">{entry.label}</p>
        <p className="font-mono text-xs text-text-faint">{relativeTime(entry.createdAt)}</p>
      </div>
    </li>
  );
}

export type ActivityTimelineProps = {
  entries: TimelineEntry[];
};

export function ActivityTimeline({ entries }: ActivityTimelineProps) {
  // Sort ascending by createdAt (oldest top — D-C-04)
  const sorted = [...entries].sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );

  const groups = groupByDay(sorted);

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-text-faint py-4">No activity yet.</p>
    );
  }

  return (
    <div className="relative">
      {/* Vertical line — per interaction-patterns.md ::before pattern, approximated with a div */}
      <div
        aria-hidden
        className="absolute left-3.5 top-3.5 bottom-3.5 w-px bg-border-subtle"
      />

      {groups.map((group) => (
        <div key={group.dayKey}>
          {/* Day header */}
          <p
            data-day-header
            className="mb-2 text-xs font-medium uppercase tracking-wider text-text-faint"
          >
            {group.label}
          </p>

          <ul role="list" className="space-y-0">
            {group.entries.map((entry) =>
              entry.kind === 'comment' ? (
                <CommentRow key={entry.id} entry={entry} />
              ) : (
                <SyncRow key={entry.id} entry={entry} />
              ),
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}
