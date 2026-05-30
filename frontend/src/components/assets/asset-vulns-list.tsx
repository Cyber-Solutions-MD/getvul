'use client';
/**
 * AssetVulnsList — UX-04-02 main column.
 *
 * Compact vuln rows for vulnerabilities on the current asset. Clicking a row
 * sets the URL `?cve=<id>&open=drill`, which mounts the Phase 11 DrillPanel
 * (D-D-03 reuse contract). Keyboard nav mirrors Phase 11 VulnTable:
 * ArrowDown/Up navigate; Enter/Space activates.
 */
import { useCallback, useRef, type KeyboardEvent } from 'react';
import type { VulnerabilitySummary } from '@/lib/queries/use-vulnerabilities';
import { cn } from '@/lib/utils';

const SEV_GLYPH: Record<string, { glyph: string; tint: string }> = {
  CRITICAL: { glyph: '■', tint: 'text-severity-critical' },
  HIGH: { glyph: '▲', tint: 'text-severity-high' },
  MEDIUM: { glyph: '◆', tint: 'text-severity-medium' },
  LOW: { glyph: '○', tint: 'text-severity-low' },
  INFO: { glyph: '□', tint: 'text-severity-info' },
};

export type AssetVulnsListProps = {
  rows: VulnerabilitySummary[];
  onRowOpen: (cveOrId: string) => void;
};

export function AssetVulnsList({ rows, onRowOpen }: AssetVulnsListProps) {
  const tbodyRef = useRef<HTMLDivElement>(null);

  const onKey = useCallback(
    (e: KeyboardEvent<HTMLDivElement>, id: string, idx: number) => {
      const list = tbodyRef.current?.querySelectorAll<HTMLDivElement>(
        '[role="row"][tabindex="0"]',
      );
      if (!list) return;
      // WR-08: mirror AssetsTable keyboard contract — ArrowDown/Up + Home/End
      // + Enter/Space. Without Home/End the two tables on the detail page
      // expose inconsistent contracts to keyboard users.
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        list[Math.min(idx + 1, list.length - 1)]?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        list[Math.max(idx - 1, 0)]?.focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        list[0]?.focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        list[list.length - 1]?.focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onRowOpen(id);
      }
    },
    [onRowOpen],
  );

  if (rows.length === 0) {
    // Page composes empty state via Phase 11 EmptyState — list itself renders
    // nothing rather than a "No rows" stub.
    return null;
  }

  return (
    <div role="table" aria-label="Vulnerabilities on this host" ref={tbodyRef}>
      {/* WR-07: WAI-ARIA requires role="rowgroup" between role="table" and
          role="row" (mirroring <tbody>). axe-core flags the missing
          rowgroup as aria-required-children. */}
      <div role="rowgroup">
      {rows.map((r, idx) => {
        const sev =
          SEV_GLYPH[String(r.severity).toUpperCase()] ?? {
            glyph: '○',
            tint: 'text-text-faint',
          };
        const idOrCve = r.cve_id ?? r.id;
        return (
          <div
            key={r.id}
            role="row"
            tabIndex={0}
            onClick={() => onRowOpen(idOrCve)}
            onKeyDown={(e) => onKey(e, idOrCve, idx)}
            className={cn(
              'flex cursor-pointer items-center gap-3 border-b border-border-subtle px-3 py-2 hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none',
            )}
            data-testid={`vuln-row-${idOrCve}`}
          >
            <span className={cn('w-5 text-center font-mono', sev.tint)}>{sev.glyph}</span>
            <span className="w-32 font-mono text-sm text-text">{r.cve_id ?? '—'}</span>
            <span className="flex-1 truncate text-sm text-text">
              {r.vulnerability_name ?? '—'}
            </span>
            <span className="font-mono text-sm text-text-faint">
              {r.cvss_v3_score ?? '—'}
            </span>
            {r.cisa_kev && (
              <span className="rounded border border-severity-critical/40 px-1.5 py-0.5 font-mono text-[10px] uppercase text-severity-critical">
                KEV
              </span>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}
