/**
 * use-connectors-admin.test.ts — TDD RED-phase tests for useConnectorsAdmin hooks.
 *
 * Test 1: useConnectorsList returns the connectors array from GET /api/v1/connectors (mock fetch).
 * Test 2: useSyncConnector mutation POSTs /api/v1/connectors/{id}/sync and invalidates queryKeys.connectors.all.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import {
  useConnectorsList,
  useSyncConnector,
  useCreateConnector,
  useUpdateConnector,
  useDeleteConnector,
  useTestConnector,
  useConnectorTypes,
} from './use-connectors-admin';

// ——— Mock api so tests don't make real HTTP calls ———
vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

import { api } from '@/lib/api';
const mockApi = api as ReturnType<typeof vi.fn>;

// ——— Mock useToast ———
const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

const MOCK_CONNECTORS = [
  {
    id: 'conn-1',
    connector_type: 'CROWDSTRIKE',
    connector_name: 'CrowdStrike Spotlight',
    is_enabled: true,
    config: {},
    has_credentials: true,
    last_sync_at: '2026-06-02T10:00:00Z',
    last_sync_status: 'ok',
    last_sync_record_count: 512,
    sync_interval_minutes: 15,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-06-02T10:00:00Z',
  },
  {
    id: 'conn-2',
    connector_type: 'JIRA',
    connector_name: 'Jira Cloud',
    is_enabled: true,
    config: {},
    has_credentials: true,
    last_sync_at: null,
    last_sync_status: null,
    last_sync_record_count: null,
    sync_interval_minutes: 30,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('useConnectorsList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Test 1: returns the connectors array from GET /api/v1/connectors', async () => {
    mockApi.mockResolvedValueOnce(MOCK_CONNECTORS);
    const { result } = renderHook(() => useConnectorsList(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi).toHaveBeenCalledWith('/api/v1/connectors', expect.any(Object));
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data![0].connector_type).toBe('CROWDSTRIKE');
  });
});

describe('useSyncConnector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Test 2: POSTs /api/v1/connectors/{id}/sync and shows STARTED toast', async () => {
    mockApi.mockResolvedValueOnce({ status: 'STARTED', message: 'Sync started' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);

    const { result } = renderHook(() => useSyncConnector(), { wrapper });
    result.current.mutate('conn-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi).toHaveBeenCalledWith(
      '/api/v1/connectors/conn-1/sync',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Sync started.' }),
    );
  });

  it('Test 2b: shows info toast when ALREADY_RUNNING', async () => {
    mockApi.mockResolvedValueOnce({ status: 'ALREADY_RUNNING', message: 'Sync already running' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);

    const { result } = renderHook(() => useSyncConnector(), { wrapper });
    result.current.mutate('conn-1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Sync already running.' }),
    );
  });
});

describe('useCreateConnector', () => {
  it('exports useCreateConnector', () => {
    expect(typeof useCreateConnector).toBe('function');
  });
});

describe('useUpdateConnector', () => {
  it('exports useUpdateConnector', () => {
    expect(typeof useUpdateConnector).toBe('function');
  });
});

describe('useDeleteConnector', () => {
  it('exports useDeleteConnector', () => {
    expect(typeof useDeleteConnector).toBe('function');
  });
});

describe('useTestConnector', () => {
  it('exports useTestConnector', () => {
    expect(typeof useTestConnector).toBe('function');
  });
});

describe('useConnectorTypes', () => {
  it('exports useConnectorTypes', () => {
    expect(typeof useConnectorTypes).toBe('function');
  });
});
