export interface AssetSummary {
  id: string;
  hostname: string | null;
  os_name: string | null;
  os_version: string | null;
  asset_type: string | null;
  cloud_provider: string | null;
  seen_by_sources: string[] | null;
  risk_score: number | null;
  open_vuln_count: number;
  critical_count: number;
  high_count: number;
  exploitable_count: number;
  kev_count: number;
}

export interface AssetStats {
  total_assets: number;
  average_risk_score: number;
  by_os: { os: string; count: number }[];
  by_risk_range: { range: string; count: number }[];
  scanner_coverage: Record<string, number>;
}
