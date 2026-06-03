/**
 * TDD RED — profile-pane.tsx
 * Tests for ProfilePane component.
 *
 * Plan 14-05, Task 1 (Behaviors 2-3).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ── Mocks ─────────────────────────────────────────────────────────────────────
const mockUser = {
  id: 'u1',
  email: 'ana@example.com',
  display_name: 'Ana Sokolova',
  avatar_url: null,
  role: 'ADMIN',
  tenant_id: 't1',
  tenant_name: 'Acme Corp',
};

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ user: mockUser }),
}));

const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock('@/lib/api', () => ({
  api: vi.fn(),
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

// ── Test 2: ProfilePane renders identity from useAuth + idp_source/last_login from useTenantUsers ──
describe('ProfilePane', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders display_name, email, role, tenant_name from useAuth().user', async () => {
    // Mock useTenantUsers to return the current user's record with idp_source + last_login_at
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce([
      {
        id: 'u1',
        email: 'ana@example.com',
        display_name: 'Ana Sokolova',
        avatar_url: null,
        role: 'ADMIN',
        is_active: true,
        allow_password_login: true,
        idp_source: 'google',
        last_login_at: '2026-06-01T12:00:00Z',
      },
    ]);

    const { ProfilePane } = await import('./profile-pane');
    render(React.createElement(Wrapper, null, React.createElement(ProfilePane)));

    // Identity from useAuth
    expect(screen.getByText('Ana Sokolova')).toBeDefined();
    expect(screen.getByText('ana@example.com')).toBeDefined();
    expect(screen.getByText(/ADMIN/i)).toBeDefined();
    expect(screen.getByText(/Acme Corp/i)).toBeDefined();
  });

  it('sources idp_source and last_login_at from useTenantUsers (finding #4)', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    mockApiTyped.mockResolvedValueOnce([
      {
        id: 'u1',
        email: 'ana@example.com',
        display_name: 'Ana Sokolova',
        avatar_url: null,
        role: 'ADMIN',
        is_active: true,
        allow_password_login: true,
        idp_source: 'google',
        last_login_at: '2026-06-01T12:00:00Z',
      },
    ]);

    const { ProfilePane } = await import('./profile-pane');
    render(React.createElement(Wrapper, null, React.createElement(ProfilePane)));

    // idp_source and last_login_at from /tenant/users endpoint
    await screen.findByText(/google/i);
  });
});

// ── Test 3: Change Password form hidden for SSO-only accounts ────────────────
describe('ProfilePane SSO-only', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('hides the Change Password form when allow_password_login===false', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // SSO-only user
    mockApiTyped.mockResolvedValueOnce([
      {
        id: 'u1',
        email: 'ana@example.com',
        display_name: 'Ana Sokolova',
        avatar_url: null,
        role: 'ADMIN',
        is_active: true,
        allow_password_login: false, // SSO-only
        idp_source: 'google',
        last_login_at: '2026-06-01T12:00:00Z',
      },
    ]);

    const { ProfilePane } = await import('./profile-pane');
    render(React.createElement(Wrapper, null, React.createElement(ProfilePane)));

    // Wait for data to load then assert password form is absent
    await screen.findByText(/google/i);
    // Change password form should NOT be present
    expect(screen.queryByText(/Change password/i)).toBeNull();
    expect(screen.queryByLabelText(/Current password/i)).toBeNull();
  });

  it('shows the Change Password form when allow_password_login===true', async () => {
    const { api } = await import('@/lib/api');
    const mockApiTyped = vi.mocked(api);
    // Password-login user
    mockApiTyped.mockResolvedValueOnce([
      {
        id: 'u1',
        email: 'ana@example.com',
        display_name: 'Ana Sokolova',
        avatar_url: null,
        role: 'ADMIN',
        is_active: true,
        allow_password_login: true,
        idp_source: 'local',
        last_login_at: '2026-06-01T12:00:00Z',
      },
    ]);

    const { ProfilePane } = await import('./profile-pane');
    render(React.createElement(Wrapper, null, React.createElement(ProfilePane)));

    // Change password form should be present
    await screen.findByText(/Change password/i);
  });
});
