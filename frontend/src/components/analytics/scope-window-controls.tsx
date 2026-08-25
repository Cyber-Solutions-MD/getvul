'use client';
/**
 * ScopeWindowControls — the top-of-page selector row for /dashboard/
 * analytics (Phase 42 Plan 01 shipped the WINDOW preset toggle only,
 * 7d/30d/90d/1y — TREND-01 D-03). Plan 03 completes it:
 *
 *   - D-02: a searchable scope dropdown ("All (tenant)" + every
 *     AssetGroup) that re-scopes EVERY chart on the page in one action.
 *   - D-03: a 5th "Custom range" preset revealing native `<input
 *     type="date">` From/To fields (no new date-picker dependency —
 *     mirrors exception-grant-dialog.tsx's FIELD_CLASS precedent) with
 *     client-side To>=From validation.
 *   - D-06: the mandatory group-scope caption, rendered whenever a group
 *     is selected.
 *
 * Extends `components/ui/trend-chart.tsx`'s RangeToggle (`role="group"` +
 * `aria-pressed` accessible-toggle idiom) from 3 options (Plan 01: 4) to 5.
 * Owned state lives in the page (mirrors `dashboard/trend-section.tsx`'s
 * TrendSection owning `useUrlState` and handing `range`/`onRangeChange`
 * down to TrendChart's internal dumb RangeToggle) — this component stays
 * presentational; `page.tsx` owns scope/window/customFrom/customTo state.
 */
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { isCustomRangeComplete, isCustomRangeValid, type AnalyticsWindow } from '@/lib/queries/use-analytics';
import { useAssetGroupsList } from '@/lib/queries/use-asset-groups';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { microcopy } from './microcopy';

export type ScopeValue = { type: 'all' } | { type: 'group'; groupId: string; groupName: string };

export type ScopeWindowControlsProps = {
  scope: ScopeValue;
  onScopeChange: (next: ScopeValue) => void;
  window: AnalyticsWindow;
  onWindowChange: (next: AnalyticsWindow) => void;
  customFrom: string;
  customTo: string;
  onCustomFromChange: (next: string) => void;
  onCustomToChange: (next: string) => void;
};

const WINDOW_OPTIONS: { id: AnalyticsWindow; label: string; a11y: string }[] = [
  { id: '7d', label: microcopy.window.d7, a11y: microcopy.window.d7A11y },
  { id: '30d', label: microcopy.window.d30, a11y: microcopy.window.d30A11y },
  { id: '90d', label: microcopy.window.d90, a11y: microcopy.window.d90A11y },
  { id: '1y', label: microcopy.window.y1, a11y: microcopy.window.y1A11y },
  { id: 'custom', label: microcopy.window.custom, a11y: microcopy.window.customA11y },
];

// Mirrors exception-grant-dialog.tsx:61-62's FIELD_CLASS — the codebase's
// established native <input type="date"> styling convention (39-UI-SPEC
// precedent), reused verbatim rather than adding a date-picker dependency.
const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const FIELD_LABEL_CLASS = 'mb-1 block text-xs font-semibold uppercase tracking-wide text-text-muted';

// Only show the inline search filter once the group count actually
// warrants it (UI-SPEC E1 overflow) — a short list doesn't need one.
const SEARCH_FILTER_THRESHOLD = 6;

