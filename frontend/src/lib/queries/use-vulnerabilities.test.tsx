// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import {
  useVulnerabilities,
  buildSearchParams,
} from './use-vulnerabilities';
import { queryKeys } from './keys';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = 'Wrapper';
  return Wrapper;
}

const emptyResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 50,
  total_pages: 0,
  facets: { severity: {}, source: {}, status: {} },
};

describe('useVulnerabilities + buildSearchParams (query-key shape + filter composition)', () => {
  beforeEach(() => {
    apiMock.mockReset();
    apiMock.mockResolvedValue(emptyResponse);
  });

  it('Test 1: queryKey includes filters, group, page, sort, order (D-D-03 domain-first)', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(
      () =>
        useVulnerabilities({
          filters: { severity: ['critical'] },
          group: 'cve',
          page: 1,
          sort: 'cve_id',
          order: 'asc',
        }),
      { wrapper: wrap(qc) }
    );

    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    const key = qc.getQueryCache().findAll()[0]!.queryKey;
    expect(key).toEqual(
      queryKeys.vulnerabilities.list({
        filters: { severity: ['critical'] },
        group: 'cve',
        page: 1,
        sort: 'cve_id',
        order: 'asc',
      })
    );
  });

  it('Test 2: buildSearchParams composes severity + source + facets + page', () => {
    const sp = buildSearchParams({
      filters: { severity: ['critical', 'high'], source: ['QUALYS'] },
      group: 'cve',
      page: 1,
      sort: '',
      order: 'asc',
    });
    expect(sp.getAll('severity')).toEqual(['critical', 'high']);
    expect(sp.getAll('source')).toEqual(['QUALYS']);
    expect(sp.get('facets')).toBe('severity,source,status');
    expect(sp.get('page')).toBe('1');
    // No group=host when group is 'cve' (default).
    expect(sp.get('group')).toBeNull();
  });

  it("Test 3: ?group=host flows through when opts.group === 'host'", () => {
    const sp = buildSearchParams({
      filters: {},
      group: 'host',
      page: 1,
      sort: '',
      order: 'asc',
    });
    expect(sp.get('group')).toBe('host');
  });

  it('Test 4: ?facets=severity,source,status is ALWAYS appended (D-F-02)', () => {
    const sp1 = buildSearchParams({ filters: {}, group: 'cve', page: 1, sort: '', order: 'asc' });
    expect(sp1.get('facets')).toBe('severity,source,status');

    const sp2 = buildSearchParams({
      filters: { search: 'log4j', kev_only: true, exploit_only: true },
      group: 'host',
      page: 2,
      sort: 'sla_due_at',
      order: 'desc',
    });
    expect(sp2.get('facets')).toBe('severity,source,status');
    expect(sp2.get('search')).toBe('log4j');
    expect(sp2.get('cisa_kev')).toBe('true');
    expect(sp2.get('exploit_available')).toBe('true');
    expect(sp2.get('sort')).toBe('sla_due_at');
    expect(sp2.get('order')).toBe('desc');
  });

  it('Test 5: 401 on the underlying api() call rejects the query (api.ts BL-06 safe-method path is silent; this only verifies error propagation)', async () => {
    apiMock.mockRejectedValue(new Error('Session expired. Please login again.'));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

    const { result } = renderHook(
      () =>
        useVulnerabilities({
          filters: {},
          group: 'cve',
          page: 1,
          sort: '',
          order: 'asc',
        }),
      { wrapper: wrap(qc) }
    );

    // retry: 1 with TanStack's default exponential backoff (~1000ms) means
    // the error settles after the second attempt; allow up to 5s.
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 5000 });
    expect((result.current.error as Error).message).toContain('Session expired');
  });
});
