/**
 * use-campaigns.test.ts — TDD tests for useCampaigns / useCampaignDetail.
 *
 * Test 1: useCampaigns calls api('/api/v1/campaigns') and returns the list.
 * Test 2: useCampaignDetail(id) hits /api/v1/campaigns/{id}.
 * Test 3: useCampaignDetail is disabled for an empty id (never fetches).
 * Test 4: both hooks set staleTime: 0 (D-07 — compute-on-read is never
 *         cached as authoritative).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useCampaigns, useCampaignDetail, type CampaignSummary } from './use-campaigns';

// ——— Mock api so tests don't make real HTTP calls ———
vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

import { api } from '@/lib/api';
const mockApi = api as ReturnType<typeof vi.fn>;

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

const MOCK_CAMPAIGNS: CampaignSummary[] = [
  {
    id: 'c1',
    remediation_id: 'CVE-2024-1234: openssl upgrade',
    status: 'ACTIVE',
    total: 10,
    open: 4,
    in_progress: 3,
    done: 3,
    pct_remediated: 30,
  },
];

describe('useCampaigns', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls api(/api/v1/campaigns) and returns the list', async () => {
    mockApi.mockResolvedValueOnce(MOCK_CAMPAIGNS);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCampaigns(), { wrapper: makeWrapper(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi).toHaveBeenCalledWith('/api/v1/campaigns', expect.any(Object));
    expect(result.current.data).toEqual(MOCK_CAMPAIGNS);
  });

  it('sets staleTime: 0 (D-07 compute-on-read is never cached as authoritative)', async () => {
    mockApi.mockResolvedValueOnce(MOCK_CAMPAIGNS);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderHook(() => useCampaigns(), { wrapper: makeWrapper(qc) });

    await waitFor(() => expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0));
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<string, unknown>;
    expect(opts.staleTime).toBe(0);
  });
});

describe('useCampaignDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('hits /api/v1/campaigns/{id}', async () => {
    mockApi.mockResolvedValueOnce({ ...MOCK_CAMPAIGNS[0], mttr_seconds: 3600 });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCampaignDetail('c1'), { wrapper: makeWrapper(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi).toHaveBeenCalledWith('/api/v1/campaigns/c1', expect.any(Object));
    expect(result.current.data?.mttr_seconds).toBe(3600);
  });

  it('is disabled for an empty id (never calls api)', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCampaignDetail(''), { wrapper: makeWrapper(qc) });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockApi).not.toHaveBeenCalled();
  });

  it('sets staleTime: 0', async () => {
    mockApi.mockResolvedValueOnce({ ...MOCK_CAMPAIGNS[0], mttr_seconds: null });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderHook(() => useCampaignDetail('c1'), { wrapper: makeWrapper(qc) });

    await waitFor(() => expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0));
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<string, unknown>;
    expect(opts.staleTime).toBe(0);
  });
});
