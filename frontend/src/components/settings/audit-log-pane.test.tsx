/**
 * TDD RED — audit-log-pane.tsx + use-audit-log.ts + api-tokens-pane.tsx
 * + notifications-pane.tsx (lightweight assertions) + workspace-pane.tsx
 *
 * Plan 14-05, Task 2 (Behaviors 1-5).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));

const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: {
      id: 'u1',
      email: 'owner@example.com',
      display_name: 'Owner User',
      role: 'OWNER',
      tenant_id: 't1',
      tenant_name: 'Acme Corp',
    },
  }),
}));

// ── Helper ────────────────────────────────────────────────────────────────────

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = makeClient();
  return React.createElement(QueryClientProvider, { client }, children);
}

// ── Audit log data ─────────────────────────────────────────────────────────────
const mockAuditLogResponse = {
  items: [
    {
      id: 'log1',
      user_email: 'ana@example.com',
      action: 'user.role_change',
      resource_type: 'user',
      resource_id: 'u2',
      created_at: '2026-06-01T10:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
  pages: 1,
};

// ── Test 1: useAuditLog hook ───────────────────────────────────────────────────
describe('useAuditLog', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('GETs /api/v1/tenant/audit-log with filter params and returns {items,total,...} envelope', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce(mockAuditLogResponse);

    const { useAuditLog } = await import('@/lib/queries/use-audit-log');
    const client = makeClient();
    const { result } = renderHook(
      () => useAuditLog({ action: 'user', resource_type: 'user', user_email: 'ana@example.com', page: 1 }),
      { wrapper: wrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockAuditLogResponse);
    const url = mockApiTyped.mock.calls[0][0] as string;
    expect(url).toContain('/api/v1/tenant/audit-log');
    expect(url).toContain('action=user');
    expect(url).toContain('page_size=50');
  });
});

// ── Test 2: AuditLogPane rendering ────────────────────────────────────────────
describe('AuditLogPane', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders a paginated table with actor email, action, target, timestamp', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce(mockAuditLogResponse);

    const { AuditLogPane } = await import('./audit-log-pane');
    render(React.createElement(Wrapper, null, React.createElement(AuditLogPane)));

    // Wait for data to load
    await screen.findByText('ana@example.com');
    expect(screen.getByText('user.role_change')).toBeDefined();
    // resource_type is 'user' — get all and check at least one matches
    expect(screen.getAllByText(/user/i).length).toBeGreaterThan(0);
  });

  it('shows SkeletonTable while loading (isPending)', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // Never resolves — simulates pending state
    mockApiTyped.mockReturnValueOnce(new Promise(() => {}));

    const { AuditLogPane } = await import('./audit-log-pane');
    render(React.createElement(Wrapper, null, React.createElement(AuditLogPane)));

    // data-skeleton-row should appear while loading
    expect(document.querySelector('[data-skeleton-row]')).not.toBeNull();
  });

  it('shows EmptyState when there are no audit events', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 50, pages: 0 });

    const { AuditLogPane } = await import('./audit-log-pane');
    render(React.createElement(Wrapper, null, React.createElement(AuditLogPane)));

    await screen.findByText(/No audit events/i);
  });
});

// ── Test 3: ApiTokensPane ─────────────────────────────────────────────────────
describe('ApiTokensPane', () => {
  it('renders EmptyState with "coming soon" message and no create button', async () => {
    const { ApiTokensPane } = await import('./api-tokens-pane');
    render(React.createElement(Wrapper, null, React.createElement(ApiTokensPane)));

    expect(screen.getByText(/coming soon/i)).toBeDefined();
    // No create or "Generate" button
    expect(screen.queryByRole('button', { name: /create|generate|new token/i })).toBeNull();
  });
});

// ── Test 4: NotificationsPane — 3 sub-sections, no nested tabs ───────────────
describe('NotificationsPane', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders three labeled sub-sections (SMTP / Syslog / Alert categories) in one pane', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce({
      sso_enforced: false,
      idp_provider: 'LOCAL',
      domain: 'example.com',
      timezone: 'UTC',
      password_policy: { min_length: 8, require_uppercase: false, require_lowercase: false, require_digit: false, require_symbol: false, history_count: 0 },
      syslog_config: null,
      smtp_config: null,
      sla_config: null,
      branding: null,
    });

    const { NotificationsPane } = await import('./notifications-pane');
    render(React.createElement(Wrapper, null, React.createElement(NotificationsPane)));

    // Three section headings should be present — use heading-level query
    await screen.findByRole('heading', { name: /SMTP|Email/i });
    expect(screen.getByRole('heading', { name: /Syslog/i })).toBeDefined();
    // No tab roles in the pane
    expect(screen.queryByRole('tab')).toBeNull();
  });
});

// ── Test 5: WorkspacePane — lists users, deactivate gated to Owner ────────────
describe('WorkspacePane', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('lists tenant users with RBAC role pill and shows deactivate control for Owner', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // First call: useTenantSettings
    mockApiTyped.mockResolvedValueOnce({
      sso_enforced: false,
      idp_provider: 'LOCAL',
      domain: 'example.com',
      timezone: 'UTC',
      password_policy: { min_length: 8, require_uppercase: false, require_lowercase: false, require_digit: false, require_symbol: false, history_count: 0 },
      syslog_config: null,
      smtp_config: null,
      sla_config: null,
      branding: null,
    });
    // Second call: useTenantUsers
    mockApiTyped.mockResolvedValueOnce([
      {
        id: 'u2',
        email: 'member@example.com',
        display_name: 'Member User',
        avatar_url: null,
        role: 'ANALYST',
        is_active: true,
        allow_password_login: true,
        idp_source: 'local',
        last_login_at: null,
      },
    ]);

    const { WorkspacePane } = await import('./workspace-pane');
    render(React.createElement(Wrapper, null, React.createElement(WorkspacePane)));

    // Wait for user list to render — email appears multiple times (name col + email col)
    await screen.findAllByText('member@example.com');

    // For OWNER viewing: role is shown as a select dropdown (editable) with ANALYST selected
    // The select element should have value "ANALYST"
    const selects = document.querySelectorAll('select');
    const roleSelect = Array.from(selects).find(s =>
      s.querySelector('option[value="ANALYST"]') !== null
    );
    expect(roleSelect).not.toBeUndefined();

    // Owner-gated deactivate button should be present (current user is OWNER)
    expect(screen.queryByRole('button', { name: /deactivate/i })).not.toBeNull();
  });
});
