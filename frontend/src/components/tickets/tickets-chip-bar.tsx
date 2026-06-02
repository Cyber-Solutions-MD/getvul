'use client';
/**
 * TicketsChipBar — UX-05-01 chip-bar with 4 axes (Status / Provider / Severity / SLA).
 *
 * Delegates to the generic <ChipBar axes={...}> primitive (Phase 12 Plan 04).
 * Each axis carries a hardcoded allowList per T-12-05 (Phase 11 XSS clamp pattern).
 *
 * Axes:
 *   1. Status   — Open / In progress / Completed / Blocked (URL key `status`)
 *   2. Provider — Jira / Asana / GitHub; only renders providers present in data (URL key `provider`)
 *   3. Severity — Critical / High / Medium / Low (URL key `severity`)
 *   4. SLA      — Overdue / Soon / OK (single-select, URL key `sla`)
 *
 * D-L-04: Search matches ID + title + assignee with 250ms debounce (inherited from ChipBar).
 * T-12-05: Each axis allowList is hardcoded — user-controlled URL values are clamped.
 */
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

// Hardcoded allow-lists per T-12-05. Reflected URL values outside these lists
// are silently dropped by useUrlStateList (D-F-05 XSS clamp pattern).
const STATUS_ALLOW = ['open', 'in_progress', 'completed', 'blocked'] as const;
const PROVIDER_ALLOW = ['jira', 'asana', 'github'] as const;
const SEVERITY_ALLOW = ['critical', 'high', 'medium', 'low'] as const;
const SLA_ALLOW = ['overdue', 'soon', 'ok'] as const;

const STATUS_LABEL: Record<(typeof STATUS_ALLOW)[number], string> = {
  open: 'Open',
  in_progress: 'In progress',
  completed: 'Completed',
  blocked: 'Blocked',
};

const PROVIDER_LABEL: Record<(typeof PROVIDER_ALLOW)[number], string> = {
  jira: 'Jira',
  asana: 'Asana',
  github: 'GitHub',
};

const SEVERITY_LABEL: Record<(typeof SEVERITY_ALLOW)[number], string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

const SLA_LABEL: Record<(typeof SLA_ALLOW)[number], string> = {
  overdue: 'Overdue',
  soon: 'Soon',
  ok: 'OK',
};

export type TicketsChipBarFacets = {
  /** Provider values present in data (D-L-04: only render providers with synced tickets). */
  provider?: string[];
};

type Props = { facets?: TicketsChipBarFacets };

export function TicketsChipBar({ facets }: Props) {
  // Provider axis is data-driven: only render providers actually present in the data.
  // When no facets, render all three as a static fallback (chips will show with no count).
  const providerFacetCounts: Record<string, number> | undefined = facets?.provider
    ? Object.fromEntries(facets.provider.map((p) => [p, 1]))
    : undefined;

  // When no facet counts given, show all three providers statically.
  const providerChips = (providerFacetCounts
    ? Object.keys(providerFacetCounts)
        .filter((p) => (PROVIDER_ALLOW as readonly string[]).includes(p))
    : [...PROVIDER_ALLOW]
  ).map((p) => ({
    value: p,
    label: PROVIDER_LABEL[p as (typeof PROVIDER_ALLOW)[number]] ?? p,
  }));

  const axes: ChipAxis[] = [
    {
      key: 'status',
      label: 'Status',
      allowList: STATUS_ALLOW,
      chips: STATUS_ALLOW.map((s) => ({ value: s, label: STATUS_LABEL[s] })),
    },
    {
      key: 'provider',
      label: 'Provider',
      allowList: PROVIDER_ALLOW,
      chips: providerChips,
    },
    {
      key: 'severity',
      label: 'Severity',
      allowList: SEVERITY_ALLOW,
      chips: SEVERITY_ALLOW.map((s) => ({ value: s, label: SEVERITY_LABEL[s] })),
    },
    {
      key: 'sla',
      label: 'SLA',
      allowList: SLA_ALLOW,
      chips: SLA_ALLOW.map((s) => ({ value: s, label: SLA_LABEL[s] })),
    },
  ];

  return (
    <ChipBar
      axes={axes}
      searchPlaceholder="Search ID, title, or assignee…"
      searchAriaLabel="Search tickets"
    />
  );
}
