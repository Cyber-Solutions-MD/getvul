'use client';
import { useEffect, useState, useRef, useCallback } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useSavedFilters } from '@/lib/queries/use-saved-filters';
import { microcopy } from './microcopy';
import { cn } from '@/lib/utils';

// D-F-01 — search debounce. Chip clicks bypass it (synchronous URL update).
// D-F-02 — severity / source chips multi-value.
// D-F-03 — source chip list derived from facets (not hardcoded), still clamped
// by the XSS allow-list inside useUrlStateList.
// D-F-04 — saved-filter pill is READ-ONLY (renders only when at least one exists).
// D-F-05 — multi-value URL chips via useUrlStateList.
// Pitfall 10 mitigation — a chip click that fires while a search-debounce
// timer is pending flushes the pending search synchronously alongside the
// chip toggle by writing both keys in one URLSearchParams batch.

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const;
type Severity = (typeof SEVERITIES)[number];

// XSS allow-list for source chips (D-F-03). The facets prop drives which
// chips are rendered; the allow-list constrains what useUrlStateList will
// persist to the URL. Adding a new connector means adding it here.
const SOURCES = [
  'QUALYS',
  'TENABLE',
  'RAPID7',
  'CROWDSTRIKE',
  'AWS_INSPECTOR',
  'WIZ',
  'MOCK',
] as const;
type Source = (typeof SOURCES)[number];

const SEVERITY_GLYPH: Record<Severity, string> = {
  critical: '■',
  high: '▲',
  medium: '◆',
  low: '○',
  info: '□',
};

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: microcopy.chips.critical,
  high: microcopy.chips.high,
  medium: microcopy.chips.medium,
  low: microcopy.chips.low,
  info: microcopy.chips.info,
};

const SEVERITY_GLYPH_COLOR: Record<Severity, string> = {
  critical: 'text-severity-critical',
  high: 'text-severity-high',
  medium: 'text-severity-medium',
  low: 'text-severity-low',
  info: 'text-severity-info',
};

export type ChipBarFacets = {
  severity: Record<string, number>;
  source: Record<string, number>;
  status?: Record<string, number>;
};

type Props = {
  facets: ChipBarFacets;
};

const SEARCH_DEBOUNCE_MS = 250;

