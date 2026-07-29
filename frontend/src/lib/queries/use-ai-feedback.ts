'use client';
/**
 * useAiFeedback — mutation hook for POST /api/v1/ai/feedback/{resourceType}/
 * {resourceId} (D-21/D-22, 24-07 Task 2).
 *
 * Curried on (resourceType, resourceId) at the call site, matching the
 * sibling AI hooks in this exact feature (useExplainStream/useExplainCache,
 * 24-05) rather than threading them through per-call mutate variables.
 *
 * Deliberately NO hook-level onError (unlike every other mutation hook in
 * this codebase, e.g. use-connectors-admin.ts's useCreateConnector) --
 * feedback is a low-stakes accuracy signal (UI-SPEC user decision,
 * 2026-07-28): a failed submission must silently revert the caller's own
 * optimistic thumb state, with NO error toast/card. There is also no
 * existing query cache to snapshot/roll back here (capture-only, D-21 --
 * nothing reads feedback back this phase), unlike use-mark-blocked.ts's
 * byId/list cache patch -- so the optimistic mark + silent revert lives in
 * the CALLER's own local component state (ai-feedback-control.tsx), driven
 * via the per-call `mutate(vars, { onError })` callback. `retry: 0` so a
 * failed submission reverts immediately rather than retrying invisibly
 * while the UI already shows "reverted."
 *
 * Sentinel is `grep -c "toast" use-ai-feedback.ts == 0`.
 */
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';

export type FeedbackVerdict = 'up' | 'down';

export type FeedbackVars = {
  verdict: FeedbackVerdict;
  note: string | null;
};

export type FeedbackResponse = {
  verdict: FeedbackVerdict;
};

export function useAiFeedback(resourceType: string, resourceId: string) {
  return useMutation<FeedbackResponse, Error, FeedbackVars>({
    mutationFn: ({ verdict, note }) =>
      api<FeedbackResponse>(
        `/api/v1/ai/feedback/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`,
        {
          method: 'POST',
          body: JSON.stringify({ verdict, note }),
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    retry: 0,
  });
}
