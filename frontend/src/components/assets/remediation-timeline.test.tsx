// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RemediationTimeline } from './remediation-timeline';
import type { RemediationTicket } from '@/lib/queries/use-asset-remediations';

// 24-09 Task 2: RemediationTimeline mounts the shared AiExplanationSection
// (resourceType="remediation") once per ticket row. Stubbed the same way
// the asset-detail page test stubs it -- this file's own responsibility is
// proving each row wires the right resourceId (the row's own cve_id, per
// the Plan-08 CVE-string-keyed grounding contract) and a unique headingId,
// not re-verifying the component's own 8-state matrix (already covered
// exhaustively for 'remediation' in ai-explanation-section.test.tsx).
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
    cve_id: 'CVE-2024-0001',
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
    cve_id: 'CVE-2023-4863',
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

  it('uses resolved tone for lowercase "completed" status (WR-12 — Asana lowercase)', () => {
    // Backend emits `Ticket.external_status = "completed"` (lowercase) for
    // Asana's terminal state. The component upper-cases on read, so the
    // STATUS_TONE map must have a COMPLETED entry — without it the pill fell
    // through to the muted fallback tone (text-text-faint).
    const completed: RemediationTicket = {
      ...TICKETS[0],
      id: 't-completed',
      external_status: 'completed',
    };
    const { container } = render(<RemediationTimeline tickets={[completed]} />);
    const row = container.querySelector(`[data-testid="timeline-row-t-completed"]`);
    // The status pill renders the raw external_status text. Find it by
    // matching the lowercase 'completed' span and verify its tone class.
    const pill = Array.from(row?.querySelectorAll('span') ?? []).find(
      (s) => s.textContent === 'completed',
    );
    expect(pill).toBeDefined();
    // Resolved tone uses text-severity-low; fallback would carry text-text-faint.
    expect(pill!.className).toMatch(/text-severity-low/);
    expect(pill!.className).not.toMatch(/text-text-faint/);
  });

  it('mounts an AI Explanation section per ticket row (resourceType="remediation", resourceId=that row\'s cve_id, D-15)', () => {
    render(<RemediationTimeline tickets={TICKETS} />);
    const sections = screen.getAllByTestId('ai-explanation-section');
    expect(sections).toHaveLength(2);
    expect(sections[0]).toHaveAttribute('data-resource-type', 'remediation');
    expect(sections[0]).toHaveAttribute('data-resource-id', 'CVE-2024-0001');
    expect(sections[1]).toHaveAttribute('data-resource-id', 'CVE-2023-4863');
    // Each row's mount needs its own unique DOM id -- never a shared literal
    // that would collide the moment >1 ticket row renders.
    expect(sections[0].getAttribute('data-heading-id')).not.toBe(
      sections[1].getAttribute('data-heading-id'),
    );
    expect(sections[0].getAttribute('data-heading-id')).not.toBe('');
  });

  it('omits the AI Explanation section for a ticket row whose cve_id is null (no CVE to ground an explanation)', () => {
    const noCve: RemediationTicket = { ...TICKETS[0], id: 't-no-cve', cve_id: null };
    render(<RemediationTimeline tickets={[noCve]} />);
    expect(screen.queryByTestId('ai-explanation-section')).toBeNull();
  });
});
