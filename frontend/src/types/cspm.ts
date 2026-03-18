export interface MisconfigSummary {
  id: string;
  rule_id: string;
  rule_name: string;
  category: string;
  severity: string;
  source: string;
  status: string;
  resource_id: string;
  resource_name: string | null;
  resource_type: string | null;
  cloud_provider: string | null;
  first_detected_at: string;
  last_seen_at: string;
}

export interface CSPMDashboardStats {
  total_findings: number;
  open_findings: number;
  by_severity: { severity: string; count: number }[];
  by_category: { category: string; count: number }[];
  by_source: { source: string; count: number }[];
  by_cloud_provider: { provider: string; count: number }[];
  compliance_pass_rate: number | null;
}
