'use client';
/**
 * useMttrByTier — GET /api/v1/vulnerabilities/mttr/by-tier (Phase 36 Plan
 * 04, admin-gated, tenant-scoped). Mirrors use-coverage-summary.ts's
 * no-arg, `staleTime: 0` shape.
 *
 * Consumed by the RPT-02 leadership-lens MTTR-by-tier tile
 * (mttr-by-tier-tile.tsx). Note this route is `require_admin`-gated on the
 * backend (unchanged, out of this plan's scope) — a non-admin viewer
 * switching to the leadership lens gets a query error here, which the
 * tile treats the same as "not yet measured" rather than surfacing a
 * scary crash (Rule 2 — graceful degradation on an existing RBAC floor,
 * not a new capability).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type MttrByTierRow = {
  tier_at_remediation: string;
  /** null when the tier has zero remediation history (D-11 zero-denominator discipline). */
  avg_seconds: number | null;
  count: number;
};

export function useMttrByTier() {
  return useQuery({
    queryKey: queryKeys.mttrByTier.list(),
    queryFn: ({ signal }) => api<MttrByTierRow[]>('/api/v1/vulnerabilities/mttr/by-tier', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
