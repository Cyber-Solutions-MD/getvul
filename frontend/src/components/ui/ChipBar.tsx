'use client';
/**
 * ChipBar — generic descriptor-driven chip filter primitive (UX-04-01).
 *
 * Phase 11 originally hardcoded severity/source axes inside
 * components/vulnerabilities/chip-bar.tsx; Phase 12-04 refactors to a
 * descriptor model so Assets (Category / Risk band / Source / OS) and any
 * future surface can reuse the same primitive.
 *
 * Visual contract is preserved 1:1 from Phase 11's vuln chip-bar:
 *  - Outer container `rounded-lg border border-border-subtle bg-surface px-3 py-2`
 *  - Separator dividers (`h-5 w-px bg-border-subtle`) between groups
 *  - Chip label+count rendered in a single text node "Label · count" with `font-mono text-text-faint`
 *  - Active chip: `border-border bg-surface-2 text-text`
 *  - Inactive chip: `border-border-subtle bg-surface text-text-muted` + violet focus ring
 *  - Saved-filter pill: violet border + violet-soft fill
 *  - Clear-all is right-anchored via `ml-auto`
 *
 * Behaviors preserved 1:1 from Phase 11:
 *  - 250ms search debounce (D-F-01)
 *  - Multi-value URL state via useUrlStateList per axis (D-F-05)
 *  - Pitfall 10 — chip click during pending debounce flushes both URL keys
 *    in one router.replace batch
 *  - Saved-filter is read-only — pill renders only when prop is provided (D-F-04)
 *  - Clear-all wipes ALL axis keys + search atomically
 *
 * T-12-05 mitigation: each ChipAxis MUST carry a hardcoded `allowList`. The
 * inner ChipGroup passes it straight into useUrlStateList, which clamps the
 * value on BOTH read and write (defense in depth against any caller that
 * bypasses the chip UI).
 *
 * T-12-13 mitigation: savedFilter.query is parsed via URLSearchParams and
 * merged into the router target. Reflected values still pass through each
 * axis's useUrlStateList read-side clamp on the next render, so any value
 * outside an axis's allowList is silently dropped before reaching the DOM.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { cn } from '@/lib/utils';

export type ChipDescriptor = {
  /** URL value persisted via useUrlStateList (must be present in allowList). */
  value: string;
  /** Visible label rendered inside the chip. */
  label: string;
  /** Optional glyph (Unicode mark) — e.g. severity ■ ▲ ◆ ○ □. */
  glyph?: string;
  /** Tailwind class applied to the glyph span (e.g. severity tint). */
  glyphClassName?: string;
};

export type ChipAxis = {
  /** URL key (e.g. 'severity', 'source', 'category', 'risk_band', 'os_family'). */
  key: string;
  /** Optional group label rendered before the chips. Hidden when omitted. */
  label?: string;
  /**
   * Hardcoded XSS allow-list — required (T-12-05). Passed verbatim into
   * useUrlStateList which clamps reflected URL values AND any toggle inputs.
   */
  allowList: readonly string[];
  /** Optional facet counts (`{ value: count }`). When omitted, chip shows label only. */
  counts?: Record<string, number>;
  /** Explicit chip set rendered for this axis (ignored when derivedFromCounts=true). */
  chips?: ChipDescriptor[];
  /**
   * D-F-03 — when true, the chip set is derived from `Object.keys(counts)` and
   * further filtered through `allowList`. Used by axes whose value space is
   * data-driven (e.g. vuln sources from facets) rather than a fixed enum.
   */
  derivedFromCounts?: boolean;
};

export type ChipBarProps = {
  axes: ChipAxis[];
  /** Saved-filter pill — renders only when supplied (D-F-04 read-only). */
  savedFilter?: { label: string; query: string } | null;
  /** Search input visibility (default true). */
  showSearch?: boolean;
  /** Placeholder microcopy for the search input (default 'Search…'). */
  searchPlaceholder?: string;
  /** Aria-label for the search input (default 'Search'). */
  searchAriaLabel?: string;
};

const SEARCH_DEBOUNCE_MS = 250;

const DIVIDER = (
  <span aria-hidden="true" className="mx-1 h-5 w-px bg-border-subtle" />
);

type ChipGroupProps = {
  axis: ChipAxis;
  /** Called immediately before the chip's URL toggle — see Pitfall 10. */
  onChipFlush: () => void;
};

