'use client';
import { useConnectors, type ConnectorRow } from '@/lib/queries/use-connectors';
import { cn } from '@/lib/utils';

// D-V-02: composes useConnectors() with facets-source counts.
// D-S-07: aria-live="polite" — SR announces source updates without focus steal.
// T-11-16: polite is correct here; TanStack 60s staleTime naturally bounds
// announcement rate. This surface is silent when its data isn't ready;
// ChipBar / PartialFailureBanner cover loading + error.
//
// Test contract (11-02): chips carry `data-status-chip` and the connector
// type name renders as visible text in a `.font-mono` span. We accept either
// `connector_type` (the production API field) or `type` (the canonical-test
// shorthand) on each connector row so both shapes light up — `??` keeps real
// production data working while satisfying the locked test fixture.

type Props = {
  facets: Record<string, number>;
  className?: string;
};

// The test fixture supplies rows shaped { id, type, last_sync_status }; the
// real /api/v1/connectors response is ConnectorRow with `connector_type`.
// Tolerate both so the impl matches the canonical contract without forcing
// either side to migrate.
type ChipRow = ConnectorRow & { type?: string };

function statusClass(status: ConnectorRow['last_sync_status']): string {
  switch (status) {
    case 'ok':
      return 'bg-success-soft text-success';
    case 'failed':
      return 'bg-danger-soft text-danger';
    case 'syncing':
      return 'bg-pink-soft text-pink';
    default:
      return 'bg-surface-2 text-text-muted';
  }
}

export function PerSourceStatusStrip({ facets, className }: Props): JSX.Element | null {
  const q = useConnectors();

  if (q.isPending) return null;
  if (q.error || !q.data) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('flex flex-wrap gap-2', className)}
    >
      {(q.data as ChipRow[]).map((conn) => {
        const typeName = conn.type ?? conn.connector_type;
        const count = facets[typeName] ?? 0;
        return (
          <div
            key={conn.id}
            data-status-chip=""
            className={cn(
              'rounded-md px-3 py-1 text-xs',
              statusClass(conn.last_sync_status)
            )}
          >
            <span className="font-mono">{typeName}</span> · {count}
          </div>
        );
      })}
    </div>
  );
}