export function ScopeWindowControls({
  scope,
  onScopeChange,
  window,
  onWindowChange,
  customFrom,
  customTo,
  onCustomFromChange,
  onCustomToChange,
}: ScopeWindowControlsProps) {
  const groupsQuery = useAssetGroupsList();
  const [search, setSearch] = useState('');

  // groupsQuery.data ?? [] is memoized too — otherwise the `?? []`
  // fallback allocates a fresh array every render, which would in turn
  // invalidate filteredGroups's own memoization below on every render.
  const groups = useMemo(() => groupsQuery.data ?? [], [groupsQuery.data]);

  const filteredGroups = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return groups;
    return groups.filter((g) => g.name.toLowerCase().includes(needle));
  }, [groups, search]);

  const triggerLabel = scope.type === 'group' ? scope.groupName : microcopy.scope.allTenantLabel;
  const showOrderError = isCustomRangeComplete(customFrom, customTo) && !isCustomRangeValid(customFrom, customTo);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={microcopy.scope.accessibleLabel}
              // UI-audit fix #4a: py-1 (4px), not py-1.5 (6px) — the 4px
              // grid, matching the sibling window-toggle buttons' own py-1
              // below (42-UI-SPEC.md Spacing Scale: "must be multiples of 4").
              className="flex max-w-[220px] items-center gap-2 rounded-md border border-border-subtle bg-surface-2 px-3 py-1 text-sm text-text hover:border-border"
            >
              {/* min-w-0 lets truncate actually shrink inside this flex row
                  (UI-SPEC E1 long-text — a long AssetGroup.name ellipsizes,
                  never overflows the trigger). */}
              <span className="min-w-0 truncate">{triggerLabel}</span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            {groups.length > SEARCH_FILTER_THRESHOLD && (
              <div className="p-1">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={microcopy.scope.searchPlaceholder}
                  aria-label={microcopy.scope.searchPlaceholder}
                  // Radix's DropdownMenu.Content owns keyboard roving-focus
                  // + typeahead on its items; stop propagation so normal
                  // typing in this field never gets hijacked into a menu
                  // navigation/close gesture (UI-SPEC E1 overflow search).
                  onKeyDown={(e) => e.stopPropagation()}
                  className="w-full rounded-md border border-border-subtle bg-surface px-2 py-1 text-xs text-text placeholder-text-faint focus:border-violet focus:outline-none"
                />
              </div>
            )}
            <DropdownMenuItem onSelect={() => onScopeChange({ type: 'all' })}>
              {microcopy.scope.allTenantLabel}
            </DropdownMenuItem>
            {filteredGroups.map((g) => (
              <DropdownMenuItem
                key={g.id}
                onSelect={() => onScopeChange({ type: 'group', groupId: g.id, groupName: g.name })}
              >
                <span className="min-w-0 truncate">{g.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div
          role="group"
          aria-label={microcopy.window.groupLabel}
          className="inline-flex rounded-md border border-border-subtle p-0.5"
        >
          {WINDOW_OPTIONS.map((o) => {
            const active = o.id === window;
            return (
              <button
                key={o.id}
                type="button"
                aria-pressed={active}
                // Verbose a11y string lives in a sr-only span — the visible
                // compact label ('7d') remains the accessible name.
                onClick={() => onWindowChange(o.id)}
                // UI-audit fix #3 (Color reserved-list item 3): the active
                // preset gets a violet underline/indicator, per
                // 42-UI-SPEC.md's "RangeToggle's existing bg-surface-2
                // text-text active chrome extended with a violet
                // underline/indicator." border-b-2 is present on every
                // button (border-transparent when inactive) so the violet
                // border never introduces a layout shift between states.
                className={cn(
                  'rounded-sm border-b-2 px-3 py-1 text-xs font-mono transition-colors',
                  active
                    ? 'border-violet bg-surface-2 text-text'
                    : 'border-transparent text-text-muted hover:text-text',
                )}
              >
                {o.label}
                <span className="sr-only">{' '}({o.a11y})</span>
              </button>
            );
          })}
        </div>
      </div>

      {window === 'custom' && (
        <div className="flex flex-wrap items-end gap-3 rounded-md border border-border-subtle bg-surface-2 p-3">
          <div>
            <label htmlFor="analytics-range-from" className={FIELD_LABEL_CLASS}>
              {microcopy.customRange.from}
            </label>
            <input
              id="analytics-range-from"
              type="date"
              value={customFrom}
              onChange={(e) => onCustomFromChange(e.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label htmlFor="analytics-range-to" className={FIELD_LABEL_CLASS}>
              {microcopy.customRange.to}
            </label>
            <input
              id="analytics-range-to"
              type="date"
              value={customTo}
              onChange={(e) => onCustomToChange(e.target.value)}
              className={FIELD_CLASS}
            />
          </div>
          {showOrderError && (
            <p role="alert" className="text-xs text-danger">
              {microcopy.customRange.orderError}
            </p>
          )}
        </div>
      )}

      {scope.type === 'group' && (
        <p className="text-xs text-text-muted">{microcopy.scope.groupCaption(scope.groupName)}</p>
      )}
    </div>
  );
}