function ChipGroup({ axis, onChipFlush }: ChipGroupProps) {
  // Phase 11 contract — useUrlStateList(key, allowList) handles XSS clamp on
  // both read and write. Allow-list is hardcoded at the call site, never
  // user-supplied at runtime (T-12-05).
  const [value, , toggle] = useUrlStateList<string>(axis.key, axis.allowList, []);

  // Compute chip list: either an explicit `chips` array or derived from facet
  // keys filtered by the allow-list. The derived path mirrors Phase 11's
  // `Object.keys(facets.source).map(...)` shape.
  const chips: ChipDescriptor[] = axis.derivedFromCounts
    ? Object.keys(axis.counts ?? {})
        .filter((k) => (axis.allowList as readonly string[]).includes(k))
        .map((k) => ({ value: k, label: k }))
    : (axis.chips ?? []);

  if (chips.length === 0) return null;

  return (
    <>
      {axis.label && (
        <span
          className="mr-1 text-xs uppercase tracking-wide text-text-muted"
          data-axis-label={axis.key}
        >
          {axis.label}
        </span>
      )}
      <div className="inline-flex flex-wrap items-center gap-1.5" data-axis={axis.key}>
        {chips.map((c) => {
          const active = value.includes(c.value);
          const count = axis.counts?.[c.value];
          // Phase 11 contract — label + count rendered as a single text node
          // so the test `getByText(/Critical/).textContent.toContain('12')` matches.
          const display = typeof count === 'number' ? `${c.label} · ${count}` : c.label;
          return (
            <button
              key={c.value}
              type="button"
              onClick={() => {
                onChipFlush();
                toggle(c.value);
              }}
              aria-pressed={active}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors',
                'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
                active
                  ? 'border-border bg-surface-2 text-text'
                  : 'border-border-subtle bg-surface text-text-muted hover:bg-surface-2 hover:text-text',
              )}
            >
              {c.glyph && (
                <span aria-hidden="true" className={c.glyphClassName}>
                  {c.glyph}
                </span>
              )}
              <span className="font-mono text-text-faint">{display}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

export function ChipBar({
  axes,
  savedFilter,
  showSearch = true,
  searchPlaceholder = 'Search…',
  searchAriaLabel = 'Search',
}: ChipBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // Search is free-text → can't ride useUrlState (allow-list doesn't fit).
  // Local mirror + 250ms debounced flush. Track refs so a chip click can
  // flush synchronously (Pitfall 10).
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

  const buildHref = useCallback(
    (mutate: (sp: URLSearchParams) => void): string => {
      const sp = new URLSearchParams(params?.toString() ?? '');
      mutate(sp);
      const qs = sp.toString();
      return qs ? `${pathname}?${qs}` : (pathname ?? '/');
    },
    [params, pathname],
  );

  // D-F-01 — debounce the search-to-URL flush. The 250ms idle window resets
  // on each keystroke; cleanup clears the prior timer.
  useEffect(() => {
    pendingSearchRef.current = searchInput;
    if (!showSearch) return;
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
  }, [searchInput, buildHref, router, showSearch]);

  // Pitfall 10 — chip click flushes the pending search synchronously so both
  // the search key and the axis key land in one URL batch. We write search
  // first (when pending) so the subsequent chip-toggle's router.replace
  // coalesces same-tick, matching Phase 11 chip-bar's behavior.
  const onChipFlush = useCallback(() => {
    if (!showSearch) return;
    if (searchInput === lastFlushedRef.current) return;
    const href = buildHref((sp) => {
      if (searchInput === '') sp.delete('search');
      else sp.set('search', searchInput);
    });
    lastFlushedRef.current = searchInput;
    router.replace(href, { scroll: false });
  }, [searchInput, buildHref, router, showSearch]);

  const clearAll = () => {
    setSearchInput('');
    lastFlushedRef.current = '';
    pendingSearchRef.current = '';
    const href = buildHref((sp) => {
      axes.forEach((a) => sp.delete(a.key));
      sp.delete('search');
    });
    router.replace(href, { scroll: false });
  };

  const applySavedFilter = () => {
    if (!savedFilter) return;
    // D-F-04 — saved filter is read-only; the query blob is parsed once and
    // merged into the router target. Each axis's useUrlStateList read-side
    // clamp drops any value outside its allowList on the next render
    // (T-12-13 defense in depth).
    const parsed = new URLSearchParams(savedFilter.query);
    const sp = new URLSearchParams(params?.toString() ?? '');
    axes.forEach((a) => sp.delete(a.key));
    sp.delete('search');
    parsed.forEach((value, key) => sp.append(key, value));
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : (pathname ?? '/'), { scroll: false });
  };

  return (
    <div
      role="search"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-border-subtle bg-surface px-3 py-2"
      data-chip-bar="generic"
    >
      {showSearch && (
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder={searchPlaceholder}
          aria-label={searchAriaLabel}
          className="w-[220px] bg-transparent px-2 py-1 text-sm text-text placeholder:text-text-faint focus:outline-none"
        />
      )}

      {axes.map((axis, idx) => (
        <span key={axis.key} className="contents">
          {(showSearch || idx > 0) && DIVIDER}
          <ChipGroup axis={axis} onChipFlush={onChipFlush} />
        </span>
      ))}

      {savedFilter && (
        <>
          {DIVIDER}
          <button
            type="button"
            onClick={applySavedFilter}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border border-violet bg-violet-soft px-3 py-1 text-xs font-medium text-[var(--color-violet-on-soft)]',
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet',
            )}
            data-saved-filter-pill
          >
            <span aria-hidden="true">★</span>
            <span>{savedFilter.label}</span>
          </button>
        </>
      )}

      {DIVIDER}

      <button
        type="button"
        onClick={clearAll}
        className="ml-auto inline-flex items-center rounded-md px-2 py-1 text-xs text-text-muted hover:text-pink focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet"
      >
        Clear all
      </button>
    </div>
  );
}
