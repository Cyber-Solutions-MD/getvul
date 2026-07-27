'use client';
/**
 * use-connectors-admin.ts — TanStack mutation + query hooks for the connectors
 * admin surface (14-02-PLAN).
 *
 * Endpoints (all require Admin):
 *   GET    /api/v1/connectors              → ConnectorConfigResponse[]
 *   GET    /api/v1/connectors/types        → ConnectorTypeInfo[]
 *   POST   /api/v1/connectors              body { connector_type, credentials, config?, sync_interval_minutes? }
 *   PATCH  /api/v1/connectors/{id}         body { credentials?, config?, is_enabled?, sync_interval_minutes? }
 *   DELETE /api/v1/connectors/{id}         → { message }
 *   POST   /api/v1/connectors/test         body { connector_type, credentials, config? } → { success, message, scopes? }
 *   POST   /api/v1/connectors/{id}/sync    → { status: "STARTED"|"ALREADY_RUNNING", message }
 *
 * Snake_case fields: no transform layer (D-X-02).
 * Cache: queryKeys.connectors.all invalidated on mutations (single source from keys.ts).
 *
 * Sentinel passthrough (D-CONN-04 / Pitfall 5): the EDIT form omits credentials
 * when untouched — that logic lives in ConnectorForm, not here. The hooks accept
 * whatever body the caller passes.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

// ——— Types ———

export type ConnectorConfigResponse = {
  id: string;
  connector_type: string;
  connector_name: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
  has_credentials: boolean;
  last_sync_at: string | null;
  last_sync_status: 'ok' | 'syncing' | 'failed' | null;
  last_sync_record_count: number | null;
  last_error: string | null;
  consecutive_failure_count: number;
  sync_interval_minutes: number;
  created_at: string;
  updated_at: string;
};

export type ConnectorTypePermission = {
  scope: string;
  access: string;
  purpose: string;
};

export type ConnectorTypeInfo = {
  type: string;
  name: string;
  description: string;
  fields: string[];
  defaults: Record<string, string>;
  category: string;
  permissions: ConnectorTypePermission[];
  base_urls: Record<string, string>;
  setup_url: string;
  notes?: string;
};

export type CreateConnectorBody = {
  connector_type: string;
  credentials: Record<string, string>;
  config?: Record<string, unknown>;
  sync_interval_minutes?: number;
};

export type UpdateConnectorBody = {
  credentials?: Record<string, string>;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
  sync_interval_minutes?: number;
};

export type TestConnectorBody = {
  connector_type: string;
  credentials: Record<string, string>;
  config?: Record<string, unknown>;
};

export type TestConnectorResult = {
  success: boolean;
  message: string;
  scopes?: string[];
};

export type SyncConnectorResult = {
  status: 'STARTED' | 'ALREADY_RUNNING';
  message: string;
};

// ——— Queries ———

/**
 * useConnectorsList — GET /api/v1/connectors
 * Returns the configured connectors for this tenant (Admin required on backend).
 */
export function useConnectorsList() {
  return useQuery({
    queryKey: queryKeys.connectors.list(),
    queryFn: ({ signal }) =>
      api<ConnectorConfigResponse[]>('/api/v1/connectors', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}

/**
 * useConnectorTypes — GET /api/v1/connectors/types
 * Returns the supported connector type definitions (fields, permissions, categories).
 */
export function useConnectorTypes() {
  return useQuery({
    queryKey: ['connectors', 'types'] as const,
    queryFn: ({ signal }) =>
      api<ConnectorTypeInfo[]>('/api/v1/connectors/types', { signal }),
    staleTime: 5 * 60_000, // type definitions rarely change
    retry: 1,
  });
}

// ——— Mutations ———

/**
 * useCreateConnector — POST /api/v1/connectors
 * Adds a new connector configuration. Invalidates connectors cache on success.
 */
export function useCreateConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (body: CreateConnectorBody) =>
      api<ConnectorConfigResponse>('/api/v1/connectors', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.all });
      toast({ variant: 'success', message: 'Connector added.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Failed to add connector.' });
    },
  });
}

/**
 * useUpdateConnector — PATCH /api/v1/connectors/{id}
 * Updates connector settings or credentials. Invalidates connectors cache on success.
 */
export function useUpdateConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateConnectorBody }) =>
      api<ConnectorConfigResponse>(`/api/v1/connectors/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.all });
      toast({ variant: 'success', message: 'Connector updated.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Failed to update connector.' });
    },
  });
}

/**
 * useDeleteConnector — DELETE /api/v1/connectors/{id}
 * Removes a connector configuration (Admin only). Invalidates on success.
 */
export function useDeleteConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (id: string) =>
      api<{ message: string }>(`/api/v1/connectors/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.all });
      toast({ variant: 'success', message: 'Connector deleted.' });
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Failed to delete connector.' });
    },
  });
}

/**
 * useTestConnector — POST /api/v1/connectors/test
 * Tests connectivity for a new connector before saving.
 * Returns { success, message, scopes? }.
 */
export function useTestConnector() {
  return useMutation({
    mutationFn: (body: TestConnectorBody) =>
      api<TestConnectorResult>('/api/v1/connectors/test', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    // No cache invalidation needed — test does not mutate state.
    retry: 0,
  });
}

/**
 * useSyncConnector — POST /api/v1/connectors/{id}/sync
 * Triggers an immediate sync. Toasts based on response status.
 *   STARTED       → "Sync started."
 *   ALREADY_RUNNING → "Sync already running."
 */
export function useSyncConnector() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (id: string) =>
      api<SyncConnectorResult>(`/api/v1/connectors/${id}/sync`, {
        method: 'POST',
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.connectors.all });
      if (data.status === 'ALREADY_RUNNING') {
        toast({ variant: 'info', message: 'Sync already running.' });
      } else {
        toast({ variant: 'success', message: 'Sync started.' });
      }
    },
    onError: (err: Error) => {
      toast({ variant: 'error', message: err.message || 'Sync failed.' });
    },
    retry: 0,
  });
}
