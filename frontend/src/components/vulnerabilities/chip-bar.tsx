'use client';
// Phase 12-04 thin wrapper over the generic <ChipBar> at components/ui/ChipBar.tsx.
// Preserves the Phase 11 exports (`ChipBar` + `ChipBarFacets`) so the existing
// /vulnerabilities page callsite is unchanged. Owns only the vuln axes
// descriptor (severity fixed enum + source derived from facets) + saved-filter
// shape adapter. Visual contract + behavior live in the generic primitive.
import { ChipBar as GenericChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import { useSavedFilters } from '@/lib/queries/use-saved-filters';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { cn } from '@/lib/utils';
import { microcopy } from './microcopy';

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const;
type Severity = (typeof SEVERITIES)[number];

const SEVERITY_GLYPH: Record<Severity, string> = {
  critical: '■', high: '▲', medium: '◆', low: '○', info: '□',
};
const SEVERITY_GLYPH_COLOR: Record<Severity, string> = {
  critical: 'text-[var(--color-severity-critical-on-soft)]',
  high: 'text-[var(--color-severity-high-on-soft)]',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

// XSS allow-list for source chips (D-F-03). Reconciled to the real backend
// VulnSource enum (vulnerabilities/models.py:32-38) — Phase 35 SRC-06/CONTEXT
// dropped the non-existent placeholder scanner values this list previously
// carried and added the two real connectors it was missing entirely.
const SOURCES = ['CROWDSTRIKE', 'NESSUS', 'DEFENDER', 'WIZ', 'QUALYS', 'RAPID7'] as const;

// Phase 35 SRC-02/03/04: OR (any selected source) is the default; AND
// (corroborated by ALL selected sources) is an explicit opt-in toggle, bound
// to ?source_mode via the same singular useUrlState sibling hook `?order=`
// already uses. Disabled below 2 selected sources (Pitfall 1) — AND with
// fewer than 2 sources is a documented no-op on the backend (35-01), so the
// toggle is kept inert rather than letting the analyst flip a control with
// no observable effect.
const SOURCE_MODES = ['or', 'and'] as const;

export type ChipBarFacets = {
  severity: Record<string, number>;
  source: Record<string, number>;
  status?: Record<string, number>;
};

type Props = { facets: ChipBarFacets };
type SavedFilterRow = { name?: string; query?: string; filters?: Record<string, unknown> };

// Backend may key severity counts in UPPER or lower case depending on aggregation path.
const sevCount = (f: ChipBarFacets, k: Severity) => f.severity[k.toUpperCase()] ?? f.severity[k] ?? 0;

// D-F-04 — saved filter is read-only. Supports both `query` (preferred) and `filters`
// (blob) shapes; the blob path serializes via URLSearchParams for forward-compat.
function savedQuery(row: SavedFilterRow): string {
  if (row.query) return row.query;
  if (!row.filters) return '';
  const sp = new URLSearchParams();
  Object.entries(row.filters).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach((item) => sp.append(k, String(item)));
    else if (v != null) sp.set(k, String(v));
  });
  return sp.toString();
}

export function ChipBar({ facets }: Props) {
  const savedFilters = useSavedFilters();
  const firstSaved = savedFilters.data?.[0] as SavedFilterRow | undefined;

  // SRC-04 / Pitfall 1 — the AND toggle only has an observable effect once
  // 2+ sources are selected (the backend treats AND-with-<2 as a documented
  // OR no-op, 35-01). Read the same `?source=` list the source axis chips
  // write to, so the toggle disables itself the instant the analyst drops
  // below 2 selections.
  const [selectedSources] = useUrlStateList('source', SOURCES, []);
  const [sourceMode, setSourceMode] = useUrlState('source_mode', SOURCE_MODES, 'or');
  const sourceModeDisabled = selectedSources.length < 2;
  const sourceModeIsAnd = sourceMode === 'and';

  const severityAxis: ChipAxis = {
    key: 'severity',
    allowList: SEVERITIES,
    counts: Object.fromEntries(SEVERITIES.map((s) => [s, sevCount(facets, s)])),
    chips: SEVERITIES.map((s) => ({
      value: s,
      label: microcopy.chips[s],
      glyph: SEVERITY_GLYPH[s],
      glyphClassName: SEVERITY_GLYPH_COLOR[s],
    })),
  };

  const sourceAxis: ChipAxis = {
    key: 'source',
    allowList: SOURCES,
    counts: facets.source,
    derivedFromCounts: true,
  };

  const savedFilter = firstSaved
    ? { label: firstSaved.name ?? 'Saved', query: savedQuery(firstSaved) }
    : null;

  return (
    <div className="flex flex-col gap-2">
      <GenericChipBar
        axes={[severityAxis, sourceAxis]}
        savedFilter={savedFilter}
        searchPlaceholder={microcopy.page.searchPlaceholder}
        searchAriaLabel={microcopy.page.searchPlaceholder}
      />
      {/* SRC-02/03/04 — OR/AND toggle, sibling to the source axis (ChipAxis
          has no mode field, so this can't be an axis chip). Disabled below 2
          selected sources — a no-op AND is worse UX than an inert control. */}
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
