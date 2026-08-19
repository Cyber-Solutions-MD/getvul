'use client';
/**
 * ExceptionsTable — Phase 39 Plan 06 (EXC-02/EXC-03) /dashboard/exceptions
 * manage-only list table; Plan 07 (D-17) wires the Revoke column below.
 *
 * Columns (39-UI-SPEC.md Layout & Entry Points §3): Type (status-pill family)
 * · CVE/target (mono, truncate+title) · Scope label · Approver (avatar+name,
 * truncate+title) · Granted (relative "Nd ago", tabular-nums) · Expires
 * (sla-pill soon/ok, or a muted "Revoked"/"Expired" chip for historical rows)
 * · Revoke (live-wired, see below).
 *
 * Row click/Enter/Space toggles a LOCAL inline-accordion expand (full
 * justification + who-approved/when audit metadata) — this component never
 * imports next/navigation's router hook and never opens a drill panel
 * (UI-SPEC Layout §3: "the record has only 4 short fields, no benefit to a
 * side panel"). This is a deliberate, phase-specific override of the general
 * sketch-findings interaction-patterns.md anti-pattern "don't put drill-down
 * inside row expansion" — 39-UI-SPEC.md (checker-approved) explicitly chose
 * the inline accordion for this one small record shape to avoid a redundant
 * modal-inside-modal; see 39-06-SUMMARY.md Decisions.
 *
 * Keyboard nav (tabIndex=0 rows, Arrow/Home/End) copies
 * campaigns-table.tsx:56-121's shape verbatim; only the Enter/Space handler
 * differs (toggles local expand state instead of an onRowClick callback).
 *
 * Revoke column (D-17, Plan 07): clicking the per-row button tracks that row
 * in local state and opens ONE shared `ConfirmModal` (variant="warning")
 * below the table; confirming calls `useRevokeException(revokeTarget.id)`,
 * which invalidates the exceptions list on success so the row's state
 * (revoked/muted chip) updates on the next render. Disabled only for
 * already-historical (revoked/expired) rows — re-revoking is a no-op the
 * backend itself 409s on, so the UI never offers it. Hand-rolled markup
 * (not `<Button variant="icon">`) for the same reason as 39-06's original
 * placeholder — that variant's default `size:'md'` padding compounds with
 * the fixed `h-[34px] w-[34px]` box (components/ui/button.tsx, logged to
 * deferred-items.md, out of this plan's files_modified scope).
 *
 * The revoke confirmation names the CVE + scope-label target rather than a
 * resolved hostname/group-name — same "no fake human-readable target" call
 * as the CVE/target column's own `targetTitle()` (ExceptionResponse has no
 * such join, 39-01/39-02's documented scope boundary).
 *
 * T-38-09-class (XSS): cve_id / approver_display_name / justification are
 * all rendered as React text children (no dangerouslySetInnerHTML) — React
 * auto-escapes them.
 */
import { Fragment, useCallback, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Ban } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '@/components/ui/Avatar';
import { SlaPill } from '@/components/tickets/sla-pill';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { useRevokeException } from '@/lib/queries/use-exception-mutations';
import type { ExceptionResponse } from '@/lib/queries/use-exceptions';

export type ExceptionsTableProps = {
  rows: ExceptionResponse[];
};

// Type badge — reuses the status-pill family's violet/amber tint classes
// verbatim (39-UI-SPEC.md Color: FALSE_POSITIVE -> "status-pill Open" hue,
// ACCEPTED_RISK -> "status-pill In progress" hue) rather than importing
// tickets/status-pill.tsx, whose prop contract (`externalStatus`) is keyed
// to ticket-specific literals ('open'/'in_progress'/'completed') with no
// custom-label escape hatch.
const TYPE_PILL_CONFIG: Record<ExceptionResponse['type'], { classes: string; label: string }> = {
  FALSE_POSITIVE: {
    classes: 'border-violet/40 bg-violet-soft text-[var(--color-violet-on-soft)]',
    label: 'False positive',
  },
  ACCEPTED_RISK: {
    classes: 'border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]',
    label: 'Accept risk',
  },
};

const SCOPE_LABEL: Record<ExceptionResponse['scope_type'], string> = {
  FINDING: 'Finding',
  ASSET: 'Asset',
  ASSET_GROUP: 'Asset group',
};

// Neutral muted chip for historical (revoked/expired) rows — never
// sla-pill.overdue red, per 39-UI-SPEC.md Color: "that specifically means
// 'SLA breached,' not 'exception lifecycle ended.'"
const MUTED_CHIP_CLASSES =
  'inline-flex items-center rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs text-text-faint';

