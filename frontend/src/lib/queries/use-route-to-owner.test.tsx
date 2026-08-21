import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// `api` must be mocked BEFORE import (hoisted vi.mock pattern) — mirrors
// use-reassign-asset.test.tsx. The hook POSTs (no body) to
// /api/v1/coverage/assets/{id}/route-to-owner and returns
// {hostname, routed_to}.
vi.mock('@/lib/api', () => ({ api: vi.fn() }));

const toastFn = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: toastFn }),
}));

import { api } from '@/lib/api';
import { useRouteToOwner } from './use-route-to-owner';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(qc: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

describe('useRouteToOwner', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs /api/v1/coverage/assets/{id}/route-to-owner with no body', async () => {
    apiMock.mockResolvedValue({ hostname: 'prod-db-01', routed_to: 'Jane Doe' });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useRouteToOwner('a1'), { wrapper: wrap(qc) });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/coverage/assets/a1/route-to-owner',
      expect.objectContaining({ method: 'POST' }),
    );
    // No request body — the endpoint resolves the owner server-side.
    const [, opts] = apiMock.mock.calls[0];
    expect((opts as { body?: unknown }).body).toBeUndefined();
  });

  it('never retries a failed mutation (retry: 0 — audit/notification side effects)', async () => {
    apiMock.mockRejectedValue(new Error('boom'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useRouteToOwner('a1'), { wrapper: wrap(qc) });

    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  it('invalidates coverage.all on success', async () => {
    apiMock.mockResolvedValue({ hostname: 'prod-db-01', routed_to: 'Jane Doe' });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useRouteToOwner('a1'), { wrapper: wrap(qc) });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callKeys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(callKeys).toContainEqual(queryKeys.coverage.all);
  });

  it('emits the exact success toast "{hostname} routed to {routed_to}"', async () => {
    apiMock.mockResolvedValue({ hostname: 'prod-db-01', routed_to: 'Jane Doe' });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useRouteToOwner('a1'), { wrapper: wrap(qc) });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toastFn).toHaveBeenCalledWith({
      variant: 'success',
      message: 'prod-db-01 routed to Jane Doe',
    });
  });

  it('emits the exact UI-SPEC error toast copy on failure', async () => {
    apiMock.mockRejectedValue(new Error('network down'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useRouteToOwner('a1'), { wrapper: wrap(qc) });
    result.current.mutate();
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastFn).toHaveBeenCalledWith({
      variant: 'error',
      message:
        "Couldn't send the notification. Try again, or check the device's owner directly in your directory connector.",
    });
  });
});
