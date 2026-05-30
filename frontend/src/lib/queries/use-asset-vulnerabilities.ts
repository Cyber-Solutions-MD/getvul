import { useVulnerabilities, type VulnerabilitiesResponse } from './use-vulnerabilities';

/**
 * useAssetVulnerabilities — UX-04-02 main column data source.
 *
 * Thin wrapper over Phase 11's useVulnerabilities that pre-sets
 * filters.asset_id. The Phase 11 hook is the single source of truth for vuln
 * listing; the TanStack cache key naturally differentiates a per-asset query
 * from the global /vulnerabilities list because filters.asset_id is part of
 * the cache key (queryKeys.vulnerabilities.list({ filters, ... })).
 *
 * Returns the same VulnerabilitiesResponse shape — consumers just narrow on
 * items[].asset_hostname / id if they need to.
 *
 * Backend route: GET /api/v1/vulnerabilities?asset_id=<id>&... — verified
 * accepts asset_id in RESEARCH §5 (and threaded by 12-05 Task 1).
 */
export function useAssetVulnerabilities(assetId: string | null | undefined) {
  return useVulnerabilities({
    filters: assetId ? { asset_id: assetId } : {},
    group: 'cve',
    page: 1,
    sort: '',
    order: 'desc',
  });
}

export type { VulnerabilitiesResponse };
