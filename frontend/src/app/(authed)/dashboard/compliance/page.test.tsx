/**
 * page.test.tsx — tests for the /dashboard/compliance page (Phase 43 Plan
 * 01, RPT-03 tracer slice). Mirrors dashboard/coverage/page.test.tsx's
 * `vi.spyOn(module, 'hook').mockReturnValue` convention (closest precedent
 * — both pages combine a primary query with useCoverageSummary() for
 * empty-state branch selection).
 *
 * One test per WR-13 state-branch order (error > loading > empty > populated),
 * plus the two empty-state root-cause branches asserted by their OWN
 * distinguishing copy/CTA (not merely "an empty state renders").
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();
const replaceMock = vi.fn();
let searchParamsMock = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => '/dashboard/compliance',
  useSearchParams: () => searchParamsMock,
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

import * as useComplianceModule from '@/lib/queries/use-compliance';
import type { ComplianceOverviewResponse, ControlStatus } from '@/lib/queries/use-compliance';
import * as useCoverageSummaryModule from '@/lib/queries/use-coverage-summary';
import type { CoverageSummaryResponse } from '@/lib/queries/use-coverage-summary';
import CompliancePage from './page';

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function mockComplianceQuery(overrides: {
  data?: ComplianceOverviewResponse;
  isPending?: boolean;
  error?: Error | null;
}) {
  vi.spyOn(useComplianceModule, 'useComplianceOverview').mockReturnValue({
    data: overrides.data,
    isPending: overrides.isPending ?? false,
    isLoading: overrides.isPending ?? false,
    error: overrides.error ?? null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useComplianceModule.useComplianceOverview>);
}

function mockCoverageSummaryQuery(overrides: {
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

// A full 10-row catalog shape where every measurable (percentage/tiered)
// control is not_measured and the boolean has_active_scanning control is
// the tenant's real, honest signal — mirrors the actual backend's
// fresh-tenant behavior (see backend/tests/test_compliance.py).
function notMeasuredControls(hasActiveScanning: boolean): ControlStatus[] {
  const base: Omit<ControlStatus, 'framework' | 'control_id' | 'title'>[] = [
    { metric_key: 'coverage_pct', value: null, status: 'not_measured' },
    { metric_key: 'critical_sla_health_pct', value: null, status: 'not_measured' },
    { metric_key: 'coverage_pct', value: null, status: 'not_measured' },
    { metric_key: 'has_active_scanning', value: hasActiveScanning ? 1 : 0, status: hasActiveScanning ? 'pass' : 'fail' },
    { metric_key: 'critical_sla_health_pct', value: null, status: 'not_measured' },
    { metric_key: 'coverage_pct', value: null, status: 'not_measured' },
    { metric_key: 'critical_sla_health_pct', value: null, status: 'not_measured' },
    { metric_key: 'coverage_pct', value: null, status: 'not_measured' },
    { metric_key: 'sla_compliance_pct', value: null, status: 'not_measured' },
    { metric_key: 'mttr_by_tier', value: null, status: 'not_measured' },
  ];
  const ids: [string, string, string][] = [
    ['soc2', 'CC7.1', 'Vulnerability detection & monitoring'],
    ['iso27001', 'A.8.8', 'Management of technical vulnerabilities'],
    ['iso27001', 'A.8.9', 'Configuration management'],
    ['pci_dss', '6.3.1', 'Vulnerabilities identified & risk-ranked'],
    ['pci_dss', '6.3.3', 'Critical/high patches applied within a documented timeframe'],
    ['pci_dss', '11.3.1', 'Internal vulnerability scans at least quarterly'],
    ['pci_dss', '11.3.1.1', 'Critical/high vulnerabilities resolved per a risk-based timeframe'],
    ['nist_csf', 'ID.RA-01', 'Vulnerabilities in assets are identified, validated, and recorded.'],
    ['nist_csf', 'ID.RA-06', 'Risk responses are chosen, prioritized, planned, tracked, and communicated.'],
    ['nist_csf', 'PR.PS-02', 'Software is maintained, replaced, and removed commensurate with risk.'],
  ];
  return base.map((b, i) => ({ ...b, framework: ids[i][0], control_id: ids[i][1], title: ids[i][2] }));
}

const POPULATED_CONTROLS: ControlStatus[] = [
  {
    framework: 'soc2',
    control_id: 'CC7.1',
    title: 'Vulnerability detection & monitoring',
    metric_key: 'coverage_pct',
    value: 92,
    status: 'pass',
  },
  {
    framework: 'iso27001',
    control_id: 'A.8.8',
    title: 'Management of technical vulnerabilities',
    metric_key: 'critical_sla_health_pct',
    value: 60,
    status: 'partial',
  },
  {
    framework: 'pci_dss',
    control_id: '6.3.1',
    title: 'Vulnerabilities identified & risk-ranked',
    metric_key: 'has_active_scanning',
    value: 1,
    status: 'pass',
  },
  {
    framework: 'nist_csf',
    control_id: 'ID.RA-06',
    title: 'Risk responses are chosen, prioritized, planned, tracked, and communicated.',
    metric_key: 'sla_compliance_pct',
    value: 20,
    status: 'fail',
  },
];

describe('/dashboard/compliance page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    replaceMock.mockClear();
    searchParamsMock = new URLSearchParams();
    mockCoverageSummaryQuery({});
  });

  it('loading branch renders skeleton control cards, no alert/status', () => {
    mockComplianceQuery({ isPending: true });
    mockCoverageSummaryQuery({ isPending: true });
    const { container } = renderWithClient(<CompliancePage />);
    expect(container.querySelectorAll('[data-skeleton-card]').length).toBeGreaterThan(0);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('error branch renders PartialFailureBanner, not the skeleton or an empty state', () => {
    mockComplianceQuery({ error: new Error('Connection refused: cannot reach backend') });
    renderWithClient(<CompliancePage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('branch order: error takes priority even when isPending is also true', () => {
    mockComplianceQuery({ isPending: true, error: new Error('boom') });
    renderWithClient(<CompliancePage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('no-scanner empty branch renders when has_scanner_connector is false', () => {
    mockComplianceQuery({ data: { controls: notMeasuredControls(false) } });
    mockCoverageSummaryQuery({
      data: {
        cards: [],
        total_authoritative_assets: 0,
        has_authoritative_inventory: false,
        has_scanner_connector: false,
      },
    });
    renderWithClient(<CompliancePage />);
    expect(screen.getByText('Not enough posture data yet')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'Connect a scanner' });
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/dashboard/connectors');
    expect(screen.queryByText('Configure SLA policy')).toBeNull();
  });

  it('no-SLA-policy empty branch renders when has_scanner_connector is true (correct root cause, not merely "an empty state")', () => {
    mockComplianceQuery({ data: { controls: notMeasuredControls(true) } });
    mockCoverageSummaryQuery({
      data: {
        cards: [{ connector_type: 'QUALYS', coverage_pct: null, is_stale: false, stale_days: null, last_sync_status: 'ok', last_sync_at: null }],
        total_authoritative_assets: 0,
        has_authoritative_inventory: false,
        has_scanner_connector: true,
      },
    });
    renderWithClient(<CompliancePage />);
    expect(screen.getByText('Not enough posture data yet')).toBeInTheDocument();
    const cta = screen.getByRole('link', { name: 'Configure SLA policy' });
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/dashboard/settings?category=sla');
    expect(screen.queryByRole('link', { name: 'Connect a scanner' })).toBeNull();
  });

  it('populated branch renders control cards grouped by framework, never re-deriving status client-side', () => {
    mockComplianceQuery({ data: { controls: POPULATED_CONTROLS } });
    mockCoverageSummaryQuery({
      data: {
        cards: [{ connector_type: 'QUALYS', coverage_pct: 92, is_stale: false, stale_days: null, last_sync_status: 'ok', last_sync_at: null }],
        total_authoritative_assets: 10,
        has_authoritative_inventory: true,
        has_scanner_connector: true,
      },
    });
    const { container } = renderWithClient(<CompliancePage />);
    // Framework group headings (h2) — scoped via role to avoid ambiguity
    // with the chip bar's identically-labeled filter buttons.
    expect(screen.getByRole('heading', { name: 'SOC 2' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'ISO 27001' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'PCI DSS' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'NIST CSF' })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-control-card]').length).toBe(4);
    // Status pills render exactly what the backend returned -- Pass/Partial/Fail.
    const passCard = container.querySelector('[data-control-card][data-control-status="pass"]');
    expect(passCard).not.toBeNull();
    const partialCard = container.querySelector('[data-control-card][data-control-status="partial"]');
    expect(partialCard).not.toBeNull();
    const failCard = container.querySelector('[data-control-card][data-control-status="fail"]');
    expect(failCard).not.toBeNull();
    expect(screen.queryByText('Not enough posture data yet')).toBeNull();
  });

  it('framework chip bar filters the populated grid to a single framework', () => {
    searchParamsMock = new URLSearchParams('framework=soc2');
    mockComplianceQuery({ data: { controls: POPULATED_CONTROLS } });
    mockCoverageSummaryQuery({
      data: {
        cards: [],
        total_authoritative_assets: 10,
        has_authoritative_inventory: true,
        has_scanner_connector: true,
      },
    });
    const { container } = renderWithClient(<CompliancePage />);
    expect(container.querySelectorAll('[data-control-card]').length).toBe(1);
    // The SOC 2 group heading renders; the chip bar itself always shows
    // every framework label as a filter button (that's separate from
    // whether that framework's GROUP renders below) — scope via role to
    // assert on the group heading specifically, not the filter chip.
    expect(screen.getByRole('heading', { name: 'SOC 2' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'ISO 27001' })).toBeNull();
  });
});
