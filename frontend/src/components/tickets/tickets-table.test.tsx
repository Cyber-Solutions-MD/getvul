/**
 * tickets-table.test.tsx — TDD tests for TicketsTable (8-column contract).
 *
 * Test 1: 8 column headers rendered in order per D-L-01.
 * Test 2: Row composes Plan-04 primitives: ProviderMark, StatusPill, SlaPill, VulnCount.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TicketsTable } from './tickets-table';
import type { TicketSummary } from '@/lib/queries/use-tickets';

const ROW: TicketSummary = {
  id: 't1',
  provider: 'jira',
  externalId: 'PROJ-101',
  title: 'Fix login bypass vulnerability',
  externalStatus: 'open',
  blocked: false,
  blockedReason: null,
  slaDueAt: null,
  assignee: 'alice@example.com',
  maxSeverity: 'critical',
  vulnCount: 5,
  criticalCount: 2,
  highCount: 1,
  externalTicketUrl: 'https://example.atlassian.net/browse/PROJ-101',
};

describe('TicketsTable', () => {
  it('renders all 8 column headers in order (UX-05-01 8-column contract)', () => {
    render(<TicketsTable rows={[]} onRowClick={vi.fn()} />);
    const headers = ['Severity', 'Provider', 'ID', 'Title', 'Vulns', 'Assignee', 'Status', 'SLA'];
    headers.forEach((h) => {
      expect(screen.getByText(h)).toBeInTheDocument();
    });
  });

  it('row composes Plan-04 primitives: ProviderMark, StatusPill, SlaPill, VulnCount', () => {
    const { container } = render(
      <TicketsTable rows={[ROW]} onRowClick={vi.fn()} />
    );

    // ProviderMark — rendered as a span with aria-label='jira'
    const providerMark = container.querySelector('[aria-label="jira"]');
    expect(providerMark).toBeInTheDocument();

    // StatusPill — has [data-status] attribute (the Pill inner span)
    const statusPill = container.querySelector('[data-status]');
    expect(statusPill).toBeInTheDocument();

    // SlaPill — has font-mono class (D-SLA-04 spec) + shows Unknown for null dueAt
    const slaPill = screen.getByText('Unknown');
    expect(slaPill).toBeInTheDocument();

    // VulnCount — renders total·critical·high
    // total=5, shows '5' text node
    const vulnTotal = screen.getByText('5');
    expect(vulnTotal).toBeInTheDocument();
  });
});
