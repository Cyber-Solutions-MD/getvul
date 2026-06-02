import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import type { Watcher } from '@/components/tickets/watcher-stack';
import type { TicketProvider } from '@/components/tickets/types';

/**
 * useTicketDetail — detail query for /tickets/[id] (UX-05-04).
 *
 * O1 logical-ticket identity (RESOLVED, inherited from Plan 03):
 * A logical ticket is the group of `tickets` rows sharing one `external_ticket_url`.
 * The route `id` is the canonical `first_ticket_id` — the MIN row id in the group,
 * exactly what GET /tickets returns as `id`. All detail hooks pass that id through
 * verbatim to `/tickets/{id}/...`; the backend `_resolve_group` maps it to the group.
 * The frontend NEVER reconstructs the group itself.
 */

export type Person = {
  userId: string;
  displayName: string;
  email?: string;
};

export type LinkedVuln = {
  cve: string;
  severity: string;
  cvss: number | null;
};

// CR-02/03/04: top-level keys are snake_case to match the verbatim JSON the
// detail endpoint emits (api() does no casing transform). Nested objects
// (assignee/reporter/watchers/asset) keep camelCase keys because the backend
// emits THOSE nested keys camelCase (matching the existing reporter/watcher
// convention on this endpoint).
export type TicketDetail = {
  id: string;
  provider: TicketProvider;
  external_ticket_id: string;
  external_ticket_url: string;
  external_status: string | null;
  blocked: boolean;
  blocked_reason: string | null;
  sla_due_at: string | null;
  /** CR-02: Person object (or null), never a bare string. */
  assignee: Person | null;
  /**
   * reporter is always typed as Person | null — the People card renders '—' when null.
   * The backend derives this from Ticket.created_by_user_id; null when unknowable.
   */
  reporter: Person | null;
  title: string;
  description: string | null;
  max_severity: string | null;
  vuln_count: number;
  critical_count: number;
  high_count: number;
  linked_vulns: LinkedVuln[];
  watchers: Watcher[];
  asset: {
    assetId: string;
    hostname: string | null;
    osName: string | null;
    riskScore: number | null;
  } | null;
};

export function useTicketDetail(id: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.tickets.byId(id ?? ''),
    queryFn: ({ signal }) =>
      api<TicketDetail>(`/api/v1/tickets/${id}`, { signal }),
    enabled: !!id,
    staleTime: 30_000,
    retry: 1,
  });
}
