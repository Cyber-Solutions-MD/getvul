/**
 * page.test.tsx — TDD tests for the /dashboard/campaigns list page.
 *
 * Not explicitly named in 38-04-PLAN.md's `files_modified`, but required to
 * prove the plan's own must_haves (WR-13 state-branch order, exact empty
 * copy, row-click navigation) — mirrors every other list page's co-located
 * page.test.tsx convention in this codebase (tickets/, connectors/,
 * asset-groups/, etc.). See 38-04-SUMMARY.md Deviations.
 *
 * Test 1: renders campaign rows via CampaignsTable with a live query.
 * Test 2: state branches — error / loading / empty are mutually exclusive (WR-13).
 * Test 3: empty state renders exact UI-SPEC copy + "View remediation groups" CTA.
 * Test 4: row click navigates to /dashboard/campaigns/{id} via router.push.
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  usePathname: () => '/dashboard/campaigns',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

import * as useCampaignsModule from '@/lib/queries/use-campaigns';
import CampaignsPage from './page';

const mockCampaign: useCampaignsModule.CampaignSummary = {
  id: 'c1',
  remediation_id: 'CVE-2024-1234: openssl 3.0 upgrade',
  status: 'ACTIVE',
  total: 12,
  open: 5,
  in_progress: 4,
  done: 3,
  pct_remediated: 25,
};

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('/campaigns page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    vi.spyOn(useCampaignsModule, 'useCampaigns').mockReturnValue({
      data: [mockCampaign],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCampaignsModule.useCampaigns>);
  });

  it('Test 1: renders campaign rows via CampaignsTable', () => {
    renderWithClient(<CampaignsPage />);
    expect(screen.getByText(mockCampaign.remediation_id)).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
  });

  it('Test 2: error / loading / empty branches are mutually exclusive (WR-13)', () => {
    // Error state
    vi.spyOn(useCampaignsModule, 'useCampaigns').mockReturnValueOnce({
      data: undefined,
      isPending: false,
      isLoading: false,
      error: new Error('Connection refused: cannot reach backend'),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCampaignsModule.useCampaigns>);
    const { unmount } = renderWithClient(<CampaignsPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
    unmount();

    // Loading state
    vi.spyOn(useCampaignsModule, 'useCampaigns').mockReturnValueOnce({
      data: undefined,
      isPending: true,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCampaignsModule.useCampaigns>);
    const { unmount: unmount2 } = renderWithClient(<CampaignsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
    unmount2();

    // Empty state
    vi.spyOn(useCampaignsModule, 'useCampaigns').mockReturnValueOnce({
      data: [],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCampaignsModule.useCampaigns>);
    renderWithClient(<CampaignsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('Test 3: empty state renders exact UI-SPEC copy + CTA', () => {
    vi.spyOn(useCampaignsModule, 'useCampaigns').mockReturnValueOnce({
      data: [],
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useCampaignsModule.useCampaigns>);
    const { container } = renderWithClient(<CampaignsPage />);
    expect(screen.getByText('No campaigns yet')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'View remediation groups' });
    expect(cta).toBeInTheDocument();
    expect(container.querySelector('a[href="/dashboard/vulnerabilities/remediations"]')).not.toBeNull();
  });

  it('Test 4: row click navigates to /dashboard/campaigns/{id}', () => {
    renderWithClient(<CampaignsPage />);
    screen.getByText(mockCampaign.remediation_id).closest('tr')!.click();
    expect(pushMock).toHaveBeenCalledWith('/dashboard/campaigns/c1');
  });
});