// "Nd ago" relative-day format (copy-voice.md: "3d left" not "3 days left").
// Deliberately NOT Intl.RelativeTimeFormat (activity-feed.tsx's "2 days ago"
// shape) — the plan's literal spec is the sla-pill day-math style.
function grantedAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const days = Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
  return days <= 0 ? 'Today' : `${days}d ago`;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return '—';
  return d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

// The backend's ExceptionResponse has no resolved asset/asset-group display
// name (39-01/39-02 decision — see use-exceptions.ts docstring), so the
// visible "CVE / target" cell shows cve_id only; the scope-specific raw
// identifier is surfaced via this title tooltip rather than invented as fake
// human-readable text.
function targetTitle(row: ExceptionResponse): string {
  if (row.scope_type === 'ASSET' && row.asset_id) return `${row.cve_id} — asset ${row.asset_id}`;
  if (row.scope_type === 'ASSET_GROUP' && row.asset_group_id) {
    return `${row.cve_id} — asset group ${row.asset_group_id}`;
  }
  return `${row.cve_id} — this finding`;
}

// D-17: an already-revoked or lapsed-expired row can't be usefully
// re-revoked — the backend 409s on an already-revoked exception_id, so the
// Revoke button disables itself for historical rows rather than offering an
// action that only round-trips into an error.
function isHistorical(row: ExceptionResponse): boolean {
  if (row.revoked_at) return true;
  const expiresMs = new Date(row.expires_at).getTime();
  return Number.isFinite(expiresMs) && expiresMs <= Date.now();
}

// Same "no fake human-readable target" call as targetTitle() above — the
// Revoke confirmation names the scope kind, not an invented hostname/
// group-name the backend response doesn't carry.
const SCOPE_TARGET_PHRASE: Record<ExceptionResponse['scope_type'], string> = {
  FINDING: 'this finding',
  ASSET: 'this asset',
  ASSET_GROUP: 'this asset group',
};

function ExpiresCell({ row }: { row: ExceptionResponse }) {
  if (row.revoked_at) {
    return <span className={MUTED_CHIP_CLASSES}>Revoked</span>;
  }
  const expiresMs = new Date(row.expires_at).getTime();
  if (Number.isFinite(expiresMs) && expiresMs <= Date.now()) {
    return <span className={MUTED_CHIP_CLASSES}>Expired</span>;
  }
  // Active + not-yet-lapsed is guaranteed by the branch above, so SlaPill's
  // own computeTier() can only ever land on 'soon' or 'ok' here — 'overdue'
  // is unreachable. Reused verbatim (T-36-01: never re-derive the tier
  // formula locally).
  return <SlaPill dueAt={row.expires_at} />;
}

function ExpandedDetail({ row }: { row: ExceptionResponse }) {
  return (
    <div className="space-y-3 py-1 text-sm">
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
          Justification
        </h4>
        <p className="whitespace-pre-wrap text-text">{row.justification}</p>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-text-muted">
        <span>
          Approved by <span className="text-text">{row.approver_display_name ?? '—'}</span> ·
          Granted <span className="text-text">{formatDateTime(row.created_at)}</span>
        </span>
        {row.revoked_at && (
          <span>
            Revoked <span className="text-text">{formatDateTime(row.revoked_at)}</span>
          </span>
        )}
      </div>
    </div>
  );
}

