import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

// Phase 12 D-D-01 — list endpoint for /assets surface.
// buildSearchParams is co-located + exported so URL-shape tests can assert
// the wire contract without spinning up TanStack (Phase 11 D-D-03 pattern).
export type AssetsFilters = {
  category?: readonly string[];
  risk_band?: readonly string[];
  source?: readonly string[];
  os_family?: readonly string[];
  search?: string;
};

export type AssetSummary = {
  id: string;
  hostname: string | null;
  os_name: string | null;
  device_category: string | null;
  risk_score: number | null;
  seen_by_sources: string[] | Record<string, unknown>;
  assigned_user: string | null;
  tags: string[] | null;
  total_vulns: number;
  critical: number;
  high: number;
  exploitable: number;
  kev: number;
  sla_breach_count: number;
};

export type AssetsResponse = {
  items: AssetSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export function buildSearchParams(opts: {
  filters: AssetsFilters;
  page: number;
  sort: string;
  order: 'asc' | 'desc';
}): URLSearchParams {
  const sp = new URLSearchParams();
  // Category → backend `device_category` accepts CSV (existing surface).
  if (opts.filters.category && opts.filters.category.length > 0) {
    sp.set('device_category', opts.filters.category.join(','));
  }
  // Risk band → backend `min_risk` threshold (existing surface).
  // 'critical' → 80, 'high' → 50, 'medium' → 20, 'low' → 0.
  // Multiple bands selected: send the LOWEST threshold so any band matches.
  if (opts.filters.risk_band && opts.filters.risk_band.length > 0) {
    const thresholds: Record<string, number> = {
      critical: 80,
      high: 50,
      medium: 20,
      low: 0,
    };
    const min = Math.min(
      ...opts.filters.risk_band.map((b) => thresholds[b] ?? 0)
    );
    if (min > 0) sp.set('min_risk', String(min));
  }
  // Source → backend `scanner` accepts CSV (existing surface).
  if (opts.filters.source && opts.filters.source.length > 0) {
    sp.set('scanner', opts.filters.source.join(','));
  }
  // W4 — backend list_assets accepts a comma-separated os_family value (12-01 Task 2).
  // Multi-select chip selections all flow through; backend OR-joins the patterns.
  if (opts.filters.os_family && opts.filters.os_family.length > 0) {
    sp.set('os_family', opts.filters.os_family.join(','));
  }
  if (opts.filters.search) sp.set('search', opts.filters.search);
  sp.set('page', String(opts.page));
  if (opts.sort) {
    sp.set('sort_by', opts.sort);
    sp.set('sort_dir', opts.order);
  }
  return sp;
}

export function useAssets(opts: {
  filters: AssetsFilters;
  page: number;
  sort: string;
  order: 'asc' | 'desc';
}) {
  return useQuery({
    queryKey: queryKeys.assets.list({
      filters: opts.filters,
      page: opts.page,
      sort: opts.sort,
      order: opts.order,
    }),
    queryFn: ({ signal }) =>
      api<AssetsResponse>(
        `/api/v1/assets?${buildSearchParams(opts).toString()}`,
        { signal }
      ),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: true,
  });
}
