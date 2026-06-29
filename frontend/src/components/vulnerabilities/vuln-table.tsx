'use client';
import { useCallback, useRef, useState, type KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';
import { microcopy } from './microcopy';

// UX-03-02 + UX-07-03 + D-V-04.
// 7 columns: Severity / CVE / Title / Asset / CVSS / Status / SLA.
// Sticky thead (D-T-04). Plain <table> — semantic only, no grid role (Pitfall 5).
// Row keyboard nav per RESEARCH §Pattern 6 (ArrowDown/Up/Home/End/Enter/Space).
// Stale-row tinting per D-V-04 — failedSources prop drives `data-stale`.

type SeverityLower = 'critical' | 'high' | 'medium' | 'low' | 'info';

// Sort field includes the 4 column-name keys the test asserts against.
export type VulnTableSortField =
  | 'severity'
  | 'cve_id'
  | 'cvss_v3_score'
  | 'sla_due_at'
  | null;
export type VulnTableSortOrder = 'asc' | 'desc' | null;

// Loose row shape — accepts both Phase 11 backend payload variations and the
// minimal shape used by the test. Optional fields fall back to '—' / 0.
export type VulnTableRow = {
  id: string;
  cve_id?: string | null;
  // Either `title` (test shape) or `affected_product` (backend shape) — both
  // render in the Title cell with `title` winning when both present.
  title?: string | null;
  affected_product?: string | null;
  // `asset` (test shape) or `asset_hostname` (backend shape).
  asset?: string | null;
  asset_hostname?: string | null;
  // `cvss` (test shape) or `cvss_v3_score` (backend shape).
  cvss?: number | null;
  cvss_v3_score?: number | null;
  severity: SeverityLower | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  status: string;
  cisa_kev?: boolean;
  exploit_available?: boolean;
  source: string;
  sla_due_at: string | null;
};

type Props = {
  rows: VulnTableRow[];
  sort?: VulnTableSortField;
  order?: 'asc' | 'desc' | null;
  onSort: (field: VulnTableSortField, order: VulnTableSortOrder) => void;
  onRowOpen: (idOrCve: string) => void;
  failedSources?: string[];
};

const GLYPH: Record<SeverityLower, string> = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
  info: '□',
};

const GLYPH_COLOR: Record<SeverityLower, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

const SEVERITY_LABEL: Record<SeverityLower, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

function normalizeSeverity(s: VulnTableRow['severity']): SeverityLower {
  const lower = String(s).toLowerCase();
  if (
    lower === 'critical' ||
    lower === 'high' ||
    lower === 'medium' ||
    lower === 'low' ||
    lower === 'info'
  ) {
    return lower;
  }
  return 'info';
}

function slaBand(iso: string | null): { label: string; tone: string } {
  if (!iso) return { label: '—', tone: 'text-text-muted' };
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return { label: '—', tone: 'text-text-muted' };
  const hours = (t - Date.now()) / 3_600_000;
  if (hours < 0)
    return {
      label: `−${Math.abs(Math.round(hours))}h SLA`,
      tone: 'text-severity-critical',
    };
  if (hours < 24)
    return { label: `${Math.round(hours)}h left`, tone: 'text-severity-high' };
  return {
    label: `${Math.round(hours / 24)}d left`,
    tone: 'text-success',
  };
}

// Cycle sort order: not-set → asc → desc → clear (null, null).
function cycleSort(
  curField: VulnTableSortField,
  curOrder: 'asc' | 'desc' | null | undefined,
  clicked: Exclude<VulnTableSortField, null>,
): [VulnTableSortField, VulnTableSortOrder] {
  if (curField !== clicked) return [clicked, 'asc'];
  if (curOrder === 'asc') return [clicked, 'desc'];
  return [null, null];
}

