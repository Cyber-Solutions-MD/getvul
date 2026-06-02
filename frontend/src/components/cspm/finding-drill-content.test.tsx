/**
 * TDD RED — finding-drill-content.tsx, use-cspm-detail.ts, cspm-bulk-bar.tsx
 * Plan 14-03, Task 2.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mock api ──────────────────────────────────────────────────────────────────
vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
const mockApi = vi.mocked(api);

// ── Mock ToastProvider ────────────────────────────────────────────────────────
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

// ── Test 1: useCspmDetail ─────────────────────────────────────────────────────
describe('useCspmDetail', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('GETs /api/v1/cspm/{id} returning MisconfigResponse', async () => {
    const { useCspmDetail } = await import('@/lib/queries/use-cspm-detail');
    const { renderHook } = await import('@testing-library/react');
    const client = makeClient();
    const mockData = {
      id: 'f1', rule_id: 'R1', rule_name: 'S3 public', cloud_provider: 'AWS',
      resource_id: 'arn:aws:s3:::bucket', status: 'OPEN',
      rule_description: 'S3 bucket allows public read access',
      frameworks: [{ name: 'CIS AWS', control_id: '1.1', compliance_status: 'FAILED' }],
      remediation_info: 'Enable block public access',
      remediation_url: 'https://docs.aws.amazon.com',
    };
    mockApi.mockResolvedValueOnce(mockData);

    const { result } = renderHook(() => useCspmDetail('f1'), { wrapper: wrapper(client) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/cspm/f1'),
      expect.anything(),
    );
  });
});

// ── Test 2: FindingDrillContent renders data ──────────────────────────────────
describe('FindingDrillContent - data present', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders rule_name, resource_id mono, framework mappings, remediation_info, status row', async () => {
    const { useCspmDetail } = await import('@/lib/queries/use-cspm-detail');
    const { FindingDrillContent } = await import('./finding-drill-content');

    vi.mocked(useCspmDetail).mockReturnValue({
      data: {
        id: 'f1',
        rule_id: 'R1',
        rule_name: 'S3 bucket public access',
        cloud_provider: 'AWS',
        resource_id: 'arn:aws:s3:::my-bucket',
        resource_name: 'my-bucket',
        resource_region: 'us-east-1',
        cloud_account_id: 'acc123',
        cloud_account_name: 'prod-account',
        status: 'OPEN',
        severity: 'HIGH',
        rule_description: 'S3 bucket allows public read access',
        frameworks: [{ name: 'CIS AWS', control_id: '1.1', compliance_status: 'FAILED' }],
        remediation_info: 'Enable block public access',
        remediation_url: 'https://docs.aws.amazon.com',
        category: 'STORAGE',
        source: 'WIZ',
        first_detected_at: '2026-01-01T00:00:00Z',
        last_seen_at: '2026-06-01T00:00:00Z',
      },
      isPending: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCspmDetail>);

    render(<FindingDrillContent findingId="f1" onClose={vi.fn()} />);

    expect(screen.getByText('S3 bucket public access')).toBeTruthy();
    expect(screen.getByText(/arn:aws:s3:::my-bucket/)).toBeTruthy();
    expect(screen.getByText('CIS AWS')).toBeTruthy();
    expect(screen.getByText(/Enable block public access/)).toBeTruthy();
    // status pill
    expect(document.querySelector('[data-cspm-status="OPEN"]')).toBeTruthy();
  });
});

// ── Test 3: FindingDrillContent loading/error states ─────────────────────────
describe('FindingDrillContent - loading and error states', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders skeleton while pending', async () => {
    const { useCspmDetail } = await import('@/lib/queries/use-cspm-detail');
    const { FindingDrillContent } = await import('./finding-drill-content');

    vi.mocked(useCspmDetail).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCspmDetail>);

    const { container } = render(<FindingDrillContent findingId="f1" onClose={vi.fn()} />);
    // Should show skeleton (aria-busy or skeleton element)
    expect(container.querySelector('[aria-busy="true"]') || screen.getByText(/Loading/i) || container.querySelector('[data-skeleton]')).toBeTruthy();
  });

  it('renders PartialFailureBanner on error', async () => {
    const { useCspmDetail } = await import('@/lib/queries/use-cspm-detail');
    const { FindingDrillContent } = await import('./finding-drill-content');

    vi.mocked(useCspmDetail).mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error('API error'),
    } as unknown as ReturnType<typeof useCspmDetail>);

    render(<FindingDrillContent findingId="f1" onClose={vi.fn()} />);
    // PartialFailureBanner or error indicator
    expect(
      document.querySelector('[data-partial-failure]') ||
      screen.getByRole('alert') ||
      screen.getByText(/partial|error|failed/i),
    ).toBeTruthy();
  });
});

// ── Test 4: CspmBulkBar renders + actions ─────────────────────────────────────
describe('CspmBulkBar', () => {
  it('renders Resolve/Ignore/Reopen when selectedCount>0 and clicking Resolve calls onBulkAction("REMEDIATED")', async () => {
    const { CspmBulkBar } = await import('./cspm-bulk-bar');
    const onBulkAction = vi.fn();
    render(
      <CspmBulkBar
        selectedCount={3}
        onBulkAction={onBulkAction}
        onClearSelection={vi.fn()}
      />,
    );

    expect(screen.getByText('Resolve')).toBeTruthy();
    expect(screen.getByText('Ignore')).toBeTruthy();
    expect(screen.getByText('Reopen')).toBeTruthy();

    fireEvent.click(screen.getByText('Resolve'));
    expect(onBulkAction).toHaveBeenCalledWith('REMEDIATED');
  });

  it('returns null when selectedCount is 0', async () => {
    const { CspmBulkBar } = await import('./cspm-bulk-bar');
    const { container } = render(
      <CspmBulkBar selectedCount={0} onBulkAction={vi.fn()} onClearSelection={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