export function ExceptionsTable({ rows }: ExceptionsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);
  // D-19: ascending (soonest-expiring first) by default; header click toggles.
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // D-17: the row targeted by an in-flight Revoke confirmation. A single
  // ConfirmModal + mutation instance serves every row — `revokeTarget?.id`
  // is re-read on each render, so by the time `.mutate()` fires it always
  // reflects whichever row's Revoke button was most recently clicked (the
  // modal can only be open for one row at a time).
  const [revokeTarget, setRevokeTarget] = useState<ExceptionResponse | null>(null);
  const revokeMutation = useRevokeException(revokeTarget?.id ?? '');

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const aMs = new Date(a.expires_at).getTime();
      const bMs = new Date(b.expires_at).getTime();
      if (aMs !== bMs) return sortDir === 'asc' ? aMs - bMs : bMs - aMs;
      // Stable tiebreak on `id` for equal expires_at (must_haves: "rows with
      // equal expires_at render in a stable order").
      if (a.id < b.id) return -1;
      if (a.id > b.id) return 1;
      return 0;
    });
    return copy;
  }, [rows, sortDir]);

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((cur) => (cur === id ? null : id));
  }, []);

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, row: ExceptionResponse, idx: number) => {
      const rowsEls = tbodyRef.current?.querySelectorAll<HTMLTableRowElement>(
        'tr[tabindex="0"]',
      );
      if (!rowsEls) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        rowsEls[Math.min(idx + 1, rowsEls.length - 1)]?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        rowsEls[Math.max(idx - 1, 0)]?.focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        rowsEls[0]?.focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        rowsEls[rowsEls.length - 1]?.focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleExpand(row.id);
      }
    },
    [toggleExpand],
  );

  // D-17 Copywriting Contract (39-UI-SPEC.md): "{CVE-ID} on {target} returns
  // to the active queue immediately — SLA tracking resumes and it reappears
  // on dashboards. This can't be undone; you'd need to grant a new
  // exception." — {target} uses SCOPE_TARGET_PHRASE (see above) rather than
  // an invented hostname/group-name.
  const revokeMessage = revokeTarget
    ? `${revokeTarget.cve_id} on ${SCOPE_TARGET_PHRASE[revokeTarget.scope_type]} returns to the active queue immediately — SLA tracking resumes and it reappears on dashboards. This can't be undone; you'd need to grant a new exception.`
    : '';

  return (
    <>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-surface">
          {/* 39-UI-SPEC.md Typography: Label role locked to font-semibold (600),
              not the sitewide font-medium (500) — every new component this
              phase builds must hold the 2-weight cap this way. */}
          <tr className="border-b border-border-subtle text-left text-xs font-semibold uppercase tracking-wide text-text-muted">
            <th scope="col" className="px-3 py-2" data-col="type">
              Type
            </th>
            <th scope="col" className="px-3 py-2" data-col="target">
              CVE / target
            </th>
            <th scope="col" className="px-3 py-2" data-col="scope">
              Scope
            </th>
            <th scope="col" className="px-3 py-2" data-col="approver">
              Approver
            </th>
            <th scope="col" className="px-3 py-2" data-col="granted">
              Granted
            </th>
            <th
              scope="col"
              aria-sort={sortDir === 'asc' ? 'ascending' : 'descending'}
              className="cursor-pointer px-3 py-2 hover:text-text"
              data-col="expires"
              onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
            >
              Expires {sortDir === 'asc' ? '↑' : '↓'}
            </th>
            <th scope="col" className="px-3 py-2" data-col="revoke">
              <span className="sr-only">Revoke</span>
            </th>
          </tr>
        </thead>
        <tbody ref={tbodyRef}>
          {sorted.map((row, idx) => {
            const isExpanded = expandedId === row.id;
            const typeConfig = TYPE_PILL_CONFIG[row.type];
            return (
              <Fragment key={row.id}>
                <tr
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  onClick={() => toggleExpand(row.id)}
                  onKeyDown={(e) => onRowKeyDown(e, row, idx)}
                  className={cn(
                    'cursor-pointer border-b border-border-subtle',
                    'hover:bg-surface-2 focus-visible:bg-surface-2',
                    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                    isExpanded && 'bg-surface-2',
                  )}
                >
                  <td className="px-3 py-3">
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
                        typeConfig.classes,
                      )}
                    >
                      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
                      {typeConfig.label}
                    </span>
                  </td>
                  <td className="max-w-[220px] px-3 py-3">
                    <span className="block truncate font-mono text-text" title={targetTitle(row)}>
                      {row.cve_id}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-text-muted">{SCOPE_LABEL[row.scope_type]}</td>
                  <td className="max-w-[180px] px-3 py-3">
                    <span
                      className="flex min-w-0 items-center gap-2"
                      title={row.approver_display_name ?? undefined}
                    >
                      <Avatar name={row.approver_display_name ?? undefined} size={20} />
                      <span className="min-w-0 flex-1 truncate text-text">
                        {row.approver_display_name ?? '—'}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-3 font-mono tabular-nums text-text-muted">
                    {grantedAgo(row.created_at)}
                  </td>
                  <td className="px-3 py-3">
                    <ExpiresCell row={row} />
                  </td>
                  <td className="px-3 py-3">
                    {/* D-17 — see module docstring "Revoke column". Disabled
                        only for already-historical (revoked/expired) rows. */}
                    <button
                      type="button"
                      disabled={isHistorical(row)}
                      title={isHistorical(row) ? 'Already revoked or expired' : 'Revoke exception'}
                      aria-label={`Revoke exception for ${row.cve_id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setRevokeTarget(row);
                      }}
                      className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-md border border-border-subtle bg-surface text-text-muted hover:border-danger/40 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-border-subtle disabled:hover:text-text-muted"
                    >
                      <Ban className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="border-b border-border-subtle bg-surface-2">
                    <td colSpan={7} className="px-3 py-4">
                      <ExpandedDetail row={row} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      <ConfirmModal
        open={revokeTarget !== null}
        title="Revoke this exception?"
        message={revokeMessage}
        confirmLabel="Revoke exception"
        cancelLabel="Cancel"
        variant="warning"
        confirmDisabled={revokeMutation.isPending}
        onConfirm={() => {
          revokeMutation.mutate(undefined, { onSuccess: () => setRevokeTarget(null) });
        }}
        onCancel={() => setRevokeTarget(null)}
      />
    </>
  );
}
