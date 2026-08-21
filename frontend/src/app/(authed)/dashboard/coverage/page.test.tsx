/**
 * page.test.tsx — tests for the /dashboard/coverage blind-spot list page
 * (Phase 41 Plan 01, COV-01 tracer slice; Plan 03 extends with a second
 * mocked query for the COV-02 coverage strip; Plan 05 extends with
 * DrillPanel + RBAC-gated "Route to owner" tests). Mirrors
 * exceptions/page.test.tsx's `vi.spyOn(module, 'hook').mockReturnValueOnce`
 * convention (closer precedent than assets/page.test.tsx's factory `vi.mock`,
 * since both pages are single-query v5.0-era list screens).
 *
 * One test per branch (WR-13 state-branch order): loading, error,
 * no-inventory-empty (D-11), all-covered-empty (quiet win), populated.
 * `mockSummaryQuery` defaults every pre-existing test to
 * `has_scanner_connector: true` so the Plan 01 branch assertions keep
 * exercising the exact same branch they did before Plan 03 added the
 * second read (page.tsx now branches on BOTH queries — see coverage strip
 * tests below for the has_scanner_connector: false / cards-populated cases).
 *
 * `searchParamsMock` is now mutable (`let`, mirroring
 * vulnerabilities/page.test.tsx's `mockParams` convention) so the Plan 05
 * drill-panel test can pre-set `?asset=<id>&open=drill` before rendering.
 */
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();
const replaceMock = vi.fn();
let searchParamsMock = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => '/dashboard/coverage',
  useSearchParams: () => searchParamsMock,
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

