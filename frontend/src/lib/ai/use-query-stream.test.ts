/**
 * use-query-stream.test.ts -- TDD RED-phase tests for useQueryStream
 * (44-03 Task 1, NLQ-01).
 *
 * Mirrors use-explain-stream.test.ts's mocked fetch() + manual ReadableStream
 * reader approach -- no real network, no real Anthropic call. Three
 * behaviors asserted (plan `<behavior>` block):
 *   1. POSTs {question} as a JSON body with Content-Type + Bearer token.
 *   2. interpreted -> results -> streaming -> done, with interpreted/results
 *      state visible BEFORE any narrative text (D-15 results-first).
 *   3. no_key / refuse / error terminal states.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

import { useQueryStream } from './use-query-stream';

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

// A controllable reader: each chunk is only handed back once the test
// explicitly `push()`es it -- lets a test observe an intermediate state
// (e.g. 'interpreted') before the frame that would advance past it has even
// been read, proving the results-first ORDER, not just the final state.
function makeControllableReader() {
  const queue: Array<{ done: boolean; value?: Uint8Array }> = [];
  const waiters: Array<(r: { done: boolean; value?: Uint8Array }) => void> = [];
  return {
    push(chunk: string) {
      const value = encoder.encode(chunk);
      const item = { done: false, value };
      const waiter = waiters.shift();
      if (waiter) waiter(item);
      else queue.push(item);
    },
    close() {
      const item = { done: true, value: undefined };
      const waiter = waiters.shift();
      if (waiter) waiter(item);
      else queue.push(item);
    },
    read: vi.fn(() => {
      const item = queue.shift();
      if (item) return Promise.resolve(item);
      return new Promise<{ done: boolean; value?: Uint8Array }>((resolve) => waiters.push(resolve));
    }),
  };
}

describe('useQueryStream', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('getvul_token', 'test-token');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('POSTs {question} as a JSON body with Content-Type + Bearer token (Pitfall 7 -- never a bodyless GET-like call)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockStreamingResponse(true, [
        sseFrame({ type: 'interpreted', entity: 'vulnerabilities', filter: { severity: ['CRITICAL'] } }),
        sseFrame({ type: 'results', rows: [], total: 0 }),
        sseFrame({ type: 'done', summary: 'S', business_risk: 'B', citations: [], grounded: true }),
      ]),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());
    await act(async () => {
      await result.current.start('Show critical vulns breaching SLA');
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/ai/query'),
      expect.objectContaining({
        method: 'POST',
        headers: { Authorization: 'Bearer test-token', 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: 'Show critical vulns breaching SLA' }),
      }),
    );
  });

  it('drives interpreted -> results -> streaming -> done, with interpreted/results visible BEFORE narrative text (D-15)', async () => {
    const reader = makeControllableReader();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body: { getReader: () => reader } } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());

    act(() => {
      void result.current.start('Which internet-facing hosts have an unremediated KEV older than 30 days?');
    });
    expect(result.current.state).toEqual({ phase: 'interpreting' });

    reader.push(
      sseFrame({
        type: 'interpreted',
        entity: 'vulnerabilities',
        filter: { cisa_kev: true, age_days_min: 30, asset_internet_facing: true },
      }),
    );
    await waitFor(() => expect(result.current.state.phase).toBe('interpreted'));
    expect(result.current.state).toEqual({
      phase: 'interpreted',
      entity: 'vulnerabilities',
      filter: { cisa_kev: true, age_days_min: 30, asset_internet_facing: true },
    });

    reader.push(sseFrame({ type: 'results', rows: [{ id: 'v1' }, { id: 'v2' }], total: 2 }));
    await waitFor(() => expect(result.current.state.phase).toBe('results'));
    // Still no narrative text at this point -- proves results-first ordering,
    // not merely that results eventually arrive.
    expect(result.current.state).toEqual({
      phase: 'results',
      entity: 'vulnerabilities',
      filter: { cisa_kev: true, age_days_min: 30, asset_internet_facing: true },
      rows: [{ id: 'v1' }, { id: 'v2' }],
      total: 2,
    });

    reader.push(sseFrame({ type: 'summary_delta', text: 'Two hosts ' }));
    await waitFor(() => expect(result.current.state.phase).toBe('streaming'));
    expect(result.current.state).toMatchObject({ phase: 'streaming', text: 'Two hosts ', total: 2 });

    reader.push(sseFrame({ type: 'summary_delta', text: 'match.' }));
    await waitFor(() => (result.current.state as { text?: string }).text === 'Two hosts match.');

    reader.push(
      sseFrame({
        type: 'done',
        summary: 'Two hosts match.',
        business_risk: 'High exposure risk.',
        citations: [],
        grounded: true,
      }),
    );
    reader.close();
    await waitFor(() => expect(result.current.state.phase).toBe('done'));
    expect(result.current.state).toEqual({
      phase: 'done',
      entity: 'vulnerabilities',
      filter: { cisa_kev: true, age_days_min: 30, asset_internet_facing: true },
      rows: [{ id: 'v1' }, { id: 'v2' }],
      total: 2,
      answer: { summary: 'Two hosts match.', business_risk: 'High exposure risk.', citations: [], grounded: true },
    });
  });

  it('a {type:"no_key"} frame drives a no_key terminal state', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame({ type: 'no_key' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());
    await act(async () => {
      await result.current.start('Show critical vulns breaching SLA');
    });

    expect(result.current.state).toEqual({ phase: 'no_key' });
  });

  it('a {type:"refuse"} frame drives a refuse terminal state (D-14 -- an honest refusal, not an error)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockStreamingResponse(true, [sseFrame({ type: 'refuse' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());
    await act(async () => {
      await result.current.start('What is the weather in Paris?');
    });

    expect(result.current.state).toEqual({ phase: 'refuse' });
  });

  it('a {type:"error",kind} frame drives an error state carrying kind', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockStreamingResponse(true, [sseFrame({ type: 'error', kind: 'budget_exceeded' })]));
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());
    await act(async () => {
      await result.current.start('Show critical vulns breaching SLA');
    });

    expect(result.current.state).toEqual({ phase: 'error', kind: 'budget_exceeded' });
  });

  it('sets phase error kind unknown on a non-ok fetch response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, body: null } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useQueryStream());
    await act(async () => {
      await result.current.start('Show critical vulns breaching SLA');
    });

    expect(result.current.state).toEqual({ phase: 'error', kind: 'unknown' });
  });
});
