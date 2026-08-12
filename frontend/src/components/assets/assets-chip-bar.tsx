'use client';
/**
 * AssetsChipBar — UX-04-01 chip-bar, now 5 axes (Category / Risk band /
 * Scanner / Enrichment / OS family) after the Phase 35 SRC-06 partition.
 *
 * Delegates to the generic <ChipBar axes={...}> primitive from Plan 12-04. Each axis
 * carries a hardcoded allowList per T-12-05 (Phase 11 XSS clamp pattern).
 *
 * Axes:
 *   1. Category         — Workstation / Server / Network / Mobile / Other (URL key `category`)
 *   2. Risk band         — Critical / High / Medium / Low (URL key `risk_band`)
 *   3. Scanner            — facet-derived, real 6-value VulnSource set (URL key `scanner`)
 *   4. Enrichment source — facet-derived, JAMF/HUMAANS/INTUNE (URL key `enrichment_source`)
 *   5. OS family         — Linux / Windows / macOS / Other (URL key `os_family`)
 *
 * Phase 35 SRC-06: the Assets scanner-source filter and its non-scanner
 * enrichment sources (device-management/HR presence facts) are different
 * provenance classes and must never be conflated in the UI or query — see
 * `backend/app/assets/constants.py` (SCANNER_SOURCES/ENRICHMENT_SOURCES,
 * Plan 03) for the backend partition this axis split mirrors.
 *
 * Phase 35 SRC-02/03/04: the `scanner` axis additionally exposes an OR/AND
 * `?source_mode` toggle (mirrors the vuln chip-bar's Plan-02 pattern
 * verbatim) — disabled below 2 selected scanners (Pitfall 1), since the
 * backend documents AND-with-<2 as a no-op. The `enrichment_source` facet is
 * plain-OR only; there is no AND-corroboration concept for presence facts.
 *
 * Saved-filter pill is intentionally not wired here (read-only deferred per
 * CONTEXT.md D-L-04 — backend `/assets/saved-filters` does not exist yet).
 */
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { cn } from '@/lib/utils';
import { microcopy } from './microcopy';

const CATEGORIES = ['WORKSTATION', 'SERVER', 'NETWORK', 'MOBILE', 'OTHER'] as const;
const RISK_BANDS = ['critical', 'high', 'medium', 'low'] as const;
// Phase 35 SRC-03/06: reconciled to the real 6-value VulnSource enum
// (backend/app/assets/constants.py::SCANNER_SOURCES) — the pre-Phase-35
// fake placeholder scanner values are gone (see 35-CONTEXT.md).
const SCANNER_SOURCES = ['CROWDSTRIKE', 'NESSUS', 'DEFENDER', 'WIZ', 'QUALYS', 'RAPID7'] as const;
// Non-scanner enrichment sources (device-management/HR presence facts) —
// backend/app/assets/constants.py::ENRICHMENT_SOURCES. Plain OR facet, no
// AND-corroboration toggle (SRC-06).
const ENRICHMENT_SOURCES = ['JAMF', 'HUMAANS', 'INTUNE'] as const;
const OS_FAMILIES = ['linux', 'windows', 'macos', 'other'] as const;
// Phase 35 SRC-04: OR (any selected scanner, default) vs AND (seen by ALL
// selected scanners — true multi-scanner corroboration).
const SOURCE_MODES = ['or', 'and'] as const;

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
  scanner?: Record<string, number>;
  enrichment_source?: Record<string, number>;
  category?: Record<string, number>;
};

type Props = { facets?: AssetsChipBarFacets };

export function AssetsChipBar({ facets }: Props) {
  // SRC-04 / Pitfall 1 — the AND toggle only has an observable effect once
  // 2+ scanners are selected (the backend treats AND-with-<2 as a
  // documented OR no-op, 35-03). Read the same `?scanner=` list the scanner
  // axis chips write to, so the toggle disables itself the instant the
  // analyst drops below 2 selections.
  const [selectedScanners] = useUrlStateList('scanner', SCANNER_SOURCES, []);
  const [sourceMode, setSourceMode] = useUrlState('source_mode', SOURCE_MODES, 'or');
  const sourceModeDisabled = selectedScanners.length < 2;
  const sourceModeIsAnd = sourceMode === 'and';

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
      key: 'scanner',
      label: microcopy.chips.scanner,
      allowList: SCANNER_SOURCES,
      counts: facets?.scanner,
      derivedFromCounts: true,
    },
    {
      key: 'enrichment_source',
      label: microcopy.chips.enrichment_source,
      allowList: ENRICHMENT_SOURCES,
      counts: facets?.enrichment_source,
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
  return (
    <div className="flex flex-col gap-2">
      <ChipBar axes={axes} searchPlaceholder="Search hostname or OS…" />
      {/* SRC-02/03/04 — OR/AND toggle, sibling to the scanner axis (ChipAxis
          has no mode field, so this can't be an axis chip). Disabled below 2
          selected scanners — a no-op AND is worse UX than an inert control.
          Mirrors chip-bar.tsx's (Plan 02) toggle shape + copy verbatim. */}
      <div className="flex items-center gap-2 px-1">
        <span className="text-xs uppercase tracking-wide text-text-muted">
          {microcopy.chips.sourceModeLabel}
        </span>
        <button
          type="button"
          onClick={() => setSourceMode(sourceModeIsAnd ? 'or' : 'and')}
          disabled={sourceModeDisabled}
          aria-pressed={sourceModeIsAnd}
          title={sourceModeDisabled ? microcopy.chips.sourceModeDisabledHint : undefined}
          data-source-mode-toggle
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            'disabled:cursor-not-allowed disabled:opacity-50',
            sourceModeIsAnd
              ? 'border-border bg-surface-2 text-text'
              : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
          )}
        >
          {sourceModeIsAnd ? microcopy.chips.sourceModeAll : microcopy.chips.sourceModeAny}
        </button>
      </div>
    </div>
  );
}
