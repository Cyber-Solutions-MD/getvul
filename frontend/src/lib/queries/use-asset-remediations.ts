import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Phase 12 D-D-02 — remediation timeline on /assets/[id].
// Backend route: GET /api/v1/tickets?asset_id=<id> (filter extension added in
// Plan 12-02 Task 2). Ordered by ticket_created_at desc on the backend.
export type RemediationTicket = {
  id: string;
  provider: string | null;
  external_ticket_url: string | null;
  external_status: string | null;
  assignee: string | null;
  title: string | null;
  subtitle: string | null;
  max_severity: string | null;
  vuln_count: number;
  critical_count: number;
  high_count: number;
  ticket_created_at: string | null;
  resolved_at: string | null;
};

export type RemediationsResponse = {
  items: RemediationTicket[];
  total: number;
  page: number;
  page_size: number;
  // Backend ticketing/service.py returns "pages" (not "total_pages").
  pages: number;
};

export function useAssetRemediations(assetId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.assets.remediations(assetId ?? ''),
    queryFn: ({ signal }) => {
      // WR-05: build the URL via URLSearchParams so any future caller passing
      // a non-UUID assetId can't silently corrupt the URL with reserved
      // characters (&, #, ?, whitespace). UUIDs are safe today; this is
      // hygiene consistency with buildSearchParams in use-assets / use-vulns.
      const sp = new URLSearchParams();
      sp.set('asset_id', assetId!);
      sp.set('page', '1');
      return api<RemediationsResponse>(
        `/api/v1/tickets?${sp.toString()}`,
        { signal },
      );
    },
    enabled: !!assetId,
    staleTime: 30_000,
    retry: 1,
  });
}
