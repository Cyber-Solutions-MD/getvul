// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RemediationTimeline } from './remediation-timeline';
import type { RemediationTicket } from '@/lib/queries/use-asset-remediations';

const TICKETS: RemediationTicket[] = [
  {
    id: 't1',
    provider: 'JIRA',
    external_ticket_url: 'https://j/A-1',
    external_status: 'IN_PROGRESS',
    assignee: null,
    title: 'Patch OpenSSL',
    subtitle: null,
    max_severity: 'CRITICAL',
    vuln_count: 5,
    critical_count: 2,
    high_count: 3,
    ticket_created_at: new Date(Date.now() - 86400 * 1000 * 2).toISOString(),
    resolved_at: null,
  },
  {
    id: 't2',
    provider: 'ASANA',
    external_ticket_url: null,
    external_status: 'OPEN',
    assignee: null,
    title: 'Investigate curl flaw',
    subtitle: null,
    max_severity: 'HIGH',
    vuln_count: 1,
    critical_count: 0,
    high_count: 1,
    ticket_created_at: new Date(Date.now() - 3600 * 1000 * 5).toISOString(),
    resolved_at: null,
  },
];

describe('RemediationTimeline', () => {
  it('returns null on empty tickets', () => {
    const { container } = render(<RemediationTimeline tickets={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders one row per ticket', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    expect(screen.getByTestId('timeline-row-t1')).toBeInTheDocument();
    expect(screen.getByTestId('timeline-row-t2')).toBeInTheDocument();
  });

  it('renders provider gradient mark with provider data-testid', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    expect(screen.getByTestId('provider-mark-jira')).toBeInTheDocument();
    expect(screen.getByTestId('provider-mark-asana')).toBeInTheDocument();
  });

  it('renders external_ticket_url as link with rel="noreferrer" when present', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    const link = screen.getByRole('link', { name: 'Patch OpenSSL' });
    expect(link).toHaveAttribute('href', 'https://j/A-1');
    expect(link).toHaveAttribute('rel', 'noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders ticket without external_ticket_url as plain text (no link)', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    // Asana ticket has no link — title rendered as plain text
    expect(screen.queryByRole('link', { name: 'Investigate curl flaw' })).toBeNull();
    expect(screen.getByText('Investigate curl flaw')).toBeInTheDocument();
  });

  it('renders relative timestamp (d/h ago)', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    expect(screen.getByText(/2d ago/)).toBeInTheDocument();
    expect(screen.getByText(/5h ago/)).toBeInTheDocument();
  });

  it('renders status pill text', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    expect(screen.getByText('IN_PROGRESS')).toBeInTheDocument();
    expect(screen.getByText('OPEN')).toBeInTheDocument();
  });

  it('clamps future timestamp to "just now" (clock skew defense)', () => {
    const future: RemediationTicket = {
      ...TICKETS[0],
      id: 't-future',
      ticket_created_at: new Date(Date.now() + 60_000).toISOString(),
    };
    render(<RemediationTimeline tickets={[future]} />);
    expect(screen.getByText(/just now/)).toBeInTheDocument();
  });

  it('renders unknown provider with gray mark fallback', () => {
    const unknown: RemediationTicket = {
      ...TICKETS[0],
      id: 't-unk',
      provider: 'GITLAB',
    };
    render(<RemediationTimeline tickets={[unknown]} />);
    expect(screen.getByTestId('provider-mark-gitlab')).toBeInTheDocument();
  });
});
