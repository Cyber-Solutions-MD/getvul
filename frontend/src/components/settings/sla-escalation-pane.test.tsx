/**
 * sla-escalation-pane.test.tsx — Phase 36 Plan 06, Task 1.
 *
 * notifications-pane.tsx (this pane's structural analog) has no test file
 * (36-PATTERNS.md) — mirrors saml-pane.test.tsx / ai-usage-pane.test.tsx's
 * api-mock + QueryClientProvider harness for the *test* structure instead.
 *
 * Covers: three-card render, loading/empty/error states, dirty-state ->
 * SaveBar, save-sends-touched-secrets-only (proving the whole-object-replace
 * mask-preservation fix), RBAC (OWNER can edit / ADMIN cannot), and the
 * long-webhook-URL truncate+title overflow behavior.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

let mockRole = 'OWNER';
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ user: { role: mockRole } }),
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

const EMPTY_SETTINGS = {
  sso_enforced: false,
  idp_provider: 'LOCAL',
  domain: 'example.com',
  timezone: 'UTC',
  password_policy: {
    min_length: 8,
    require_uppercase: false,
    require_lowercase: false,
    require_digit: false,
    require_symbol: false,
    history_count: 0,
  },
  syslog_config: null,
  smtp_config: null,
  sla_config: null,
  branding: null,
};

const CONFIGURED_SLA_CONFIG = {
  tier_policy: { critical: 7, high: 30, moderate: 90 },
  approaching_pct: 0.8,
  tier_floor: 'moderate',
  channels: {
    slack: { enabled: true, url: '••••••••' },
    teams: { enabled: false, url: null },
    pagerduty: { enabled: false, routing_key: null },
    email: { enabled: false, to: [] },
  },
  routing: { approaching: ['slack'], breached: ['slack'] },
};

const CONFIGURED_SETTINGS = { ...EMPTY_SETTINGS, sla_config: CONFIGURED_SLA_CONFIG };

describe('SlaEscalationPane', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'OWNER';
  });

  it('renders the three section cards + the data-pane hook once settings load', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    expect(await screen.findByText('SLA policy')).toBeInTheDocument();
    expect(screen.getByText('Escalation channels')).toBeInTheDocument();
    expect(screen.getByText('Escalation floor')).toBeInTheDocument();
    expect(document.querySelector('[data-pane="sla-escalation"]')).not.toBeNull();
  });

  it('loading state renders the SkeletonTable (no cards yet)', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockImplementation(() => new Promise(() => {}));

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText('SLA policy')).toBeNull();
  });

  it('error state renders the PartialFailureBanner', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockRejectedValue(
      Object.assign(new Error('boom'), { code: 500, requestId: 'req_test' }),
    );

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByRole('alert', undefined, { timeout: 4000 });
  });

  it('renders "No escalation channels configured" when zero channels are enabled', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    expect(await screen.findByText('No escalation channels configured')).toBeInTheDocument();
  });

  it('does NOT render the empty state once a channel is enabled', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    expect(screen.queryByText('No escalation channels configured')).toBeNull();
  });

  it('editing a field enables the SaveBar (dirty state) for an OWNER', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    expect(document.querySelector('[data-save-bar]')).toBeNull();

    fireEvent.change(screen.getByLabelText('Critical'), { target: { value: '5' } });
    expect(document.querySelector('[data-save-bar]')).not.toBeNull();
  });

  it('save sends only the touched secret; an untouched previously-configured secret round-trips as the mask (never blank/omitted)', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(CONFIGURED_SETTINGS); // GET
    mockApi.mockResolvedValueOnce({ message: 'ok' }); // PATCH

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    // Dirty the pane via an UNRELATED field — never touching Slack's secret.
    fireEvent.change(screen.getByLabelText('Escalate at'), { target: { value: 'critical' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      const patchCall = mockApi.mock.calls.find(
        (call) => (call[1] as RequestInit | undefined)?.method === 'PATCH',
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse((patchCall as [string, RequestInit])[1].body as string);
      expect(body.sla_config.channels.slack.url).toBe('••••••••');
      expect(body.sla_config.channels.slack.enabled).toBe(true);
      expect(body.sla_config.tier_floor).toBe('critical');
    });
  });

  it('save sends the real value for a TOUCHED secret field', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(CONFIGURED_SETTINGS);
    mockApi.mockResolvedValueOnce({ message: 'ok' });

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    fireEvent.change(screen.getByLabelText('Webhook URL'), {
      target: { value: 'https://hooks.slack.com/services/NEW' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      const patchCall = mockApi.mock.calls.find(
        (call) => (call[1] as RequestInit | undefined)?.method === 'PATCH',
      );
      const body = JSON.parse((patchCall as [string, RequestInit])[1].body as string);
      expect(body.sla_config.channels.slack.url).toBe('https://hooks.slack.com/services/NEW');
    });
  });

  it('RBAC: a non-OWNER (ADMIN) sees every control disabled', async () => {
    mockRole = 'ADMIN';
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    expect(screen.getByLabelText('Critical')).toBeDisabled();
    expect(screen.getByLabelText('Escalate at')).toBeDisabled();
    expect(screen.getByRole('switch', { name: 'Enable Slack' })).toBeDisabled();
  });

  it('OWNER role leaves controls enabled', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    expect(screen.getByLabelText('Critical')).not.toBeDisabled();
  });

  it('a long Slack webhook URL value truncates (text-ellipsis overflow-hidden) with a title attr showing the full value', async () => {
    const longUrl = 'https://hooks.slack.com/services/' + 'T'.repeat(120);
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    const urlInput = screen.getByLabelText('Webhook URL') as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: longUrl } });

    expect(urlInput.className).toMatch(/truncate/);
    expect(urlInput.title).toBe(longUrl);
  });

  it('shows the mandatory PagerDuty manual-resolution copy (D-13) and Teams Workflows setup copy (D-15)', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { SlaEscalationPane } = await import('./sla-escalation-pane');
    render(React.createElement(Wrapper, null, React.createElement(SlaEscalationPane)));

    await screen.findByText('SLA policy');
    expect(screen.getByText(/manual resolution/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('switch', { name: 'Enable Microsoft Teams' }));
    expect(screen.getByText(/Workflows/i)).toBeInTheDocument();
  });
});
