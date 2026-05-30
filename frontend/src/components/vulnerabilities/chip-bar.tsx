'use client';
// Phase 12-04 thin wrapper over the generic <ChipBar> at components/ui/ChipBar.tsx.
// Preserves the Phase 11 exports (`ChipBar` + `ChipBarFacets`) so the existing
// /vulnerabilities page callsite is unchanged. Owns only the vuln axes
// descriptor (severity fixed enum + source derived from facets) + saved-filter
// shape adapter. Visual contract + behavior live in the generic primitive.
import { ChipBar as GenericChipBar, type ChipAxis } from '@/components/ui/ChipBar';
import { useSavedFilters } from '@/lib/queries/use-saved-filters';
import { microcopy } from './microcopy';

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const;
type Severity = (typeof SEVERITIES)[number];

const SEVERITY_GLYPH: Record<Severity, string> = {
  critical: '■', high: '▲', medium: '◆', low: '○', info: '□',
};
const SEVERITY_GLYPH_COLOR: Record<Severity, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

// XSS allow-list for source chips (D-F-03). Adding a new connector means adding it here.
const SOURCES = ['QUALYS', 'TENABLE', 'RAPID7', 'CROWDSTRIKE', 'AWS_INSPECTOR', 'WIZ', 'MOCK'] as const;

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
    <GenericChipBar
      axes={[severityAxis, sourceAxis]}
      savedFilter={savedFilter}
      searchPlaceholder={microcopy.page.searchPlaceholder}
      searchAriaLabel={microcopy.page.searchPlaceholder}
    />
  );
}
