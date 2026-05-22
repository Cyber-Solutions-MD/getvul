// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';

// Wave 1 (Plan 11-03) will create this file. Import is the RED signal.
// `buildSearchParams` is exported alongside the hook for testability per the
// plan's behavior block.
import {
  useVulnerabilities,
  buildSearchParams,
} from './use-vulnerabilities';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useVulnerabilities (D-D-03 query-key + D-F-02 facet composition)', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('queryKey includes filters, group, page, sort, order in the third positional object', async () => {
    apiMock.mockResolvedValueOnce({ items: [], total: 0, facets: {} });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    const opts = {
      filters: { severity: ['critical'] as const, source: ['QUALYS'] as const },
      group: 'cve' as const,
      page: 1,
      sort: 'cve_id',
      order: 'asc' as const,
    };
    const { result } = renderHook(() => useVulnerabilities(opts), {
      wrapper: wrap(qc),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // D-D-03: domain-first key shape ['vulnerabilities','list', { ...opts }]
    const queries = qc.getQueryCache().findAll();
    const key = queries[0]?.queryKey as readonly unknown[];
    expect(key[0]).toBe('vulnerabilities');
    expect(key[1]).toBe('list');
    expect(key[2]).toMatchObject({
      filters: { severity: ['critical'], source: ['QUALYS'] },
      group: 'cve',
      page: 1,
      sort: 'cve_id',
      order: 'asc',
    });
  });

  it('buildSearchParams composes ?severity=critical&severity=high&source=QUALYS&facets=...&page=1', () => {
    const qs = buildSearchParams({
      filters: {
        severity: ['critical', 'high'],
        source: ['QUALYS'],
      },
      group: 'cve',
      page: 1,
      sort: 'cve_id',
      order: 'asc',
    });
    expect(qs).toContain('severity=critical');
    expect(qs).toContain('severity=high');
    expect(qs).toContain('source=QUALYS');
    expect(qs).toContain('facets=severity%2Csource%2Cstatus');
    expect(qs).toContain('page=1');
  });

  it("?group=host flows through to the request URL when opts.group === 'host'", async () => {
    apiMock.mockResolvedValueOnce({ items: [], total: 0, facets: {} });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    renderHook(
      () =>
        useVulnerabilities({
          filters: {},
          group: 'host',
          page: 1,
          sort: 'triage',
          order: 'desc',
        }),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => expect(apiMock).toHaveBeenCalledTimes(1));
    const url = apiMock.mock.calls[0][0] as string;
    expect(url).toContain('group=host');
  });

  it('?facets=severity,source,status is ALWAYS appended (per D-F-02 — chip counts stay synced)', async () => {
    apiMock.mockResolvedValueOnce({ items: [], total: 0, facets: {} });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    renderHook(
      () =>
        useVulnerabilities({
          filters: {},
          group: 'cve',
          page: 1,
          sort: 'triage',
          order: 'desc',
        }),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => expect(apiMock).toHaveBeenCalledTimes(1));
    const url = apiMock.mock.calls[0][0] as string;
    expect(url).toMatch(/facets=severity(?:%2C|,)source(?:%2C|,)status/);
  });

  it('401 on safe-method underlying api() call surfaces as the api.ts redirect path (no silent dirty data)', async () => {
    // Safe-method GET on the list endpoint follows the BL-06 silent-refresh
    // path in api.ts. From the hook's perspective the rejected promise on
    // refresh-failure flows out as a query error; happy-path is `Error`.
    apiMock.mockRejectedValueOnce(new Error('Session expired. Please login again.'));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    const { result } = renderHook(
      () =>
        useVulnerabilities({
          filters: {},
          group: 'cve',
          page: 1,
          sort: 'triage',
          order: 'desc',
        }),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as Error).message).toContain('Session expired');
  });
});
