import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';

// `api` must be mocked BEFORE import (hoisted vi.mock pattern) — mirrors
// use-reassign-asset.test.tsx.
vi.mock('@/lib/api', () => ({ api: vi.fn() }));

const toastFn = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: toastFn }),
}));

import { api } from '@/lib/api';
import { useMarkBlocked } from './use-mark-blocked';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(qc: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

// Phase 18 (18-00 Task 3) — Pitfall 1 regression guard: the optimistic list
// patch must target the FUZZY ['tickets','list'] prefix (setQueriesData),
// not the exact ['tickets'] key (setQueryData), or the board/list row never
// moves until the server round-trip completes.
describe('useMarkBlocked — optimistic list-cache patch (Pitfall 1)', () => {
  const listKey = queryKeys.tickets.list({ filters: {}, page: 1, view: 'list' });

  beforeEach(() => {
    apiMock.mockReset();
    toastFn.mockReset();
  });

  it('onMutate flips blocked+blocked_reason in EVERY cached [\'tickets\',\'list\',*] query', async () => {
    let resolveApi: (v: unknown) => void = () => {};
    apiMock.mockImplementation(() => new Promise((res) => { resolveApi = res; }));

    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    qc.setQueryData(listKey, {
      items: [{ id: 't1', blocked: false, blocked_reason: null }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    const { result } = renderHook(() => useMarkBlocked(), { wrapper: wrap(qc) });
    result.current.mutate({ id: 't1', blocked: true, blocked_reason: 'flaky dep' });

    // onMutate runs synchronously — the list cache should already flip
    // BEFORE the mocked network call resolves (in-flight window).
    await waitFor(() => {
      const cached = qc.getQueryData(listKey) as { items: Array<{ id: string; blocked: boolean; blocked_reason: string | null }> };
      expect(cached.items[0].blocked).toBe(true);
      expect(cached.items[0].blocked_reason).toBe('flaky dep');
    });

    resolveApi({ blocked: true, blocked_reason: 'flaky dep' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it('onError restores every captured list snapshot AND the byId snapshot', async () => {
    apiMock.mockRejectedValue(new Error('boom'));

    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });
    qc.setQueryData(listKey, {
      items: [{ id: 't1', blocked: false, blocked_reason: null }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    qc.setQueryData(queryKeys.tickets.byId('t1'), {
      id: 't1',
      blocked: false,
      blocked_reason: null,
    });

    const { result } = renderHook(() => useMarkBlocked(), { wrapper: wrap(qc) });
    result.current.mutate({ id: 't1', blocked: true, blocked_reason: 'flaky dep' });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const listCached = qc.getQueryData(listKey) as { items: Array<{ id: string; blocked: boolean }> };
    expect(listCached.items[0].blocked).toBe(false);

    const byIdCached = qc.getQueryData(queryKeys.tickets.byId('t1')) as { blocked: boolean };
    expect(byIdCached.blocked).toBe(false);

    expect(toastFn).toHaveBeenCalledWith(expect.objectContaining({ variant: 'error' }));
  });

  it('sends ONLY {blocked, blocked_reason} in the mutation body (T-13-23 mass-assignment guard)', async () => {
    apiMock.mockResolvedValue({ blocked: true, blocked_reason: 'x' });
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 } } });

    const { result } = renderHook(() => useMarkBlocked(), { wrapper: wrap(qc) });
    result.current.mutate({ id: 't1', blocked: true, blocked_reason: 'x' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/tickets/t1/blocked',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ blocked: true, blocked_reason: 'x' }),
      }),
    );
  });
});
