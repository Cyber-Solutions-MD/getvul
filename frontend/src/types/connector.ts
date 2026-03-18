export interface ConnectorType {
  type: string;
  name: string;
  fields: string[];
  defaults: Record<string, string>;
}

export interface ConnectorConfig {
  id: string;
  connector_type: string;
  connector_name: string;
  is_enabled: boolean;
  config: Record<string, string>;
  has_credentials: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_record_count: number | null;
  sync_interval_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorTestResult {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}
