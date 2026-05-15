// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Stub localStorage BEFORE importing api (api.ts captures the global reference
// at call-time via getToken(), but Node 25's built-in localStorage conflicts
// with jsdom's. A simple in-memory replacement makes the test deterministic).
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

import { api } from './api';

// Regression-style coverage for api():
// - signal pass-through (Phase 10 / RESEARCH Pattern 5)
// - 401 refresh-retry chain still works (Phase 9 contract preserved)
describe('api() wrapper', () => {
  const originalFetch = globalThis.fetch;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    memLocalStorage.clear();
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('passes AbortSignal through to fetch (D-D Pattern 5)', async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    } as Response);

    await api('/x', { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const callArgs = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(callArgs.signal).toBe(controller.signal);
  });

  it('retries once after 401 → successful refresh (Phase 9 chain preserved)', async () => {
    memLocalStorage.setItem('getvul_refresh', 'refresh-token');

    fetchMock
      // initial 401
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'expired' }),
      } as Response)
      // refresh succeeds
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ access_token: 'new-token' }),
      } as Response)
      // retry succeeds
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ data: 'ok' }),
      } as Response);

    const result = await api<{ data: string }>('/x');

    expect(result).toEqual({ data: 'ok' });
    expect(fetchMock).toHaveBeenCalledTimes(3); // initial + refresh + retry
    const lastCall = fetchMock.mock.calls[2]?.[1] as RequestInit;
    const auth = (lastCall.headers as Record<string, string>).Authorization;
    expect(auth).toBe('Bearer new-token');
  });

  it('throws on non-2xx (no 401) with the server detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({ detail: 'boom' }),
    } as Response);

    await expect(api('/x')).rejects.toThrow('boom');
  });
});