export function VulnTable({
  rows,
  sort: sortProp,
  order: orderProp,
  onSort,
  onRowOpen,
  failedSources = [],
}: Props) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  // Uncontrolled cycle state: when the parent doesn't supply sort/order
  // (test path + most callers), we track the most-recent click locally so
  // the asc → desc → clear cycle progresses across rerenders. When the
  // parent DOES supply sort/order (controlled — Plan 06 page wires this
  // to ?sort= + ?order=), the props override our local state.
  const [localSort, setLocalSort] = useState<VulnTableSortField>(null);
  const [localOrder, setLocalOrder] = useState<'asc' | 'desc' | null>(null);
  const sort: VulnTableSortField =
    sortProp !== undefined ? sortProp : localSort;
  const order: 'asc' | 'desc' | null =
    orderProp !== undefined ? orderProp : localOrder;

  const onRowKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTableRowElement>, idOrCve: string) => {
      const tbody = tbodyRef.current;
      if (!tbody) return;
      const navRows = Array.from(
        tbody.querySelectorAll<HTMLTableRowElement>('tr[tabindex="0"]'),
      );
      const idx = navRows.indexOf(e.currentTarget);
      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          onRowOpen(idOrCve);
          return;
        case 'ArrowDown':
          e.preventDefault();
          navRows[Math.min(idx + 1, navRows.length - 1)]?.focus();
          return;
        case 'ArrowUp':
          e.preventDefault();
          navRows[Math.max(idx - 1, 0)]?.focus();
          return;
        case 'Home':
          e.preventDefault();
          navRows[0]?.focus();
          return;
        case 'End':
          e.preventDefault();
          navRows[navRows.length - 1]?.focus();
          return;
      }
    },
    [onRowOpen],
  );

  const handleSortClick = (field: Exclude<VulnTableSortField, null>) => {
    const [nextField, nextOrder] = cycleSort(sort, order, field);
    if (sortProp === undefined) setLocalSort(nextField);
    if (orderProp === undefined) setLocalOrder(nextOrder);
    onSort(nextField, nextOrder);
  };

  const sortIndicator = (field: Exclude<VulnTableSortField, null>) =>
    sort === field ? (order === 'asc' ? ' ↑' : ' ↓') : '';

  return (
    // overflow-x-auto: the 7-column table is wider than a phone viewport; let it
    // scroll within its own container so the page body never scrolls horizontally
    // (UX-07-01). No mobile card view exists for this surface.
    <div className="overflow-x-auto">
    <table className="w-full border-collapse text-sm">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
          <th
            scope="col"
            onClick={() => handleSortClick('severity')}
            className="cursor-pointer px-3 py-2 hover:text-text"
          >
            {microcopy.table.columns.severity}
            {sortIndicator('severity')}
          </th>
          <th
            scope="col"
            onClick={() => handleSortClick('cve_id')}
            className="cursor-pointer px-3 py-2 hover:text-text"
          >
            {microcopy.table.columns.cve}
            {sortIndicator('cve_id')}
          </th>
          <th scope="col" className="px-3 py-2">
            {microcopy.table.columns.title}
          </th>
          <th scope="col" className="px-3 py-2">
            {microcopy.table.columns.asset}
          </th>
          <th
            scope="col"
            onClick={() => handleSortClick('cvss_v3_score')}
            className="cursor-pointer px-3 py-2 text-right hover:text-text"
          >
            {microcopy.table.columns.cvss}
            {sortIndicator('cvss_v3_score')}
          </th>
          <th scope="col" className="px-3 py-2">
            {microcopy.table.columns.status}
          </th>
          <th
            scope="col"
            onClick={() => handleSortClick('sla_due_at')}
            className="cursor-pointer px-3 py-2 text-right hover:text-text"
          >
            {microcopy.table.columns.sla}
            {sortIndicator('sla_due_at')}
          </th>
        </tr>
      </thead>
      <tbody ref={tbodyRef}>
        {rows.map((row) => {
          const sev = normalizeSeverity(row.severity);
          const idOrCve = row.cve_id ?? row.id;
          const stale = failedSources.includes(row.source);
          const sla = slaBand(row.sla_due_at);
          const cvss = row.cvss ?? row.cvss_v3_score ?? null;
          const titleText = row.title ?? row.affected_product ?? '—';
          const assetText = row.asset ?? row.asset_hostname ?? '—';
          return (
            <tr
              key={row.id}
              tabIndex={0}
              onClick={() => onRowOpen(idOrCve)}
              onKeyDown={(e) => onRowKeyDown(e, idOrCve)}
              data-stale={stale ? 'true' : undefined}
              className={cn(
                'cursor-pointer border-b border-border-subtle',
                'hover:bg-surface-2 focus-visible:bg-surface-2',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                stale && 'bg-amber-soft data-[stale=true]:bg-amber-soft',
              )}
            >
              <td data-col="severity" className="px-3 py-2.5">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-surface-2 px-2 py-0.5 text-xs">
                  <span aria-hidden="true" className={GLYPH_COLOR[sev]}>
                    {GLYPH[sev]}
                  </span>
                  <span className={GLYPH_COLOR[sev]}>{SEVERITY_LABEL[sev]}</span>
                </span>
              </td>
              <td data-col="cve" className="px-3 py-2.5 font-mono text-text">
                {row.cve_id ?? '—'}
              </td>
              <td data-col="title" className="px-3 py-2.5 text-text">
                {titleText}
              </td>
              <td
                data-col="asset"
                className="px-3 py-2.5 font-mono text-text-muted"
              >
                {assetText}
              </td>
              <td
                data-col="cvss"
                className="px-3 py-2.5 text-right font-mono text-text"
              >
                {cvss !== null ? cvss.toFixed(1) : '—'}
              </td>
              <td data-col="status" className="px-3 py-2.5">
                <span className="inline-flex items-center gap-1.5 text-text-muted">
                  {row.cisa_kev && (
                    <span
                      aria-label="CISA KEV"
                      className="rounded-md border border-severity-critical bg-pink-soft px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wide text-severity-critical"
                    >
                      ★ KEV
                    </span>
                  )}
                  {row.exploit_available && (
                    <span
                      aria-label="exploit available"
                      className="rounded-md bg-amber-soft px-1.5 py-0.5 text-[10px] font-medium text-amber"
                    >
                      ⚡
                    </span>
                  )}
                  <span className="text-xs">{row.status}</span>
                </span>
              </td>
              <td
                data-col="sla"
                className={cn(
                  'px-3 py-2.5 text-right font-mono text-xs',
                  sla.tone,
                )}
              >
                {sla.label}
              </td>
            </tr>
          );
        })}
        {rows.length === 0 && (
          <tr>
            <td
              colSpan={7}
              className="px-3 py-6 text-center text-text-muted"
            >
              {microcopy.table.empty}
            </td>
          </tr>
        )}
      </tbody>
    </table>
    </div>
  );
}
