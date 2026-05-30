// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AssetVulnsList } from './asset-vulns-list';
import type { VulnerabilitySummary } from '@/lib/queries/use-vulnerabilities';

const ROWS: VulnerabilitySummary[] = [
  {
    id: 'v1',
    cve_id: 'CVE-2024-0001',
    vulnerability_name: 'OpenSSL heap overflow',
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
  {
    id: 'v2',
    cve_id: 'CVE-2024-0002',
    vulnerability_name: 'curl flaw',
    severity: 'HIGH',
    cvss_v3_score: 7.4,
    cisa_kev: false,
    exploit_available: false,
    source: 'TENABLE',
    asset_id: 'a1',
    asset_hostname: 'h',
    status: 'OPEN',
    first_detected_at: '',
    last_seen_at: '',
    sla_due_at: null,
  },
];

describe('AssetVulnsList', () => {
  it('returns null on empty rows', () => {
    const { container } = render(<AssetVulnsList rows={[]} onRowOpen={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders one role=row per item with correct severity glyph', () => {
    render(<AssetVulnsList rows={ROWS} onRowOpen={vi.fn()} />);
    expect(screen.getAllByRole('row')).toHaveLength(2);
    // critical glyph rendered with severity-critical tint
    expect(screen.getByText('■').className).toContain('text-severity-critical');
  });

  it('renders KEV badge only for cisa_kev rows', () => {
    render(<AssetVulnsList rows={ROWS} onRowOpen={vi.fn()} />);
    const kevs = screen.getAllByText('KEV');
    expect(kevs).toHaveLength(1);
  });

  it('click on a row fires onRowOpen with cve_id', () => {
    const onOpen = vi.fn();
    render(<AssetVulnsList rows={ROWS} onRowOpen={onOpen} />);
    fireEvent.click(screen.getByTestId('vuln-row-CVE-2024-0001'));
    expect(onOpen).toHaveBeenCalledWith('CVE-2024-0001');
  });

  it('Enter on focused row fires onRowOpen', () => {
    const onOpen = vi.fn();
    render(<AssetVulnsList rows={ROWS} onRowOpen={onOpen} />);
    const row = screen.getByTestId('vuln-row-CVE-2024-0002');
    row.focus();
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onOpen).toHaveBeenCalledWith('CVE-2024-0002');
  });

  it('ArrowDown moves focus to next row', () => {
    render(<AssetVulnsList rows={ROWS} onRowOpen={vi.fn()} />);
    const first = screen.getByTestId('vuln-row-CVE-2024-0001');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(screen.getByTestId('vuln-row-CVE-2024-0002'));
  });
});
