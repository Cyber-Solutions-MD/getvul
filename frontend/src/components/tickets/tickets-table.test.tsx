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
  external_ticket_id: 'PROJ-101',
  title: 'Fix login bypass vulnerability',
  external_status: 'open',
  blocked: false,
  blocked_reason: null,
  sla_due_at: null,
  assignee: 'alice@example.com',
  max_severity: 'critical',
  vuln_count: 5,
  critical_count: 2,
  high_count: 1,
  external_ticket_url: 'https://example.atlassian.net/browse/PROJ-101',
  // Phase 35 SRC-07: transitive union provenance — 2 scanners corroborate.
  sources: ['QUALYS', 'RAPID7'],
  sources_count: 2,
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

    // SlaPill — has font-mono class (D-SLA-04 spec) + shows Unknown for null dueAt.
    // Both desktop table and mobile card render an SlaPill, so we use getAllByText.
    const slaPills = screen.getAllByText('Unknown');
    expect(slaPills.length).toBeGreaterThan(0);

    // VulnCount — renders total·critical·high
    // Both desktop table and mobile card render VulnCount; use getAllByText.
    const vulnTotals = screen.getAllByText('5');
    expect(vulnTotals.length).toBeGreaterThan(0);
  });

  // Phase 35 SRC-01/07 — shared SourceBadgeGroup: transitive union
  // provenance, distinct from the ticket-provider mark.
  it('renders SourceBadgeGroup (transitive union provenance) distinct from ProviderMark', () => {
    render(<TicketsTable rows={[ROW]} onRowClick={vi.fn()} />);
    const groups = screen.getAllByText('2 sources');
    expect(groups.length).toBeGreaterThan(0);
    const multiGroup = document.querySelectorAll('[data-source-badge-group="multi"]');
    expect(multiGroup.length).toBeGreaterThan(0);
    // Never overclaims "confirmed" from provenance.
    expect(document.body.textContent).not.toContain('confirmed');
  });

  it('renders the neutral empty-source state (em-dash) when a ticket has no sources', () => {
    const noSourceRow: TicketSummary = { ...ROW, sources: undefined, sources_count: undefined };
    render(<TicketsTable rows={[noSourceRow]} onRowClick={vi.fn()} />);
    const emptyGroups = document.querySelectorAll('[data-source-badge-group="empty"]');
    expect(emptyGroups.length).toBeGreaterThan(0);
  });
});
