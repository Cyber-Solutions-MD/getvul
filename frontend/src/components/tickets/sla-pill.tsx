/**
 * SlaPill — client-side SLA tier computation from a due timestamp.
 *
 * D-SLA-04: Tiers computed CLIENT-SIDE from ticket.sla_due_at (no backend "state" column).
 * Thresholds defined ONCE here (Pitfall 5 — single source prevents tier drift between surfaces).
 *
 * Tiers:
 *   Overdue  < now              → severity-critical (red)
 *   Soon     < now + 7 days     → severity-high (amber)
 *   OK       >= now + 7 days    → severity-low (green)
 *   Unknown  dueAt = null       → text-faint (gray)
 *
 * No inline hex — all colors via Tailwind tokens.
 */
import { cn } from '@/lib/utils';

// 7-day threshold in milliseconds (D-SLA-04 — defined ONCE here).
//
// WR-03 (intentional, documented): the "soon" window is a single flat 7-day
// band, NOT derived from the per-severity SLA budgets the backend assigns
// (CRITICAL 3d / HIGH 14d / ... / INFO 180d). The pill answers "is this due
// imminently?" on a uniform scale across all severities — the severity itself
// is already surfaced by the Severity column/glyph, so weighting the SLA band
// by severity too would double-encode it. The backend SLA chip filter
// (list_tickets, WR-01) uses the SAME 7-day window so the chip and the pill
// agree. If product later wants per-severity bands, surface a backend-computed
// tier and switch this constant to read it.
const SOON_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000;

type SlaTier = 'overdue' | 'soon' | 'ok' | 'unknown';

interface TierConfig {
  classes: string;
  label: (due: Date | null) => string;
}

const TIER_CONFIG: Record<SlaTier, TierConfig> = {
  overdue: {
    classes:
      'border-severity-critical/30 bg-severity-critical/10 text-severity-critical',
    label: (due) => {
      if (!due) return 'Overdue';
      const diffMs = Date.now() - due.getTime();
      const hours = Math.floor(diffMs / (1000 * 60 * 60));
      if (hours < 24) return `−${hours}h`;
      const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      return `−${days}d`;
    },
  },
  soon: {
    classes:
      'border-severity-high/30 bg-severity-high/10 text-[var(--color-severity-high-on-soft)]',
    label: (due) => {
      if (!due) return 'Soon';
      const diffMs = due.getTime() - Date.now();
      const hours = Math.floor(diffMs / (1000 * 60 * 60));
      if (hours < 24) return `${hours}h left`;
      const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      return `${days}d left`;
    },
  },
  ok: {
    classes:
      'border-severity-low/30 bg-severity-low/10 text-severity-low',
    label: (due) => {
      if (!due) return 'OK';
      const diffMs = due.getTime() - Date.now();
      const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      return `${days}d left`;
    },
  },
  unknown: {
    classes: 'border-border-subtle bg-surface-2 text-text-faint',
    label: () => 'Unknown',
  },
};

function computeTier(dueAt: string | null): { tier: SlaTier; due: Date | null } {
  if (!dueAt) return { tier: 'unknown', due: null };
  const due = new Date(dueAt);
  const now = Date.now();
  if (due.getTime() < now) return { tier: 'overdue', due };
  if (due.getTime() < now + SOON_THRESHOLD_MS) return { tier: 'soon', due };
  return { tier: 'ok', due };
}

export type SlaPillProps = {
  /** ISO timestamp (or null). Tier computed client-side. */
  dueAt: string | null;
  className?: string;
};

export function SlaPill({ dueAt, className }: SlaPillProps) {
  const { tier, due } = computeTier(dueAt);
  const config = TIER_CONFIG[tier];

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-mono',
        config.classes,
        className,
      )}
    >
      {config.label(due)}
    </span>
  );
}
