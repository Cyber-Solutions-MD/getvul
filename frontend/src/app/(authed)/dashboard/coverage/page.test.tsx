/**
 * page.test.tsx — tests for the /dashboard/coverage blind-spot list page
 * (Phase 41 Plan 01, COV-01 tracer slice). Mirrors
 * exceptions/page.test.tsx's `vi.spyOn(module, 'hook').mockReturnValueOnce`
 * convention (closer precedent than assets/page.test.tsx's factory `vi.mock`,
 * since both pages are single-query v5.0-era list screens).
 *
 * One test per branch (WR-13 state-branch order): loading, error,
 * no-inventory-empty (D-11), all-covered-empty (quiet win), populated.
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();
const replaceMock = vi.fn();
const searchParamsMock = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => '/dashboard/coverage',
  useSearchParams: () => searchParamsMock,
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

import * as useBlindSpotAssetsModule from '@/lib/queries/use-blind-spot-assets';
import type { BlindSpotAssetListResponse } from '@/lib/queries/use-blind-spot-assets';
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

describe('/dashboard/coverage page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
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
});
