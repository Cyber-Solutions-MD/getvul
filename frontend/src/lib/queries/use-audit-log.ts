/**
 * use-audit-log.ts — TanStack hook for /tenant/audit-log.
 *
 * Hook:
 *   useAuditLog(opts) — paginated GET /api/v1/tenant/audit-log
 *
 * Endpoint (D-SET-09 / RESEARCH):
 *   GET /api/v1/tenant/audit-log?action=&resource_type=&user_email=&page=&page_size=50
 *   Returns { items, total, page, page_size, pages }
 *
 * Security (T-14-19):
 *   The backend scopes results by tenant_id (server-side WHERE clause). The
 *   pane renders only what the API returns — no cross-tenant data reaches
 *   the client.
 *
 * Plan 14-05.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// ── Types ─────────────────────────────────────────────────────────────────────

export type AuditLogItem = {
  id: string;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  created_at: string;
};

export type AuditLogResponse = {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type AuditLogFilters = {
  action?: string;
  resource_type?: string;
  user_email?: string;
  page: number;
};

// ── URL param builder ─────────────────────────────────────────────────────────

export function buildAuditLogParams(opts: AuditLogFilters): URLSearchParams {
  const sp = new URLSearchParams();
  if (opts.action) sp.set('action', opts.action);
  if (opts.resource_type) sp.set('resource_type', opts.resource_type);
  if (opts.user_email) sp.set('user_email', opts.user_email);
  sp.set('page', String(opts.page));
  sp.set('page_size', '50');
  return sp;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * useAuditLog — GET /api/v1/tenant/audit-log with pagination + filter params.
 * Requires Admin role (backend-enforced). keepPreviousData via placeholderData.
 */
export function useAuditLog(opts: AuditLogFilters) {
  return useQuery({
    queryKey: queryKeys.settings.auditLog({
      action: opts.action,
      resource_type: opts.resource_type,
      user_email: opts.user_email,
      page: opts.page,
    }),
    queryFn: ({ signal }) =>
      api<AuditLogResponse>(
        `/api/v1/tenant/audit-log?${buildAuditLogParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 30_000,
    retry: 1,
    // keepPreviousData pattern (TanStack v5): placeholderData from previous query
    placeholderData: (previousData) => previousData,
  });
}
