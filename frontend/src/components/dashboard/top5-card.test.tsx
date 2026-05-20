import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/lib/queries/use-top-triage', () => ({
  useTopTriage: vi.fn(),
}));

import { Top5Card } from './top5-card';
import { useTopTriage } from '@/lib/queries/use-top-triage';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const SAMPLE = {
  items: [
    {
      id: '1',
      cve_id: 'CVE-2024-A',
      severity: 'CRITICAL' as const,
      host: 'host-a',
      cvss_v3_score: 9.8,
      cisa_kev: true,
      sla_due_at: null,
    },
    {
      id: '2',
      cve_id: 'CVE-2024-B',
      severity: 'HIGH' as const,
      host: 'host-b',
      cvss_v3_score: 8.0,
      cisa_kev: false,
      sla_due_at: null,
    },
    {
      id: '3',
      cve_id: 'CVE-2024-C',
      severity: 'MEDIUM' as const,
      host: 'host-c',
      cvss_v3_score: 5.5,
      cisa_kev: false,
      sla_due_at: new Date(Date.now() + 24 * 3_600_000).toISOString(),
    },
    {
      id: '4',
      cve_id: 'CVE-2024-D',
      severity: 'LOW' as const,
      host: 'host-d',
      cvss_v3_score: 3.0,
      cisa_kev: false,
      sla_due_at: new Date(Date.now() + 30 * 24 * 3_600_000).toISOString(),
    },
    {
      id: '5',
      cve_id: 'CVE-2024-E',
      severity: 'CRITICAL' as const,
      host: 'host-e',
      cvss_v3_score: 9.4,
      cisa_kev: false,
      sla_due_at: new Date(Date.now() - 1 * 3_600_000).toISOString(),
    },
  ],
  total: 5,
};

describe('<Top5Card>', () => {
  beforeEach(() => {
    (useTopTriage as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      isPending: false,
      error: null,
      data: SAMPLE,
    });
  });

  it('renders the Top 5 to triage heading (microcopy.top5.h2)', () => {
    render(<Top5Card />, { wrapper });
    expect(screen.getByText('Top 5 to triage')).toBeInTheDocument();
  });

  it('renders 5 rows with severity glyphs ■ ▲ ◆ ○ (D-T-04)', () => {
    render(<Top5Card />, { wrapper });
    // Each row has its glyph; 2 CRITICALs share ■.
    expect(screen.getAllByText('■').length).toBe(2);
    expect(screen.getByText('▲')).toBeInTheDocument();
    expect(screen.getByText('◆')).toBeInTheDocument();
    expect(screen.getByText('○')).toBeInTheDocument();
  });

  it('each row CVE id renders in mono', () => {
    const { container } = render(<Top5Card />, { wrapper });
    const cveCells = container.querySelectorAll('p.font-mono');
    expect(cveCells.length).toBeGreaterThanOrEqual(5);
  });

  it('rows are wrapped in Link with ?cve=…&open=drill (D-T-03)', () => {
    render(<Top5Card />, { wrapper });
    const link = screen.getByRole('link', { name: /CVE-2024-A/ });
    expect(link.getAttribute('href')).toBe(
      '/dashboard/vulnerabilities?cve=CVE-2024-A&open=drill'
    );
  });

  it('has no axe violations', async () => {
    const { container } = render(<Top5Card />, { wrapper });
    expect(await axe(container)).toHaveNoViolations();
  });
});
