/**
 * remediations-table.test.tsx — TDD tests for RemediationsTable.
 *
 * Test 1: all columns rendered + a "Start campaign" CTA per row.
 * Test 2: member count singularizes at M=1 (never "1 findings").
 * Test 3: clicking "Start campaign" invokes onStartCampaign with that row's
 *         remediation_id.
 * Test 4: the table never imports/calls useRouter (page owns navigation).
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { RemediationsTable } from './remediations-table';
import type { RemediationGroup } from '@/lib/queries/use-remediations-grouped';

const ROW: RemediationGroup = {
  remediation_id: 'CVE-2024-1234: openssl 3.0 upgrade',
  remediation_action: 'Upgrade openssl to 3.0.14',
  affected_product: 'openssl',
  affected_hosts: 12,
  vuln_count: 12,
  max_severity: 'CRITICAL',
  is_suppressed: false,
  suppressed_count: 0,
};

const SINGLE_ROW: RemediationGroup = {
  remediation_id: 'CVE-2024-5678: patch curl',
  remediation_action: null,
  affected_product: 'curl',
  affected_hosts: 1,
  vuln_count: 1,
  max_severity: 'LOW',
  is_suppressed: false,
  suppressed_count: 0,
};

describe('RemediationsTable', () => {
  it('renders column headers and a Start campaign CTA per row', () => {
    render(<RemediationsTable rows={[ROW]} onStartCampaign={vi.fn()} />);
    ['Remediation', 'Hosts', 'Members', 'Severity'].forEach((h) => {
      expect(screen.getByText(h)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Start campaign' })).toBeInTheDocument();
  });

  it('falls back to remediation_id when remediation_action is null', () => {
    render(<RemediationsTable rows={[SINGLE_ROW]} onStartCampaign={vi.fn()} />);
    expect(screen.getByText(SINGLE_ROW.remediation_id)).toBeInTheDocument();
  });

  it('singularizes the member count at M=1 (never "1 findings")', () => {
    render(<RemediationsTable rows={[ROW, SINGLE_ROW]} onStartCampaign={vi.fn()} />);
    expect(screen.getByText('12 findings')).toBeInTheDocument();
    expect(screen.getByText('1 finding')).toBeInTheDocument();
    expect(screen.queryByText('1 findings')).toBeNull();
  });

  it('clicking Start campaign invokes onStartCampaign with that row\'s remediation_id', () => {
    const onStartCampaign = vi.fn();
    render(<RemediationsTable rows={[ROW]} onStartCampaign={onStartCampaign} />);
    screen.getByRole('button', { name: 'Start campaign' }).click();
    expect(onStartCampaign).toHaveBeenCalledTimes(1);
    expect(onStartCampaign).toHaveBeenCalledWith(ROW.remediation_id);
  });

  it('disables every CTA while isStarting is true', () => {
    render(<RemediationsTable rows={[ROW]} onStartCampaign={vi.fn()} isStarting />);
    expect(screen.getByRole('button', { name: 'Start campaign' })).toBeDisabled();
  });

  it('never imports next/navigation / calls useRouter (the page owns navigation)', () => {
    const source = readFileSync(join(__dirname, 'remediations-table.tsx'), 'utf-8');
    expect(source).not.toMatch(/from ['"]next\/navigation['"]/);
    expect(source).not.toMatch(/useRouter\(/);
  });
});
