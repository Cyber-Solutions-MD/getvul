/**
 * TDD RED — use-tenant-settings.ts
 * Tests for useTenantSettings and useUpdateTenantSettings hooks.
 *
 * Plan 14-05, Task 1 (Behavior 1).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ── Mock api ──────────────────────────────────────────────────────────────────
vi.mock('@/lib/api', () => ({
  api: vi.fn(),
}));
import { api } from '@/lib/api';
const mockApi = vi.mocked(api);

// ── Mock toast ────────────────────────────────────────────────────────────────
const mockToast = vi.fn();
vi.mock('@/components/ui/ToastProvider', () => ({
  useToast: () => ({ toast: mockToast }),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────
function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

const mockSettings = {
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

// ── Test 1: useTenantSettings ─────────────────────────────────────────────────
describe('useTenantSettings', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('GETs /api/v1/tenant/settings and returns settings data', async () => {
    const { useTenantSettings } = await import('./use-tenant-settings');
    const client = makeClient();
    mockApi.mockResolvedValueOnce(mockSettings);

    const { result } = renderHook(() => useTenantSettings(), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockSettings);
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tenant/settings'),
      expect.anything(),
    );
  });
});

// ── Test 1b: useUpdateTenantSettings ─────────────────────────────────────────
describe('useUpdateTenantSettings', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('PATCHes /api/v1/tenant/settings, invalidates settings cache, and toasts on success', async () => {
    const { useUpdateTenantSettings } = await import('./use-tenant-settings');
    const client = makeClient();
    mockApi.mockResolvedValueOnce({ message: 'Settings updated' });

    const { result } = renderHook(() => useUpdateTenantSettings(), {
      wrapper: wrapper(client),
    });

    await act(async () => {
      result.current.mutate({ idp_provider: 'GOOGLE' });
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tenant/settings'),
      expect.objectContaining({ method: 'PATCH' }),
    );
    // toast called on success
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'success' }),
    );
  });

  it('toasts an error on PATCH failure (e.g. 403)', async () => {
    const { useUpdateTenantSettings } = await import('./use-tenant-settings');
    const client = makeClient();
    mockApi.mockRejectedValueOnce(new Error('Forbidden'));

    const { result } = renderHook(() => useUpdateTenantSettings(), {
      wrapper: wrapper(client),
    });

    await act(async () => {
      result.current.mutate({ sso_enforced: true });
    });
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ variant: 'error' }),
    );
  });
});
