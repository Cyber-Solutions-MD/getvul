import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useTopTriage } from './use-top-triage';

const apiMock = vi.mocked(api);

function wrap(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useTopTriage', () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it('fetches /vulnerabilities?sort=triage&limit=N', async () => {
    apiMock.mockResolvedValueOnce({
      items: [],
      total: 0,
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock).toHaveBeenCalledWith(
      '/api/v1/vulnerabilities?sort=triage&limit=5',
      expect.any(Object),
    );
  });

  it('passes staleTime:60000 + retry:0 (D-D-07 — not in retry tier)', async () => {
    apiMock.mockResolvedValue({ items: [], total: 0 });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => {
      expect(qc.getQueryCache().findAll().length).toBeGreaterThan(0);
    });
    const opts = qc.getQueryCache().findAll()[0]!.options as unknown as Record<
      string,
      unknown
    >;
    expect(opts.staleTime).toBe(60_000);
    expect(opts.retry).toBe(0);
  });

  it('BL-02: adapts backend VulnerabilitySummary wire format (asset_hostname → host, missing cvss/sla → null)', async () => {
    apiMock.mockResolvedValueOnce({
      items: [
        {
          id: 'v1',
          cve_id: 'CVE-2024-X',
          severity: 'CRITICAL',
          source: 'tenable',
          status: 'OPEN',
          exploit_available: true,
          cisa_kev: true,
          affected_product: 'OpenSSL',
          asset_id: 'a1',
          asset_hostname: 'prod-web-01',
          first_detected_at: '2026-05-01T00:00:00Z',
          last_seen_at: '2026-05-18T00:00:00Z',
        },
      ],
      total: 1,
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const adapted = result.current.data!.items[0];
    expect(adapted.host).toBe('prod-web-01');
    expect(adapted.cvss_v3_score).toBeNull();
    expect(adapted.sla_due_at).toBeNull();
    expect(adapted.severity).toBe('CRITICAL');
    expect(adapted.cisa_kev).toBe(true);
  });

  it('BL-02: collapses unknown severity to LOW so glyph lookup never throws', async () => {
    apiMock.mockResolvedValueOnce({
      items: [
        {
          id: 'v2',
          cve_id: null,
          severity: 'UNKNOWN_SEVERITY',
          source: 'tenable',
          status: 'OPEN',
          exploit_available: false,
          cisa_kev: false,
          affected_product: null,
          asset_id: null,
          asset_hostname: null,
          first_detected_at: '2026-05-01T00:00:00Z',
          last_seen_at: '2026-05-18T00:00:00Z',
        },
      ],
      total: 1,
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { result } = renderHook(() => useTopTriage(5), { wrapper: wrap(qc) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data!.items[0].severity).toBe('LOW');
    expect(result.current.data!.items[0].cve_id).toBeNull();
    expect(result.current.data!.items[0].host).toBeNull();
  });
});
