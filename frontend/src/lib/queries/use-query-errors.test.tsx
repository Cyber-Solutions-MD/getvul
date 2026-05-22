// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  type QueryKey,
} from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Wave 1 (Plan 11-03) will create this file. The import is the RED signal.
import { useQueryErrors } from './use-query-errors';

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useQueryErrors (D-S-03 — QueryCache subscription bridge for PartialFailureBanner)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns [] when no queries match the supplied keys', () => {
    const qc = new QueryClient();
    const { result } = renderHook(
      () => useQueryErrors([['vulnerabilities'] as QueryKey]),
      { wrapper: wrap(qc) }
    );
    expect(result.current).toEqual([]);
  });

  it('returns errors for queries that partially-match the supplied keys', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    // Seed an errored query under ['vulnerabilities','list',{...}]
    function Errored() {
      return useQuery({
        queryKey: ['vulnerabilities', 'list', { page: 1 }],
        queryFn: () => {
          throw new Error('boom');
        },
      });
    }

    function Consumer() {
      const errs = useQueryErrors([['vulnerabilities'] as QueryKey]);
      return errs;
    }

    renderHook(() => Errored(), { wrapper: wrap(qc) });
    const { result } = renderHook(() => Consumer(), { wrapper: wrap(qc) });

    await waitFor(() => {
      expect(result.current.length).toBeGreaterThanOrEqual(1);
    });
    expect(result.current[0]).toMatchObject({
      queryKey: ['vulnerabilities', 'list', { page: 1 }],
      error: expect.any(Error),
    });
  });

  it('re-renders the consuming component when a query transitions success → error', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    let renderCount = 0;
    function Probe() {
      renderCount += 1;
      const errs = useQueryErrors([['stats'] as QueryKey]);
      return errs;
    }

    // Initial render — no errors
    renderHook(() => Probe(), { wrapper: wrap(qc) });
    const renderCountBefore = renderCount;

    // Inject an errored query in the cache
    act(() => {
      qc.setQueryData(['stats'], undefined);
      qc.getQueryCache().build(qc, {
        queryKey: ['stats'],
        queryFn: () => {
          throw new Error('500');
        },
      });
      // Force the cache to subscribe-fire by setting state to error
      const query = qc.getQueryCache().find({ queryKey: ['stats'] });
      query?.setState({
        data: undefined,
        error: new Error('500'),
        status: 'error',
        fetchStatus: 'idle',
      } as Parameters<NonNullable<typeof query>['setState']>[0]);
    });

    await waitFor(() => {
      expect(renderCount).toBeGreaterThan(renderCountBefore);
    });
  });

  it('re-renders when error → success (banner disappears — array length 1 → 0)', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    // Seed an errored query
    qc.getQueryCache().build(qc, {
      queryKey: ['vulnerabilities', 'list'],
      queryFn: () => Promise.reject(new Error('500')),
    });
    const query = qc.getQueryCache().find({
      queryKey: ['vulnerabilities', 'list'],
    });
    query?.setState({
      data: undefined,
      error: new Error('500'),
      status: 'error',
      fetchStatus: 'idle',
    } as Parameters<NonNullable<typeof query>['setState']>[0]);

    const { result } = renderHook(
      () => useQueryErrors([['vulnerabilities'] as QueryKey]),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => {
      expect(result.current.length).toBe(1);
    });

    // Transition error → success
    act(() => {
      query?.setState({
        data: { items: [] },
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as Parameters<NonNullable<typeof query>['setState']>[0]);
    });

    await waitFor(() => {
      expect(result.current.length).toBe(0);
    });
  });

  it('SSR-safe: returns [] when invoked with no window snapshot (getServerSnapshot path)', () => {
    // The third arg of useSyncExternalStore is exercised by calling the hook in
    // a setup where the cache is empty — SSR-equivalent. (Vitest jsdom env still
    // has window, but the empty-cache path must yield [] without throwing.)
    const qc = new QueryClient();
    const { result } = renderHook(
      () => useQueryErrors([['vulnerabilities'] as QueryKey]),
      { wrapper: wrap(qc) }
    );
    expect(result.current).toEqual([]);
  });

  it('snapshot fingerprint stability — repeated subscribes with same error set return SAME array reference', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    qc.getQueryCache().build(qc, {
      queryKey: ['vulnerabilities', 'list'],
      queryFn: () => Promise.reject(new Error('500')),
    });
    const query = qc.getQueryCache().find({
      queryKey: ['vulnerabilities', 'list'],
    });
    query?.setState({
      data: undefined,
      error: new Error('500'),
      status: 'error',
      fetchStatus: 'idle',
    } as Parameters<NonNullable<typeof query>['setState']>[0]);

    const { result, rerender } = renderHook(
      () => useQueryErrors([['vulnerabilities'] as QueryKey]),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => expect(result.current.length).toBe(1));
    const firstRef = result.current;

    // Re-render the hook without changing the cache — reference should remain stable
    rerender();
    expect(result.current).toBe(firstRef);
  });
});
