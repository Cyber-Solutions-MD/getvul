/**
 * ai-usage-pane.test.tsx — AIE-04 admin pane coverage (Plan 28-04, Task 2).
 *
 * Covers every 28-UI-SPEC.md state: breaker-tripped banner (anchor +
 * conditional), no-cap (no meter bar), the 6-fixed-row table + the
 * ticket-draft backstop (no fabricated 7th row), zero-usage (cards still
 * render, not an empty screen), no-key (whole-pane replacement), and error
 * (PartialFailureBanner). Mirrors audit-log-pane.test.tsx's
 * QueryClientProvider + vi.mock('@/lib/api') pattern.
 *
 * No useAuth mock needed — AiUsagePane performs zero role checks of its own
 * (RBAC is sidebar-hide + backend require_admin only, T-14-04/T-14-16).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { AiUsageResult } from '@/lib/queries/use-ai-usage';

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = makeClient();
  return React.createElement(QueryClientProvider, { client }, children);
}

const BASE_USAGE: AiUsageResult = {
  configured: true,
  model: 'claude-sonnet-5',
  monthly_budget_usd: 100,
  spent_this_month_usd: 42.5,
  breaker_tripped: false,
  capability_breakdown: [
    { resource_type: 'vuln', is_batch: null, calls: 10, cost_usd: 5.0, tokens: 12000 },
    { resource_type: 'host', is_batch: null, calls: 3, cost_usd: 1.5, tokens: 3000 },
    { resource_type: 'remediation', is_batch: null, calls: 2, cost_usd: 1.0, tokens: 2000 },
    { resource_type: 'remediation-guidance', is_batch: null, calls: 5, cost_usd: 2.5, tokens: 5000 },
    { resource_type: 'prioritization', is_batch: false, calls: 4, cost_usd: 2.0, tokens: 4000 },
    { resource_type: 'prioritization', is_batch: true, calls: 20, cost_usd: 30.5, tokens: 40000 },
  ],
  degraded_calls_count: 0,
};

const LOCKED_ROW_LABELS = [
  'Explain — vulnerability',
  'Explain — host posture',
  'Explain — remediation impact',
  'Remediation guidance',
  'Prioritization — on demand',
  'Prioritization — batch',
];

describe('AiUsagePane', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders exactly 6 fixed capability rows with the locked labels (ticket-draft backstop: no 7th row)', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(BASE_USAGE);

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('Explain — vulnerability');
    for (const label of LOCKED_ROW_LABELS) {
      expect(screen.getByText(label)).toBeDefined();
    }
    const rows = document.querySelectorAll('tbody tr');
    expect(rows.length).toBe(6);
    // Backstop: no fabricated "ticket-draft" row / resource_type anywhere.
    expect(screen.queryByText(/ticket-draft/i)).toBeNull();
  });

  it('renders the breaker-tripped banner as the anchor, above the rest of the pane, when breaker_tripped', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({
      ...BASE_USAGE,
      breaker_tripped: true,
      spent_this_month_usd: 100,
    });

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('AI paused — budget exceeded');
    const pane = document.querySelector('[data-pane="ai"]');
    expect(pane).not.toBeNull();
    // The banner is the first child — the pane's primary visual anchor while tripped.
    expect(pane?.firstElementChild?.textContent).toContain('AI paused — budget exceeded');
    const link = screen.getByRole('link', { name: 'Raise the cap' });
    expect(link.getAttribute('href')).toBe('/dashboard/connectors');
  });

  it('does not render the breaker-tripped banner when breaker_tripped is false', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(BASE_USAGE);

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('Explain — vulnerability');
    expect(screen.queryByText('AI paused — budget exceeded')).toBeNull();
  });

  it('renders no meter bar + the no-cap caption when monthly_budget_usd is null', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({ ...BASE_USAGE, monthly_budget_usd: null });

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText(/No monthly cap set/i);
    expect(screen.queryByRole('progressbar')).toBeNull();
  });

  it('renders a progress meter when a cap is set', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(BASE_USAGE);

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('Explain — vulnerability');
    expect(screen.getByRole('progressbar')).toBeDefined();
  });

  it('renders all-zero rows (not an empty screen) when usage is zero for the month', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({
      ...BASE_USAGE,
      spent_this_month_usd: 0,
      capability_breakdown: BASE_USAGE.capability_breakdown.map((row) => ({
        ...row,
        calls: 0,
        cost_usd: 0,
        tokens: 0,
      })),
      degraded_calls_count: 0,
    });

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('No AI usage yet');
    // The 6 rows are still present — never replaced by an empty-state card.
    expect(screen.getByText('Explain — vulnerability')).toBeDefined();
    expect(document.querySelectorAll('tbody tr').length).toBe(6);
    expect(screen.getAllByText('$0.00').length).toBeGreaterThan(0);
  });

  it("shows the \"AI isn't set up yet\" card when no key is configured", async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce({ ...BASE_USAGE, configured: false });

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText("AI isn't set up yet");
    const link = screen.getByRole('link', { name: 'Configure AI' });
    expect(link.getAttribute('href')).toBe('/dashboard/connectors');
    // No capability table renders in this state — whole pane replaced.
    expect(screen.queryByText('Explain — vulnerability')).toBeNull();
  });

  it('renders PartialFailureBanner on a query error', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    // useAiUsage() hardcodes retry:1 — reject every attempt (initial + retry).
    mockApi.mockRejectedValue(Object.assign(new Error('boom'), { code: 500, requestId: 'req_test' }));

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByRole('alert', undefined, { timeout: 4000 });
  });

  it('shows the model as its enum label, never the raw model id', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(BASE_USAGE);

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('Sonnet 5');
    expect(screen.queryByText(BASE_USAGE.model)).toBeNull();
  });

  it('every Stat renders with delta={0} — no stray "Δ —" placeholder', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(BASE_USAGE);

    const { AiUsagePane } = await import('./ai-usage-pane');
    render(React.createElement(Wrapper, null, React.createElement(AiUsagePane)));

    await screen.findByText('Explain — vulnerability');
    expect(screen.queryByText('Δ —')).toBeNull();
  });
});
