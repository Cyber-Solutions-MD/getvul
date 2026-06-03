/**
 * TDD RED — settings/page.tsx
 * Tests for the Settings page composition.
 *
 * Plan 14-05, Task 3 (Behaviors 1-5).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Mocks ─────────────────────────────────────────────────────────────────────

// Mock Next.js navigation
let mockCategoryParam = 'profile';
vi.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: (key: string) => key === 'category' ? mockCategoryParam : null,
    toString: () => `category=${mockCategoryParam}`,
  }),
  usePathname: () => '/dashboard/settings',
  useRouter: () => ({
    replace: vi.fn(),
  }),
}));

// Viewer role mock (will be overridden per test)
let mockRole = 'ADMIN';
vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 'admin@example.com',
      display_name: 'Admin User',
      role: mockRole,
      tenant_id: 't1',
      tenant_name: 'Acme Corp',
    },
  }),
}));

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

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

// ── Test 1: Page renders SettingsSidebarShell with 6 categories for ADMIN ─────
describe('Settings page — ADMIN role', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'ADMIN';
    mockCategoryParam = 'profile';
  });

  it('renders SettingsSidebarShell and shows all 6 categories for Admin role', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // useTenantUsers call for ProfilePane
    mockApiTyped.mockResolvedValue([]);

    const SettingsPage = (await import('./page')).default;
    render(React.createElement(Wrapper, null, React.createElement(SettingsPage)));

    // SettingsSidebarShell renders category nav buttons
    const nav = document.querySelector('nav[aria-label="Settings categories"]');
    expect(nav).not.toBeNull();
    // All 6 category buttons should exist in the nav
    const navButtons = nav?.querySelectorAll('button');
    const buttonLabels = Array.from(navButtons ?? []).map(b => b.textContent?.trim());
    expect(buttonLabels).toContain('Profile');
    expect(buttonLabels).toContain('Workspace');
    expect(buttonLabels).toContain('SAML & OIDC');
    expect(buttonLabels).toContain('Notifications');
    expect(buttonLabels).toContain('API tokens');
    expect(buttonLabels).toContain('Audit log');
  });
});

// ── Test 2: Active category driven by ?category= URL param ────────────────────
describe('Settings page — URL category routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'ADMIN';
    mockCategoryParam = 'api-tokens';
  });

  it('renders the matching pane for ?category=api-tokens', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValue([]);

    const SettingsPage = (await import('./page')).default;
    render(React.createElement(Wrapper, null, React.createElement(SettingsPage)));

    // ApiTokensPane should render for ?category=api-tokens
    expect(screen.getByText(/coming soon/i)).toBeDefined();
  });
});

// ── Test 3: Unsaved-changes guard fires on dirty category switch ────────────────
describe('Settings page — unsaved-changes guard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'OWNER';
    mockCategoryParam = 'saml';
  });

  it('shows ConfirmModal when switching category while pane is dirty', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValue({
      sso_enforced: false,
      idp_provider: 'GOOGLE',
      domain: 'example.com',
      timezone: 'UTC',
      password_policy: { min_length: 8, require_uppercase: false, require_lowercase: false, require_digit: false, require_symbol: false, history_count: 0 },
      syslog_config: null,
      smtp_config: null,
      sla_config: null,
      branding: null,
    });

    const SettingsPage = (await import('./page')).default;
    render(React.createElement(Wrapper, null, React.createElement(SettingsPage)));

    // Wait for SAML pane to load and settings to hydrate (GOOGLE should be active)
    await waitFor(() => {
      const googleBtn = screen.queryByRole('button', { name: /Google Workspace/i });
      expect(googleBtn?.getAttribute('aria-pressed')).toBe('true');
    });

    // Click Local to make the pane dirty — SaveBar should appear
    const localBtn = screen.getByRole('button', { name: /Local/i });
    fireEvent.click(localBtn);

    // Wait for SaveBar to appear (dirty state is confirmed)
    await waitFor(() => {
      expect(document.querySelector('[data-save-bar]')).not.toBeNull();
    });

    // Now click Profile category — should trigger unsaved guard since paneDirty
    // (PaneWithDirtyBridge.checkDirty fires on click and sees the SaveBar)
    const profileBtn = Array.from(
      document.querySelectorAll('nav[aria-label="Settings categories"] button')
    ).find(b => b.textContent?.trim() === 'Profile') as HTMLButtonElement | undefined;
    if (profileBtn) {
      fireEvent.click(profileBtn);
    }

    // ConfirmModal should appear with unsaved changes content
    // (title "Unsaved changes" + message text — both match the regex)
    await waitFor(() => {
      const guardTexts = screen.queryAllByText(/unsaved changes|discard/i);
      expect(guardTexts.length).toBeGreaterThan(0);
    });
  });
});

// ── Test 4: VIEWER role sees only Profile + API tokens ────────────────────────
describe('Settings page — VIEWER role', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'VIEWER';
    mockCategoryParam = 'profile';
  });

  it('VIEWER sees only Profile and API tokens categories', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValue([]);

    const SettingsPage = (await import('./page')).default;
    render(React.createElement(Wrapper, null, React.createElement(SettingsPage)));

    // Check sidebar nav buttons — VIEWER sees only Profile + API tokens
    const nav = document.querySelector('nav[aria-label="Settings categories"]');
    expect(nav).not.toBeNull();
    const navButtons = nav?.querySelectorAll('button');
    const buttonLabels = Array.from(navButtons ?? []).map(b => b.textContent?.trim());

    // Profile and API tokens always visible
    expect(buttonLabels).toContain('Profile');
    expect(buttonLabels).toContain('API tokens');

    // Admin-only categories should NOT be in the sidebar nav
    expect(buttonLabels).not.toContain('Workspace');
    expect(buttonLabels).not.toContain('SAML & OIDC');
    expect(buttonLabels).not.toContain('Notifications');
    expect(buttonLabels).not.toContain('Audit log');
  });
});

// ── Test 5: No horizontal-tab patterns (grep gate — verified separately) ─────
// The grep gate is verified in the <verify> block; this test checks SettingsSidebarShell
// is present in the page.
describe('Settings page — SC-4 SettingsSidebarShell gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRole = 'ADMIN';
    mockCategoryParam = 'profile';
  });

  it('renders page with SettingsSidebarShell (nav + settings categories)', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValue([]);

    const SettingsPage = (await import('./page')).default;
    render(React.createElement(Wrapper, null, React.createElement(SettingsPage)));

    // The settings sidebar nav should be present
    const nav = document.querySelector('nav[aria-label="Settings categories"]');
    expect(nav).not.toBeNull();
  });
});
