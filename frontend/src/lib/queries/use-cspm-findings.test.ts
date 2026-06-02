/**
 * TDD RED — use-cspm-findings.ts
 * Tests for useCspmFindings, useComplianceFrameworks hooks.
 *
 * Plan 14-03, Task 1.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mock api ──────────────────────────────────────────────────────────────────
vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));
import { api } from '@/lib/api';
const mockApi = vi.mocked(api);

// ── Helpers ───────────────────────────────────────────────────────────────────
function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

// ── Test 1: useCspmFindings ───────────────────────────────────────────────────
describe('useCspmFindings', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('GETs /api/v1/cspm with filter params and returns paginated items', async () => {
    const { useCspmFindings } = await import('./use-cspm-findings');
    const client = makeClient();
    const mockData = {
      items: [{ id: 'f1', rule_id: 'R1', severity: 'HIGH', status: 'OPEN', cloud_provider: 'AWS' }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    };
    mockApi.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useCspmFindings({ filters: { severity: ['HIGH'], source: [], status: [] }, page: 1 }),
      { wrapper: wrapper(client) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/cspm'),
      expect.anything(),
    );
    // Severity filter must be in the URL
    const url = mockApi.mock.calls[0][0] as string;
    expect(url).toContain('severity=HIGH');
  });
});

// ── Test 2: useComplianceFrameworks ──────────────────────────────────────────
describe('useComplianceFrameworks', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('GETs /api/v1/cspm/compliance and returns framework array', async () => {
    const { useComplianceFrameworks } = await import('./use-cspm-findings');
    const client = makeClient();
    const mockData = [
      { name: 'CIS AWS', total_controls: 100, passed: 80, failed: 15, suppressed: 5, pass_rate: 80 },
    ];
    mockApi.mockResolvedValueOnce(mockData);

    const { result } = renderHook(
      () => useComplianceFrameworks(),
      { wrapper: wrapper(client) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/cspm/compliance'),
      expect.anything(),
    );
  });
});
