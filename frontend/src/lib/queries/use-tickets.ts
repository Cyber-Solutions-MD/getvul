import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Phase 13 D-D-03 — list endpoint for /tickets surface.
// buildSearchParams is co-located + exported so URL-shape tests can assert
// the wire contract without spinning up TanStack (Phase 11 D-D-03 pattern).

// XSS allow-lists per T-12-05. Reflected URL values outside these lists are
// dropped before sending to the backend. mirrors the chip-bar axis allow-lists.
const STATUS_ALLOW = ['open', 'in_progress', 'completed', 'blocked'] as const;
const PROVIDER_ALLOW = ['jira', 'asana', 'github'] as const;
const SEVERITY_ALLOW = ['critical', 'high', 'medium', 'low'] as const;
const SLA_ALLOW = ['overdue', 'soon', 'ok'] as const;

export type TicketsFilters = {
  status?: readonly string[];
  provider?: readonly string[];
  severity?: readonly string[];
  sla?: readonly string[];
  search?: string;
};

// CR-04: snake_case end-to-end. The backend (service.py:list_tickets) emits
// these keys verbatim and api() does NO casing transform (return res.json()),
// so the frontend type/accessors MUST be snake_case to match the wire payload.
export type TicketSummary = {
  id: string;
  /** Lowercased by the backend (CR-06) — 'jira' | 'asana' | 'github'. */
  provider: string;
  external_ticket_id: string;
  title: string;
  external_status: string | null;
  blocked: boolean;
  blocked_reason: string | null;
  sla_due_at: string | null;
  assignee: string | null;
  max_severity: string | null;
  vuln_count: number;
  critical_count: number;
  high_count: number;
  external_ticket_url: string;
};

export type TicketsResponse = {
  items: TicketSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export function buildSearchParams(opts: {
  filters: TicketsFilters;
  page: number;
}): URLSearchParams {
  const sp = new URLSearchParams();
  const { filters } = opts;

  // Status — multi, comma-separated. Apply allow-list clamp (T-13-22).
  if (filters.status && filters.status.length > 0) {
    const clamped = filters.status.filter((v) =>
      (STATUS_ALLOW as readonly string[]).includes(v)
    );
    if (clamped.length > 0) sp.set('status', clamped.join(','));
  }

  // Provider — multi, comma-separated. Apply allow-list clamp.
  if (filters.provider && filters.provider.length > 0) {
    const clamped = filters.provider.filter((v) =>
      (PROVIDER_ALLOW as readonly string[]).includes(v)
    );
    if (clamped.length > 0) sp.set('provider', clamped.join(','));
  }

  // Severity — multi, comma-separated. Apply allow-list clamp.
  if (filters.severity && filters.severity.length > 0) {
    const clamped = filters.severity.filter((v) =>
      (SEVERITY_ALLOW as readonly string[]).includes(v)
    );
    if (clamped.length > 0) sp.set('severity', clamped.join(','));
  }

  // SLA — single-select (but stored as array in state). Apply allow-list clamp.
  if (filters.sla && filters.sla.length > 0) {
    const clamped = filters.sla.filter((v) =>
      (SLA_ALLOW as readonly string[]).includes(v)
    );
    if (clamped.length > 0) sp.set('sla', clamped.join(','));
  }

  // Search — free-text, no allow-list (URL-encoded by URLSearchParams).
  if (filters.search) sp.set('search', filters.search);

  sp.set('page', String(opts.page));

  return sp;
}

export function useTickets(opts: {
  filters: TicketsFilters;
  page: number;
  view?: string;
}) {
  return useQuery({
    queryKey: queryKeys.tickets.list({
      filters: opts.filters,
      page: opts.page,
      view: opts.view ?? 'list',
    }),
    queryFn: ({ signal }) =>
      api<TicketsResponse>(
        `/api/v1/tickets?${buildSearchParams({ filters: opts.filters, page: opts.page }).toString()}`,
        { signal }
      ),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: true,
  });
}
