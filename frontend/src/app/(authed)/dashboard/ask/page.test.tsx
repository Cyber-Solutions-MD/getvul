/**
 * page.test.tsx -- TDD tests for the /dashboard/ask page (44-04-PLAN.md
 * Task 1 acceptance criteria).
 *
 * Mirrors the co-located page.test.tsx convention (campaigns/page.test.tsx
 * analog). Mocks useAiStatus + useQueryStream so every branch is driven
 * directly, without a real SSE stream.
 *
 * Test 1: configured:false renders the Configure-AI DegradedCard + CTA.
 * Test 2: configured:true + idle phase renders the 4 starter chips.
 * Test 3: refuse phase renders "Can't answer that one".
 * Test 4: a rendered answer's "Open in {entity}" href equals buildNlqDeepLink's output.
 * Test 5: budget_exceeded renders the amber card; grounded_false renders danger;
 *         busy/unknown renders the transient error banner with Retry now.
 * Test 6: zero-results renders "Nothing matches that" with the interpretation still shown.
 */
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  usePathname: () => '/dashboard/ask',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/hooks/use-document-title', () => ({
  useDocumentTitle: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ user: { role: 'ADMIN', id: 'u1' }, loading: false }),
}));

import * as useAiStatusModule from '@/lib/queries/use-ai-status';
import * as useQueryStreamModule from '@/lib/ai/use-query-stream';
import { buildNlqDeepLink } from '@/lib/ai/nlq-deep-link';
import AskPage from './page';

function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function mockAiStatus(configured: boolean, overrides: Record<string, unknown> = {}) {
  vi.spyOn(useAiStatusModule, 'useAiStatus').mockReturnValue({
    data: { configured },
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useAiStatusModule.useAiStatus>);
}

function mockQueryStream(state: useQueryStreamModule.QueryStreamState) {
  vi.spyOn(useQueryStreamModule, 'useQueryStream').mockReturnValue({
    state,
    start: vi.fn(),
  });
}

const mockRows = [
  {
    id: 'v1',
    cve_id: 'CVE-2024-1234',
    severity: 'CRITICAL',
    status: 'OPEN',
    source: 'tenable',
    sla_due_at: null,
  },
];
const mockFilter = { severity: ['CRITICAL'], cisa_kev: true };

describe('/dashboard/ask page', () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockQueryStream({ phase: 'idle' });
  });

  it('Test 1: configured:false renders the Configure-AI DegradedCard + CTA', () => {
    mockAiStatus(false);
    renderWithClient(<AskPage />);
    expect(screen.getByText("AI isn't set up yet")).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Configure AI' })).toHaveAttribute(
      'href',
      '/dashboard/connectors',
    );
  });

  it('Test 2: configured:true + idle phase renders the 4 starter chips', () => {
    mockAiStatus(true);
    mockQueryStream({ phase: 'idle' });
    renderWithClient(<AskPage />);
    expect(
      screen.getByText('Ask a question about your vulnerabilities, assets, or tickets'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: 'Which internet-facing hosts have an unremediated KEV older than 30 days?',
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show critical vulns breaching SLA' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open tickets for asset prod-db-01' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: 'Vulnerabilities on internet-facing assets with an active exploit',
      }),
    ).toBeInTheDocument();
  });

  it('Test 3: refuse phase renders "Can\'t answer that one"', () => {
    mockAiStatus(true);
    mockQueryStream({ phase: 'refuse' });
    renderWithClient(<AskPage />);
    expect(screen.getByText("Can't answer that one")).toBeInTheDocument();
  });

  it('Test 4: a rendered answer\'s "Open in {entity}" href equals buildNlqDeepLink output', () => {
    mockAiStatus(true);
    mockQueryStream({
      phase: 'done',
      entity: 'vulnerabilities',
      filter: mockFilter,
      rows: mockRows,
      total: 1,
      answer: { summary: 'S', business_risk: 'B', citations: [], grounded: true },
    });
    renderWithClient(<AskPage />);
    const link = screen.getByRole('link', { name: 'Open in Vulnerabilities' });
    expect(link).toHaveAttribute('href', buildNlqDeepLink('vulnerabilities', mockFilter));
  });

  it('Test 5a: budget_exceeded renders the amber "budget is used up" card', () => {
    mockAiStatus(true);
    mockQueryStream({ phase: 'error', kind: 'budget_exceeded' });
    renderWithClient(<AskPage />);
    expect(screen.getByText("This tenant's monthly AI budget is used up")).toBeInTheDocument();
  });

  it('Test 5b: grounded_false renders the danger "withheld" card', () => {
    mockAiStatus(true);
    mockQueryStream({ phase: 'error', kind: 'grounded_false' });
    renderWithClient(<AskPage />);
    expect(screen.getByText('This answer was withheld')).toBeInTheDocument();
  });

  it('Test 5c: busy/unknown renders the transient error banner with Retry now, question retained', () => {
    mockAiStatus(true);
    mockQueryStream({ phase: 'error', kind: 'unknown', httpStatus: 500, requestId: 'req-123' });
    renderWithClient(<AskPage />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry now/i })).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
    expect(screen.getByText(/req-123/)).toBeInTheDocument();
  });

  it('Test 6: zero-results renders "Nothing matches that" with the interpretation still shown', () => {
    mockAiStatus(true);
    mockQueryStream({
      phase: 'results',
      entity: 'tickets',
      filter: { status: 'OPEN' },
      rows: [],
      total: 0,
    });
    renderWithClient(<AskPage />);
    expect(screen.getByText('Nothing matches that')).toBeInTheDocument();
    expect(screen.getByText('Interpreted as:')).toBeInTheDocument();
  });
});
