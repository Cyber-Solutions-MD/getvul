import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// `api` must be mocked BEFORE import (hoisted vi.mock pattern). The hook
// posts {assigned_user_email} to /api/v1/assets/{id}/owner and returns the
// updated asset (Plan 12-02 contract).
vi.mock('@/lib/api', () => ({ api: vi.fn() }));

// Toast is observed via spy — useReassignAsset emits success / error toasts
// per ROADMAP SC-6 (toast surface). The test mocks the provider hook directly
// to avoid wiring a full <ToastProvider> tree.
const toastFn = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: toastFn }),
}));

import { api } from '@/lib/api';
import { useReassignAsset } from './use-reassign-asset';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useReassignAsset', () => {
  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('POSTs /api/v1/assets/{id}/owner with assigned_user_email body', async () => {
    apiMock.mockResolvedValue({
      id: 'a1',
      hostname: 'h',
      assigned_user: 'bob@example.com',
      directory_user: null,
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useReassignAsset('a1'), { wrapper: wrap(qc) });

    result.current.mutate('bob@example.com');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/assets/a1/owner',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ assigned_user_email: 'bob@example.com' }),
      }),
    );
  });

  it('invalidates assets.byId(id) + assets.all on success', async () => {
    apiMock.mockResolvedValue({
      id: 'a1', hostname: 'h', assigned_user: 'carol@example.com', directory_user: null,
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const invalidate = vi.spyOn(qc, 'invalidateQueries');

    const { result } = renderHook(() => useReassignAsset('a1'), { wrapper: wrap(qc) });
    result.current.mutate('carol@example.com');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callKeys = invalidate.mock.calls.map((c) => c[0]?.queryKey);
    expect(callKeys).toContainEqual(queryKeys.assets.byId('a1'));
    expect(callKeys).toContainEqual(queryKeys.assets.all);
  });

  it('optimistically patches assigned_user in cache BEFORE network resolves (VALIDATION manual-only #3)', async () => {
    // Block the response so we can inspect cache mid-flight.
    let resolveApi: (v: unknown) => void = () => {};
    apiMock.mockImplementation(
      () => new Promise((res) => { resolveApi = res; }),
    );
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    // Seed the cache with a "before" asset record.
    qc.setQueryData(queryKeys.assets.byId('a1'), {
      id: 'a1', hostname: 'h', assigned_user: 'old@example.com',
    });

    const { result } = renderHook(() => useReassignAsset('a1'), { wrapper: wrap(qc) });
    result.current.mutate('new@example.com');

    // onMutate has run synchronously — cache should already reflect the new value.
    await waitFor(() => {
      const cached = qc.getQueryData(queryKeys.assets.byId('a1')) as { assigned_user: string };
      expect(cached.assigned_user).toBe('new@example.com');
    });

    resolveApi({ id: 'a1', hostname: 'h', assigned_user: 'new@example.com', directory_user: null });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('rolls back cache on error and emits an error toast', async () => {
    apiMock.mockRejectedValue(new Error('boom'));
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    qc.setQueryData(queryKeys.assets.byId('a1'), {
      id: 'a1', hostname: 'h', assigned_user: 'old@example.com',
    });

    const { result } = renderHook(() => useReassignAsset('a1'), { wrapper: wrap(qc) });
    result.current.mutate('new@example.com');

    await waitFor(() => expect(result.current.isError).toBe(true));
    const cached = qc.getQueryData(queryKeys.assets.byId('a1')) as { assigned_user: string };
    expect(cached.assigned_user).toBe('old@example.com');
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'error' }),
    );
  });

  it('emits a success toast naming the new owner', async () => {
    apiMock.mockResolvedValue({
      id: 'a1', hostname: 'h', assigned_user: 'bob@example.com', directory_user: null,
    });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    const { result } = renderHook(() => useReassignAsset('a1'), { wrapper: wrap(qc) });
    result.current.mutate('bob@example.com');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'success',
        message: expect.stringContaining('bob@example.com'),
      }),
    );
  });
});
