'use client';
/**
 * AssetsChipBar — UX-04-01 chip-bar with 4 axes (Category / Risk band / Source / OS family).
 *
 * Delegates to the generic <ChipBar axes={...}> primitive from Plan 12-04. Each axis
 * carries a hardcoded allowList per T-12-05 (Phase 11 XSS clamp pattern).
 *
 * Axes:
 *   1. Category  — Workstation / Server / Network / Mobile / Other (URL key `category`)
 *   2. Risk band — Critical / High / Medium / Low (URL key `risk_band`)
 *   3. Source    — facet-derived; rendered only when present in counts (URL key `source`)
 *   4. OS family — Linux / Windows / macOS / Other (URL key `os_family`)
 *
 * Saved-filter pill is intentionally not wired here (read-only deferred per
 * CONTEXT.md D-L-04 — backend `/assets/saved-filters` does not exist yet).
 */
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import { microcopy } from './microcopy';

const CATEGORIES = ['WORKSTATION', 'SERVER', 'NETWORK', 'MOBILE', 'OTHER'] as const;
const RISK_BANDS = ['critical', 'high', 'medium', 'low'] as const;
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;
const OS_FAMILIES = ['linux', 'windows', 'macos', 'other'] as const;

const CATEGORY_LABEL: Record<(typeof CATEGORIES)[number], string> = {
  WORKSTATION: 'Workstation',
  SERVER: 'Server',
  NETWORK: 'Network',
  MOBILE: 'Mobile',
  OTHER: 'Other',
};

const RISK_LABEL: Record<(typeof RISK_BANDS)[number], string> = {
  critical: 'Critical · 80–100',
  high: 'High · 50–79',
  medium: 'Medium · 20–49',
  low: 'Low · 0–19',
};

const OS_LABEL: Record<(typeof OS_FAMILIES)[number], string> = {
  linux: 'Linux',
  windows: 'Windows',
  macos: 'macOS',
  other: 'Other',
};

export type AssetsChipBarFacets = {
  source?: Record<string, number>;
  category?: Record<string, number>;
};

type Props = { facets?: AssetsChipBarFacets };

export function AssetsChipBar({ facets }: Props) {
  const axes: ChipAxis[] = [
    {
      key: 'category',
      label: microcopy.chips.category,
      allowList: CATEGORIES,
      counts: facets?.category,
      chips: CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABEL[c] })),
    },
    {
      key: 'risk_band',
      label: microcopy.chips.risk_band,
      allowList: RISK_BANDS,
      chips: RISK_BANDS.map((b) => ({ value: b, label: RISK_LABEL[b] })),
    },
    {
      key: 'source',
      label: microcopy.chips.source,
      allowList: SOURCES,
      counts: facets?.source,
      derivedFromCounts: true,
    },
    {
      key: 'os_family',
      label: microcopy.chips.os_family,
      allowList: OS_FAMILIES,
      chips: OS_FAMILIES.map((o) => ({ value: o, label: OS_LABEL[o] })),
    },
  ];
  // Backend list_assets searches hostname + os_name only (router.py:88-89).
  // Keep the placeholder honest — IP / tag search is a deferred enhancement.
  return <ChipBar axes={axes} searchPlaceholder="Search hostname or OS…" />;
}
