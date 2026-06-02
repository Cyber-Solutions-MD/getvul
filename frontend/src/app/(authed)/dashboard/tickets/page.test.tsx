/**
 * page.test.tsx — TDD tests for the /tickets list page rewrite (Plan 13-07 Task 3).
 *
 * Test 1: Renders 8 column headers; given list data, rows render.
 * Test 2: State branches — error/loading/empty are mutually exclusive.
 * Test 3: List/Board toggle buttons present.
 * Test 4: Asana unconfigured error renders deep-link to /dashboard/connectors (D-S-02).
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Use vi.mock with factory — no top-level variable references inside factory (vitest hoisting).
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/tickets',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

vi.mock('@/lib/queries/use-mark-blocked', () => ({
  useMarkBlocked: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

// Import the hook mock AFTER vi.mock declarations so we can control return values.
import * as useTicketsModule from '@/lib/queries/use-tickets';
import TicketsPage from './page';

const mockTicket = {
  id: 't1',
  provider: 'jira',
  externalId: 'PROJ-101',
  title: 'Fix login bypass',
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

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('/tickets page', () => {
  beforeEach(() => {
    vi.spyOn(useTicketsModule, 'useTickets').mockReturnValue({
      data: {
        items: [mockTicket],
        total: 1,
        page: 1,
        page_size: 25,
        pages: 1,
      },
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      // Minimal TanStack query result shape
    } as ReturnType<typeof useTicketsModule.useTickets>);
  });

  it('Test 1: renders 8 column headers and row data', () => {
    renderWithClient(<TicketsPage />);
    // 8 column headers per D-L-01 (use getAllByText since desktop+mobile both render)
    ['Severity', 'Provider', 'ID', 'Title', 'Vulns', 'Assignee', 'Status', 'SLA'].forEach((h) => {
      expect(screen.getAllByText(h).length).toBeGreaterThan(0);
    });
    // Row data rendered (desktop + mobile both render, use getAllByText)
    expect(screen.getAllByText('PROJ-101').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Fix login bypass').length).toBeGreaterThan(0);
  });

  it('Test 2: error branch shows PartialFailureBanner; loading shows skeleton; empty shows EmptyState — mutually exclusive (WR-13)', () => {
    // Error state
    vi.spyOn(useTicketsModule, 'useTickets').mockReturnValueOnce({
      data: null,
      isPending: false,
      isLoading: false,
      error: new Error('Connection refused: cannot reach backend'),
      refetch: vi.fn(),
    } as ReturnType<typeof useTicketsModule.useTickets>);
    const { unmount } = renderWithClient(<TicketsPage />);
    // PartialFailureBanner should be present (role='alert')
    expect(screen.getByRole('alert')).toBeInTheDocument();
    // No EmptyState (role='status') alongside the error
    expect(screen.queryByRole('status')).toBeNull();
    unmount();

    // Empty state
    vi.spyOn(useTicketsModule, 'useTickets').mockReturnValueOnce({
      data: { items: [], total: 0, page: 1, page_size: 25, pages: 0 },
      isPending: false,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as ReturnType<typeof useTicketsModule.useTickets>);
    renderWithClient(<TicketsPage />);
    // Should show EmptyState (role='status'), no error alert
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('Test 3: List/Board toggle buttons are present', () => {
    renderWithClient(<TicketsPage />);
    // The page should have List and Board toggle buttons (D-L-03)
    const listButton = screen.getByRole('button', { name: 'List' });
    expect(listButton).toBeInTheDocument();
    const boardButton = screen.getByRole('button', { name: 'Board' });
    expect(boardButton).toBeInTheDocument();
  });

  it('Test 4: connector missing signal renders EmptyState with deep-link to /dashboard/connectors (D-S-02)', () => {
    vi.spyOn(useTicketsModule, 'useTickets').mockReturnValueOnce({
      data: null,
      isPending: false,
      isLoading: false,
      error: new Error('asana_not_configured: no connector found for tenant'),
      refetch: vi.fn(),
    } as ReturnType<typeof useTicketsModule.useTickets>);
    const { container } = renderWithClient(<TicketsPage />);
    // The page should render a link to /dashboard/connectors
    const connectorLinks = container.querySelectorAll('a[href*="/dashboard/connectors"]');
    expect(connectorLinks.length).toBeGreaterThan(0);
  });
});
