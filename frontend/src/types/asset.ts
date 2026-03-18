export interface AssetSummary {
  id: string;
  hostname: string | null;
  os_name: string | null;
  asset_type: string | null;
  cloud_provider: string | null;
  seen_by_sources: string[] | null;
  risk_score: number | null;
  open_vuln_count: number;
}
