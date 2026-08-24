import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

// Phase 43 Plan 04 (RPT-02): mutable searchParams/router mocks so individual
// tests can simulate a `?lens=` param and assert `router.replace` calls
// (`useLens`'s URL persistence). vi.hoisted lets these be referenced inside
// the hoisted vi.mock factory below.
const { mockSearchParamsGet, mockRouterReplace } = vi.hoisted(() => ({
  mockSearchParamsGet: vi.fn((_key: string) => null as string | null),
  mockRouterReplace: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockRouterReplace }),
  usePathname: () => '/dashboard',
  useSearchParams: () => ({ get: mockSearchParamsGet, toString: () => '' }),
}));

// Mock the dynamic recharts wrapper so jsdom doesn't try to render SVG charts.
vi.mock('@/components/ui/trend-chart', () => ({
  TrendChart: () => <div data-testid="trend-chart-mock" />,
}));
vi.mock('@/components/analytics/risk-trend-chart', () => ({
  RiskTrendChart: () => <div data-testid="risk-trend-chart-mock" />,
}));

// Leadership/compliance-lens data hooks — mocked so switching lenses in this
// test file never issues a real network request.
vi.mock('@/lib/queries/use-analytics', async () => {
  const actual = await vi.importActual<typeof import('@/lib/queries/use-analytics')>(
    '@/lib/queries/use-analytics'
  );
  return { ...actual, useAnalytics: vi.fn() };
});
vi.mock('@/lib/queries/use-mttr-by-tier', () => ({ useMttrByTier: vi.fn() }));
vi.mock('@/lib/queries/use-sla-metrics', () => ({ useSlaMetrics: vi.fn() }));
vi.mock('@/lib/queries/use-compliance', () => ({ useComplianceOverview: vi.fn() }));

