// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

// In-memory localStorage stub (Node 25 + jsdom collision — see api.test.ts).
const memStore: Record<string, string> = {};
const memLocalStorage = {
  getItem: (k: string) => (k in memStore ? memStore[k] : null),
  setItem: (k: string, v: string) => {
    memStore[k] = v;
  },
  removeItem: (k: string) => {
    delete memStore[k];
  },
  clear: () => {
    for (const k of Object.keys(memStore)) delete memStore[k];
  },
  key: (i: number) => Object.keys(memStore)[i] ?? null,
  get length() {
    return Object.keys(memStore).length;
  },
};
Object.defineProperty(globalThis, 'localStorage', {
  value: memLocalStorage,
  writable: true,
  configurable: true,
});
Object.defineProperty(window, 'localStorage', {
  value: memLocalStorage,
  writable: true,
  configurable: true,
});

// Mock next/navigation before importing auth so AuthProvider's useRouter resolves.
const replace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/dashboard',
}));

import { AuthProvider, useAuth } from './auth';

function wrap(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

describe('useAuth().logout() (D-D-09 / T-10-11)', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    memLocalStorage.clear();
    replace.mockReset();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    } as Response) as unknown as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('clears the TanStack cache so cross-user data does not leak on shared machines', async () => {
    const qc = new QueryClient();
    qc.setQueryData(['x'], 'sentinel');
    expect(qc.getQueryData(['x'])).toBe('sentinel');

    const { result } = renderHook(() => useAuth(), { wrapper: wrap(qc) });

    // AuthProvider's mount effect can be async; wait until the hook surface is stable.
    await waitFor(() => expect(result.current.logout).toBeDefined());

    act(() => {
      result.current.logout();
    });

    // qc.clear() runs synchronously inside the logout callback.
    expect(qc.getQueryData(['x'])).toBeUndefined();
    // And the user is redirected to /login (Phase 9 behavior preserved).
    expect(replace).toHaveBeenCalledWith('/login');
  });
});
