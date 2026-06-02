'use client';
/**
 * TicketsTable — UX-05-01 list table (8 columns).
 *
 * Columns: Severity (glyph) · Provider (ProviderMark) · ID (mono) · Title (truncated)
 *          · Vulns (VulnCount T·C·H) · Assignee (Avatar + name) · Status (StatusPill)
 *          · SLA (SlaPill).
 *
 * Row click → onRowClick(ticket) — the page sets ?ticket=<id>&open=drill.
 * Row checkbox selection feeds the bulk bar.
 *
 * Mobile (<900px): card layout collapses per D-L-01 — use `min-[900px]:` variants (Pitfall 3).
 *
 * T-12-07 compliance: all user data rendered as React text children (no dangerouslySetInnerHTML).
 * No inline hex — all colors via Tailwind sunset tokens.
 */
import { useCallback, useRef, useState, type KeyboardEvent } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { ProviderMark } from './provider-mark';
import { StatusPill } from './status-pill';
import { SlaPill } from './sla-pill';
import { VulnCount } from './vuln-count';
import { cn } from '@/lib/utils';
import type { TicketSummary } from '@/lib/queries/use-tickets';
import type { TicketProvider } from './types';

// Severity glyph map from visual-language.md
const SEVERITY_GLYPH: Record<string, string> = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
  info: '□',
};

// Severity tint classes from sunset tokens
const SEVERITY_CLASS: Record<string, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

function isTicketProvider(value: string | null): value is TicketProvider {
  return value === 'jira' || value === 'asana' || value === 'github';
}

export type TicketsTableProps = {
  rows: TicketSummary[];
  onRowClick: (ticket: TicketSummary) => void;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
};

