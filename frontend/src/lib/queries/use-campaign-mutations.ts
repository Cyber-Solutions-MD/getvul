'use client';
/**
 * useCampaignMutations — Phase 38 Plan 05 (CAMP-01/02/04 UI mutations).
 *
 * Three hooks, all mirroring use-reassign-asset.ts / use-mark-blocked.ts's
 * shape (useMutation + useToast, retry: 0 — BL-06 inheritance: mutations
 * are never silently retried, audit attribution > convenience):
 *
 *   useStartCampaign  — POST /api/v1/campaigns (D-11 get-or-create; routes
 *                        to the detail page either way, swaps toast copy
 *                        on already_existed).
 *   useBulkAssign     — POST /api/v1/campaigns/{id}/bulk-assign (CAMP-02
 *                        "Create tickets" CTA).
 *   useCloseCampaign  — POST /api/v1/campaigns/{id}/close (CAMP-04 manual
 *                        early close, always gated behind a destructive
 *                        ConfirmModal by the caller — never a bare click).
 *
 * T-38-02 (mass assignment): every mutationFn body sends ONLY the fields
 * the backend's `extra="forbid"` schemas declare — never a spread of
 * arbitrary caller state.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

export type CampaignCreateResponse = {
  id: string;
  remediation_id: string;
  already_existed: boolean;
};

export type BulkAssignResponse = {
  created_tickets: number;
  tickets_linked: number;
  adopted: number;
  owners: number;
  /** D-08: `null` entries are the unassigned bucket — render as "Unassigned". */
  failed_owners: (string | null)[];
};

export type CloseCampaignResponse = {
  status: string;
};

/**
 * useStartCampaign — POST /api/v1/campaigns.
 *
 * D-11 get-or-create: `already_existed=true` means the backend opened a
 * pre-existing ACTIVE campaign instead of creating a new one. The UI routes
 * to the detail page in BOTH cases, only the toast copy differs — the
 * already-existed branch fires the exact D-11 redirect toast (info-toned,
 * 6s auto-dismiss per state-patterns.md's toast convention), verbatim from
 * 38-UI-SPEC.md's Copywriting Contract.
 */
export function useStartCampaign() {
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<CampaignCreateResponse, Error, string>({
    mutationFn: (remediationId) =>
      api<CampaignCreateResponse>('/api/v1/campaigns', {
        method: 'POST',
        body: JSON.stringify({ remediation_id: remediationId }),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: (data, remediationId) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.all });
      if (data.already_existed) {
        toast({
          variant: 'info',
          message: `Campaign already running for ${remediationId} — opening it.`,
          duration: 6000,
        });
      } else {
        toast({ variant: 'success', message: `Campaign started for ${remediationId}.` });
      }
      router.push(`/dashboard/campaigns/${data.id}`);
    },
    onError: () => {
      toast({ variant: 'error', message: "Couldn't start campaign — try again." });
    },
    retry: 0,
  });
}

export type BulkAssignVars = {
  campaignId: string;
  provider: string;
  projectKey: string;
  dueDays?: number | null;
};

/**
 * useBulkAssign — POST /api/v1/campaigns/{campaignId}/bulk-assign.
 *
 * Always fires the "{N} tickets created, {M} adopted." confirmation toast
 * on a successful (2xx) response, regardless of `failed_owners` — the
 * caller (campaign detail page) is responsible for ALSO rendering the
 * amber partial-failure banner when `failed_owners.length > 0` (never red
 * — the campaign itself isn't broken, per UI-SPEC).
 */
export function useBulkAssign() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<BulkAssignResponse, Error, BulkAssignVars>({
    mutationFn: ({ campaignId, provider, projectKey, dueDays }) =>
      api<BulkAssignResponse>(`/api/v1/campaigns/${campaignId}/bulk-assign`, {
        method: 'POST',
        body: JSON.stringify({
          provider,
          project_key: projectKey,
          due_days: dueDays ?? null,
        }),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: (data, { campaignId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.list() });
      toast({
        variant: 'success',
        message: `${data.created_tickets} tickets created, ${data.adopted} adopted.`,
      });
    },
    onError: () => {
      toast({ variant: 'error', message: "Couldn't create tickets — try again." });
    },
    retry: 0,
  });
}

/**
 * useCloseCampaign — POST /api/v1/campaigns/{campaignId}/close.
 *
 * Callers MUST route this through a destructive confirmation (ConfirmModal
 * variant="danger") — never invoke `.mutate()` from a bare click handler.
 */
export function useCloseCampaign() {
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation<CloseCampaignResponse, Error, string>({
    mutationFn: (campaignId) =>
      api<CloseCampaignResponse>(`/api/v1/campaigns/${campaignId}/close`, {
        method: 'POST',
      }),
    onSuccess: (_data, campaignId) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.list() });
    },
    onError: () => {
      toast({ variant: 'error', message: "Couldn't close campaign — try again." });
    },
    retry: 0,
  });
}
