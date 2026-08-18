'use client';
/**
 * CampaignsTable — CAMP-01 dedicated campaign list table.
 *
 * Columns (38-UI-SPEC.md Layout & Interaction Reuse item 2): remediation
 * label (mono) · member count (mono, singularized at M=1) · % remediated
 * (mono, tabular-nums) · MTTR (mono) · status pill (CampaignStatusRibbon) ·
 * owner-ticket count (mono, singularized at M=1).
 *
 * Row click -> onRowClick(campaign) — invoked on <tr onClick> AND
 * Enter/Space keydown, exactly like tickets-table.tsx. This component NEVER
 * imports/calls useRouter — the page owns navigation (UI-SPEC's explicit
 * "the table itself must NOT import or call useRouter" contract).
 *
 * Two documented deviations from the plan's <interfaces> block, both driven
 * by the ACTUAL shipped backend contract (backend/app/campaigns/schemas.py),
 * not invented data:
 *
 * 1. MTTR: `CampaignSummary` (the GET /campaigns LIST response) has no
 *    `mttr_seconds` field at all — Plan 03 wired MTTR only into
 *    `CampaignDetail` (the GET /{id} single-campaign response). The MTTR
 *    column therefore always renders the em-dash placeholder at the list
 *    level (never crashes on a missing field); real MTTR is a Plan 05
 *    campaign-DETAIL concern.
 * 2. Owner-ticket count: `CampaignSummary` has no distinct-owner or
 *    distinct-ticket field either (only per-VULNERABILITY total/open/
 *    in_progress/done). The best available proxy — and the one used here —
 *    is `in_progress` (members that have moved off raw OPEN into an active
 *    ticket), labeled "Tickets". A literal owner count would require a new
 *    backend aggregation query, out of this frontend-only plan's scope.
 *
 * T-38-09 (XSS): remediation_id is rendered as a React text child (no
 * dangerouslySetInnerHTML) — React auto-escapes it.
 */
import { useCallback, useRef, type KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';
import { CampaignStatusRibbon } from './campaign-status-ribbon';
import type { CampaignSummary } from '@/lib/queries/use-campaigns';

export type CampaignsTableProps = {
  rows: CampaignSummary[];
  onRowClick: (campaign: CampaignSummary) => void;
};

// Singularizes a count string per the zero-one-many gotcha flagged
// throughout 38-UI-SPEC.md ("never '1 findings'").
function countLabel(n: number, singular: string): string {
  return n === 1 ? `1 ${singular}` : `${n} ${singular}s`;
}

// MTTR is never present on CampaignSummary (see module docstring, deviation
// 1) — the column always shows the same "not available at this level"
// placeholder used elsewhere for a null compute-on-read value.
const MTTR_PLACEHOLDER = '—';

export function CampaignsTable({ rows, onRowClick }: CampaignsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, campaign: CampaignSummary, idx: number) => {
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
        onRowClick(campaign);
      }
    },
    [onRowClick],
  );

  return (
    <table className="w-full border-collapse text-sm">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
          <th scope="col" className="px-3 py-2" data-col="remediation">
            Remediation
          </th>
          <th scope="col" className="px-3 py-2" data-col="members">
            Members
          </th>
          <th scope="col" className="px-3 py-2" data-col="pct">
            % remediated
          </th>
          <th scope="col" className="px-3 py-2" data-col="mttr">
            MTTR
          </th>
          <th scope="col" className="px-3 py-2" data-col="status">
            Status
          </th>
          <th scope="col" className="px-3 py-2" data-col="tickets">
            Tickets
          </th>
        </tr>
      </thead>
      <tbody ref={tbodyRef}>
        {rows.map((r, idx) => (
          <tr
            key={r.id}
            tabIndex={0}
            onClick={() => onRowClick(r)}
            onKeyDown={(e) => onRowKeyDown(e, r, idx)}
            className={cn(
              'cursor-pointer border-b border-border-subtle',
              'hover:bg-surface-2 focus-visible:bg-surface-2',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            )}
          >
            {/* Remediation label — mono, truncated with full string on hover
                (backstop: "Long remediation label -> ellipsis + full string
                in title tooltip"). */}
            <td className="px-3 py-3 max-w-[320px]">
              <span
                className="block truncate font-mono text-text"
                title={r.remediation_id}
              >
                {r.remediation_id}
              </span>
            </td>
            {/* Member count — mono, singularized at M=1. */}
            <td className="px-3 py-3 font-mono tabular-nums text-text-muted">
              {countLabel(r.total, 'finding')}
            </td>
            {/* % remediated — mono, tabular-nums, the focal accent column. */}
            <td className="px-3 py-3 font-mono tabular-nums text-text">
              {r.pct_remediated}%
            </td>
            {/* MTTR — always the placeholder at list level (deviation 1). */}
            <td className="px-3 py-3 font-mono text-text-muted">
              {MTTR_PLACEHOLDER}
            </td>
            {/* Status pill — the other focal accent column. */}
            <td className="px-3 py-3">
              <CampaignStatusRibbon status={r.status} />
            </td>
            {/* Owner-ticket count proxy — mono, singularized at M=1
                (deviation 2). */}
            <td className="px-3 py-3 font-mono tabular-nums text-text-muted">
              {countLabel(r.in_progress, 'ticket')}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
