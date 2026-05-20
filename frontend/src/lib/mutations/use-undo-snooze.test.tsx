import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useUndoSnoozeMutation } from './use-undo-snooze';
import { queryKeys } from '@/lib/queries/keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useUndoSnoozeMutation (D-H-08 reverse path)', () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue({ message: 'Snooze undone' });
  });

  it('POSTs /vulnerabilities/{id}/unsnooze', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useUndoSnoozeMutation(), {
      wrapper: wrap(qc),
    });

    result.current.mutate({ id: 'vuln-1' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities/vuln-1/unsnooze',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('invalidates the same 3-key D-D-13 set as snooze', async () => {
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useUndoSnoozeMutation(), {
      wrapper: wrap(qc),
    });
    result.current.mutate({ id: 'vuln-1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callKeys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.stats());
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.dashboardTiles());
    expect(callKeys).toContainEqual(queryKeys.vulnerabilities.all);
  });
});
