'use client';
import { useCallback, useState } from 'react';

// Phase 44 (NLQ-01, 44-03 Task 1) -- a NEW sibling to useExplainStream, not a
// generalization of it. The frame-parsing loop (fetch() + manual
// ReadableStream reader, \n\n-delimited SSE frames, mid-frame-split
// reassembly across reader.read() calls) is copied near-verbatim from
// use-explain-stream.ts (RESEARCH Pattern 6) -- the same reasons apply here:
// EventSource cannot set a custom Authorization header, and this app has no
// cookie session.
//
// The one deliberate, load-bearing difference (44-RESEARCH Pitfall 7):
// useExplainStream's fetch() sends NO body and interpolates a resourceId
// into the URL; useQueryStream POSTs `{question}` as a JSON body to a FIXED
// URL (/api/v1/ai/query) -- there is no per-record resource to address, the
// "record" IS the analyst's own free-text question.
//
// The SSE vocabulary is also wider than useExplainStream's: the backend
// (query_assistant.py::_run_query_stream) emits `interpreted` and `results`
// frames BEFORE any narrative streams (D-15 results-first), on top of the
// existing summary_delta/done/no_key/error kinds and a NEW terminal
// `refuse` kind (D-14: an honest "can't answer that" is not a failure).
// These two new event shapes are added to THIS file's own RawSseEvent union
// only -- use-explain-stream.ts's own union is untouched.

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export type NlqEntity = 'vulnerabilities' | 'assets' | 'tickets';

// Mirrors the backend's NlqAnswerResponse (an ExplainResponseBase subclass,
// query_assistant.py `done` frame: `{"type": "done", **answer.model_dump()}`).
export type NlqAnswer = {
  summary: string;
  business_risk: string;
  citations: Array<{ text: string; source: 'scanner_verbatim' | 'ai_interpreted'; source_field: string | null }>;
  grounded: boolean;
};

export type QueryStreamErrorKind = 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown';

// D-15 results-first: `interpreted` and `results` are always reflected in
// state BEFORE any narrative text (`streaming`/`done`) -- the reducer below
// accumulates entity/filter/rows/total once known and carries them forward
// onto every later phase so a consumer never loses the interpretation while
// the narrative streams in.
export type QueryStreamState =
  | { phase: 'idle' }
  | { phase: 'interpreting' }
  | { phase: 'interpreted'; entity: NlqEntity; filter: Record<string, unknown> }
  | { phase: 'results'; entity: NlqEntity; filter: Record<string, unknown>; rows: unknown[]; total: number }
  | {
      phase: 'streaming';
      entity: NlqEntity;
      filter: Record<string, unknown>;
      rows: unknown[];
      total: number;
      text: string;
    }
  | {
      phase: 'done';
      entity: NlqEntity;
      filter: Record<string, unknown>;
      rows: unknown[];
      total: number;
      answer: NlqAnswer;
    }
  | { phase: 'no_key' }
  | { phase: 'refuse' }
  // 44-04 (UI-SPEC E8 backstop): httpStatus/requestId are OPTIONAL and only
  // ever populated when a real fetch() Response was obtained (the
  // transient-error banner's "HTTP code + request ID" contract) -- the
  // pre-fetch network-failure catch (no Response object exists yet) leaves
  // both undefined, and callers must never assume either is present.
  | { phase: 'error'; kind: QueryStreamErrorKind; httpStatus?: number; requestId?: string };

type InterpretedEvent = { type: 'interpreted'; entity: NlqEntity; filter: Record<string, unknown> };
type ResultsEvent = { type: 'results'; rows: unknown[]; total: number };
type SummaryDeltaEvent = { type: 'summary_delta'; text: string };
type DoneEvent = { type: 'done' } & NlqAnswer;
type NoKeyEvent = { type: 'no_key' };
type RefuseEvent = { type: 'refuse' };
type ErrorEvent = { type: 'error'; kind: QueryStreamErrorKind };
type RawSseEvent =
  | InterpretedEvent
  | ResultsEvent
  | SummaryDeltaEvent
  | DoneEvent
  | NoKeyEvent
  | RefuseEvent
  | ErrorEvent;

