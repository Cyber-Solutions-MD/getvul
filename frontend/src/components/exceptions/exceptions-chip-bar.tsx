'use client';
/**
 * ExceptionsChipBar — Phase 39 Plan 06 (EXC-02/EXC-03) /dashboard/exceptions
 * two-axis chip-bar: Type (False positive / Accept risk) and Scope (Finding /
 * Asset / Asset group). Mirrors campaigns-chip-bar.tsx's single-<ChipBar>
 * composition shape with a second axis added.
 *
 * T-39-22 (Tampering, 39-06-PLAN threat_model): both TYPE_ALLOW and
 * SCOPE_ALLOW are hardcoded allow-lists (T-38-09/T-12-05 precedent) — the
 * generic <ChipBar> primitive clamps any reflected URL value against them on
 * both read and write, so a value outside either list is dropped, never
 * passed through.
 */
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

const TYPE_ALLOW = ['FALSE_POSITIVE', 'ACCEPTED_RISK'] as const;

const TYPE_LABEL: Record<(typeof TYPE_ALLOW)[number], string> = {
  FALSE_POSITIVE: 'False positive',
  ACCEPTED_RISK: 'Accept risk',
};

const SCOPE_ALLOW = ['FINDING', 'ASSET', 'ASSET_GROUP'] as const;

const SCOPE_LABEL: Record<(typeof SCOPE_ALLOW)[number], string> = {
  FINDING: 'Finding',
  ASSET: 'Asset',
  ASSET_GROUP: 'Asset group',
};

export function ExceptionsChipBar() {
  const axes: ChipAxis[] = [
    {
      key: 'type',
      label: 'Type',
      allowList: TYPE_ALLOW,
      chips: TYPE_ALLOW.map((t) => ({ value: t, label: TYPE_LABEL[t] })),
    },
    {
      key: 'scope_type',
      label: 'Scope',
      allowList: SCOPE_ALLOW,
      chips: SCOPE_ALLOW.map((s) => ({ value: s, label: SCOPE_LABEL[s] })),
    },
  ];

  return (
    <ChipBar
      axes={axes}
      searchPlaceholder="Search CVE / target…"
      searchAriaLabel="Search exceptions"
    />
  );
}

export { TYPE_ALLOW as EXCEPTIONS_TYPE_ALLOW, SCOPE_ALLOW as EXCEPTIONS_SCOPE_ALLOW };
