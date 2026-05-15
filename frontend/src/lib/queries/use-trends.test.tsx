import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useTrends } from './use-trends';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useTrends', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('encodes range into query key + URL (D-D-03)', async () => {
    apiMock.mockResolvedValue({ severity_trends: {} });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTrends('7d'), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Key includes the range param.
    const cached = qc.getQueryCache().findAll();
    expect(cached[0]?.queryKey).toEqual([
      'vulnerabilities',
      'trends',
      { range: '7d' },
    ]);
    // URL encodes the matching `days` value.
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities/trends?days=7',
      expect.any(Object),
    );
  });

  it('passes staleTime:60000 + retry:1 + refetchOnWindowFocus:false', async () => {
    apiMock.mockResolvedValue({ severity_trends: {} });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(() => useTrends('30d'), { wrapper: wrap(qc) });

    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<
      string,
      unknown
    >;
    expect(opts.staleTime).toBe(60_000);
    expect(opts.retry).toBe(1);
    expect(opts.refetchOnWindowFocus).toBe(false);
  });
});