// 44-04 (E8 backstop, Rule 2): the transient-error DegradedCard/banner needs
// an HTTP code + request ID to point the analyst at (mirrors
// PartialFailureBanner's own ErrorRow shape, T-11-15 -- code + requestId
// only, never a raw stack). Both are read defensively via optional chaining
// so a test's plain `{ ok, body }` Response stub (no `.headers`/`.status`)
// never throws -- the fields simply come back `undefined` and are omitted
// from state (keeping every existing `toEqual({phase:'error',kind:...})`
// assertion in use-query-stream.test.ts byte-identical).
function statusOf(res: Response | undefined): number | undefined {
  return typeof res?.status === 'number' ? res.status : undefined;
}

function requestIdOf(res: Response | undefined): string | undefined {
  return res?.headers?.get?.('X-Request-ID') ?? undefined;
}

function errorState(kind: QueryStreamErrorKind, res?: Response): QueryStreamState {
  const httpStatus = statusOf(res);
  const requestId = requestIdOf(res);
  return {
    phase: 'error',
    kind,
    ...(httpStatus !== undefined ? { httpStatus } : {}),
    ...(requestId !== undefined ? { requestId } : {}),
  };
}

/**
 * useQueryStream() -- fetch() + ReadableStream SSE consumer for the
 * natural-language "Ask" endpoint (NLQ-01). Unlike useExplainStream, this
 * hook takes no resourceType/resourceId at hook-call time; `start(question)`
 * carries the analyst's free-text question instead.
 */
export function useQueryStream() {
  const [state, setState] = useState<QueryStreamState>({ phase: 'idle' });

  const start = useCallback(async (question: string) => {
    setState({ phase: 'interpreting' });

    // EventSource cannot set a custom Authorization header -- fetch() is the
    // only way to stream while still authenticating (RESEARCH Pattern 6).
    const token = localStorage.getItem('getvul_token') || 'dev-token';

    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/v1/ai/query`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });
    } catch {
      setState({ phase: 'error', kind: 'unknown' });
      return;
    }

    if (!res.ok || !res.body) {
      setState(errorState('unknown', res));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // Accumulated across frames (D-15): once `interpreted` names the entity
    // and filter, every later state carries them forward so the analyst
    // never loses sight of what was searched while the narrative streams.
    let entity: NlqEntity | null = null;
    let filter: Record<string, unknown> = {};
    let rows: unknown[] = [];
    let total = 0;
    let text = '';

    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line (\n\n). The trailing
        // element after split() may be a partial frame still awaiting more
        // bytes -- it stays buffered instead of being parsed, so a frame
        // split mid-way across two separate reader.read() calls reassembles
        // correctly once the remaining bytes arrive.
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          const line = frame.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;

          let evt: RawSseEvent;
          try {
            evt = JSON.parse(line.slice('data: '.length));
          } catch {
            continue;
          }

          if (evt.type === 'interpreted') {
            entity = evt.entity;
            filter = evt.filter;
            setState({ phase: 'interpreted', entity, filter });
          } else if (evt.type === 'results') {
            rows = evt.rows;
            total = evt.total;
            // Defensive: `results` structurally always follows `interpreted`
            // (D-15 ordering is server-guaranteed) -- entity is never null
            // here in practice, but this never silently drops the frame if
            // it somehow were.
            if (entity) setState({ phase: 'results', entity, filter, rows, total });
          } else if (evt.type === 'summary_delta') {
            text += evt.text;
            if (entity) setState({ phase: 'streaming', entity, filter, rows, total, text });
          } else if (evt.type === 'done') {
            const { type: _type, ...answer } = evt;
            if (entity) setState({ phase: 'done', entity, filter, rows, total, answer });
          } else if (evt.type === 'no_key') {
            setState({ phase: 'no_key' });
          } else if (evt.type === 'refuse') {
            setState({ phase: 'refuse' });
          } else if (evt.type === 'error') {
            setState(errorState(evt.kind, res));
          }
        }
      }
    } catch {
      setState(errorState('unknown', res));
    }
  }, []);

  return { state, start };
}
