import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mocks set up BEFORE component import so the module reads the mocked values.
vi.mock('@/lib/queries/use-stats', () => ({
  useStats: vi.fn(),
}));
const mutateAsyncMock = vi.fn().mockResolvedValue({ message: 'snoozed', until: 'iso' });
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: mutateAsyncMock, isPending: false }),
}));
const undoMock = vi.fn();
vi.mock('@/lib/mutations/use-undo-snooze', () => ({
  useUndoSnoozeMutation: () => ({ mutate: undoMock }),
}));
const toastMock = vi.fn();
vi.mock('@/components/ui/ToastProvider', async () => {
  const actual = await vi.importActual<typeof import('@/components/ui/ToastProvider')>(
    '@/components/ui/ToastProvider'
  );
  return {
    ...actual,
    useToast: () => ({ toast: toastMock }),
  };
});

import { Hero } from './hero';
import { useStats } from '@/lib/queries/use-stats';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const baseStats = {
  isPending: false,
  error: null,
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

describe('<Hero>', () => {
  beforeEach(() => {
    mutateAsyncMock.mockClear();
    undoMock.mockClear();
    toastMock.mockClear();
  });

  it('singular headline with criticalOpen=1 (D-H-02)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      ...baseStats,
      data: {
        ...baseStats.data,
        dashboard_tiles: {
          ...baseStats.data.dashboard_tiles,
          critical_open: { value: 1, delta: 0, delta_direction: 'flat' },
        },
      },
    });
    render(<Hero />, { wrapper });
    expect(screen.getByText('1 critical CVE needs your eyes')).toBeInTheDocument();
  });

  it('plural headline with criticalOpen=3 (D-H-02)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    render(<Hero />, { wrapper });
    expect(screen.getByText('3 critical CVEs need your eyes')).toBeInTheDocument();
  });

  it('sub-line uses real host/path/cvss/exploited exemplar (D-H-03)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    render(<Hero />, { wrapper });
    expect(
      screen.getByText(/Top one is on prod-db-01 — Postgres path, CVSS 9\.8, exploited in the wild\./)
    ).toBeInTheDocument();
  });

  it('quiet-win renders "Nothing critical right now" without Snooze CTA (D-H-09)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      ...baseStats,
      data: {
        ...baseStats.data,
        dashboard_tiles: {
          ...baseStats.data.dashboard_tiles,
          critical_open: { value: 0, delta: 0, delta_direction: 'flat' },
        },
        top_vuln: null,
      },
    });
    render(<Hero />, { wrapper });
    expect(screen.getByText('Nothing critical right now')).toBeInTheDocument();
    expect(screen.queryByText('Snooze 1h')).toBeNull();
  });

  it('CTAs: Start triage is a link to /dashboard/vulnerabilities filter; Snooze 1h is a button (D-H-06)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    render(<Hero />, { wrapper });
    const startTriage = screen.getByRole('link', { name: /Start triage/ });
    expect(startTriage.getAttribute('href')).toBe(
      '/dashboard/vulnerabilities?status=open&severity=critical'
    );
    expect(screen.getByRole('button', { name: /Snooze 1h/ })).toBeInTheDocument();
  });

  it('eyebrow dot uses bg-severity-critical when count>0 (D-H-05)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    const { container } = render(<Hero />, { wrapper });
    const dot = container.querySelector('span.bg-severity-critical');
    expect(dot).not.toBeNull();
  });

  it('eyebrow dot uses bg-success when count===0 (D-H-05 quiet-win)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      ...baseStats,
      data: {
        ...baseStats.data,
        dashboard_tiles: {
          ...baseStats.data.dashboard_tiles,
          critical_open: { value: 0, delta: 0, delta_direction: 'flat' },
        },
      },
    });
    const { container } = render(<Hero />, { wrapper });
    const dot = container.querySelector('span.bg-success');
    expect(dot).not.toBeNull();
  });

  it('clicking Snooze 1h fires snooze mutation with top_vuln.id and a toast with Undo action (D-H-08)', async () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    render(<Hero />, { wrapper });
    fireEvent.click(screen.getByRole('button', { name: /Snooze 1h/ }));
    await waitFor(() => expect(mutateAsyncMock).toHaveBeenCalled());
    expect(mutateAsyncMock.mock.calls[0][0]).toEqual({
      id: '00000000-0000-0000-0000-000000000001',
    });
    await waitFor(() => expect(toastMock).toHaveBeenCalled());
    const arg = toastMock.mock.calls[0][0];
    expect(arg.message).toMatch(/Snoozed CVE-2024-1234/);
    expect(arg.action?.label).toBe('Undo');
  });

  it('loading state renders skeleton with aria-busy (D-D-11 + D-R-02)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: true,
      error: null,
      data: undefined,
    });
    const { container } = render(<Hero />, { wrapper });
    const busy = container.querySelector('[aria-busy="true"]');
    expect(busy).not.toBeNull();
  });

  it('error state renders inline-error pattern (D-E-02)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: { code: 503, requestId: 'req_abc' },
      data: undefined,
    });
    render(<Hero />, { wrapper });
    expect(screen.getByText(/Hero unavailable\. HTTP 503/)).toBeInTheDocument();
  });

  it('renders Zap + Clock leftIcons on the CTAs (D-H-11)', () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    const { container } = render(<Hero />, { wrapper });
    // lucide renders svgs with .lucide-zap / .lucide-clock classes
    expect(container.querySelector('svg.lucide-zap')).not.toBeNull();
    expect(container.querySelector('svg.lucide-clock')).not.toBeNull();
  });

  it('has no axe violations (action mode)', async () => {
    (useStats as unknown as ReturnType<typeof vi.fn>).mockReturnValue(baseStats);
    const { container } = render(<Hero />, { wrapper });
    expect(await axe(container)).toHaveNoViolations();
  });
});
