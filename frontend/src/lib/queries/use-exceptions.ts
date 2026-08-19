'use client';
/**
 * useExceptions — GET /api/v1/exceptions (list), Phase 39 Plan 06 (EXC-02/
 * EXC-03) manage-only /dashboard/exceptions list surface. Mirrors
 * use-campaigns.ts's useCampaigns() shape (signal-aware queryFn, staleTime 0,
 * retry 1).
 *
 * KEY DEVIATION from the use-assignable-users.ts 30_000 default: staleTime: 0
 * — mirrors useCampaigns()'s own D-07 reasoning. Whether an exception is
 * still active (not yet expired/revoked) and its expiry countdown pill are
 * both compute-on-read fields with zero persisted snapshot on the backend
 * (backend/app/exceptions/service.py::list_exceptions returns every row for
 * the tenant unfiltered, and the endpoint runs the Pattern-4 lazy-audit
 * sweep first, which can flip a row's "still active" status between reads).
 * A stale client cache would show an out-of-date expiring-soon pill or an
 * already-revoked row as still active.
 *
 * Backend contract: backend/app/exceptions/schemas.py::ExceptionResponse.
 * Deliberately has NO pre-formatted `target` display label (39-01/39-02
 * decision) — ASSET/ASSET_GROUP scope ships raw scope_type/cve_id/
 * vulnerability_id/asset_id/asset_group_id only; resolving a hostname/
 * group-name would need a separate assets/asset-groups join this plan's
 * key_links doesn't authorize (see 39-06-SUMMARY.md).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type ExceptionType = 'FALSE_POSITIVE' | 'ACCEPTED_RISK';
export type ExceptionScopeType = 'FINDING' | 'ASSET' | 'ASSET_GROUP';

// CR-04 precedent (use-campaigns.ts/use-tickets.ts): snake_case end-to-end —
// the backend (exceptions/schemas.py ExceptionResponse) emits these keys
// verbatim and api() does no casing transform.
export type ExceptionResponse = {
  id: string;
  type: ExceptionType;
  scope_type: ExceptionScopeType;
  cve_id: string;
  vulnerability_id: string | null;
  asset_id: string | null;
  asset_group_id: string | null;
  justification: string;
  approver_user_id: string | null;
  approver_display_name: string | null;
  granted_by_user_id: string | null;
  /** ISO timestamp. */
  expires_at: string;
  /** ISO timestamp, null while still active. */
  revoked_at: string | null;
  revoked_by_user_id: string | null;
  /** Pattern-4 lazy-audit stamp; null until the sweep fires once. */
  resurfaced_audited_at: string | null;
  /** ISO timestamp — this is the "granted at" moment (39-01-SUMMARY.md). */
  created_at: string;
};

export function useExceptions() {
  return useQuery({
    queryKey: queryKeys.exceptions.list(),
    queryFn: ({ signal }) =>
      api<ExceptionResponse[]>('/api/v1/exceptions', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
