'use client';
/**
 * useCoverageSummary — GET /api/v1/coverage/summary (Phase 41 Plan 03,
 * COV-02): the per-connector coverage strip rendered above the blind-spot
 * list on /dashboard/coverage. Mirrors use-blind-spot-assets.ts's
 * no-arg-shape (queryKeys.coverage.summary() was reserved in Plan 01).
 *
 * staleTime: 0 (D-10 precedent) — coverage % and staleness are compute-on-
 * read over Asset.seen_by_sources + ConnectorConfig.last_sync_at, so a
 * stale client cache could show an out-of-date % or staleness badge.
 *
 * Backend contract: backend/app/coverage/schemas.py::CoverageSummaryResponse
 * / CoverageConnectorCardResponse (snake_case end-to-end — CR-04 precedent,
 * api() does no casing transform).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type CoverageConnectorCard = {
  connector_type: string;
  /** D-11: null (never 0 or 100) when the authoritative-asset denominator is zero. */
  coverage_pct: number | null;
  /** D-06: strict `now - last_sync_at > 7 days`. */
  is_stale: boolean;
  stale_days: number | null;
  /** Wire-normalized via app.connectors.service._normalize_sync_status (Pitfall 3). */
  last_sync_status: 'ok' | 'failed' | 'syncing' | null;
  /** ISO timestamp, or null. */
  last_sync_at: string | null;
};

export type CoverageSummaryResponse = {
  cards: CoverageConnectorCard[];
  total_authoritative_assets: number;
  has_authoritative_inventory: boolean;
  /** True when >=1 enabled scanner connector exists at all. */
  has_scanner_connector: boolean;
};

export function useCoverageSummary() {
  return useQuery({
    queryKey: queryKeys.coverage.summary(),
    queryFn: ({ signal }) => api<CoverageSummaryResponse>('/api/v1/coverage/summary', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
