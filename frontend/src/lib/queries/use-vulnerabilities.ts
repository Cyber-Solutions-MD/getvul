import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// D-F-02 — single round-trip returns list + facets. Chip counts and table
// data update atomically; no two-query coordination problem.
export type VulnerabilitiesFilters = {
  severity?: readonly string[];
  source?: readonly string[];
  status?: readonly string[];
  search?: string;
  kev_only?: boolean;
  exploit_only?: boolean;
  // Phase 12 (D-D-01) — pre-set by useAssetVulnerabilities to scope the list to one host.
  // Backend `/api/v1/vulnerabilities` already accepts `asset_id` (verified RESEARCH §5).
  asset_id?: string;
  // Phase 44 / NLQ-01 / D-17: the two D-03 additive predicates (VulnerabilityFilter
  // already supports both; the router now binds them as Query params — see
  // backend/app/vulnerabilities/router.py) + the bounded-age param, all three
  // wired into the URL by vulnerabilities/page.tsx's useUrlStateBool/useUrlStateNumber.
  sla_breached?: boolean;
  asset_internet_facing?: boolean;
  age_days_min?: number | null;
};

export type FacetsResponse = {
  severity: Record<string, number>;
  source: Record<string, number>;
  status: Record<string, number>;
};

// Loose VulnerabilitySummary shape — locked at the backend in Plan 11-01.
// Re-declared inline because the FE types file isn't generated yet; consumers
// downstream (Plan 11-05) can narrow as needed.
export type VulnerabilitySummary = {
  id: string;
  cve_id: string | null;
  vulnerability_name: string | null;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  cvss_v3_score: number | null;
  cisa_kev: boolean;
  exploit_available: boolean;
  source: string;
  asset_id: string | null;
  asset_hostname: string | null;
  status: string;
  first_detected_at: string;
  last_seen_at: string;
  sla_due_at: string | null;
};

export type VulnerabilityByHost = {
  host: string;
  ip: string | null;
  severity_counts: { critical: number; high: number; medium: number; low: number };
  top_cve_id: string | null;
  top_cvss: number | null;
  source: string;
  last_seen_at: string;
};

export type VulnerabilitiesResponse = {
  items: VulnerabilitySummary[] | VulnerabilityByHost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: FacetsResponse;
};

// Exported so page-level + chip-bar tests can assert URL composition.
export function buildSearchParams(opts: {
  filters: VulnerabilitiesFilters;
  group: 'cve' | 'host';
  page: number;
  sort: string; // '' | 'cve_id' | 'cvss_v3_score' | 'sla_due_at' | 'severity' | 'triage'
  order: 'asc' | 'desc';
}): URLSearchParams {
  const sp = new URLSearchParams();
  opts.filters.severity?.forEach((s) => sp.append('severity', s));
  opts.filters.source?.forEach((s) => sp.append('source', s));
  opts.filters.status?.forEach((s) => sp.append('status', s));
  if (opts.filters.search) sp.set('search', opts.filters.search);
  if (opts.filters.kev_only) sp.set('cisa_kev', 'true');
  if (opts.filters.exploit_only) sp.set('exploit_available', 'true');
  if (opts.filters.asset_id) sp.set('asset_id', opts.filters.asset_id);
  if (opts.filters.sla_breached) sp.set('sla_breached', 'true');
  if (opts.filters.asset_internet_facing) sp.set('asset_internet_facing', 'true');
  if (opts.filters.age_days_min != null) sp.set('age_days_min', String(opts.filters.age_days_min));
  // D-F-02: always request facets so chip counts stay synced with the list.
  sp.set('facets', 'severity,source,status');
  if (opts.group === 'host') sp.set('group', 'host');
  sp.set('page', String(opts.page));
  if (opts.sort) {
    sp.set('sort', opts.sort);
    sp.set('order', opts.order);
  }
  return sp;
}

export function useVulnerabilities(opts: {
  filters: VulnerabilitiesFilters;
  group: 'cve' | 'host';
  page: number;
  sort: string;
  order: 'asc' | 'desc';
}) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.list({
      filters: opts.filters,
      group: opts.group,
      page: opts.page,
      sort: opts.sort,
      order: opts.order,
    }),
    queryFn: ({ signal }) =>
      api<VulnerabilitiesResponse>(
        `/api/v1/vulnerabilities?${buildSearchParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 30_000, // facets must reflect filter state without thrashing
    retry: 1, // D-D-07 — list is most-visible
    refetchOnWindowFocus: true,
  });
}
