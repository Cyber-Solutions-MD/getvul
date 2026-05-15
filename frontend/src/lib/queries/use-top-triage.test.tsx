import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useTopTriage } from './use-top-triage';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useTopTriage', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('fetches /vulnerabilities?sort=triage&limit=N', async () => {
    apiMock.mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities?sort=triage&limit=5',
      expect.any(Object),
    );
  });

  it('passes staleTime:60000 + retry:0 (D-D-07 — not in retry tier)', async () => {
    apiMock.mockResolvedValue({ items: [], total: 0 });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<
      string,
      unknown
    >;
    expect(opts.staleTime).toBe(60_000);
    expect(opts.retry).toBe(0);
  });
});
