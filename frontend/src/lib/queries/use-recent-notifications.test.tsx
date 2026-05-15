import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useRecentNotifications } from './use-recent-notifications';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useRecentNotifications', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('fetches /notifications?page=1&page_size=5', async () => {
    apiMock.mockResolvedValueOnce({ items: [], total: 0 });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useRecentNotifications(), {
      wrapper: wrap(qc),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/notifications?page=1&page_size=5',
      expect.any(Object),
    );
  });

  it('passes staleTime:30000 + retry:0 (D-D-06)', async () => {
    apiMock.mockResolvedValue({ items: [], total: 0 });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(() => useRecentNotifications(), { wrapper: wrap(qc) });

    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<
      string,
      unknown
    >;
    expect(opts.staleTime).toBe(30_000);
    expect(opts.retry).toBe(0);
  });
});
