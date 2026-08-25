'use client';
/**
 * useCampaigns / useCampaignDetail — GET /api/v1/campaigns (list) and
 * GET /api/v1/campaigns/{id} (detail), Phase 38 CAMP-01 dedicated campaign
 * view. Mirrors useVulnEscalations.ts's shape (signal-aware queryFn,
 * enabled-gate on a non-empty id for the detail hook).
 *
 * KEY DEVIATION from the use-vuln-escalations.ts analog: staleTime: 0, not
 * 30_000. D-07 (backend/38-01-SUMMARY.md) — campaign progress/status/MTTR
 * are computed fresh on every backend read with zero persisted snapshot; a
 * client-cached stale value would silently show an out-of-date %-remediated
 * or a stale ACTIVE/COMPLETE status, which is never acceptable for a
 * compute-on-read field.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type CampaignStatus = 'ACTIVE' | 'COMPLETE';

// CR-04 precedent (use-tickets.ts): snake_case end-to-end — the backend
// (campaigns/schemas.py CampaignSummary/CampaignDetail) emits these keys
// verbatim and api() does no casing transform.
export type CampaignSummary = {
  id: string;
  remediation_id: string;
  status: CampaignStatus;
  total: number;
  open: number;
  in_progress: number;
  done: number;
  pct_remediated: number;
};

export type CampaignDetail = CampaignSummary & {
  /** D-12: null (never 0) when no member has ever been remediated. */
  mttr_seconds: number | null;
};

export function useCampaigns() {
  return useQuery({
    queryKey: queryKeys.campaigns.list(),
    queryFn: ({ signal }) =>
      api<CampaignSummary[]>('/api/v1/campaigns', { signal }),
    staleTime: 0,
    retry: 1,
  });
}

export function useCampaignDetail(id: string | null) {
  return useQuery({
    queryKey: queryKeys.campaigns.detail(id ?? ''),
    queryFn: ({ signal }) =>
      api<CampaignDetail>(
        `/api/v1/campaigns/${encodeURIComponent(id!)}`,
        { signal },
      ),
    enabled: id !== null && id !== '',
    staleTime: 0,
    retry: 1,
  });
}