// Plan 05 (COV-03) — D-08 asymmetric RBAC gating. Mutable per-test via
// `mockUseAuth.mockReturnValueOnce(...)`; defaults to an analyst so every
// pre-existing (Plan 01/03) test keeps exercising the action-enabled path.
const mockUseAuth = vi.fn(() => ({ user: { role: 'ANALYST', id: 'u1' } }));
vi.mock('@/lib/auth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Plan 05 (COV-03) — the route-to-owner mutation hook. Real toasts/queries
// are irrelevant to these branch/RBAC tests (nothing here clicks "confirm"),
// so a plain isPending-only stub is enough.
const routeToOwnerMutate = vi.fn();
vi.mock('@/lib/queries/use-route-to-owner', () => ({
  useRouteToOwner: () => ({ mutate: routeToOwnerMutate, isPending: false }),
}));

import * as useBlindSpotAssetsModule from '@/lib/queries/use-blind-spot-assets';
import type { BlindSpotAssetListResponse } from '@/lib/queries/use-blind-spot-assets';
import * as useCoverageSummaryModule from '@/lib/queries/use-coverage-summary';
import type { CoverageSummaryResponse } from '@/lib/queries/use-coverage-summary';
import CoveragePage from './page';

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function mockQuery(overrides: {
  data?: BlindSpotAssetListResponse;
  isPending?: boolean;
  error?: Error | null;
}) {
  vi.spyOn(useBlindSpotAssetsModule, 'useBlindSpotAssets').mockReturnValue({
    data: overrides.data,
    isPending: overrides.isPending ?? false,
    isLoading: overrides.isPending ?? false,
    error: overrides.error ?? null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useBlindSpotAssetsModule.useBlindSpotAssets>);
}

// Plan 03 (COV-02) — defaults to has_scanner_connector: true, no cards, so
// every pre-existing Plan 01 branch test above keeps exercising the exact
// branch it did before this query existed (isPopulated only requires
// hasScannerConnector, not a non-empty cards array).
function mockSummaryQuery(overrides: {
  data?: CoverageSummaryResponse;
  isPending?: boolean;
  error?: Error | null;
}) {
  const defaultData: CoverageSummaryResponse = {
    cards: [],
    total_authoritative_assets: 0,
    has_authoritative_inventory: false,
    has_scanner_connector: true,
  };
  vi.spyOn(useCoverageSummaryModule, 'useCoverageSummary').mockReturnValue({
    data: overrides.data ?? defaultData,
    isPending: overrides.isPending ?? false,
    isLoading: overrides.isPending ?? false,
    error: overrides.error ?? null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useCoverageSummaryModule.useCoverageSummary>);
}

const POPULATED_ONE_ROW: BlindSpotAssetListResponse = {
  items: [
    {
      id: 'a1',
      hostname: 'prod-db-01',
      category: 'SERVER',
      os: 'Ubuntu 22.04',
      last_seen_at: null,
      seen_by_sources: ['JAMF'],
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
  pages: 1,
  has_authoritative_inventory: true,
  total_authoritative_assets: 1,
};

describe('/dashboard/coverage page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
    routeToOwnerMutate.mockClear();
    searchParamsMock = new URLSearchParams();
    mockUseAuth.mockReset();
    mockUseAuth.mockReturnValue({ user: { role: 'ANALYST', id: 'u1' } });
    mockSummaryQuery({});
  });

  it('loading branch renders the skeleton table, no alert/status', () => {
    mockQuery({ isPending: true });
    const { container } = renderWithClient(<CoveragePage />);
    expect(container.querySelectorAll('[data-skeleton-row]').length).toBeGreaterThan(0);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('error branch renders PartialFailureBanner, not the skeleton or an empty state', () => {
    mockQuery({ error: new Error('Connection refused: cannot reach backend') });
    renderWithClient(<CoveragePage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('no-inventory empty state (D-11) renders when has_authoritative_inventory is false', () => {
    mockQuery({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        has_authoritative_inventory: false,
        total_authoritative_assets: 0,
      },
    });
    const { container } = renderWithClient(<CoveragePage />);
    expect(screen.getByText('No inventory source connected')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'Connect an inventory source' });
    expect(cta).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/connectors"]')).not.toBeNull();
  });

  it('all-covered quiet-win empty state renders when has_authoritative_inventory is true and total is 0 (no CTA)', () => {
    mockQuery({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        has_authoritative_inventory: true,
        total_authoritative_assets: 3,
      },
    });
    renderWithClient(<CoveragePage />);
    expect(screen.getByText('Every device is covered')).toBeInTheDocument();
    expect(screen.getByText(/All 3 devices in your inventory/)).toBeInTheDocument();
    expect(screen.queryByText('No inventory source connected')).toBeNull();
    // Quiet win = genuinely quiet: no CTA/link rendered for this branch.
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('populated branch renders a blind-spot row with hostname + "No scanner coverage" badge', () => {
    mockQuery({
      data: {
        items: [
          {
            id: 'a1',
            hostname: 'prod-db-01',
            category: 'SERVER',
            os: 'Ubuntu 22.04',
            last_seen_at: null,
            seen_by_sources: ['JAMF'],
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
        has_authoritative_inventory: true,
        total_authoritative_assets: 1,
      },
    });
    renderWithClient(<CoveragePage />);
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(screen.getByText('prod-db-01')).toBeInTheDocument();
    expect(screen.getByText('No scanner coverage')).toBeInTheDocument();
    // Subtitle uses the real total (1 device, singular-safe).
    expect(screen.getByText(/1 device in inventory has never been touched/)).toBeInTheDocument();
  });

  // --- Plan 03 (COV-02) — coverage strip branches ---

  it('renders the coverage strip cards above the blind-spot table when populated', () => {
    mockQuery({
      data: {
        items: [
          {
            id: 'a1',
            hostname: 'prod-db-01',
            category: 'SERVER',
            os: 'Ubuntu 22.04',
            last_seen_at: null,
            seen_by_sources: ['JAMF'],
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        pages: 1,
        has_authoritative_inventory: true,
        total_authoritative_assets: 1,
      },
    });
    mockSummaryQuery({
      data: {
        cards: [
          {
            connector_type: 'QUALYS',
            coverage_pct: 75,
            is_stale: false,
            stale_days: null,
            last_sync_status: 'ok',
            last_sync_at: '2026-08-19T00:00:00Z',
          },
        ],
        total_authoritative_assets: 1,
        has_authoritative_inventory: true,
        has_scanner_connector: true,
      },
    });
    renderWithClient(<CoveragePage />);
    expect(document.querySelector('[data-coverage-card][data-connector-type="QUALYS"]')).not.toBeNull();
    expect(screen.getByText('prod-db-01')).toBeInTheDocument();
  });

  it('scanner-absent empty state (E4 backstop) renders when inventory exists but no scanner connector does', () => {
    mockQuery({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        has_authoritative_inventory: true,
        total_authoritative_assets: 5,
      },
    });
    mockSummaryQuery({
      data: {
        cards: [],
        total_authoritative_assets: 5,
        has_authoritative_inventory: true,
        has_scanner_connector: false,
      },
    });
    renderWithClient(<CoveragePage />);
    expect(screen.getByText('No scanner connected')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'Connect a scanner' });
    expect(cta).toBeInTheDocument();
    expect(screen.queryByText('Every device is covered')).toBeNull();
    expect(screen.queryByText('No inventory source connected')).toBeNull();
  });

  it('loading branch waits on BOTH queries — summary still pending keeps the skeleton up even once blind-spots resolves', () => {
    mockQuery({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        pages: 0,
        has_authoritative_inventory: false,
        total_authoritative_assets: 0,
      },
    });
    mockSummaryQuery({ isPending: true });
    const { container } = renderWithClient(<CoveragePage />);
    expect(container.querySelectorAll('[data-skeleton-row]').length).toBeGreaterThan(0);
    expect(screen.queryByText('No inventory source connected')).toBeNull();
  });

  // --- Plan 05 (COV-03) — DrillPanel (idKey="asset") + RBAC-gated "Route to owner" ---

  it('clicking a blind-spot row updates the URL to ?asset={id}&open=drill (D-D-02)', () => {
    mockQuery({ data: POPULATED_ONE_ROW });
    renderWithClient(<CoveragePage />);
    const row = screen.getByText('prod-db-01').closest('tr');
    expect(row).not.toBeNull();
    fireEvent.click(row!);
    expect(replaceMock).toHaveBeenCalled();
    const [target] = replaceMock.mock.calls[replaceMock.mock.calls.length - 1];
    expect(target).toContain('asset=a1');
    expect(target).toContain('open=drill');
  });

  it('?asset=a1&open=drill pre-opens the asset DrillPanel with the row content', () => {
    searchParamsMock = new URLSearchParams('asset=a1&open=drill');
    mockQuery({ data: POPULATED_ONE_ROW });
    renderWithClient(<CoveragePage />);
    const dialog = screen.getByRole('dialog', { name: 'Device detail' });
    expect(dialog).toBeInTheDocument();
    // Hostname renders both in the table row and the drill header — assert
    // at least the drill's own mono heading is present.
    expect(screen.getAllByText('prod-db-01').length).toBeGreaterThanOrEqual(2);
    // "No scanner coverage" also renders in both the row badge and the
    // drill body — scope this assertion to inside the dialog.
    expect(within(dialog).getByText('No scanner coverage')).toBeInTheDocument();
  });

  it('viewer role: "Route to owner" row action is disabled (D-08 asymmetric RBAC, never a raw 403)', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'VIEWER', id: 'u2' } });
    mockQuery({ data: POPULATED_ONE_ROW });
    renderWithClient(<CoveragePage />);
    const rowAction = screen.getByRole('button', { name: 'Route to owner' });
    expect(rowAction).toBeDisabled();
  });

  it('analyst role: "Route to owner" row action is enabled', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'ANALYST', id: 'u1' } });
    mockQuery({ data: POPULATED_ONE_ROW });
    renderWithClient(<CoveragePage />);
    const rowAction = screen.getByRole('button', { name: 'Route to owner' });
    expect(rowAction).not.toBeDisabled();
  });
});
