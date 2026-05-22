'use client';
import { useConnectors, type ConnectorRow } from '@/lib/queries/use-connectors';
import { cn } from '@/lib/utils';

// D-V-02: composes useConnectors() with facets-source counts.
// D-S-07: aria-live="polite" — SR announces source updates without focus steal.
// T-11-16: polite is correct here; TanStack 60s staleTime naturally bounds
// announcement rate. This surface is silent when its data isn't ready;
// ChipBar / PartialFailureBanner cover loading + error.

type Props = {
  facets: Record<string, number>;
  className?: string;
};

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
      {q.data.map((conn) => {
        const count = facets[conn.connector_type] ?? 0;
        return (
          <div
            key={conn.id}
            className={cn(
              'rounded-md px-3 py-1 text-xs',
              statusClass(conn.last_sync_status)
            )}
          >
            <span className="font-mono">{conn.connector_type}</span> · {count}
          </div>
        );
      })}
    </div>
  );
}