import DashboardPage from './page';
import { ApiError } from '@/lib/api';
import { useStats } from '@/lib/queries/use-stats';
import { useTrends } from '@/lib/queries/use-trends';
import { useTopTriage } from '@/lib/queries/use-top-triage';
import { useRecentNotifications } from '@/lib/queries/use-recent-notifications';
import { useAnalytics } from '@/lib/queries/use-analytics';
import { useMttrByTier } from '@/lib/queries/use-mttr-by-tier';
import { useSlaMetrics } from '@/lib/queries/use-sla-metrics';
import { useComplianceOverview } from '@/lib/queries/use-compliance';

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
    mockSearchParamsGet.mockReset().mockReturnValue(null);
    mockRouterReplace.mockClear();
    window.localStorage.clear();

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
    (useAnalytics as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      refetch: vi.fn(),
      data: { trend: [], boundaries: [], aging: [], aging_pct_overdue: 0, burndown: null, scope: 'all', group_name: null },
    });
    (useMttrByTier as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: [],
    });
    (useSlaMetrics as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: {
        sla_config: {},
        open_with_sla: 0,
        breached: 0,
        at_risk: 0,
        within_sla: 0,
        compliance_pct: 0,
        remediated_within_sla: 0,
        remediated_total: 0,
        breach_by_severity: {},
        avg_days_remaining: null,
      },
    });
    (useComplianceOverview as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: { controls: [] },
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

  // ── Phase 43 Plan 04 (RPT-02): lens switcher + branching ──────────────

  describe('lens switcher (RPT-02)', () => {
    it('defaults to analyst lens (no URL param, no localStorage) and renders the existing widget set', async () => {
      render(<DashboardPage />, { wrapper });
      expect(await screen.findByText(/3 critical CVEs need your eyes/)).toBeInTheDocument();
      const group = await screen.findByRole('group', { name: 'Dashboard lens' });
      expect(group).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Analyst' })).toHaveAttribute('aria-pressed', 'true');
      // No leadership/compliance widgets rendered.
      expect(screen.queryByText('Export board report')).not.toBeInTheDocument();
    });

    it('?lens=leadership renders the leadership widget set (no triage widgets)', async () => {
      mockSearchParamsGet.mockImplementation((key: string) => (key === 'lens' ? 'leadership' : null));
      render(<DashboardPage />, { wrapper });

      expect(await screen.findByText('Export board report')).toBeInTheDocument();
      expect(screen.getByText('MTTR by tier')).toBeInTheDocument();
      expect(screen.getByText('SLA compliance')).toBeInTheDocument();
      expect(screen.getByText('Framework posture')).toBeInTheDocument();
      // No analyst/IT-ops triage widgets.
      expect(screen.queryByText(/critical CVEs need your eyes/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Top 5 to triage/)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Recent activity/)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Leadership' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('?lens=compliance renders the compliance widget set + a link to the full compliance page', async () => {
      mockSearchParamsGet.mockImplementation((key: string) => (key === 'lens' ? 'compliance' : null));
      render(<DashboardPage />, { wrapper });

      expect(await screen.findByText('Framework posture')).toBeInTheDocument();
      expect(screen.getByText('SLA compliance')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'View full compliance page' })).toHaveAttribute(
        'href',
        '/dashboard/compliance'
      );
      expect(screen.queryByText('Export board report')).not.toBeInTheDocument();
    });

    it('switching lens updates the URL via router.replace and writes localStorage', async () => {
      const user = userEvent.setup();
      render(<DashboardPage />, { wrapper });
      const leadershipButton = await screen.findByRole('button', { name: 'Leadership' });
      await user.click(leadershipButton);

      expect(mockRouterReplace).toHaveBeenCalledWith('/dashboard?lens=leadership', { scroll: false });
      expect(window.localStorage.getItem('dashboard-lens')).toBe('leadership');
      // The widget set updates immediately, without needing the (mocked)
      // router to actually round-trip the URL.
      expect(await screen.findByText('Export board report')).toBeInTheDocument();
    });

    it('a bare /dashboard visit with a stored lens in localStorage (no URL param) seeds that lens', async () => {
      window.localStorage.setItem('dashboard-lens', 'compliance');
      render(<DashboardPage />, { wrapper });
      expect(await screen.findByText('Framework posture')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Compliance' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('the onboarding empty state preempts ALL lenses — the lens switcher does not render', () => {
      window.localStorage.setItem('dashboard-lens', 'leadership');
      (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        ...happyStats,
        data: { ...happyStats.data, onboarding_state: 'no_scanners' },
      });
      render(<DashboardPage />, { wrapper });
      expect(screen.getByText('No scanners connected yet')).toBeInTheDocument();
      expect(screen.queryByRole('group', { name: 'Dashboard lens' })).not.toBeInTheDocument();
      expect(screen.queryByText('Export board report')).not.toBeInTheDocument();
    });

    it('lens availability does not depend on User.role — all four segments always render', async () => {
      render(<DashboardPage />, { wrapper });
      await waitFor(() => {
        expect(screen.getByRole('group', { name: 'Dashboard lens' })).toBeInTheDocument();
      });
      for (const label of ['Analyst', 'IT-ops', 'Compliance', 'Leadership']) {
        expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
      }
    });
  });

  // ── WR-01 (43-REVIEW.md): leadership-lens tiles distinguish a genuine
  // backend error from an honestly-empty tenant, with a retry affordance. ──
  describe('leadership-lens error states (WR-01)', () => {
    beforeEach(() => {
      mockSearchParamsGet.mockImplementation((key: string) => (key === 'lens' ? 'leadership' : null));
    });

    it('MTTR tile: a non-admin 403 keeps the existing honest "Not yet measured" treatment (no banner)', async () => {
      (useMttrByTier as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        isPending: false,
        error: new ApiError('Forbidden', 403, 'req_mttr_403'),
        refetch: vi.fn(),
        data: undefined,
      });
      render(<DashboardPage />, { wrapper });
      expect(await screen.findByText('MTTR by tier')).toBeInTheDocument();
      expect(screen.getAllByText('Not yet measured').length).toBeGreaterThan(0);
      expect(screen.queryByText(/Some data is incomplete|unreachable/)).not.toBeInTheDocument();
    });

    it('MTTR tile: a genuine 500 renders a PartialFailureBanner with retry, distinct from the empty state', async () => {
      const refetch = vi.fn();
      (useMttrByTier as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        isPending: false,
        error: new ApiError('Internal Server Error', 500, 'req_mttr_500'),
        refetch,
        data: undefined,
      });
      render(<DashboardPage />, { wrapper });
      const banner = await screen.findByText('MTTR by tier connector is unreachable');
      expect(banner.closest('[role="alert"]')).toHaveTextContent('500');
      const retryButton = screen.getByRole('button', { name: /retry now/i });
      await userEvent.setup().click(retryButton);
      expect(refetch).toHaveBeenCalled();
    });

    it('SLA tile: a query error renders a PartialFailureBanner with retry (require_viewer-gated, so any error is a real bug)', async () => {
      const refetch = vi.fn();
      (useSlaMetrics as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        isPending: false,
        error: new ApiError('Internal Server Error', 500, 'req_sla_500'),
        refetch,
        data: undefined,
      });
      render(<DashboardPage />, { wrapper });
      await screen.findByText('SLA compliance connector is unreachable');
      const retryButton = screen.getByRole('button', { name: /retry now/i });
      await userEvent.setup().click(retryButton);
      expect(refetch).toHaveBeenCalled();
    });

    it('Framework posture strip: a query error renders a PartialFailureBanner with retry', async () => {
      const refetch = vi.fn();
      (useComplianceOverview as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        isPending: false,
        error: new ApiError('Internal Server Error', 500, 'req_posture_500'),
        refetch,
        data: undefined,
      });
      render(<DashboardPage />, { wrapper });
      await screen.findByText('Framework posture connector is unreachable');
      const retryButton = screen.getByRole('button', { name: /retry now/i });
      await userEvent.setup().click(retryButton);
      expect(refetch).toHaveBeenCalled();
    });

    it('SLA/posture failures do not unmount sibling leadership widgets (D-E-01 partial failure)', async () => {
      (useSlaMetrics as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        isPending: false,
        error: new ApiError('Internal Server Error', 500, 'req_sla_500'),
        refetch: vi.fn(),
        data: undefined,
      });
      render(<DashboardPage />, { wrapper });
      await screen.findByText('SLA compliance connector is unreachable');
      // MTTR tile (happy path, unaffected) and the SLA-failure banner
      // co-exist on the page.
      expect(screen.getByText('MTTR by tier')).toBeInTheDocument();
      expect(screen.getByText('Framework posture')).toBeInTheDocument();
    });
  });
});
