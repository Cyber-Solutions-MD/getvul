'use client';
/**
 * use-ticketing-providers.ts — React Query hook for the tenant-scoped
 * configured-providers endpoint (D-15, Plan 04).
 *
 * GET /api/v1/tickets/providers → the caller's tenant's ticketing
 * connectors that are configured + enabled. Consumed by the Plan 08
 * TicketProviderPicker (drill-panel create flow) and reused by Phase 27's
 * ticket auto-drafting.
 *
 * Wire convention (CR-06): uppercase provider values on the wire, matching
 * `TicketProvider` ('ASANA'|'JIRA'|'GITHUB') — no case transform at this
 * boundary. The create mutation (use-create-ticket.ts) already sends
 * uppercase, so this hook's output plugs straight into it.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { TicketProvider } from '@/lib/ticketing/providers';

export type ConfiguredTicketProvider = {
  provider: TicketProvider;
  enabled: boolean;
};

/**
 * useTicketingProviders — GET /api/v1/tickets/providers
 * Returns the configured+enabled ticketing providers for this tenant.
 * T-23-22 mitigation: this hook renders ONLY what the tenant-scoped
 * endpoint returns — there is no client-side global provider list to leak
 * across tenants.
 */
export function useTicketingProviders() {
  return useQuery({
    queryKey: ['ticketing', 'providers'] as const,
    queryFn: ({ signal }) =>
      api<ConfiguredTicketProvider[]>('/api/v1/tickets/providers', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}
