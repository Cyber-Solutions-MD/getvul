'use client';
/**
 * CampaignsChipBar — CAMP-01 dedicated campaign list, single `status` axis
 * (Active / Complete). Delegates to the generic <ChipBar axes={...}>
 * primitive (mirrors tickets-chip-bar.tsx's 1-axis composition shape).
 *
 * Values are the backend's literal `status` enum (`ACTIVE`/`COMPLETE`, per
 * campaigns/schemas.py's CampaignSummary), unlike tickets' lowercase
 * `external_status` convention — GET /campaigns has no server-side status
 * filter param (D-07 always returns the full tenant list), so the page
 * filters `items` client-side against this chip's URL state.
 *
 * T-38-09/T-12-05: STATUS_ALLOW is a hardcoded allow-list — the ChipBar
 * primitive clamps any reflected URL value against it on both read and write.
 */
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

const STATUS_ALLOW = ['ACTIVE', 'COMPLETE'] as const;

const STATUS_LABEL: Record<(typeof STATUS_ALLOW)[number], string> = {
  ACTIVE: 'Active',
  COMPLETE: 'Complete',
};

export function CampaignsChipBar() {
  const axes: ChipAxis[] = [
    {
      key: 'status',
      label: 'Status',
      allowList: STATUS_ALLOW,
      chips: STATUS_ALLOW.map((s) => ({ value: s, label: STATUS_LABEL[s] })),
    },
  ];

  return (
    <ChipBar
      axes={axes}
      searchPlaceholder="Search remediation label…"
      searchAriaLabel="Search campaigns"
    />
  );
}

export { STATUS_ALLOW as CAMPAIGNS_STATUS_ALLOW };
