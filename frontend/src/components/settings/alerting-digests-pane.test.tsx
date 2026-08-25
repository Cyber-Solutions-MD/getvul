/**
 * alerting-digests-pane.test.tsx — Phase 40 Plan 05 (ALERT-03), Task 1.
 *
 * Started as the Plan 01 Wave 0 RED scaffold (data-pane render hook, three
 * section headings, OWNER RBAC gate, no-channels-configured EmptyState);
 * this plan graduates it to full assertions: save calls mutateAsync with
 * an `alerting_config` key, and the "Send test digest" empty-branch (E1
 * backstop) renders the fixed inline message.
 *
 * Clones the sla-escalation-pane.test.tsx harness (api/auth/toast mocks +
 * QueryClientProvider wrapper). `./alerting-digests-pane` is imported via
 * the `importPane()` helper below (a runtime-computed, non-literal dynamic
 * import specifier) rather than a literal `await import('./alerting-digests-pane')`
 * inline -- Vite's import-analysis plugin statically resolves a literal
 * specifier (a `@vite-ignore` comment on a literal is NOT sufficient,
 * verified empirically) at TRANSFORM time even inside an async test body,
 * so a missing target would fail this file's whole collection, not just
 * one test. Kept as-is now that the component exists (harmless, and avoids
 * re-verifying the empirical Vite finding).
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

// Vite's import-analysis plugin statically resolves a literal
// `await import('./x')` specifier at TRANSFORM time -- unlike Python's
// import machinery (which the backend Wave 0 scaffolds rely on deferring to
// RUN time), a missing target here fails the WHOLE FILE's collection, not
// just one test. A `@vite-ignore`-commented literal is NOT sufficient in
// this vitest SSR module runner (verified empirically -- it still eagerly
// resolves at transform time); the specifier must be a genuinely
// non-literal, runtime-computed string so the plugin's static-literal
// detection cannot see a resolvable path at all. This lets the file still
// collect every named test below before the component exists; each test
// then fails individually (module-not-found) until Plan 05 lands.
const PANE_MODULE_SEGMENTS = ['.', 'alerting-digests-pane'];
async function importPane() {
  return import(PANE_MODULE_SEGMENTS.join('/'));
}

// Envelope shape mirrors the existing GET /api/v1/tenant/settings response
// (sla-escalation-pane.test.tsx's EMPTY_SETTINGS) plus the new
// `alerting_config` key (null until Plan 04 ships persistence).
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
  alerting_config: null,
};

// Channel shape mirrors sla_config.channels (D-19 — alerting reuses these
// same tenant channel credentials; alerting_config itself never holds a
// secret).
const CONFIGURED_SLA_CONFIG = {
  channels: {
    slack: { enabled: true, url: '••••••••' },
    teams: { enabled: false, url: null },
    pagerduty: { enabled: false, routing_key: null },
    email: { enabled: false, to: [] },
  },
};

// Mirrors DEFAULT_ALERTING_CONFIG (backend/app/notifications/alerting_config.py).
const CONFIGURED_ALERTING_CONFIG = {
  kev_enabled: true,
  epss_threshold: 0.5,
  cadence: 'daily',
  send_hour: 8,
  per_owner_digests: true,
  per_team_digests: true,
  routing: { new_kev_epss: ['slack'], digest_owner: ['email'], digest_team: ['slack'] },
};

const CONFIGURED_SETTINGS = {
  ...EMPTY_SETTINGS,
  sla_config: CONFIGURED_SLA_CONFIG,
  alerting_config: CONFIGURED_ALERTING_CONFIG,
};

// Matches the pane's `COPY.kevToggleLabel` verbatim (40-UI-SPEC.md
// Copywriting Contract) — kept as a local const so a future copy edit only
// needs to change one string here, not every assertion site.
const COPY_KEV_LABEL = 'Alert on new CISA KEV listings';

describe('AlertingDigestsPane', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'OWNER';
  });

  it('renders the data-pane hook + the three digest section headings once settings load', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    // Let the initial data load settle before probing headings. (The Plan 01
    // scaffold used `findByText(/./)`, which throws once the pane renders
    // more than one text node — fixed here to wait on a specific heading.)
    await screen.findByText('New exposure alerts');
    expect(document.querySelector('[data-pane="alerting-digests"]')).not.toBeNull();
    // The three section headings Plan 05 renders (40-UI-SPEC.md Copywriting
    // Contract — exact copy, now pinned since the pane exists).
    expect(screen.getByRole('heading', { name: 'New exposure alerts' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Scheduled digests' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Delivery channels' })).toBeInTheDocument();
  });

  it('renders the no-channels-configured EmptyState when sla_config has no enabled channel', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(EMPTY_SETTINGS);

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    expect(await screen.findByText(/no.*channels configured/i)).toBeInTheDocument();
  });

  it('RBAC: a non-OWNER (ADMIN) sees every control disabled', async () => {
    mockRole = 'ADMIN';
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    const switches = await screen.findAllByRole('switch');
    expect(switches.length).toBeGreaterThan(0);
    switches.forEach((el) => expect(el).toBeDisabled());
  });

  it('OWNER role leaves controls enabled', async () => {
    const { api } = await import('@/lib/api');
    vi.mocked(api).mockResolvedValueOnce(CONFIGURED_SETTINGS);

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    const switches = await screen.findAllByRole('switch');
    expect(switches.length).toBeGreaterThan(0);
    switches.forEach((el) => expect(el).not.toBeDisabled());
  });

  it('save calls mutateAsync (PATCH) with an alerting_config key reflecting the edit', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(CONFIGURED_SETTINGS); // GET
    mockApi.mockResolvedValueOnce({ message: 'ok' }); // PATCH

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    await screen.findByText('New exposure alerts');
    // Dirty the pane by toggling KEV off (was true in CONFIGURED_ALERTING_CONFIG).
    fireEvent.click(screen.getByRole('switch', { name: COPY_KEV_LABEL }));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      const patchCall = mockApi.mock.calls.find(
        (call) => (call[1] as RequestInit | undefined)?.method === 'PATCH',
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse((patchCall as [string, RequestInit])[1].body as string);
      expect(body.alerting_config).toBeDefined();
      expect(body.alerting_config.kev_enabled).toBe(false);
      expect(body.alerting_config.cadence).toBe('daily');
      expect(body.alerting_config.routing).toEqual(CONFIGURED_ALERTING_CONFIG.routing);
    });
  });

  it('"Send test digest" empty-branch renders the fixed E1 inline message (not a false-positive error)', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(CONFIGURED_SETTINGS); // GET
    mockApi.mockResolvedValueOnce({ status: 'empty' }); // POST /settings/alerting/test-digest

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    await screen.findByText('New exposure alerts');
    fireEvent.click(screen.getByRole('button', { name: 'Send test digest' }));

    expect(
      await screen.findByText(/nothing to send right now/i),
    ).toBeInTheDocument();

    const postCall = mockApi.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === 'POST',
    );
    expect(postCall?.[0]).toBe('/api/v1/tenant/settings/alerting/test-digest');
  });

  it('"Send test digest" error-branch renders the fixed UI-SPEC error copy', async () => {
    const { api } = await import('@/lib/api');
    const mockApi = vi.mocked(api);
    mockApi.mockResolvedValueOnce(CONFIGURED_SETTINGS); // GET
    mockApi.mockResolvedValueOnce({ status: 'error', error: 'SMTP is not configured for this tenant' }); // POST

    const { AlertingDigestsPane } = await importPane();
    render(React.createElement(Wrapper, null, React.createElement(AlertingDigestsPane)));

    await screen.findByText('New exposure alerts');
    fireEvent.click(screen.getByRole('button', { name: 'Send test digest' }));

    expect(
      await screen.findByText(/test digest couldn't be sent/i),
    ).toBeInTheDocument();
  });
});
