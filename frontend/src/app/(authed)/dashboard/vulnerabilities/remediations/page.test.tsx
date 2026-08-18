/**
 * page.test.tsx — TDD tests for the /dashboard/vulnerabilities/remediations
 * entry point.
 *
 * Not explicitly named in 38-05-PLAN.md's `files_modified`, but required to
 * prove the plan's own <behavior> items (WR-13 state-branch order, exact
 * empty copy, Start-campaign mutation wiring) — mirrors the identical
 * deviation 38-04-SUMMARY.md documented for /dashboard/campaigns/page.test.tsx.
 *
 * Test 1: renders remediation-group rows via RemediationsTable with a live query.
 * Test 2: state branches — error / loading / empty are mutually exclusive (WR-13).
 * Test 3: empty state renders the exact "No remediation groups yet" copy.
 * Test 4: clicking "Start campaign" invokes useStartCampaign().mutate with
 *         that row's remediation_id.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

import * as useRemediationsGroupedModule from '@/lib/queries/use-remediations-grouped';
import * as useCampaignMutationsModule from '@/lib/queries/use-campaign-mutations';
import RemediationsPage from './page';

const mockGroup: useRemediationsGroupedModule.RemediationGroup = {
  remediation_id: 'CVE-2024-1234: openssl 3.0 upgrade',
  remediation_action: 'Upgrade openssl to 3.0.14',
  affected_product: 'openssl',
  affected_hosts: 12,
  vuln_count: 12,
  max_severity: 'CRITICAL',
  is_suppressed: false,
  suppressed_count: 0,
};

const startMutate = vi.fn();

function mockGroupedQuery(overrides: Partial<ReturnType<typeof useRemediationsGroupedModule.useRemediationsGrouped>>) {
  vi.spyOn(useRemediationsGroupedModule, 'useRemediationsGrouped').mockReturnValue({
    data: { items: [mockGroup], total: 1, page: 1, page_size: 25, total_pages: 1 },
    isPending: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useRemediationsGroupedModule.useRemediationsGrouped>);
}

describe('/vulnerabilities/remediations page', () => {
  beforeEach(() => {
    startMutate.mockClear();
    vi.spyOn(useCampaignMutationsModule, 'useStartCampaign').mockReturnValue({
      mutate: startMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useCampaignMutationsModule.useStartCampaign>);
    mockGroupedQuery({});
  });

  it('Test 1: renders remediation-group rows via RemediationsTable', () => {
    render(<RemediationsPage />);
    expect(screen.getByText(mockGroup.remediation_action!)).toBeInTheDocument();
  });

  it('Test 2: error / loading / empty branches are mutually exclusive (WR-13)', () => {
    mockGroupedQuery({
      data: undefined,
      error: new Error('Connection refused: cannot reach backend'),
    });
    const { unmount } = render(<RemediationsPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
    unmount();

    mockGroupedQuery({ data: undefined, isPending: true });
    const { unmount: unmount2 } = render(<RemediationsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
    unmount2();

    mockGroupedQuery({ data: { items: [], total: 0, page: 1, page_size: 25, total_pages: 1 } });
    render(<RemediationsPage />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('Test 3: empty state renders exact "No remediation groups yet" copy', () => {
    mockGroupedQuery({ data: { items: [], total: 0, page: 1, page_size: 25, total_pages: 1 } });
    render(<RemediationsPage />);
    expect(screen.getByText('No remediation groups yet')).toBeInTheDocument();
  });

  it('Test 4: clicking Start campaign invokes the mutation with the row\'s remediation_id', () => {
    render(<RemediationsPage />);
    screen.getByRole('button', { name: 'Start campaign' }).click();
    expect(startMutate).toHaveBeenCalledWith(mockGroup.remediation_id);
  });
});
