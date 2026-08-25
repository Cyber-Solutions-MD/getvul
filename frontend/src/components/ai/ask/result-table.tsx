'use client';
/**
 * ResultTable -- D-08 entity-dispatch THIN wrapper. Never a new/second
 * table pattern: it selects the EXISTING vuln/asset/ticket list-row
 * primitive by `entity` and hands it the streamed `rows` unchanged. Each
 * row still links to its real drill panel / detail via `onRowOpen`
 * (row-primitive click handlers already carry that behavior verbatim).
 *
 * The streamed rows are the SAME shape `list_vulnerabilities`/`list_assets`/
 * `list_tickets` already return elsewhere in the app (query_assistant.py
 * `model_dump(mode="json")` of the exact same Pydantic summary models) --
 * cast to each primitive's own row type at this ONE boundary, mirroring how
 * every existing list page (e.g. vulnerabilities/page.tsx) already casts
 * `q.data.items as VulnTableRow[]`.
 */
import type { ReactNode } from 'react';
import { VulnTable, type VulnTableRow } from '@/components/vulnerabilities/vuln-table';
import { AssetsTable } from '@/components/assets/assets-table';
import type { AssetSummary } from '@/lib/queries/use-assets';
import { TicketsTable } from '@/components/tickets/tickets-table';
import type { TicketSummary } from '@/lib/queries/use-tickets';

export type ResultTableEntity = 'vulnerabilities' | 'assets' | 'tickets';

export type ResultTableProps = {
  entity: ResultTableEntity;
  /** The streamed top-N rows (query_assistant.py TOP_N_RESULTS=10) -- already truncated server-side. */
  rows: unknown[];
  /** The deterministic exact match count (D-07) -- NOT rows.length, which is only the shown top-N. */
  total: number;
  onRowOpen: (idOrCve: string) => void;
  /** D-S-01: the parent (Plan 04) fills this with the "Nothing matches that" EmptyState when rows is empty. */
  emptyState?: ReactNode;
};

export function ResultTable({ entity, rows, total, onRowOpen, emptyState }: ResultTableProps) {
  if (rows.length === 0) {
    return emptyState ?? null;
  }

  return (
    <div>
      {/* D-07 caption: "{topN} of {total} total" in mono numerals -- the
          top-N truncation IS the partial-data affordance. */}
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <span className="font-mono text-text">{rows.length}</span> of{' '}
        <span className="font-mono text-text">{total}</span> total
      </p>
      {/* E5 overflow backstop: the wrapper scrolls, rows never clip the page. */}
      <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
        {entity === 'vulnerabilities' && (
          <VulnTable rows={rows as VulnTableRow[]} onSort={() => {}} onRowOpen={onRowOpen} />
        )}
        {entity === 'assets' && <AssetsTable rows={rows as AssetSummary[]} onRowOpen={onRowOpen} />}
        {entity === 'tickets' && (
          <TicketsTable rows={rows as TicketSummary[]} onRowClick={(ticket) => onRowOpen(ticket.id)} />
        )}
      </div>
    </div>
  );
}
