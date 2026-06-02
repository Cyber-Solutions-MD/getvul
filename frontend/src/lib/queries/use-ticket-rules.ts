import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// TicketRule mirrors the backend TicketRuleResponse schema verbatim
// (backend/app/ticketing/schemas.py TicketRuleResponse — field names preserved).
export type TicketRule = {
  id: string;
  name: string;
  is_enabled: boolean;
  conditions: Record<string, unknown>;
  action: Record<string, unknown>;
  saved_filter_id: string | null;
  schedule_minutes: number;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_tickets_created: number | null;
  created_at: string;
};

// Phase 13 Plan 09 — read-only list query for the /tickets/rules surface.
// Query key is queryKeys.tickets.rules() (defined in Plan 04 / keys.ts — do NOT re-declare here).
// staleTime 30_000 + retry 1 mirror the use-assets.ts pattern.
export function useTicketRules() {
  return useQuery({
    queryKey: queryKeys.tickets.rules(),
    queryFn: ({ signal }) =>
      api<TicketRule[]>('/api/v1/tickets/rules', { signal }),
    staleTime: 30_000,
    retry: 1,
  });
}
