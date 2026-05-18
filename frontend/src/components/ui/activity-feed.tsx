'use client';
import {
  ShieldAlert,
  Clock,
  WifiOff,
  TrendingDown,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

// D-P-04 + D-A-01..05: Recent-activity feed primitive for the dashboard right rail.
// Pure presentation — caller fetches items (Plan 02's useRecentNotifications) and
// passes them in. Primitive owns row layout, category → icon-variant mapping, and
// relative-time formatting via Intl.RelativeTimeFormat (copy-voice "Xm ago").

export type ActivityCategory =
  | 'new_critical_vuln'
  | 'sla_breach'
  | 'sync_failure'
  | 'risk_change';

export type ActivityItem = {
  id: string;
  category: ActivityCategory;
  title: string;
  body?: string | null;
  /** ISO timestamp. */
  occurred_at: string;
  href?: string;
};

export type ActivityFeedProps = {
  items: ActivityItem[];
  emptyCopy?: string;
};

// D-A-01 verbatim mapping: new_critical_vuln → pink, sla_breach → amber,
// sync_failure → violet, risk_change → success. Each consumes Tailwind tokens
// declared in tailwind.config.ts which themselves consume sunset.css CSS vars.
// No hex literals here (T-10-19).
const CATEGORY_META: Record<
  ActivityCategory,
  { Icon: LucideIcon; tintClass: string }
> = {
  new_critical_vuln: {
    Icon: ShieldAlert,
    tintClass: 'bg-pink-soft text-pink',
  },
  sla_breach: {
    Icon: Clock,
    tintClass: 'bg-amber-soft text-amber',
  },
  sync_failure: {
    Icon: WifiOff,
    tintClass: 'bg-violet-soft text-violet',
  },
  risk_change: {
    Icon: TrendingDown,
    tintClass: 'bg-success-soft text-success',
  },
};

/**
 * Format an ISO timestamp as "Xm ago" / "Xh ago" / "Xd ago" using
 * Intl.RelativeTimeFormat. Per RESEARCH "Don't Hand-Roll" table — built-in
 * Intl avoids brittle date math.
 */
function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  // Guard against invalid dates — Intl.RelativeTimeFormat throws on non-finite
  // input, which would crash the whole rail. Bad data → em-dash fallback.
  if (!Number.isFinite(then)) return '—';
  const now = Date.now();
  const diffSec = Math.round((then - now) / 1000);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const absSec = Math.abs(diffSec);
  if (absSec < 60) return rtf.format(diffSec, 'second');
  if (absSec < 3600) return rtf.format(Math.round(diffSec / 60), 'minute');
  if (absSec < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour');
  return rtf.format(Math.round(diffSec / 86400), 'day');
}

export function ActivityFeed({
  items,
  emptyCopy = "No recent activity. We'll show events here as they happen.",
}: ActivityFeedProps) {
  if (items.length === 0) {
    // D-A-03: empty state uses sentence-case copy with no exclamation per copy-voice.md.
    // T-10-16: React default escaping applies to the emptyCopy string.
    return <p className="text-sm text-text-muted">{emptyCopy}</p>;
  }
  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const meta = CATEGORY_META[item.category];
        const Icon = meta.Icon;
        const inner = (
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'grid h-7 w-7 shrink-0 place-items-center rounded-md',
                meta.tintClass
              )}
              aria-hidden="true"
            >
              <Icon className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-text">{item.title}</p>
              {item.body && (
                <p className="truncate text-xs text-text-muted">{item.body}</p>
              )}
              <p
                className="font-mono text-xs text-text-faint"
                suppressHydrationWarning
              >
                {relativeTime(item.occurred_at)}
              </p>
            </div>
          </div>
        );
        return (
          <li key={item.id} data-testid={`row-${item.category}`}>
            {item.href ? (
              // T-10-17: href is server-provided; Next <Link> rejects unsupported
              // protocols at build. Backend contract restricts to internal routes.
              <Link
                href={item.href}
                className="block rounded-md p-1 hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
              >
                {inner}
              </Link>
            ) : (
              inner
            )}
          </li>
        );
      })}
    </ul>
  );
}
