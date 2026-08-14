/**
 * use-tenant-settings.ts — TanStack hooks for /tenant/settings surface.
 *
 * Hooks:
 *   useTenantSettings       — GET /api/v1/tenant/settings (Admin-gated)
 *   useUpdateTenantSettings — PATCH /api/v1/tenant/settings (Owner-gated, partial)
 *
 * Security (T-14-16):
 *   The backend enforces require_admin for GET and require_owner for PATCH.
 *   Frontend RBAC gating (sidebar) is a UX layer only — backend 403 is
 *   authoritative. This hook surfaces errors via toast so the pane can render
 *   PartialFailureBanner on 403.
 *
 * Security (T-14-18 / D-SET-07):
 *   sso_enforced=true without a non-LOCAL idp_provider is rejected by the
 *   backend. The SamlPane enforces this locally as a UX courtesy; the hook
 *   does not re-validate — that is the pane's responsibility.
 *
 * Plan 14-05.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';
import { useToast } from '@/components/ui/ToastProvider';

// ── Types ─────────────────────────────────────────────────────────────────────

export type PasswordPolicy = {
  min_length: number;
  require_uppercase: boolean;
  require_lowercase: boolean;
  require_digit: boolean;
  require_symbol: boolean;
  history_count: number;
};

export type SyslogConfig = {
  enabled: boolean;
  host: string;
  port: number;
  protocol: 'udp' | 'tcp';
  facility: string;
} | null;

export type SmtpConfig = {
  host: string;
  port: number;
  username: string;
  /** Backend returns "••••••••" (8 bullets) as mask; never the real secret. */
  password: string;
  from_email: string;
  tls: boolean;
  use_starttls?: boolean;
} | null;

// Phase 36 (SLA-01/SLA-03, D-10): shape of Tenant.sla_config as returned by
// GET /tenant/settings (masked secrets) / accepted by PATCH (mirrors
// backend/app/tenants/router.py's SlaConfigUpdate + nested models). Loosely
// typed (all-optional) since the JSONB column may be null/partial for a
// tenant that hasn't configured this yet.
export type SlaWebhookChannelConfig = { enabled: boolean; url?: string } | null;
export type SlaPagerDutyChannelConfig = { enabled: boolean; routing_key?: string } | null;
export type SlaEmailChannelConfig = { enabled: boolean; to?: string[] } | null;
export type SlaChannelsConfig = {
  slack?: SlaWebhookChannelConfig;
  teams?: SlaWebhookChannelConfig;
  pagerduty?: SlaPagerDutyChannelConfig;
  email?: SlaEmailChannelConfig;
} | null;
export type SlaRoutingConfig = { approaching?: string[]; breached?: string[] } | null;
export type SlaTierPolicyConfig = { critical?: number; high?: number; moderate?: number } | null;
export type SlaConfig = {
  tier_policy?: SlaTierPolicyConfig;
  approaching_pct?: number;
  tier_floor?: 'critical' | 'high' | 'moderate';
  channels?: SlaChannelsConfig;
  routing?: SlaRoutingConfig;
} | null;

export type TenantSettings = {
  sso_enforced: boolean;
  /** "LOCAL" | "GOOGLE" | "AZURE" */
  idp_provider: string;
  domain: string | null;
  timezone: string;
  password_policy: PasswordPolicy;
  syslog_config: SyslogConfig;
  smtp_config: SmtpConfig;
  sla_config: Record<string, unknown> | null;
  branding: Record<string, unknown> | null;
};

export type TenantSettingsPatch = Partial<{
  sso_enforced: boolean;
  name: string;
  domain: string;
  idp_provider: string;
  slug: string;
  timezone: string;
  password_policy: Partial<PasswordPolicy>;
  syslog_config: Record<string, unknown>;
  smtp_config: Record<string, unknown>;
  sla_config: Record<string, unknown>;
  branding: Record<string, unknown>;
}>;

// ── Hooks ─────────────────────────────────────────────────────────────────────

/**
 * useTenantSettings — GET /api/v1/tenant/settings.
 * Requires Admin role (backend-enforced). staleTime 60s.
 */
export function useTenantSettings() {
  return useQuery({
    queryKey: queryKeys.settings.tenant(),
    queryFn: ({ signal }) =>
      api<TenantSettings>('/api/v1/tenant/settings', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}

/**
 * useUpdateTenantSettings — PATCH /api/v1/tenant/settings.
 * Requires Owner role (backend-enforced).
 * On success: invalidates queryKeys.settings.tenant + toasts "Settings updated."
 * On error: toasts the error message (e.g. 403 "You don't have permission…").
 */
export function useUpdateTenantSettings() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: (patch: TenantSettingsPatch) =>
      api<{ message: string }>('/api/v1/tenant/settings', {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.settings.tenant() });
      toast({ variant: 'success', message: 'Settings updated.' });
    },
    onError: (err: Error) => {
      const msg =
        err.message?.includes('403') || err.message?.toLowerCase().includes('forbidden')
          ? "You don't have permission to change settings."
          : err.message || 'Could not save settings. Try again.';
      toast({ variant: 'error', message: msg });
    },
    retry: 0,
  });
}
