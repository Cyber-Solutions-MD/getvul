'use client';
/**
 * useBlindSpotAssets — GET /api/v1/coverage/blind-spots (Phase 41 Plan 01,
 * COV-01 tracer slice). Mirrors use-assets.ts's paginated-GET shape;
 * simpler `opts` — the blind-spot list has no multi-axis facet set the way
 * `/assets` does (41-PATTERNS.md).
 *
 * staleTime: 0 (D-10) — this is a compute-on-read reconciliation over
 * `Asset.seen_by_sources`, recomputed on every request; a stale client
 * cache would show an out-of-date blind-spot list or
 * has_authoritative_inventory/total_authoritative_assets signal.
 *
 * Backend contract: backend/app/coverage/schemas.py::BlindSpotAssetListResponse
 * (snake_case end-to-end — CR-04 precedent, api() does no casing transform).
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type BlindSpotAsset = {
  id: string;
  hostname: string;
  category: string | null;
  os: string | null;
  /** ISO timestamp, or null if the asset has never reported a last-seen signal. */
  last_seen_at: string | null;
  seen_by_sources: string[];
};

export type BlindSpotAssetListResponse = {
  items: BlindSpotAsset[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  /** D-11 — false when the tenant has zero authoritative (MDM/HR) assets at all. */
  has_authoritative_inventory: boolean;
  /** The quiet-win empty copy's "All {N} devices…" count (independent of the blind-spot `total` above). */
  total_authoritative_assets: number;
};

export function useBlindSpotAssets(opts: { page: number }) {
  return useQuery({
    queryKey: queryKeys.coverage.blindSpots({ page: opts.page }),
    queryFn: ({ signal }) =>
      api<BlindSpotAssetListResponse>(
        `/api/v1/coverage/blind-spots?page=${opts.page}&page_size=50`,
        { signal },
      ),
    staleTime: 0,
    retry: 1,
  });
}
