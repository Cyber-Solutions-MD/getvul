'use client';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queries/keys';
import type { TicketProvider } from '@/lib/ticketing/providers';

export type CreateTicketRequest = {
  vulnerability_ids: string[]; // 1..50 UUIDs (validated server-side)
  provider: TicketProvider;
  project_key?: string;
  assignee?: string;
  due_days?: number;
};

export type CreateTicketResponse = {
  created: number;
  tickets: Array<{
    id: string;
    external_ticket_id: string;
    external_ticket_url: string;
    provider: string;
  }>;
};

// D-P-04: NO optimistic updates — external Jira/Asana side-effect is
// irreversible from our side. Drill-panel "Create ticket" goes through
// the ConfirmModal first, then fires this mutation. Success surfaces a
// toast (consumer); failure surfaces the API error inline (consumer).
//
// BL-06 carryover (Phase 10): api.ts already throws
//   `Session expired during mutation. Please retry.`
// on 401 for non-safe methods. This mutation surfaces that error string to
// the caller WITHOUT silent retry — the audit trail's user attribution
// matters more than convenience.
export function useCreateTicketMutation() {
  const qc = useQueryClient();
  return useMutation<CreateTicketResponse, Error, CreateTicketRequest>({
    mutationFn: (body) =>
      api<CreateTicketResponse>('/api/v1/tickets', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      }),
    // RESEARCH Open Question 3 — refresh notifications so the
    // `ticket.create` audit event appears in the activity feed.
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: queryKeys.notifications.all });
    },
    // BL-06: POST must not silently re-fire. The 401 path is handled at
    // api.ts which throws before we reach here.
    retry: 0,
  });
}
