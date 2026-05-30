'use client';
/**
 * AssetsTable — UX-04-01 list table (6 columns).
 *
 * Columns: Hostname (mono) · OS · Owner (Avatar + name) · Risk Score
 *          (mono, band-tinted) · Tags (wrap chips) · Sources (mono chips).
 *
 * Mirrors VulnTable's keyboard nav + sticky thead + stale-row tinting patterns
 * (Phase 11 D-V-04). Plain semantic <table> (Pitfall 5 — no grid role). Row
 * focus + ArrowDown/Up/Home/End/Enter/Space keyboard contract.
 *
 * T-12-07: hostname, owner email, tags, and source values are rendered as
 * React text children (no dangerouslySetInnerHTML). Avatar primitive carries
 * its own XSS guard (T-12-04).
 */
import { useCallback, useRef, type KeyboardEvent } from 'react';
import { Avatar } from '@/components/ui/Avatar';
import { getRiskBand } from '@/components/ui/RiskRing';
import { cn } from '@/lib/utils';
import type { AssetSummary } from '@/lib/queries/use-assets';
import { microcopy } from './microcopy';

export type AssetsTableProps = {
  rows: AssetSummary[];
  onRowOpen: (id: string) => void;
  failedSources?: string[];
};

// D-R-01 — band-tinted risk score text. Stroke gradient lives on RiskRing
// itself; the table only tints the numeric cell. `unavailable` falls back to
// text-text-faint (no `text-text-subtle` token exists in tailwind.config.ts).
const BAND_TINT: Record<string, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  unavailable: 'text-text-faint',
};

function sourcesOf(a: AssetSummary): string[] {
  if (Array.isArray(a.seen_by_sources)) return a.seen_by_sources as string[];
  if (a.seen_by_sources && typeof a.seen_by_sources === 'object') {
    return Object.keys(a.seen_by_sources);
  }
  return [];
}

export function AssetsTable({ rows, onRowOpen, failedSources }: AssetsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, id: string, idx: number) => {
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
        onRowOpen(id);
      }
    },
    [onRowOpen],
  );

  return (
    <table className="w-full border-collapse text-sm">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
          <th scope="col" className="px-3 py-2" data-col="hostname">
            {microcopy.columns.hostname}
          </th>
          <th scope="col" className="px-3 py-2" data-col="os">
            {microcopy.columns.os}
          </th>
          <th scope="col" className="px-3 py-2" data-col="owner">
            {microcopy.columns.owner}
          </th>
          <th scope="col" className="px-3 py-2 text-right" data-col="risk">
            {microcopy.columns.risk}
          </th>
          <th scope="col" className="px-3 py-2" data-col="tags">
            {microcopy.columns.tags}
          </th>
          <th scope="col" className="px-3 py-2" data-col="sources">
            {microcopy.columns.sources}
          </th>
        </tr>
      </thead>
      <tbody ref={tbodyRef}>
        {rows.map((r, idx) => {
          const band = getRiskBand(r.risk_score);
          const tint = BAND_TINT[band] ?? '';
          const sources = sourcesOf(r);
          const isStale = failedSources?.some((s) => sources.includes(s));
          return (
            <tr
              key={r.id}
              tabIndex={0}
              onClick={() => onRowOpen(r.id)}
              onKeyDown={(e) => onRowKeyDown(e, r.id, idx)}
              data-stale={isStale ? 'true' : undefined}
              className={cn(
                'cursor-pointer border-b border-border-subtle',
                'hover:bg-surface-2 focus-visible:bg-surface-2',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                isStale && 'bg-amber-soft',
              )}
            >
              <td className="px-3 py-3 font-mono text-text">
                {r.hostname ?? '—'}
              </td>
              <td className="px-3 py-3 text-text-muted">{r.os_name ?? '—'}</td>
              <td className="px-3 py-3">
                <span className="inline-flex items-center gap-2">
                  <Avatar
                    name={r.assigned_user ?? undefined}
                    email={r.assigned_user ?? undefined}
                    size={24}
                  />
                  <span className="text-text">
                    {r.assigned_user ?? 'Unassigned'}
                  </span>
                </span>
              </td>
              <td
                className={cn(
                  'px-3 py-3 text-right font-mono tabular-nums',
                  tint,
                )}
              >
                {r.risk_score ?? '—'}
              </td>
              <td className="px-3 py-3">
                <span className="flex flex-wrap gap-1">
                  {(r.tags ?? []).map((t) => (
                    <span
                      key={t}
                      className="rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs text-text-muted"
                    >
                      {t}
                    </span>
                  ))}
                </span>
              </td>
              <td className="px-3 py-3">
                <span className="flex flex-wrap gap-1">
                  {sources.map((s) => (
                    <span
                      key={s}
                      className="rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 font-mono text-xs text-text-muted"
                    >
                      {s}
                    </span>
                  ))}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
