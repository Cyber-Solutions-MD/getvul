'use client';
/**
 * useTicketComments + useAddComment — comment list query + optimistic create mutation.
 *
 * Contract (13-08-PLAN Task 1):
 *   useTicketComments: GET /api/v1/tickets/{id}/comments — ascending by created_at (D-C-04).
 *   useAddComment: POST /api/v1/tickets/{id}/comments with body { body } ONLY.
 *     - onMutate: cancel + snapshot tickets.comments(id), optimistically append temp comment.
 *     - onError: restore snapshot + error toast (peer voice, no "Please").
 *     - onSuccess: invalidate tickets.comments(id) + tickets.byId(id).
 *     - retry: 0.
 *
 * Threat model:
 *   T-13-26 (mass assignment): ONLY { body } sent — never spread arbitrary form state.
 *   T-13-27 (Stored XSS): comment body rendered as React text nodes via ActivityTimeline
 *     (whitespace-pre-wrap, no dangerouslySetInnerHTML).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

// CR-05: snake_case to match the comments endpoint payload verbatim
// (api() does no casing transform). The backend now LEFT JOINs users to emit
// user_display_name; previously every author rendered as "Unknown".
export type Comment = {
  id: string;
  user_id: string;
  user_display_name: string | null;
  body: string;
  created_at: string;
  edited_at: string | null;
};

// ---------------------------------------------------------------------------
// Query: comment list (ascending by created_at — D-C-04)
// ---------------------------------------------------------------------------

export function useTicketComments(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.tickets.comments(id ?? ''),
    queryFn: ({ signal }) =>
      api<Comment[]>(`/api/v1/tickets/${id}/comments`, { signal }),
    enabled: !!id,
    staleTime: 30_000,
    retry: 1,
  });
}

// ---------------------------------------------------------------------------
// Mutation: optimistic comment add
// ---------------------------------------------------------------------------

type AddCommentCtx = { snapshot: unknown };

export function useAddComment(id: string) {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<Comment, Error, string, AddCommentCtx>({
    // T-13-26: ONLY { body } — never spread arbitrary vars.
    mutationFn: (body) =>
      api<Comment>(`/api/v1/tickets/${id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body }),
        headers: { 'Content-Type': 'application/json' },
      }),

    onMutate: async (body) => {
      const key = queryKeys.tickets.comments(id);
      await qc.cancelQueries({ queryKey: key });
      const snapshot = qc.getQueryData(key);

      // Optimistically append a temp comment (will be replaced by onSuccess invalidation)
      qc.setQueryData(key, (prev: unknown) => {
        const list = Array.isArray(prev) ? prev : [];
        const optimistic: Comment = {
          id: `optimistic-${Date.now()}`,
          user_id: '',
          user_display_name: 'You',
          body,
          created_at: new Date().toISOString(),
          edited_at: null,
        };
        return [...list, optimistic];
      });

      return { snapshot };
    },

    onError: (_err, _body, ctx) => {
      // Roll back to the snapshot so the UI shows the previous comment list.
      if (ctx && ctx.snapshot !== undefined) {
        qc.setQueryData(queryKeys.tickets.comments(id), ctx.snapshot);
      }
      // Peer voice — no "Please", no "Unable to".
      toast({ variant: 'error', message: "Couldn't post that note. Try again." });
    },

    onSuccess: () => {
      // Reconcile against server truth: comment list and ticket detail counts.
      qc.invalidateQueries({ queryKey: queryKeys.tickets.comments(id) });
      qc.invalidateQueries({ queryKey: queryKeys.tickets.byId(id) });
    },

    retry: 0,
  });
}
