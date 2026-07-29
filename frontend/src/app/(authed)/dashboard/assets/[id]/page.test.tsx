// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AssetDetailPage from './page';

const replace = vi.fn();
const refetch = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => '/assets/a1',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ id: 'a1' }),
}));

vi.mock('@/lib/queries/use-asset-detail', () => ({
  useAsset: () => ({
    data: {
      id: 'a1',
      hostname: 'prod-db-01',
      os_name: 'Ubuntu',
      os_version: '22.04',
      device_category: 'SERVER',
      risk_score: 85,
      seen_by_sources: ['QUALYS'],
      assigned_user: 'alice@example.com',
      tags: ['pci', 'tier-1'],
      sla_breach: 3,
      vuln_counts: {
        total: 12,
        critical: 2,
        high: 5,
        medium: 3,
        low: 2,
        exploitable: 1,
        kev: 4,
        sla_breach: 3,
      },
      directory_user: {
        email: 'alice@example.com',
        display_name: 'Alice',
        idp_source: 'okta',
        role: 'USER',
        department: null,
        job_title: null,
        avatar_url: null,
        groups: [],
        is_active: true,
      },
      ip_addresses: ['10.0.0.1'],
      mac_addresses: [],
      serial_number: null,
      model: null,
      managed_by: 'JAMF',
      last_checkin_at: null,
      building: null,
      department: null,
    },
    isLoading: false,
    error: null,
    refetch,
  }),
}));

vi.mock('@/lib/queries/use-asset-vulnerabilities', () => ({
  useAssetVulnerabilities: () => ({
    data: {
      items: [
        {
          id: 'v1',
          cve_id: 'CVE-2024-0001',
          vulnerability_name: 'OpenSSL',
          severity: 'CRITICAL',
          cvss_v3_score: 9.8,
          cisa_kev: true,
          exploit_available: false,
          source: 'QUALYS',
          asset_id: 'a1',
          asset_hostname: 'h',
          status: 'OPEN',
          first_detected_at: '',
          last_seen_at: '',
          sla_due_at: null,
        },
      ],
      total: 1,
      page: 1,
      page_size: 25,
      total_pages: 1,
      facets: { severity: {}, source: {}, status: {} },
    },
    isLoading: false,
    error: null,
  }),
}));

vi.mock('@/lib/queries/use-asset-remediations', () => ({
  useAssetRemediations: () => ({
    data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
    isLoading: false,
    error: null,
    refetch,
  }),
}));

vi.mock('@/components/vulnerabilities/drill-panel', () => ({
  DrillPanel: ({ cveId }: { cveId: string | null }) => (
    <div data-testid="drill-panel" data-cve={cveId ?? ''} />
  ),
}));
vi.mock('@/components/vulnerabilities/drill-panel-mobile', () => ({
  DrillPanelMobile: () => null,
}));

// 24-09 Task 2: the page mounts the shared AiExplanationSection
// (resourceType="host"). Stubbed here the same way DrillPanel is stubbed
// above -- this page's own test responsibility is proving the MOUNT
// (right resourceType/resourceId/headingId), not re-verifying the
// component's own 8-state matrix or three-view parity, which
// ai-explanation-section.test.tsx already covers exhaustively for 'host'
// alongside 'vuln'/'remediation'.
vi.mock('@/components/ai/ai-explanation-section', () => ({
  AiExplanationSection: ({
    resourceType,
    resourceId,
    headingId,
  }: {
    resourceType: string;
    resourceId: string;
    headingId?: string;
  }) => (
    <div
      data-testid="ai-explanation-section"
      data-resource-type={resourceType}
      data-resource-id={resourceId}
      data-heading-id={headingId ?? ''}
    />
  ),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AssetDetailPage />
    </QueryClientProvider>,
  );
}

describe('/assets/[id] page', () => {
  beforeEach(() => {
    replace.mockReset();
  });

  it('renders Breadcrumb (Assets / hostname)', () => {
    renderPage();
    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(nav).toHaveTextContent('Assets');
    expect(nav).toHaveTextContent('prod-db-01');
  });

  it('renders the hostname as the page H1 in mono', () => {
    renderPage();
    const h1 = screen.getByRole('heading', { level: 1, name: 'prod-db-01' });
    expect(h1.className).toContain('font-mono');
  });

  it('renders tags inline with the hostname', () => {
    renderPage();
    const tagBlock = screen.getByTestId('header-tags');
    expect(tagBlock).toHaveTextContent('pci');
    expect(tagBlock).toHaveTextContent('tier-1');
  });

  it('renders the right rail with RiskCard, OwnerCard, IdentityMetadataRail', () => {
    renderPage();
    expect(screen.getByTestId('asset-detail-rail')).toBeInTheDocument();
    expect(screen.getByTestId('risk-card')).toBeInTheDocument();
    expect(screen.getByTestId('owner-card')).toBeInTheDocument();
    expect(screen.getByTestId('identity-metadata')).toBeInTheDocument();
  });

  it('renders the severity ribbon with vuln_counts from the asset', () => {
    renderPage();
    expect(screen.getByTestId('ribbon-critical').textContent).toBe('■2');
    expect(screen.getByTestId('ribbon-high').textContent).toBe('▲5');
    expect(screen.getByTestId('ribbon-medium').textContent).toBe('◆3');
    expect(screen.getByTestId('ribbon-low').textContent).toBe('○2');
  });

  it('clicking a vuln row sets ?cve=<id>&open=drill via router.replace', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('vuln-row-CVE-2024-0001'));
    expect(replace).toHaveBeenCalled();
    const target = replace.mock.calls[0][0] as string;
    expect(target).toContain('cve=CVE-2024-0001');
    expect(target).toContain('open=drill');
  });

  it('mounts the DrillPanel (Phase 11 component) reading ?cve from URL', () => {
    renderPage();
    expect(screen.getByTestId('drill-panel')).toBeInTheDocument();
  });

  it('renders empty state for remediations when list is empty', () => {
    renderPage();
    expect(screen.getByText('No remediation tickets')).toBeInTheDocument();
  });

  it('mounts the AI Explanation section for the host view (resourceType="host", resourceId=asset id, D-15)', () => {
    renderPage();
    const el = screen.getByTestId('ai-explanation-section');
    expect(el).toHaveAttribute('data-resource-type', 'host');
    expect(el).toHaveAttribute('data-resource-id', 'a1');
    // Own unique headingId -- never the vuln drill's default 'drill-ai-h',
    // since both can theoretically be reachable from the same page render
    // tree in this test (no drill open here, but the id must be collision-
    // safe by construction, not by the drill happening to be closed).
    expect(el.getAttribute('data-heading-id')).toBe('ai-explanation-h-host');
  });
});
