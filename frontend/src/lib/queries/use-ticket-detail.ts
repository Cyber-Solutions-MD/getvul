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

export type TicketDetail = {
  id: string;
  provider: TicketProvider;
  externalTicketUrl: string;
  externalStatus: string | null;
  blocked: boolean;
  blockedReason: string | null;
  slaDueAt: string | null;
  /** Ticket assignee (null if not assigned). */
  assignee: Person | null;
  /**
   * reporter is always typed as Person | null — the People card renders '—' when null.
   * The backend derives this from Ticket.created_by_user_id; null when unknowable.
   */
  reporter: Person | null;
  title: string;
  description: string | null;
  maxSeverity: string | null;
  vulnCount: number;
  criticalCount: number;
  highCount: number;
  linkedVulns: LinkedVuln[];
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
