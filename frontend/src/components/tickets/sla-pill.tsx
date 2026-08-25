/**
 * SlaPill — dual-path SLA state: client-computed (tickets, legacy) OR
 * server-truth (findings, Phase 36 D-11).
 *
 * D-SLA-04 (tickets, unchanged): when `dueAt` is passed WITHOUT `state`,
 * tiers are computed CLIENT-SIDE from ticket.sla_due_at (no backend "state"
 * column existed at the time). Thresholds defined ONCE here (Pitfall 5 —
 * single source prevents tier drift between surfaces).
 *
 * Phase 36 / D-01/D-02/D-11 (findings, NEW): when the optional `state` prop
 * is present, it is the server-computed risk-tier SLA state
 * (on_track/approaching/breached/not_tracked) and is rendered DIRECTLY —
 * `computeTier()` is skipped entirely. The server is authoritative; this
 * component never re-derives the tier formula client-side (T-36-01,
 * Anti-Pattern). Existing ticket call sites (tickets-table.tsx,
 * kanban-card.tsx, ticket-drill-content.tsx) never pass `state`, so their
 * behavior is byte-identical to before this phase.
 *
 * Tiers (dueAt-only path):
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
      'border-severity-critical/30 bg-severity-critical/10 text-[var(--color-severity-critical-on-soft)]',
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

/** Phase 36 / D-11: server-computed finding SLA state. */
export type SlaPillState = 'on_track' | 'approaching' | 'breached' | 'not_tracked';

// Direct 1:1 map onto the existing 4-tone vocabulary (UI-SPEC "Color state->tone
// table") — never a new tone. not_tracked maps to the same faint tone as
// `unknown`, but renders distinct copy (see SlaPill below): "No SLA" (a below-
// floor / not-tracked signal, D-12) is a different situation from "Unknown"
// (a client-side computeTier() null-dueAt signal) even though the tone matches.
const SERVER_STATE_TO_TIER: Record<SlaPillState, SlaTier> = {
  on_track: 'ok',
  approaching: 'soon',
  breached: 'overdue',
  not_tracked: 'unknown',
};

export type SlaPillProps = {
  /** ISO timestamp (or null). Tier computed client-side when `state` is absent. */
  dueAt: string | null;
  /**
   * Server-computed tier-engine state (Phase 36 / D-01/D-02/D-11). When
   * present, this is rendered directly and `computeTier()` is never
   * consulted — the server is authoritative, this component does not
   * re-derive the tier formula (T-36-01). When absent, falls back to the
   * original client-side `dueAt` path unchanged (ticket call sites keep
   * their existing behavior).
   */
  state?: SlaPillState;
  className?: string;
};

export function SlaPill({ dueAt, state, className }: SlaPillProps) {
  let tier: SlaTier;
  let label: string;

  if (state) {
    tier = SERVER_STATE_TO_TIER[state];
    // D-12 / UI-SPEC Surface E2: not_tracked always renders "No SLA" — distinct
    // copy from the client-computed "unknown" tier's "Unknown", even though
    // both share the same faint tone (see SERVER_STATE_TO_TIER comment above).
    label = state === 'not_tracked' ? 'No SLA' : TIER_CONFIG[tier].label(dueAt ? new Date(dueAt) : null);
  } else {
    const computed = computeTier(dueAt);
    tier = computed.tier;
    label = TIER_CONFIG[tier].label(computed.due);
  }

  const config = TIER_CONFIG[tier];

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-mono',
        config.classes,
        className,
      )}
    >
      {label}
    </span>
  );
}
