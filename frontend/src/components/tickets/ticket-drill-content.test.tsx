// @vitest-environment jsdom
/**
 * Tests for TicketDrillContent (D-D-01)
 *
 * TDD RED phase — these tests define the contract before the component exists.
 *
 * Test structure:
 *   1. Header: ProviderMark + mono ID + truncated title + close button
 *   2. Body: linked-vulns mini-list (top 3, +N more)
 *   3. Body: status+SLA pill row + truncated description + Show full link
 *   4. Footer: Open in provider (external) + Open full detail (internal) + blocked toggle slot
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Link from 'next/link';

// Mock next/link (App Router) — render as plain <a>
vi.mock('next/link', () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

// Import the component under test (will fail — RED phase)
import { TicketDrillContent } from './ticket-drill-content';
import type { TicketDrillData } from './ticket-drill-content';

// ── Shared fixture ──────────────────────────────────────────────────────────

const baseTicket: TicketDrillData = {
  provider: 'jira',
  externalId: 'JIRA-2841',
  title: 'Patch CVE-2024-3094 on prod hosts',
  externalUrl: 'https://example.atlassian.net/browse/JIRA-2841',
  externalStatus: 'open',
  blocked: false,
  slaDueAt: null,
  description: 'This ticket tracks remediation of the critical xz backdoor across all production hosts.',
  linkedVulns: [
    { cveId: 'CVE-2024-3094', severity: 'critical', cvss: 10.0 },
    { cveId: 'CVE-2024-1111', severity: 'high', cvss: 7.5 },
    { cveId: 'CVE-2024-2222', severity: 'medium', cvss: 5.0 },
  ],
  totalVulns: 3,
};

// ── Test 1: Header ──────────────────────────────────────────────────────────

describe('TicketDrillContent — header (D-D-01)', () => {
  it('renders a provider mark with the provider name', () => {
    const onClose = vi.fn();
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={onClose}
      />
    );
    // ProviderMark renders a span with aria-label={provider}
    const mark = screen.getByRole('generic', { name: /jira/i }) as HTMLElement;
    // The plan says ProviderMark is imported from 'provider-mark'; test that it appears
    expect(mark).toBeDefined();
  });

  it('renders the ticket external ID in mono font', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    const id = screen.getByText('JIRA-2841');
    expect(id.className).toMatch(/font-mono/);
  });

  it('renders a close button that calls onClose when clicked', () => {
    const onClose = vi.fn();
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={onClose}
      />
    );
    const close = screen.getByRole('button', { name: /close/i });
    expect(close).toBeInTheDocument();
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders the ticket title truncated (title in DOM)', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('Patch CVE-2024-3094 on prod hosts')).toBeInTheDocument();
  });
});

// ── Test 2: Linked-vulns mini-list ──────────────────────────────────────────

describe('TicketDrillContent — linked vulns body (D-D-01)', () => {
  it('renders the top 3 linked vulns with severity glyph, CVE id, and CVSS score', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    // CVE IDs present
    expect(screen.getByText('CVE-2024-3094')).toBeInTheDocument();
    expect(screen.getByText('CVE-2024-1111')).toBeInTheDocument();
    expect(screen.getByText('CVE-2024-2222')).toBeInTheDocument();

    // Severity glyphs present (critical ■, high ▲, medium ◆)
    expect(screen.getByText('■')).toBeInTheDocument();
    expect(screen.getByText('▲')).toBeInTheDocument();
    expect(screen.getByText('◆')).toBeInTheDocument();

    // CVSS scores present
    expect(screen.getByText(/10\.0/)).toBeInTheDocument();
    expect(screen.getByText(/7\.5/)).toBeInTheDocument();
  });

  it('shows "+N more" link to /tickets/[id] when totalVulns > 3', () => {
    const ticket: TicketDrillData = {
      ...baseTicket,
      linkedVulns: [
        { cveId: 'CVE-2024-3094', severity: 'critical', cvss: 10.0 },
        { cveId: 'CVE-2024-1111', severity: 'high', cvss: 7.5 },
        { cveId: 'CVE-2024-2222', severity: 'medium', cvss: 5.0 },
      ],
      totalVulns: 7,
    };
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={ticket}
        onClose={vi.fn()}
      />
    );
    const moreLink = screen.getByText('+4 more');
    expect(moreLink).toBeInTheDocument();
    const anchor = moreLink.closest('a');
    expect(anchor?.getAttribute('href')).toBe('/tickets/ticket-123');
  });

  it('does not show "+N more" when totalVulns <= 3', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    expect(screen.queryByText(/\+\d+ more/)).not.toBeInTheDocument();
  });
});

// ── Test 3: Status, SLA pills, description, Show full ─────────────────────

describe('TicketDrillContent — status/SLA/description body (D-D-01)', () => {
  it('renders a StatusPill reflecting externalStatus', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    // StatusPill renders "Open" for externalStatus='open'
    expect(screen.getByText('Open')).toBeInTheDocument();
  });

  it('renders a SlaPill (Unknown when slaDueAt is null)', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    // SlaPill renders "Unknown" when dueAt=null
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('renders the description truncated with a Show full link', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    // Description text present
    expect(
      screen.getByText(
        'This ticket tracks remediation of the critical xz backdoor across all production hosts.'
      )
    ).toBeInTheDocument();

    // "Show full →" link to detail page
    const showFull = screen.getByText(/show full/i);
    expect(showFull).toBeInTheDocument();
    const anchor = showFull.closest('a');
    expect(anchor?.getAttribute('href')).toBe('/tickets/ticket-123');
  });
});

// ── Test 4: Sticky footer actions ──────────────────────────────────────────

describe('TicketDrillContent — footer actions (D-D-01)', () => {
  it('renders "Open in Jira" as an external link with target=_blank + noopener', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    const link = screen.getByRole('link', { name: /open in jira/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('noreferrer');
    expect(link.getAttribute('href')).toBe('https://example.atlassian.net/browse/JIRA-2841');
  });

  it('renders "Open full detail" as an internal link to /tickets/[id]', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    const link = screen.getByRole('link', { name: /open full detail/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute('href')).toBe('/tickets/ticket-123');
  });

  it('renders a disabled "Mark blocked" placeholder when renderBlockedToggle is not provided', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
      />
    );
    const btn = screen.getByRole('button', { name: /mark blocked/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled();
  });

  it('renders the custom blocked toggle when renderBlockedToggle is provided', () => {
    const BlockedToggle = () => <button type="button">Unblock</button>;
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={baseTicket}
        onClose={vi.fn()}
        renderBlockedToggle={({ ticketId }) => <BlockedToggle />}
      />
    );
    expect(screen.getByRole('button', { name: /unblock/i })).toBeInTheDocument();
    // Placeholder "Mark blocked" should be gone
    expect(screen.queryByRole('button', { name: /mark blocked/i })).not.toBeInTheDocument();
  });

  it('uses provider name in "Open in" copy (per copy-voice.md: no "Click to...")', () => {
    render(
      <TicketDrillContent
        ticketId="ticket-123"
        ticket={{ ...baseTicket, provider: 'asana' }}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByRole('link', { name: /open in asana/i })).toBeInTheDocument();
  });
});
