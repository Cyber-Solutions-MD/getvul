import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/lib/queries/use-stats', () => ({ useStats: vi.fn() }));
vi.mock('@/lib/queries/use-trends', () => ({ useTrends: vi.fn() }));
vi.mock('@/lib/queries/use-top-triage', () => ({ useTopTriage: vi.fn() }));
vi.mock('@/lib/queries/use-recent-notifications', () => ({
  useRecentNotifications: vi.fn(),
}));
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/lib/mutations/use-undo-snooze', () => ({
  useUndoSnoozeMutation: () => ({ mutate: vi.fn() }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => '/dashboard',
  useSearchParams: () => ({ get: () => null, toString: () => '' }),
}));
vi.mock('@/components/ui/trend-chart', () => ({
  TrendChart: () => <div data-testid="trend-chart-mock" aria-hidden />,
}));

import DashboardPage from './page';
import { useStats } from '@/lib/queries/use-stats';
import { useTrends } from '@/lib/queries/use-trends';
import { useTopTriage } from '@/lib/queries/use-top-triage';
import { useRecentNotifications } from '@/lib/queries/use-recent-notifications';

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

describe('DashboardPage axe', () => {
  beforeEach(() => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      refetch: vi.fn(),
      data: {
        dashboard_tiles: {
          critical_open: { value: 3, delta: 1, delta_direction: 'up' },
          sla_at_risk: { value: 12, delta: -2, delta_direction: 'down' },
          kev: { value: 5, delta: 0, delta_direction: 'flat' },
          mttr_30d: { value: '4.2d', delta: null, delta_direction: null },
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
      },
    });
    (useTrends as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        severity_trends: {
          '2026-04-01': { critical: 1, high: 2, medium: 3, low: 4 },
          '2026-04-02': { critical: 2, high: 1, medium: 4, low: 3 },
        },
      },
    });
    (useTopTriage as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        items: [
          {
            id: '1',
            cve_id: 'CVE-2024-A',
            severity: 'CRITICAL',
            host: 'h1',
            cvss_v3_score: 9.8,
            cisa_kev: true,
            sla_due_at: null,
          },
          {
            id: '2',
            cve_id: 'CVE-2024-B',
            severity: 'HIGH',
            host: 'h2',
            cvss_v3_score: 8.0,
            cisa_kev: false,
            sla_due_at: null,
          },
        ],
      },
    });
    (useRecentNotifications as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        items: [
          {
            id: 'n1',
            category: 'new_critical_vuln',
            title: 'Critical found',
            body: null,
            occurred_at: '2026-05-15T12:00:00Z',
          },
        ],
      },
    });
  });

  it('full-page has no axe violations', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
    const { container } = render(
      <QueryClientProvider client={qc}>
        <DashboardPage />
      </QueryClientProvider>
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
