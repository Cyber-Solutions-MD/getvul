'use client';
import { useCallback, useState } from 'react';

// RESEARCH Pattern 6 / PATTERNS use-wizard-state analog: a small dedicated
// hook with local state -- not useQuery/useMutation, neither fits a
// long-lived multi-event stream cleanly. Deliberately does NOT import the
// generic api() helper: api() unconditionally calls res.json(), which
// hangs/throws against a streamed text/event-stream body (RESEARCH
// Pitfall 3). EventSource is also structurally incompatible with this app's
// auth model -- it cannot set a custom Authorization header, only cookies,
// and this app has no cookie session; fetch() + a manually-read
// ReadableStream is the only way to stream while still authenticating.

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export type CitationSource = 'scanner_verbatim' | 'ai_interpreted';

export type Citation = {
  text: string;
  source: CitationSource;
  source_field: string | null;
};

// Mirrors the backend's ExplainResponseBase (AI-02 schema-validation gate).
// The SAME shape is reused across every resourceType this phase's shared
// engine supports (D-15/D-16) -- nothing here is specific to one resource
// kind, even though this plan's only caller passes resourceType='vuln'.
export type ExplainVulnResponse = {
  summary: string;
  business_risk: string;
  citations: Citation[];
  grounded: boolean;
};

export type ExplainStreamState =
  | { phase: 'idle' }
  | { phase: 'analyzing' }
  | { phase: 'done'; data: ExplainVulnResponse }
  | { phase: 'error'; kind: 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown' | 'unsafe' };

type DoneEvent = { type: 'done' } & ExplainVulnResponse;
// Phase 25 (D-04): 'unsafe' is the dangerous-pattern-denylist-hit SSE kind
// emitted by explain.py's dangerous_pattern_check gate (25-03) -- both this
// standalone type AND ExplainStreamState's error branch above are
// hand-synced (no shared alias), so an additive kind must touch both.
type ErrorEvent = { type: 'error'; kind: 'busy' | 'grounded_false' | 'budget_exceeded' | 'unknown' | 'unsafe' };
type SummaryDeltaEvent = { type: 'summary_delta'; text: string };
type NoKeyEvent = { type: 'no_key' };
type RawSseEvent = DoneEvent | ErrorEvent | SummaryDeltaEvent | NoKeyEvent;

/**
 * useExplainStream(resourceType, resourceId) -- fetch() + ReadableStream SSE
 * consumer for the per-resource "Explain this" streaming endpoint (AI-03).
 * `resourceType` is always interpolated into the URL (D-15) -- never a fixed
 * resource-kind literal -- so a future view can reuse this hook unchanged,
 * parameterized only by which resource it targets.
 */
export function useExplainStream(resourceType: string, resourceId: string) {
  const [state, setState] = useState<ExplainStreamState>({ phase: 'idle' });

  const start = useCallback(async () => {
    setState({ phase: 'analyzing' });

    // EventSource cannot set a custom Authorization header -- fetch() is the
    // only way to stream while still authenticating (RESEARCH Pattern 6).
    const token = localStorage.getItem('getvul_token') || 'dev-token';

    let res: Response;
    try {
      res = await fetch(`${API_URL}/api/v1/ai/explain-${resourceType}/${resourceId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      setState({ phase: 'error', kind: 'unknown' });
      return;
    }

    if (!res.ok || !res.body) {
      setState({ phase: 'error', kind: 'unknown' });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

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

          if (evt.type === 'done') {
            const { type: _type, ...data } = evt;
            setState({ phase: 'done', data });
          } else if (evt.type === 'error') {
            setState({ phase: 'error', kind: evt.kind });
          } else if (evt.type === 'no_key') {
            // Defensive fallback only: the trigger that calls start() should
            // already be gated on a key-configured signal, so this
            // precondition should never actually fire in normal use. If it
            // ever does (a stale client-side signal), fail into the same
            // generic retryable card as 'unknown' rather than hanging in
            // 'analyzing' forever -- never a silent no-op on an unhandled
            // event type.
            setState({ phase: 'error', kind: 'unknown' });
          }
          // 'summary_delta' events are the backend's purely cosmetic replay
          // chunking of the ALREADY-validated summary (D-12) -- this hook's
          // state shape has no slot for partial text, so they are
          // intentionally not surfaced here. The drill panel's own
          // token-by-token reveal animation runs over the complete `done`
          // payload instead, honoring prefers-reduced-motion.
        }
      }
    } catch {
      setState({ phase: 'error', kind: 'unknown' });
    }
  }, [resourceType, resourceId]);

  return { state, start };
}