export function TicketsTable({
  rows,
  onRowClick,
  selectedIds,
  onSelectionChange,
}: TicketsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);
  const [internalSelected, setInternalSelected] = useState<Set<string>>(new Set());

  const selected = selectedIds ?? internalSelected;
  const setSelected = onSelectionChange ?? setInternalSelected;

  const toggleRow = useCallback(
    (id: string) => {
      const next = new Set(selected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      setSelected(next);
    },
    [selected, setSelected]
  );

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, ticket: TicketSummary, idx: number) => {
      const rowsEls = tbodyRef.current?.querySelectorAll<HTMLTableRowElement>(
        'tr[tabindex="0"]'
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
        onRowClick(ticket);
      }
    },
    [onRowClick]
  );

  return (
    <>
      {/* Desktop table — hidden below 900px */}
      <table className="hidden min-[900px]:block w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
            <th scope="col" className="px-2 py-2 w-8" />
            <th scope="col" className="px-3 py-2" data-col="severity">
              Severity
            </th>
            <th scope="col" className="px-3 py-2" data-col="provider">
              Provider
            </th>
            <th scope="col" className="px-3 py-2 font-mono" data-col="id">
              ID
            </th>
            <th scope="col" className="px-3 py-2" data-col="title">
              Title
            </th>
            <th scope="col" className="px-3 py-2" data-col="vulns">
              Vulns
            </th>
            <th scope="col" className="px-3 py-2" data-col="assignee">
              Assignee
            </th>
            <th scope="col" className="px-3 py-2" data-col="status">
              Status
            </th>
            <th scope="col" className="px-3 py-2" data-col="sla">
              SLA
            </th>
          </tr>
        </thead>
        <tbody ref={tbodyRef}>
          {rows.map((r, idx) => {
            const severityKey = r.max_severity?.toLowerCase() ?? '';
            const glyph = SEVERITY_GLYPH[severityKey] ?? '○';
            const severityClass = SEVERITY_CLASS[severityKey] ?? 'text-text-faint';
            const isSelected = selected.has(r.id);

            return (
              <tr
                key={r.id}
                tabIndex={0}
                onClick={() => onRowClick(r)}
                onKeyDown={(e) => onRowKeyDown(e, r, idx)}
                className={cn(
                  'cursor-pointer border-b border-border-subtle',
                  'hover:bg-surface-2 focus-visible:bg-surface-2',
                  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                  isSelected && 'bg-violet-soft',
                )}
                aria-selected={isSelected}
              >
                {/* Checkbox */}
                <td className="px-2 py-3">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleRow(r.id)}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={`Select ticket ${r.external_ticket_id}`}
                    className="rounded border-border text-violet focus:ring-violet"
                  />
                </td>
                {/* Severity glyph */}
                <td className={cn('px-3 py-3 text-sm', severityClass)}>
                  <span aria-label={r.max_severity ?? 'unknown'}>{glyph}</span>
                </td>
                {/* Provider mark */}
                <td className="px-3 py-3">
                  {isTicketProvider(r.provider) && (
                    <ProviderMark provider={r.provider} />
                  )}
                </td>
                {/* ID (mono) */}
                <td className="px-3 py-3 font-mono text-text">
                  {r.external_ticket_id}
                </td>
                {/* Title (truncated, full on hover) */}
                <td className="px-3 py-3 max-w-[280px]">
                  <span className="block truncate text-text" title={r.title}>
                    {r.title}
                  </span>
                </td>
                {/* Vulns (VulnCount T·C·H) */}
                <td className="px-3 py-3">
                  <VulnCount
                    total={r.vuln_count}
                    critical={r.critical_count}
                    high={r.high_count}
                  />
                </td>
                {/* Assignee */}
                <td className="px-3 py-3">
                  <span className="inline-flex items-center gap-2">
                    <Avatar
                      name={r.assignee ?? undefined}
                      email={r.assignee ?? undefined}
                      size={24}
                    />
                    <span className="truncate text-text max-w-[100px]">
                      {r.assignee ?? '—'}
                    </span>
                  </span>
                </td>
                {/* Status */}
                <td className="px-3 py-3">
                  <StatusPill
                    externalStatus={r.external_status}
                    blocked={r.blocked}
                  />
                </td>
                {/* SLA */}
                <td className="px-3 py-3">
                  <SlaPill dueAt={r.sla_due_at} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Mobile card layout — visible below 900px (D-L-01) */}
      <ul className="min-[900px]:hidden space-y-2">
        {rows.map((r) => {
          const severityKey = r.max_severity?.toLowerCase() ?? '';
          const glyph = SEVERITY_GLYPH[severityKey] ?? '○';
          const severityClass = SEVERITY_CLASS[severityKey] ?? 'text-text-faint';
          const isSelected = selected.has(r.id);

          return (
            <li
              key={r.id}
              onClick={() => onRowClick(r)}
              className={cn(
                'cursor-pointer rounded-lg border border-border-subtle bg-surface p-3',
                'hover:bg-surface-2 active:bg-surface-2',
                isSelected && 'border-violet bg-violet-soft',
              )}
            >
              {/* Primary row: Severity · Provider · ID · Title · Status · SLA */}
              <div className="flex items-start gap-2">
                <span className={cn('mt-0.5 shrink-0 text-sm', severityClass)}>
                  {glyph}
                </span>
                {isTicketProvider(r.provider) && (
                  <ProviderMark provider={r.provider} className="mt-0.5 shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-xs text-text shrink-0">
                      {r.external_ticket_id}
                    </span>
                    <span className="truncate text-sm text-text" title={r.title}>
                      {r.title}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                    <StatusPill
                      externalStatus={r.external_status}
                      blocked={r.blocked}
                    />
                    <SlaPill dueAt={r.sla_due_at} />
                  </div>
                </div>
              </div>
              {/* Secondary row: VulnCount + Assignee */}
              <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
                <VulnCount
                  total={r.vuln_count}
                  critical={r.critical_count}
                  high={r.high_count}
                />
                {r.assignee && (
                  <span className="inline-flex items-center gap-1">
                    <Avatar
                      name={r.assignee}
                      email={r.assignee}
                      size={16}
                    />
                    <span className="truncate max-w-[120px]">{r.assignee}</span>
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
