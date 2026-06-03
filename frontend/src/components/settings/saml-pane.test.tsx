/**
 * TDD RED — saml-pane.tsx
 * Tests for SamlPane component.
 *
 * Plan 14-05, Task 1 (Behaviors 4-5).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Mocks ─────────────────────────────────────────────────────────────────────
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 'admin@example.com',
      display_name: 'Admin User',
      role: 'OWNER',
      tenant_id: 't1',
      tenant_name: 'Acme Corp',
    },
  }),
}));

const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

const mockSettings = {
  sso_enforced: false,
  idp_provider: 'LOCAL',
  domain: 'example.com',
  timezone: 'UTC',
  password_policy: { min_length: 8, require_uppercase: false, require_lowercase: false, require_digit: false, require_symbol: false, history_count: 0 },
  syslog_config: null,
  smtp_config: null,
  sla_config: null,
  branding: null,
};

// ── Helper ────────────────────────────────────────────────────────────────────
function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = makeClient();
  return React.createElement(QueryClientProvider, { client }, children);
}

// ── Test 4: Enforce SSO toggle disabled when idp_provider==='LOCAL' ──────────
describe('SamlPane - Enforce SSO disabled for LOCAL provider', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('disables the Enforce SSO toggle when idp_provider is LOCAL and shows explainer', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce({ ...mockSettings, idp_provider: 'LOCAL' });

    const { SamlPane } = await import('./saml-pane');
    render(React.createElement(Wrapper, null, React.createElement(SamlPane)));

    // Wait for the pane to load settings — use getAllByText since heading and toggle label both say "Enforce SSO"
    await screen.findAllByText(/Enforce SSO/i);

    // The Enforce SSO toggle button should be disabled (data-field="sso_enforced")
    const enforceButton = screen.getByRole('switch', { name: /Enforce SSO/i });
    expect(enforceButton).toHaveProperty('disabled', true);

    // Inline explainer should be visible
    expect(screen.getByText(/non-local|non-LOCAL|before enforcing/i)).toBeDefined();
  });
});

// ── Test 5: Choosing LOCAL forces sso_enforced=false in local state ───────────
describe('SamlPane - LOCAL forces sso_enforced off', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('forces sso_enforced to false in local state when user selects LOCAL provider', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // Start with GOOGLE provider and sso_enforced=true
    mockApiTyped.mockResolvedValueOnce({
      ...mockSettings,
      idp_provider: 'GOOGLE',
      sso_enforced: true,
    });

    const { SamlPane } = await import('./saml-pane');
    render(React.createElement(Wrapper, null, React.createElement(SamlPane)));

    // Wait for pane to load AND for settings to hydrate (GOOGLE provider button should be active)
    await waitFor(() => {
      const googleBtn = screen.queryByRole('button', { name: /Google Workspace/i });
      expect(googleBtn?.getAttribute('aria-pressed')).toBe('true');
    });

    // Click LOCAL provider button
    const localButton = screen.getByRole('button', { name: /Local/i });
    fireEvent.click(localButton);

    // After selecting LOCAL from GOOGLE, the warning about SSO enforcement being disabled should appear
    await waitFor(() => {
      const warnText = screen.queryByText(/turns SSO enforcement off|local sign-in/i);
      expect(warnText).not.toBeNull();
    });
  });
});
