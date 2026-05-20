import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useStats } from './use-stats';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useStats', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('uses the vulnerabilities.stats() query key and resolves with the typed response', async () => {
    const payload = {
      dashboard_tiles: {
        critical_open: { value: 3, delta: 1, delta_direction: 'up' as const },
        sla_at_risk: { value: 7, delta: 0, delta_direction: 'flat' as const },
        kev: { value: 2, delta: -1, delta_direction: 'down' as const },
        mttr_30d: { value: '4.2d', delta: null, delta_direction: null },
      },
      top_vuln: null,
      vuln_open_count: 12,
      asset_total_count: 25,
      ticket_open_count: 5,
      onboarding_state: 'ready' as const,
    };
    apiMock.mockResolvedValueOnce(payload);

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useStats(), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities/stats',
      expect.objectContaining({}),
    );

    // Confirms D-D-03 key shape — Plan 05 / Plan 03 read this key.
    const queries = qc.getQueryCache().findAll();
    expect(queries[0]?.queryKey).toEqual(queryKeys.vulnerabilities.stats());
  });

  it('passes staleTime:60000 + retry:1 + refetchOnWindowFocus:true (D-D-06 / D-D-07)', async () => {
    apiMock.mockResolvedValueOnce({});

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(() => useStats(), { wrapper: wrap(qc) });

    // Inspect the live Query observer's options — this reflects what the
    // hook actually passed to useQuery (the only stable surface; vi.spyOn
    // on ESM exports is not supported by Vitest).
    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    // QueryCache.options is typed narrowly; the runtime carries the full
    // useQuery argument set (D-D-06/07 fields). Cast to read them.
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<
      string,
      unknown
    >;
    expect(opts.staleTime).toBe(60_000);
    expect(opts.retry).toBe(1);
    expect(opts.refetchOnWindowFocus).toBe(true);
  });
});
