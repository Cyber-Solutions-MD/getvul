import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useSnoozeMutation } from './use-snooze';
import { queryKeys } from '@/lib/queries/keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('useSnoozeMutation', () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue({ message: 'Snoozed', until: '2026-05-15T13:00:00Z' });
  });

  it('POSTs /vulnerabilities/{id}/snooze with JSON body', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useSnoozeMutation(), { wrapper: wrap(qc) });

    result.current.mutate({ id: 'vuln-1', until: '2026-05-15T13:00:00Z' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities/vuln-1/snooze',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ until: '2026-05-15T13:00:00Z' }),
      }),
    );
  });

  it('invalidates the 3 D-D-13 keys on success (stats / dashboardTiles / all)', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useSnoozeMutation(), { wrapper: wrap(qc) });
    result.current.mutate({ id: 'vuln-1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callKeys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.stats());
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.dashboardTiles());
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.all);
  });
});
