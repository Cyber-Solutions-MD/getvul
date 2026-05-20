/**
 * Single-fetch invariant — Sidebar + DashboardPage share ONE /api/v1/vulnerabilities/stats
 * request when mounted under a shared QueryClientProvider.
 *
 * Phase 10 / Plan 10-06 / Task 3 (Warning 15) — see 10-VALIDATION.md.
 *
 * If TanStack Query ever drops cache-key de-duplication, or if Plan 02's
 * QueryClientProvider hoist regresses to two providers, the assertion `statsCalls.length
 * === 1` here trips and surfaces the regression in CI rather than in a /dashboard
 * production page-load.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the api() wrapper — Sidebar.useStats() and DashboardPage's useStats() both
// resolve through this single call site. We assert it is hit exactly once for the
// /stats path, regardless of how many components consume the query.
vi.mock('@/lib/api', () => ({
  api: vi.fn().mockResolvedValue({
    dashboard_tiles: {
      critical_open: { value: 3, delta: null, delta_direction: null },
      sla_at_risk:   { value: 12, delta: null, delta_direction: null },
      kev:           { value: 5,  delta: null, delta_direction: null },
      mttr_30d:      { value: '4.2d', delta: null, delta_direction: null },
    },
    top_vuln: {
      id: '00000000-0000-0000-0000-000000000001',
      cve_id: 'CVE-2024-1234',
      host: 'prod-db-01',
      path: 'Postgres path',
      cvss: 9.8,
      on_kev: true,
      exploited: true,
    },
    vuln_open_count: 200,
    asset_total_count: 50,
    ticket_open_count: 7,
    onboarding_state: 'ready',
  }),
}));

// Stub secondary queries so DashboardPage renders without hitting unrelated endpoints.
// We only care about the /stats fetch count here — the cache invariant is /stats-specific.
vi.mock('@/lib/queries/use-trends', () => ({
  useTrends: () => ({ isPending: false, error: null, data: { severity_trends: {} } }),
}));
vi.mock('@/lib/queries/use-top-triage', () => ({
  useTopTriage: () => ({ isPending: false, error: null, data: { items: [] } }),
}));
vi.mock('@/lib/queries/use-recent-notifications', () => ({
  useRecentNotifications: () => ({ isPending: false, error: null, data: { items: [] } }),
}));

vi.mock('next/navigation', () => ({
  useRouter:       () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname:     () => '/dashboard',
  useSearchParams: () => ({ get: () => null, toString: () => '' }),
}));

// recharts (route-split in production via D-C-03) probes ResizeObserver during mount
// in jsdom; stub it once globally so the chart primitive doesn't throw on import.
class RO {
  observe()    {}
  unobserve()  {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

import { Sidebar } from '@/components/shell/sidebar';
import DashboardPage from '@/app/(authed)/dashboard/page';
import { api } from '@/lib/api';

describe('Sidebar + DashboardPage single-fetch invariant', () => {
  it('shares one /stats fetch when both are mounted in the same QueryClientProvider tree', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: 0, staleTime: 60_000 } },
    });

    render(
      <QueryClientProvider client={qc}>
        <Sidebar />
        <DashboardPage />
      </QueryClientProvider>,
    );

    // Both components call useStats() with the same queryKey
    // (queryKeys.vulnerabilities.stats() per Plan 02). TanStack MUST de-dupe to a
    // SINGLE network fetch because the QueryClient + queryKey are identical.
    await waitFor(() => {
      const statsCalls = (api as unknown as { mock: { calls: unknown[][] } }).mock.calls.filter(
        (call) => call[0] === '/api/v1/vulnerabilities/stats',
      );
      expect(statsCalls.length).toBe(1);
    });
  });
});
