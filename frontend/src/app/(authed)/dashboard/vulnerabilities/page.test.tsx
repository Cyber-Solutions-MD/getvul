// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// Mock next/navigation. URL state drives view + panel openness.
const mockReplace = vi.fn();
let mockParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => '/dashboard/vulnerabilities',
  useSearchParams: () => ({
    get: (k: string) => mockParams.get(k),
    getAll: (k: string) => mockParams.getAll(k),
    toString: () => mockParams.toString(),
  }),
}));

// Mock the Wave 1 query hooks the page consumes
vi.mock('@/lib/queries/use-vulnerabilities', () => ({
  useVulnerabilities: vi.fn(),
}));
vi.mock('@/lib/queries/use-vulnerability-detail', () => ({
  useVulnerabilityDetail: vi.fn(),
}));
vi.mock('@/lib/queries/use-connectors', () => ({
  useConnectors: vi.fn(),
}));
vi.mock('@/lib/queries/use-saved-filters', () => ({
  useSavedFilters: vi.fn(),
}));
vi.mock('@/lib/queries/use-query-errors', () => ({
  useQueryErrors: vi.fn(),
}));
vi.mock('@/lib/mutations/use-snooze', () => ({
  useSnoozeMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/lib/mutations/use-undo-snooze', () => ({
  useUndoSnoozeMutation: () => ({ mutate: vi.fn() }),
}));
vi.mock('@/lib/mutations/use-create-ticket', () => ({
  useCreateTicketMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { useVulnerabilities } from '@/lib/queries/use-vulnerabilities';
import { useVulnerabilityDetail } from '@/lib/queries/use-vulnerability-detail';
import { useConnectors } from '@/lib/queries/use-connectors';
import { useSavedFilters } from '@/lib/queries/use-saved-filters';
import { useQueryErrors } from '@/lib/queries/use-query-errors';

// Wave 2 (Plan 11-05) will rewrite this page. The page exists as a v1 stub —
// the new chip-bar + table + drill-panel composition is the GREEN target.
import VulnerabilitiesPage from './page';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const happyList = {
  isPending: false,
  isError: false,
  isSuccess: true,
  data: {
    items: [
      {
        id: '1',
        cve_id: 'CVE-2024-3094',
        title: 'xz backdoor',
        asset: 'prod-01',
        cvss: 10,
        severity: 'critical',
        status: 'open',
        source: 'QUALYS',
        sla_due_at: '2026-05-23T00:00:00Z',
        cisa_kev: true,
      },
    ],
    total: 1,
    facets: {
      severity: { CRITICAL: 1 },
      source: { QUALYS: 1 },
      status: { OPEN: 1 },
    },
  },
};

describe('VulnerabilitiesPage — page-level integration (Phase 11)', () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockParams = new URLSearchParams();
    (useVulnerabilities as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      happyList
    );
    (useVulnerabilityDetail as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      data: null,
    });
    (useConnectors as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: [{ id: 'c1', type: 'QUALYS', last_sync_status: 'ok' }],
    });
    (useSavedFilters as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      data: [],
    });
    (useQueryErrors as unknown as ReturnType<typeof vi.fn>).mockReturnValue([]);
  });

  it('renders chip-bar + view-toggle + table on initial load (no panel)', () => {
    render(<VulnerabilitiesPage />, { wrapper });
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /By CVE/i })).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: /Severity/i })
    ).toBeInTheDocument();
    // No drill panel
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('URL ?cve=CVE-2024-3094&open=drill pre-opens the drill panel with that CVE', () => {
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    (useVulnerabilityDetail as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      data: { cve_id: 'CVE-2024-3094', title: 'xz backdoor' },
    });
    render(<VulnerabilitiesPage />, { wrapper });
    expect(screen.getAllByText(/CVE-2024-3094/).length).toBeGreaterThanOrEqual(1);
  });

  it('resolves the ?cve=<CVE-string> deep-link to the loaded item UUID before calling the detail hook (regression: the detail/escalations endpoints accept only a UUID, so passing a CVE 422d the whole drill)', () => {
    mockParams = new URLSearchParams('cve=CVE-2024-3094&open=drill');
    const detailMock = useVulnerabilityDetail as unknown as ReturnType<typeof vi.fn>;
    detailMock.mockReturnValue({
      isPending: false,
      isError: false,
      data: { id: '1', cve_id: 'CVE-2024-3094', title: 'xz backdoor' },
    });
    render(<VulnerabilitiesPage />, { wrapper });
    // item.id === '1' for cve_id 'CVE-2024-3094' — the drill must fetch by '1',
    // never by the raw CVE string.
    expect(detailMock).toHaveBeenCalledWith('1');
    expect(detailMock).not.toHaveBeenCalledWith('CVE-2024-3094');
  });

  it('clicking a row opens the panel + updates URL to ?cve={row.cve}&open=drill', () => {
    render(<VulnerabilitiesPage />, { wrapper });
    const bodyRows = screen
      .getAllByRole('row')
      .filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    fireEvent.click(bodyRows[0]);
    expect(mockReplace).toHaveBeenCalled();
    const [target] = mockReplace.mock.calls[0];
    expect(target).toContain('cve=CVE-2024-3094');
    expect(target).toContain('open=drill');
  });

  it('loading state — when useVulnerabilities is pending, page renders <SkeletonTable>', () => {
    (useVulnerabilities as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: true,
      isError: false,
      isSuccess: false,
      data: undefined,
    });
    const { container } = render(<VulnerabilitiesPage />, { wrapper });
    expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
  });

  it('empty-filtered state — when items=[] AND filters active, renders <EmptyState> with 3-tier CTAs + violet suggestion', () => {
    mockParams = new URLSearchParams('severity=critical');
    (useVulnerabilities as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: { items: [], total: 0, facets: {} },
    });
    render(<VulnerabilitiesPage />, { wrapper });
    // 3 action CTAs per state-patterns.md
    expect(screen.getByRole('button', { name: /Clear all/i })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Include Medium/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Search all sources/i })
    ).toBeInTheDocument();
    // Violet suggestion present
    expect(screen.getByText(/[Tt]ry broadening|[Tt]ip:/)).toBeInTheDocument();
  });

  it('partial-failure — failed query in watchKeys renders <PartialFailureBanner> + per-source strip + stale tinting', () => {
    (useQueryErrors as unknown as ReturnType<typeof vi.fn>).mockReturnValue([
      {
        queryKey: ['connectors', 'sync', 'TENABLE'],
        error: new Error('503'),
        code: 503,
        requestId: 'req_abc',
      },
    ]);
    (useConnectors as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: [
        { id: 'c1', type: 'QUALYS', last_sync_status: 'ok' },
        { id: 'c2', type: 'TENABLE', last_sync_status: 'failed' },
      ],
    });
    (useVulnerabilities as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: {
        items: [
          {
            id: '2',
            cve_id: 'CVE-2024-0002',
            title: 'OpenSSL',
            asset: 'prod-02',
            cvss: 7.5,
            severity: 'high',
            status: 'open',
            source: 'TENABLE',
            sla_due_at: null,
            cisa_kev: false,
          },
        ],
        total: 1,
        facets: { severity: { HIGH: 1 }, source: { TENABLE: 1 } },
      },
    });
    render(<VulnerabilitiesPage />, { wrapper });
    expect(screen.getByRole('alert')).toBeInTheDocument();
    // Per-source strip status region
    const statuses = screen.getAllByRole('status');
    expect(statuses.length).toBeGreaterThanOrEqual(1);
  });

  it('total-failure (UX-S-04) — primary list errors + no rows → <EmptyState> with retry CTAs', () => {
    (useVulnerabilities as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      isError: true,
      isSuccess: false,
      data: undefined,
      error: new Error('500'),
    });
    render(<VulnerabilitiesPage />, { wrapper });
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('tab title — data.total > 0 sets document.title to (N) Vulnerabilities · GetVul', () => {
    render(<VulnerabilitiesPage />, { wrapper });
    expect(document.title).toMatch(/^\(1\) Vulnerabilities · GetVul/);
  });
});