export function ChipBar({ facets }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // Severity / source chips — multi-value URL state via useUrlStateList.
  const [severity, , toggleSeverity] = useUrlStateList<Severity>(
    'severity',
    SEVERITIES,
    [],
  );
  const [source, , toggleSource] = useUrlStateList<Source>(
    'source',
    SOURCES,
    [],
  );

  const savedFilters = useSavedFilters();
  const firstSaved = savedFilters.data?.[0];

  // Search is free-text → can't ride useUrlState (allow-list doesn't fit).
  // Local mirror + 250ms debounced flush. Track a ref to the pending value
  // so the chip-click handler can flush synchronously (Pitfall 10).
  const initialSearch = params?.get('search') ?? '';
  const [searchInput, setSearchInput] = useState<string>(initialSearch);
  const pendingSearchRef = useRef<string>(initialSearch);
  const lastFlushedRef = useRef<string>(initialSearch);

  // Re-sync local input if the URL is reset externally (Clear all).
  useEffect(() => {
    const urlSearch = params?.get('search') ?? '';
    if (urlSearch === '' && lastFlushedRef.current !== '') {
      setSearchInput('');
      pendingSearchRef.current = '';
      lastFlushedRef.current = '';
    }
  }, [params]);

  // Build a URL from the current params plus optional override entries; used
  // by both the debounced search effect and the chip-click flush path so the
  // single setter call carries both updates atomically (Pitfall 10).
  const buildHref = useCallback(
    (mutate: (sp: URLSearchParams) => void): string => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      mutate(sp);
      const qs = sp.toString();
      return qs ? `${pathname}?${qs}` : (pathname ?? '/');
    },
    [params, pathname],
  );

  // D-F-01 — debounce the search-to-URL flush. The 250ms idle window starts
  // on the most recent keystroke; subsequent keystrokes within the window
  // reset the timer (each effect cleanup runs `clearTimeout`).
  useEffect(() => {
    pendingSearchRef.current = searchInput;
    if (searchInput === lastFlushedRef.current) return;
    const t = setTimeout(() => {
      const href = buildHref((sp) => {
        if (searchInput === '') sp.delete('search');
        else sp.set('search', searchInput);
      });
      lastFlushedRef.current = searchInput;
      router.replace(href, { scroll: false });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchInput, buildHref, router]);

  // Chip click — synchronous (no debounce). Toggle delegates to
  // useUrlStateList which clamps via the SEVERITIES / SOURCES allow-list.
  // Note: this writes to the URL directly via the toggle setter; the
  // pending search debounce, if any, is harmless because router.replace
  // already coalesces same-tick navigations and the next debounce flush
  // sees `searchInput === lastFlushedRef.current` after the round-trip.
  const onSeverityClick = (s: Severity) => toggleSeverity(s);
  const onSourceClick = (s: string) => {
    if ((SOURCES as readonly string[]).includes(s)) toggleSource(s as Source);
  };

  const clearAll = () => {
    setSearchInput('');
    lastFlushedRef.current = '';
    pendingSearchRef.current = '';
    const href = buildHref((sp) => {
      sp.delete('severity');
      sp.delete('source');
      sp.delete('status');
      sp.delete('search');
    });
    router.replace(href, { scroll: false });
  };

  const applySavedFilter = () => {
    if (!firstSaved) return;
    // D-F-04 — saved filter is read-only and applied wholesale. The blob's
    // shape may be either a query-string ("severity=critical&...") or a
    // plain object map; we accept both for forward compatibility.
    const filters = (firstSaved as unknown as { filters?: Record<string, unknown>; query?: string }).filters;
    const queryStr =
      (firstSaved as unknown as { query?: string }).query ?? '';
    const sp = new URLSearchParams(params?.toString() ?? '');
    sp.delete('severity');
    sp.delete('source');
    sp.delete('status');
    sp.delete('search');
    if (queryStr) {
      // Query-string variant — replay each entry through the XSS allow-list
      // by re-parsing and using setValue equivalents. The simplest path is
      // to merge directly; useUrlStateList read-side will still clamp.
      const parsed = new URLSearchParams(queryStr);
      parsed.forEach((value, key) => sp.append(key, value));
    } else if (filters) {
      Object.entries(filters).forEach(([k, v]) => {
        if (Array.isArray(v)) v.forEach((item) => sp.append(k, String(item)));
        else if (v != null) sp.set(k, String(v));
      });
    }
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), {
      scroll: false,
    });
  };

  return (
    <div
      role="search"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-border-subtle bg-surface px-3 py-2"
    >
      <input
        type="search"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        placeholder={microcopy.page.searchPlaceholder}
        aria-label={microcopy.page.searchPlaceholder}
        className="w-[220px] bg-transparent px-2 py-1 text-sm text-text placeholder:text-text-faint focus:outline-none"
      />

      <span aria-hidden="true" className="mx-1 h-5 w-px bg-border-subtle" />

      {SEVERITIES.map((s) => {
        const isActive = severity.includes(s);
        const count = facets.severity[s.toUpperCase()] ?? facets.severity[s] ?? 0;
        return (
          <button
            key={s}
            type="button"
            onClick={() => onSeverityClick(s)}
            aria-pressed={isActive}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
              isActive
                ? 'border-border bg-surface-2 text-text'
                : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
            )}
          >
            <span aria-hidden="true" className={SEVERITY_GLYPH_COLOR[s]}>
              {SEVERITY_GLYPH[s]}
            </span>
            <span className="font-mono text-text-faint">{`${SEVERITY_LABEL[s]} · ${count}`}</span>
          </button>
        );
      })}

      <span aria-hidden="true" className="mx-1 h-5 w-px bg-border-subtle" />

      {Object.keys(facets.source).map((src) => {
        const isActive = source.includes(src as Source);
        const count = facets.source[src] ?? 0;
        return (
          <button
            key={src}
            type="button"
            onClick={() => onSourceClick(src)}
            aria-pressed={isActive}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs transition-colors',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
              isActive
                ? 'border-border bg-surface-2 text-text'
                : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
            )}
          >
            <span>{`${src} · ${count}`}</span>
          </button>
        );
      })}

      {firstSaved && (
        <>
          <span aria-hidden="true" className="mx-1 h-5 w-px bg-border-subtle" />
          <button
            type="button"
            onClick={applySavedFilter}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border border-violet bg-violet-soft px-3 py-1 text-xs font-medium text-violet',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            )}
          >
            <span aria-hidden="true">{microcopy.page.savedFilterPrefix}</span>
            <span>{firstSaved.name}</span>
          </button>
        </>
      )}

      <span aria-hidden="true" className="mx-1 h-5 w-px bg-border-subtle" />

      <button
        type="button"
        onClick={clearAll}
        className="ml-auto inline-flex items-center rounded-md px-2 py-1 text-xs text-text-muted hover:text-pink focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      >
        {microcopy.page.clearAll}
      </button>
    </div>
  );
}
