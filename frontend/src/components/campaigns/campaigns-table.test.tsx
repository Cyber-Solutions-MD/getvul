/**
 * campaigns-table.test.tsx — TDD tests for CampaignsTable.
 *
 * Test 1: all UI-SPEC columns rendered (remediation/members/% remediated/
 *         MTTR/status/tickets).
 * Test 2: numerics are mono + tabular-nums; MTTR always renders the
 *         em-dash placeholder (CampaignSummary has no mttr_seconds field).
 * Test 3: member/ticket count strings singularize at M=1 (never "1 findings").
 * Test 4: clicking a row invokes onRowClick with that campaign; the table
 *         itself never imports/calls useRouter.
 * Test 5: Enter/Space on a focused row also fires onRowClick.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { CampaignsTable } from './campaigns-table';
import type { CampaignSummary } from '@/lib/queries/use-campaigns';

const ROW: CampaignSummary = {
  id: 'c1',
  remediation_id: 'CVE-2024-1234: openssl 3.0 upgrade',
  status: 'ACTIVE',
  total: 12,
  open: 5,
  in_progress: 4,
  done: 3,
  pct_remediated: 25,
};

const SINGLE_ROW: CampaignSummary = {
  id: 'c2',
  remediation_id: 'CVE-2024-5678: patch curl',
  status: 'COMPLETE',
  total: 1,
  open: 0,
  in_progress: 1,
  done: 0,
  pct_remediated: 0,
};

describe('CampaignsTable', () => {
  it('renders all UI-SPEC column headers', () => {
    render(<CampaignsTable rows={[]} onRowClick={vi.fn()} />);
    ['Remediation', 'Members', '% remediated', 'MTTR', 'Status', 'Tickets'].forEach((h) => {
      expect(screen.getByText(h)).toBeInTheDocument();
    });
  });

  it('renders numerics mono + tabular-nums; MTTR always shows the em-dash', () => {
    const { container } = render(<CampaignsTable rows={[ROW]} onRowClick={vi.fn()} />);

    const pctCell = screen.getByText('25%');
    expect(pctCell.className).toContain('font-mono');
    expect(pctCell.className).toContain('tabular-nums');

    const remediationCell = screen.getByText(ROW.remediation_id);
    expect(remediationCell.className).toContain('font-mono');

    // MTTR column always renders the placeholder — CampaignSummary carries
    // no mttr_seconds field (deviation 1, module docstring).
    const mttrCells = container.querySelectorAll('[data-col="mttr"]');
    expect(mttrCells.length).toBeGreaterThan(0);
    expect(container.textContent).toContain('—');
  });

  it('singularizes member/ticket count strings at M=1 (never "1 findings")', () => {
    render(<CampaignsTable rows={[ROW, SINGLE_ROW]} onRowClick={vi.fn()} />);

    // ROW: 12 findings / 4 tickets (plural, in_progress=4)
    expect(screen.getByText('12 findings')).toBeInTheDocument();
    expect(screen.getByText('4 tickets')).toBeInTheDocument();

    // SINGLE_ROW: 1 finding / 1 ticket (singular, in_progress=1)
    expect(screen.getByText('1 finding')).toBeInTheDocument();
    expect(screen.getByText('1 ticket')).toBeInTheDocument();
    expect(screen.queryByText('1 findings')).toBeNull();
    expect(screen.queryByText('1 tickets')).toBeNull();
  });

  it('clicking a row invokes onRowClick with that campaign', () => {
    const onRowClick = vi.fn();
    render(<CampaignsTable rows={[ROW]} onRowClick={onRowClick} />);
    screen.getByText(ROW.remediation_id).closest('tr')!.click();
    expect(onRowClick).toHaveBeenCalledTimes(1);
    expect(onRowClick).toHaveBeenCalledWith(ROW);
  });

  it('Enter/Space on a focused row also fires onRowClick', () => {
    const onRowClick = vi.fn();
    render(<CampaignsTable rows={[ROW]} onRowClick={onRowClick} />);
    const row = screen.getByText(ROW.remediation_id).closest('tr')!;
    row.focus();
    row.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(onRowClick).toHaveBeenCalledTimes(1);
    row.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(onRowClick).toHaveBeenCalledTimes(2);
  });

  it('never imports next/navigation / calls useRouter (the page owns navigation)', () => {
    const source = readFileSync(join(__dirname, 'campaigns-table.tsx'), 'utf-8');
    expect(source).not.toMatch(/from ['"]next\/navigation['"]/);
    expect(source).not.toMatch(/useRouter\(/);
  });
});
