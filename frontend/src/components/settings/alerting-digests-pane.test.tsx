/**
 * alerting-digests-pane.test.tsx — Phase 40 Plan 01 (ALERT-03), Task 3 Wave 0
 * RED scaffold.
 *
 * Clones the sla-escalation-pane.test.tsx harness (api/auth/toast mocks +
 * QueryClientProvider wrapper) for the not-yet-built AlertingDigestsPane
 * (Plan 05). `./alerting-digests-pane` is imported via the `importPane()`
 * helper below (a runtime-computed, non-literal dynamic import specifier)
 * rather than a literal `await import('./alerting-digests-pane')` inline --
 * Vite's import-analysis plugin statically resolves a literal specifier (a
 * `@vite-ignore` comment on a literal is NOT sufficient, verified
 * empirically) at TRANSFORM time even inside an async test body, so a
 * missing target would fail this file's whole collection, not just one
 * test. With a computed specifier, this file collects every named test
 * below before the component exists; each test then fails individually
 * (module-not-found) until Plan 05 lands.
 *
 * Covers exactly the four things Task 3 calls out: the data-pane render
 * hook, the three digest section headings, the OWNER RBAC gate, and the
 * no-channels-configured EmptyState. Full pane behavior (save/dirty-state/
 * per-field validation) is Plan 05's own test-authoring responsibility, not
 * this scaffold's — see 40-01-PLAN.md <artifacts_produced> for the Plan 05
 * inventory (alerting-digests-pane.tsx, microcopy.ts 'alerting' category,
 * settings-sidebar-shell.tsx wiring, page.tsx case 'alerting').
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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

    await screen.findByText(/./); // let the initial data load settle before probing headings
    expect(document.querySelector('[data-pane="alerting-digests"]')).not.toBeNull();
    // D-13 detection + recipients + routing — the three section headings
    // Plan 05 renders; exact copy is Plan 05's call (copy-voice.md), so this
    // scaffold matches loosely rather than pinning unverified strings.
    expect(screen.getByText(/detection|kev|epss/i)).toBeInTheDocument();
    expect(screen.getByText(/digest|cadence|recipient/i)).toBeInTheDocument();
    expect(screen.getByText(/channel|routing/i)).toBeInTheDocument();
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
});
