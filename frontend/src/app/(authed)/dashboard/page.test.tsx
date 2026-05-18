import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

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
// Mock the dynamic recharts wrapper so jsdom doesn't try to render SVG charts.
vi.mock('@/components/ui/trend-chart', () => ({
  TrendChart: () => <div data-testid="trend-chart-mock" />,
}));

import DashboardPage from './page';
import { useStats } from '@/lib/queries/use-stats';
import { useTrends } from '@/lib/queries/use-trends';
import { useTopTriage } from '@/lib/queries/use-top-triage';
import { useRecentNotifications } from '@/lib/queries/use-recent-notifications';

// jsdom doesn't implement ResizeObserver — recharts/inert components occasionally hit it.
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const happyStats = {
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
};

describe('DashboardPage', () => {
  beforeEach(() => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(happyStats);
    (useTrends as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: { severity_trends: {} },
    });
    (useTopTriage as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: { items: [] },
    });
    (useRecentNotifications as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: { items: [] },
    });
  });

  it('renders all five sections when stats.onboarding_state=ready (UX-02-01..05)', async () => {
    render(<DashboardPage />, { wrapper });
    expect(await screen.findByText(/3 critical CVEs need your eyes/)).toBeInTheDocument();
    expect(screen.getByText(/Critical · open/)).toBeInTheDocument();
    expect(screen.getByText(/30-day vulnerability trend/)).toBeInTheDocument();
    expect(screen.getByText(/Top 5 to triage/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Recent activity/)).toBeInTheDocument();
  });

  it('renders the OnboardingPanel for state=no_scanners (UX-02-06)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      ...happyStats,
      data: { ...happyStats.data, onboarding_state: 'no_scanners' },
    });
    render(<DashboardPage />, { wrapper });
    expect(screen.getByText('No scanners connected yet')).toBeInTheDocument();
    expect(screen.getByText('Connect a scanner')).toBeInTheDocument();
  });

  it('renders quiet-win when critical_open.value === 0 (UX-02-06)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      ...happyStats,
      data: {
        ...happyStats.data,
        dashboard_tiles: {
          ...happyStats.data.dashboard_tiles,
          critical_open: { value: 0, delta: 0, delta_direction: 'flat' },
        },
      },
    });
    render(<DashboardPage />, { wrapper });
    expect(screen.getByText('Nothing critical right now')).toBeInTheDocument();
  });

  it('partial-failure: hero error does not unmount Top5Card (D-D-10 + D-E-01)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: { code: 503, requestId: 'req_abc' },
      refetch: vi.fn(),
      data: undefined,
    });
    render(<DashboardPage />, { wrapper });
    expect(screen.getByText(/Hero unavailable/)).toBeInTheDocument();
    // Other sections (whose hooks still return happy data) keep rendering.
    expect(screen.getByText(/Top 5 to triage/)).toBeInTheDocument();
  });
});
