import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// D-V-02 — read /api/v1/connectors so PerSourceStatusStrip can colour each
// chip by last_sync_status (ok / syncing / failed / never-synced). The strip
// composes this with the facet endpoint's per-source vuln counts so we don't
// add a dedicated source-status backend surface.
export type ConnectorRow = {
  id: string;
  connector_type: string; // 'QUALYS' | 'TENABLE' | 'AWS_INSPECTOR' | 'ASANA' | ...
  last_sync_at: string | null;
  last_sync_status: 'ok' | 'syncing' | 'failed' | null;
  last_sync_record_count: number | null;
};

export function useConnectors() {
  return useQuery({
    queryKey: queryKeys.connectors.list(),
    queryFn: ({ signal }) => api<ConnectorRow[]>('/api/v1/connectors', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}
