// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';

// Wave 2 (Plan 11-05) will create this file. Import is the RED signal.
import { VulnTable } from './vuln-table';

type Row = {
  id: string;
  cve_id: string;
  title: string;
  asset: string;
  cvss: number;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'open' | 'snoozed';
  source: 'QUALYS' | 'TENABLE' | 'AWS_INSPECTOR' | 'RAPID7';
  sla_due_at: string | null;
  cisa_kev: boolean;
};

const rows: Row[] = [
  {
    id: '1',
    cve_id: 'CVE-2024-0001',
    title: 'log4j RCE',
    asset: 'prod-db-01',
    cvss: 9.8,
    severity: 'critical',
    status: 'open',
    source: 'QUALYS',
    sla_due_at: '2026-05-23T00:00:00Z',
    cisa_kev: true,
  },
  {
    id: '2',
    cve_id: 'CVE-2024-0002',
    title: 'OpenSSL flaw',
    asset: 'prod-web-02',
    cvss: 7.5,
    severity: 'high',
    status: 'open',
    source: 'TENABLE',
    sla_due_at: '2026-06-01T00:00:00Z',
    cisa_kev: false,
  },
  {
    id: '3',
    cve_id: 'CVE-2024-0003',
    title: 'NPM tarball',
    asset: 'build-runner-04',
    cvss: 5.5,
    severity: 'medium',
    status: 'open',
    source: 'RAPID7',
    sla_due_at: null,
    cisa_kev: false,
  },
];

describe('<VulnTable> (UX-03-02 + UX-07-03 keyboard + D-V-04 stale-row)', () => {
  const onRowOpen = vi.fn();
  const onSort = vi.fn();
  beforeEach(() => {
    onRowOpen.mockReset();
    onSort.mockReset();
  });

  it('renders 7 columns with the correct headers', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    expect(screen.getByRole('columnheader', { name: /Severity/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /CVE/i })).toBeInTheDocument();
    // Title/Product is one header (use partial match)
    expect(
      screen.getByRole('columnheader', { name: /Title|Product/i })
    ).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Asset/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /CVSS/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Status/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /SLA/i })).toBeInTheDocument();
  });

  it('severity column renders both colored glyph (■▲◆○) AND pill label', () => {
    const { container } = render(
      <VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />
    );
    // Glyph + label appear in the first body row's severity cell
    const firstRow = container.querySelector('tbody tr') as HTMLElement;
    const text = firstRow.textContent ?? '';
    expect(text).toMatch(/[■▲◆○]/);
    expect(text).toMatch(/Critical/i);
  });

  it('CVE column uses mono font', () => {
    const { container } = render(
      <VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />
    );
    const cveCell = container.querySelector('[data-col="cve"]') as HTMLElement;
    expect(cveCell.className).toContain('font-mono');
  });

  it('KEV badge rendered next to status when row.cisa_kev === true', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    // Both desktop table + mobile card render the KEV badge (no CSS in jsdom) —
    // scope to the table to avoid a double-match.
    expect(within(screen.getByRole('table')).getByText(/KEV/)).toBeInTheDocument();
  });

  it('SLA column right-aligned mono with color band (overdue/soon/ok)', () => {
    const { container } = render(
      <VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />
    );
    const slaCells = container.querySelectorAll('[data-col="sla"]');
    expect(slaCells.length).toBe(rows.length);
    // First SLA cell is right-aligned mono
    const first = slaCells[0] as HTMLElement;
    expect(first.className).toMatch(/font-mono/);
    expect(first.className).toMatch(/text-right|justify-end/);
  });

  it('ArrowDown moves focus row-to-row', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const bodyRows = screen.getAllByRole('row').filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    (bodyRows[0] as HTMLElement).focus();
    fireEvent.keyDown(bodyRows[0], { key: 'ArrowDown' });
    expect(document.activeElement).toBe(bodyRows[1]);
  });

  it('ArrowUp moves focus row-to-row up', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const bodyRows = screen.getAllByRole('row').filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    (bodyRows[1] as HTMLElement).focus();
    fireEvent.keyDown(bodyRows[1], { key: 'ArrowUp' });
    expect(document.activeElement).toBe(bodyRows[0]);
  });

  it('Home jumps to first row; End jumps to last row', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const bodyRows = screen.getAllByRole('row').filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    (bodyRows[1] as HTMLElement).focus();
    fireEvent.keyDown(bodyRows[1], { key: 'End' });
    expect(document.activeElement).toBe(bodyRows[bodyRows.length - 1]);
    fireEvent.keyDown(document.activeElement as Element, { key: 'Home' });
    expect(document.activeElement).toBe(bodyRows[0]);
  });

  it('Enter/Space on focused row fires onRowOpen(row.cve_id ?? row.id)', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const bodyRows = screen.getAllByRole('row').filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    (bodyRows[0] as HTMLElement).focus();
    fireEvent.keyDown(bodyRows[0], { key: 'Enter' });
    expect(onRowOpen).toHaveBeenCalledWith('CVE-2024-0001');
    fireEvent.keyDown(bodyRows[1], { key: ' ' });
    expect(onRowOpen).toHaveBeenCalledWith('CVE-2024-0002');
  });

  it('row click also fires onRowOpen', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const bodyRows = screen.getAllByRole('row').filter((r) => r.tagName === 'TR' && r.parentElement?.tagName === 'TBODY');
    fireEvent.click(bodyRows[0]);
    expect(onRowOpen).toHaveBeenCalledWith('CVE-2024-0001');
  });

  it('stale-row tinting — failedSources=[TENABLE] tints TENABLE row with data-stale + amber soft', () => {
    const { container } = render(
      <VulnTable
        rows={rows}
        onRowOpen={onRowOpen}
        onSort={onSort}
        failedSources={['TENABLE']}
      />
    );
    const tenableRow = Array.from(
      container.querySelectorAll('tbody tr')
    ).find((tr) => tr.textContent?.includes('CVE-2024-0002')) as HTMLElement;
    expect(tenableRow.getAttribute('data-stale')).toBe('true');
    expect(tenableRow.className).toMatch(/amber-soft|data-\[stale=true\]:bg-amber-soft/);
  });

  it('sticky header — <thead> className includes sticky top-0', () => {
    const { container } = render(
      <VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />
    );
    const thead = container.querySelector('thead') as HTMLElement;
    expect(thead.className).toContain('sticky');
    expect(thead.className).toMatch(/top-0/);
    expect(thead.className).toMatch(/bg-surface/);
  });

  it('sortable headers cycle asc → desc → clear (Severity / CVE / CVSS / SLA)', () => {
    render(<VulnTable rows={rows} onRowOpen={onRowOpen} onSort={onSort} />);
    const cveHeader = screen.getByRole('columnheader', { name: /CVE/i });
    // First click: asc
    fireEvent.click(cveHeader);
    expect(onSort).toHaveBeenCalledWith('cve_id', 'asc');
    // Second click: desc
    fireEvent.click(cveHeader);
    expect(onSort).toHaveBeenCalledWith('cve_id', 'desc');
    // Third click: clear (null/default)
    fireEvent.click(cveHeader);
    expect(onSort).toHaveBeenCalledWith(null, null);
  });
});
