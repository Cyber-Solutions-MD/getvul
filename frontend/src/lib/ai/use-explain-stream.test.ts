/**
 * use-explain-stream.test.ts -- TDD RED-phase tests for useExplainStream +
 * useExplainCache (24-05 Task 1).
 *
 * useExplainStream: mocks fetch() + a manual ReadableStream reader (no real
 * network, no real Anthropic call) -- SSE frame parsing on `\n\n` boundaries,
 * mid-frame-split reassembly across two reader.read() calls, and the closed
 * error-kind vocabulary are asserted directly against the hook's exposed
 * discriminated-union state.
 *
 * useExplainCache: mocks the generic api() helper (RESEARCH Pattern 6 -- this
 * one genuinely is a fast, non-streaming GET, so api() is the right tool,
 * unlike the streaming hook above) and asserts a single GET + {cached:false}
 * on a miss.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useExplainStream } from './use-explain-stream';

// useExplainCache imports the generic api() helper for real (it's a single
// GET, not a stream) -- mock it so the test never makes a real HTTP call.
vi.mock('@/lib/api', () => ({ api: vi.fn() }));
import { api } from '@/lib/api';
import { useExplainCache } from '@/lib/queries/use-explain-cache';

const mockApi = api as unknown as ReturnType<typeof vi.fn>;

const encoder = new TextEncoder();

function sseFrame(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

function makeReader(chunks: string[]) {
  let i = 0;
  return {
    read: vi.fn(async () => {
      if (i >= chunks.length) return { done: true, value: undefined };
      const value = encoder.encode(chunks[i]);
      i += 1;
      return { done: false, value };
    }),
  };
}

function mockStreamingResponse(ok: boolean, chunks: string[]) {
  return {
    ok,
    body: ok ? { getReader: () => makeReader(chunks) } : null,
  } as unknown as Response;
}

describe('useExplainStream', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('getvul_token', 'test-token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sets phase analyzing synchronously on start(), then phase done with parsed data on a done frame', async () => {
    const donePayload = {
      type: 'done',
      summary: 'Plain-English summary of the CVE.',
      business_risk: 'Business risk framing for this asset.',
      citations: [{ text: 'Plain-English summary', source: 'scanner_verbatim', source_field: 'cve_id' }],
      grounded: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame(donePayload)]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    expect(result.current.state).toEqual({ phase: 'idle' });

    act(() => {
      void result.current.start();
    });
    // The setState to 'analyzing' happens synchronously (before the first
    // await inside start()), so it must be visible immediately.
    expect(result.current.state).toEqual({ phase: 'analyzing' });

    await waitFor(() => expect(result.current.state.phase).toBe('done'));
    expect(result.current.state).toEqual({
      phase: 'done',
      data: {
        summary: 'Plain-English summary of the CVE.',
        business_risk: 'Business risk framing for this asset.',
        citations: [{ text: 'Plain-English summary', source: 'scanner_verbatim', source_field: 'cve_id' }],
        grounded: true,
      },
    });
  });

  it('sets phase error kind budget_exceeded on a mocked error frame', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockStreamingResponse(true, [sseFrame({ type: 'error', kind: 'budget_exceeded' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toEqual({ phase: 'error', kind: 'budget_exceeded' });
  });

  it('reassembles a frame split mid-way across two separate reader.read() calls', async () => {
    const donePayload = { type: 'done', summary: 'S', business_risk: 'B', citations: [], grounded: true };
    const whole = sseFrame(donePayload);
    const splitPoint = Math.floor(whole.length / 2);
    const chunk1 = whole.slice(0, splitPoint);
    const chunk2 = whole.slice(splitPoint);
    expect(chunk1 + chunk2).toBe(whole); // sanity: the split really is mid-frame

    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [chunk1, chunk2]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toEqual({
      phase: 'done',
      data: { summary: 'S', business_risk: 'B', citations: [], grounded: true },
    });
  });

  it('sets phase error kind unknown on a non-ok fetch response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, body: null } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toEqual({ phase: 'error', kind: 'unknown' });
  });

  it('builds the fetch URL from the resourceType argument, never a fixed literal (D-15)', async () => {
    const donePayload = { type: 'done', summary: 'S', business_risk: 'B', citations: [], grounded: true };
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame(donePayload)]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('host', 'host-77'));
    await act(async () => {
      await result.current.start();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/ai/explain-host/host-77'),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('carries the Bearer token from localStorage as the Authorization header', async () => {
    localStorage.setItem('getvul_token', 'my-secret-token');
    const donePayload = { type: 'done', summary: 'S', business_risk: 'B', citations: [], grounded: true };
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame(donePayload)]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    await act(async () => {
      await result.current.start();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ headers: { Authorization: 'Bearer my-secret-token' } }),
    );
  });

  it('never hangs on a defensive no_key frame -- falls into the same retryable unknown state', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame({ type: 'no_key' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useExplainStream('vuln', 'abc-123'));
    await act(async () => {
      await result.current.start();
    });

    expect(result.current.state).toEqual({ phase: 'error', kind: 'unknown' });
  });
});

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe('useExplainCache', () => {
  beforeEach(() => {
    mockApi.mockReset();
  });

  it('issues a single GET and returns {cached:false} on a cache miss', async () => {
    mockApi.mockResolvedValueOnce({ cached: false });

    const { result } = renderHook(() => useExplainCache('vuln', 'abc-123'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi).toHaveBeenCalledTimes(1);
    expect(mockApi).toHaveBeenCalledWith('/api/v1/ai/explain-vuln/abc-123', expect.any(Object));
    expect(result.current.data).toEqual({ cached: false });
  });

  it('builds the GET path from resourceType, never a fixed literal (D-15)', async () => {
    mockApi.mockResolvedValueOnce({ cached: false });

    const { result } = renderHook(() => useExplainCache('host', 'host-77'), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockApi).toHaveBeenCalledWith('/api/v1/ai/explain-host/host-77', expect.any(Object));
  });
});
