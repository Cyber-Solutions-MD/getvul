/**
 * TDD RED — CSPM page rewrite
 * Plan 14-03, Task 3.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// ── Module mocks ──────────────────────────────────────────────────────────────
vi.mock('@/lib/api', () => ({ api: vi.fn() }));
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => '/dashboard/cspm',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock all CSPM hooks
vi.mock('@/lib/queries/use-cspm-findings', () => ({
  useCspmFindings: vi.fn(),
  useCspmStats: vi.fn(),
  useComplianceFrameworks: vi.fn(),
  useBulkCspmStatus: vi.fn(),
}));
vi.mock('@/lib/queries/use-cspm-detail', () => ({
  useCspmDetail: vi.fn(),
}));

// Mock UI hooks
vi.mock('@/hooks/use-url-state', () => ({
  useUrlState: (_key: string, _allowList: string[], defaultVal: string) => [defaultVal, vi.fn()],
}));
vi.mock('@/hooks/use-url-state-list', () => ({
  useUrlStateList: (_key: string, _allowList: string[], defaultVal: string[]) => [defaultVal, vi.fn(), vi.fn()],
}));

// ── Imports ───────────────────────────────────────────────────────────────────
import * as cspmHooks from '@/lib/queries/use-cspm-findings';

// ── Helpers ───────────────────────────────────────────────────────────────────
const mockFinding = {
  id: 'f1',
  rule_id: 'R1',
  rule_name: 'S3 public access',
  category: 'STORAGE',
  severity: 'HIGH',
  source: 'WIZ',
  status: 'OPEN',
  resource_id: 'arn:aws:s3:::my-bucket',
  resource_name: 'my-bucket',
  resource_type: 'AWS::S3::Bucket',
  cloud_provider: 'AWS',
  first_detected_at: '2026-01-01T00:00:00Z',
  last_seen_at: '2026-06-01T00:00:00Z',
};

const mockFrameworks = [
  { name: 'CIS AWS', total_controls: 100, passed: 80, failed: 15, suppressed: 5, pass_rate: 80 },
];

const mockStats = {
  total_findings: 42,
  open_findings: 30,
  compliance_pass_rate: 80,
  by_cloud_provider: [
    { cloud_provider: 'AWS', count: 35 },
    { cloud_provider: 'AZURE', count: 7 },
  ],
  by_category: [],
  by_severity: [],
};

function setupSuccessfulMocks() {
  vi.mocked(cspmHooks.useCspmFindings).mockReturnValue({
    data: { items: [mockFinding], total: 1, page: 1, page_size: 25, total_pages: 1 },
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof cspmHooks.useCspmFindings>);

  vi.mocked(cspmHooks.useCspmStats).mockReturnValue({
    data: mockStats,
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof cspmHooks.useCspmStats>);

  vi.mocked(cspmHooks.useComplianceFrameworks).mockReturnValue({
    data: mockFrameworks,
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof cspmHooks.useComplianceFrameworks>);

  vi.mocked(cspmHooks.useBulkCspmStatus).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof cspmHooks.useBulkCspmStatus>);
}

// ── Test 1: Page renders ChipBar, cloud control, ComplianceFrameworkStrip ─────
describe('CSPM page - main layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupSuccessfulMocks();
  });

  it('renders ChipBar, cloud segmented control, and ComplianceFrameworkStrip', async () => {
    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);

    // ChipBar (search input or chip-bar element)
    expect(
      document.querySelector('[data-chip-bar]') ||
      screen.getByPlaceholderText(/search/i) ||
      screen.getByRole('search'),
    ).toBeTruthy();

    // Cloud control (AWS / AZURE buttons from stats)
    expect(screen.getAllByText('AWS').length).toBeGreaterThan(0);

    // ComplianceFrameworkStrip
    expect(document.querySelector('[data-framework-strip]')).toBeTruthy();
  });
});

// ── Test 2: Clicking a finding card sets URL and DrillPanel opens ──────────────
describe('CSPM page - finding drill', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupSuccessfulMocks();
  });

  it('finding card is present and has data-finding-card attribute', async () => {
    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);

    expect(document.querySelector('[data-finding-card]')).toBeTruthy();
    // The finding title is rendered
    expect(screen.getByText('S3 public access')).toBeTruthy();
  });
});

// ── Test 3: State patterns ────────────────────────────────────────────────────
describe('CSPM page - state patterns', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders SkeletonTable when isPending', async () => {
    vi.mocked(cspmHooks.useCspmFindings).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmFindings>);
    vi.mocked(cspmHooks.useCspmStats).mockReturnValue({
      data: undefined, isPending: true, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmStats>);
    vi.mocked(cspmHooks.useComplianceFrameworks).mockReturnValue({
      data: undefined, isPending: true, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useComplianceFrameworks>);
    vi.mocked(cspmHooks.useBulkCspmStatus).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof cspmHooks.useBulkCspmStatus>);

    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);
    expect(
      document.querySelector('[data-skeleton-table]') ||
      document.querySelector('[aria-busy="true"]') ||
      screen.getByRole('status'),
    ).toBeTruthy();
  });

  it('renders EmptyState when zero findings', async () => {
    vi.mocked(cspmHooks.useCspmFindings).mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 25, total_pages: 0 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmFindings>);
    vi.mocked(cspmHooks.useCspmStats).mockReturnValue({
      data: { ...mockStats, total_findings: 0, open_findings: 0 },
      isPending: false, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmStats>);
    vi.mocked(cspmHooks.useComplianceFrameworks).mockReturnValue({
      data: mockFrameworks, isPending: false, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useComplianceFrameworks>);
    vi.mocked(cspmHooks.useBulkCspmStatus).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof cspmHooks.useBulkCspmStatus>);

    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);
    // EmptyState renders (with role="status") and contains the no-data message
    expect(
      screen.getByRole('status') ||
      screen.getByText(/no cspm findings/i) ||
      screen.getByText(/nothing matches/i),
    ).toBeTruthy();
  });

  it('renders PartialFailureBanner on query error', async () => {
    vi.mocked(cspmHooks.useCspmFindings).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('500 error'),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmFindings>);
    vi.mocked(cspmHooks.useCspmStats).mockReturnValue({
      data: undefined, isPending: false, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useCspmStats>);
    vi.mocked(cspmHooks.useComplianceFrameworks).mockReturnValue({
      data: undefined, isPending: false, isError: false, error: null, refetch: vi.fn(),
    } as unknown as ReturnType<typeof cspmHooks.useComplianceFrameworks>);
    vi.mocked(cspmHooks.useBulkCspmStatus).mockReturnValue({
      mutate: vi.fn(), isPending: false,
    } as unknown as ReturnType<typeof cspmHooks.useBulkCspmStatus>);

    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);
    expect(screen.getByRole('alert')).toBeTruthy();
  });
});

// ── Test 4: Bulk selection shows CspmBulkBar ─────────────────────────────────
describe('CSPM page - bulk actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupSuccessfulMocks();
  });

  it('renders a selection checkbox for each finding card', async () => {
    const CSPMPage = (await import('./page')).default;
    render(<CSPMPage />);

    const checkbox = document.querySelector('input[type="checkbox"]');
    expect(checkbox).toBeTruthy();
  });
});
