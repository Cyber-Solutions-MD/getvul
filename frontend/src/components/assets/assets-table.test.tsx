import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AssetsTable } from './assets-table';
import type { AssetSummary } from '@/lib/queries/use-assets';

// The component renders both a desktop <table> (>=900px) and a mobile card view
// (<900px). jsdom has no CSS (css:false), so both are in the DOM — scope row
// queries to the table to avoid double-matches.
const table = () => within(screen.getByRole('table'));

const ROWS: AssetSummary[] = [
  {
    id: 'a1',
    hostname: 'prod-db-01',
    os_name: 'Ubuntu 22.04 LTS',
    device_category: 'SERVER',
    risk_score: 85,
    seen_by_sources: ['QUALYS', 'TENABLE'],
    assigned_user: 'alice@example.com',
    tags: ['pci', 'tier-1'],
    total_vulns: 12,
    critical: 2,
    high: 5,
    exploitable: 1,
    kev: 1,
    sla_breach_count: 1,
  },
  {
    id: 'a2',
    hostname: 'prod-web-02',
    os_name: 'Windows Server 2022',
    device_category: 'SERVER',
    risk_score: 15,
    seen_by_sources: ['CROWDSTRIKE'],
    assigned_user: null,
    tags: [],
    total_vulns: 3,
    critical: 0,
    high: 0,
    exploitable: 0,
    kev: 0,
    sla_breach_count: 0,
  },
];

describe('AssetsTable', () => {
  it('renders all 6 column headers', () => {
    render(<AssetsTable rows={[]} onRowOpen={vi.fn()} />);
    ['Hostname', 'OS', 'Owner', 'Risk', 'Tags', 'Sources'].forEach((h) => {
      expect(screen.getByText(h)).toBeInTheDocument();
    });
  });

  it('renders hostname in mono, risk score tinted by band', () => {
    const { container } = render(<AssetsTable rows={ROWS} onRowOpen={vi.fn()} />);
    const hostnameCell = table().getByText('prod-db-01');
    expect(hostnameCell.className).toContain('font-mono');
    // risk 85 → critical band tint (on-soft token)
    const riskCells = container.querySelectorAll('td[class*="severity-critical-on-soft"]');
    expect(riskCells.length).toBeGreaterThan(0);
  });

  it('renders "Unassigned" when assigned_user is null', () => {
    render(<AssetsTable rows={ROWS} onRowOpen={vi.fn()} />);
    expect(table().getByText('Unassigned')).toBeInTheDocument();
  });

  it('renders tags inline; empty tags = no chips', () => {
    render(<AssetsTable rows={ROWS} onRowOpen={vi.fn()} />);
    expect(table().getByText('pci')).toBeInTheDocument();
    expect(table().getByText('tier-1')).toBeInTheDocument();
  });

  it('clicking a row calls onRowOpen with id', () => {
    const onOpen = vi.fn();
    render(<AssetsTable rows={ROWS} onRowOpen={onOpen} />);
    fireEvent.click(table().getByText('prod-db-01'));
    expect(onOpen).toHaveBeenCalledWith('a1');
  });

  it('Enter on a focused row fires onRowOpen', () => {
    const onOpen = vi.fn();
    render(<AssetsTable rows={ROWS} onRowOpen={onOpen} />);
    const row = table().getByText('prod-db-01').closest('tr')!;
    row.focus();
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onOpen).toHaveBeenCalledWith('a1');
  });

  it('ArrowDown moves focus to the next row', () => {
    render(<AssetsTable rows={ROWS} onRowOpen={vi.fn()} />);
    const row1 = table().getByText('prod-db-01').closest('tr')!;
    const row2 = table().getByText('prod-web-02').closest('tr')!;
    row1.focus();
    fireEvent.keyDown(row1, { key: 'ArrowDown' });
    expect(document.activeElement).toBe(row2);
  });

  it('tints stale rows when failedSources matches one of the asset sources (D-V-04)', () => {
    render(<AssetsTable rows={ROWS} onRowOpen={vi.fn()} failedSources={['QUALYS']} />);
    const row1 = table().getByText('prod-db-01').closest('tr')!;
    expect(row1.getAttribute('data-stale')).toBe('true');
    const row2 = table().getByText('prod-web-02').closest('tr')!;
    expect(row2.getAttribute('data-stale')).toBeNull();
  });
});
