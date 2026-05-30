---
phase: 12-assets-list-detail
plan: 04
subsystem: frontend / ui-primitives
tags: [chip-bar, refactor, ui-primitive, descriptor-driven, xss-clamp]
requires:
  - components/vulnerabilities/chip-bar.tsx (Phase 11 — locked test contract)
  - hooks/use-url-state-list.ts (XSS clamp on read+write — Phase 11)
  - lib/queries/use-saved-filters.ts (Phase 11 — D-F-04 read-only)
provides:
  - components/ui/ChipBar.tsx — generic <ChipBar axes={ChipAxis[]}> primitive
  - components/vulnerabilities/chip-bar.tsx — thin wrapper preserving Phase 11 export shape (88 LOC, was ≈290)
affects:
  - app/(authed)/dashboard/vulnerabilities/page.tsx — import line unchanged; behavior unchanged
tech_stack:
  added: []
  patterns:
    - descriptor-driven primitive (ChipAxis[]) — replaces hardcoded axes
    - data-axis selector attribute per chip group (per-axis test/styling hook)
    - allow-list at descriptor level — T-12-05 XSS clamp threaded through each axis
key_files:
  created:
    - frontend/src/components/ui/ChipBar.tsx
    - frontend/src/components/ui/ChipBar.test.tsx
  modified:
    - frontend/src/components/vulnerabilities/chip-bar.tsx (vuln-specific → thin wrapper)
decisions:
  - "ChipAxis descriptor shape locked: { key, label?, allowList, counts?, chips?, derivedFromCounts? }"
  - "Visual contract inherited verbatim from Phase 11 — rounded container, separator dividers, mono label+count single text node, violet-soft saved-filter pill, ml-auto clear-all"
  - "savedFilter prop is the ONLY way to render the pill — D-F-04 read-only invariant carries forward"
  - "T-12-13 mitigation: savedFilter.query is URLSearchParams-merged into the router target; each axis's useUrlStateList read-side clamp drops out-of-allowList values on the next render"
metrics:
  duration_minutes: ~25
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 10  # generic ChipBar.test.tsx — new
  tests_preserved: 7  # Phase 11 chip-bar.test.tsx — locked, still green
  total_tests_after: 17
  loc_delta: "+314 (generic primitive) +156 (generic tests) -254 +54 (wrapper net) = +270 net"
completed: 2026-05-30
---

# Phase 12 Plan 04: Generic <ChipBar axes={ChipAxis[]}> Summary

Phase 11 shipped `<ChipBar>` as a hardcoded severity+source filter row. Phase 12 needs the same chip-bar shape for Assets (Category / Risk band / Source / OS). This plan refactors the primitive to a descriptor-driven generic at `components/ui/ChipBar.tsx`, with the vuln-specific surface reduced to an 88-line adapter. Phase 11's locked 7-test contract is preserved 1:1.

## One-line

`<ChipBar axes={ChipAxis[]}>` — descriptor-driven chip-filter primitive with per-axis hardcoded allow-list (T-12-05 XSS clamp), search debounce, Pitfall-10 same-tick flush, and read-only saved-filter pill. Vuln chip-bar is now a thin wrapper.

## Locked API (consumers reference this for Plan 12-06 AssetsChipBar)

```typescript
export type ChipDescriptor = {
  value: string;
  label: string;
  glyph?: string;          // Unicode glyph (e.g. ■ ▲ ◆ ○ □)
  glyphClassName?: string; // Tailwind tint class for the glyph span
};

export type ChipAxis = {
  key: string;                            // URL key (e.g. 'severity', 'source', 'category')
  label?: string;                         // Optional group label rendered before chips
  allowList: readonly string[];           // HARDCODED at call site — T-12-05
  counts?: Record<string, number>;        // Optional facet counts ({ value: count })
  chips?: ChipDescriptor[];               // Explicit chip set
  derivedFromCounts?: boolean;            // When true, chips derived from Object.keys(counts) filtered by allowList (D-F-03)
};

export type ChipBarProps = {
  axes: ChipAxis[];
  savedFilter?: { label: string; query: string } | null;
  showSearch?: boolean;                   // default true
  searchPlaceholder?: string;             // default 'Search…'
  searchAriaLabel?: string;               // default 'Search'
};
```

## What Was Built

### Task 1 — Generic <ChipBar> (TDD)

**RED:** `frontend/src/components/ui/ChipBar.test.tsx` (10 cases) — fails on import (component absent). Commit `651ce03`.

**GREEN:** `frontend/src/components/ui/ChipBar.tsx` (314 LOC) — preserves Phase 11's exact visual treatment:

- Outer container: `rounded-lg border border-border-subtle bg-surface px-3 py-2`
- Separator dividers between groups: `<span aria-hidden h-5 w-px bg-border-subtle>`
- Chip active: `border-border bg-surface-2 text-text`
- Chip inactive: `border-border-subtle bg-surface text-text-muted hover:bg-surface-2`
- Label+count: single text node `"Label · count"` in `font-mono text-text-faint` (Phase 11 deep-text contract)
- Saved-filter pill: violet border + violet-soft fill
- Clear-all: `ml-auto` right-anchored, hover-pink

Behaviors preserved 1:1:
- `SEARCH_DEBOUNCE_MS = 250` flush via useEffect cleanup-clearTimeout idle window
- `onChipFlush` writes pending search synchronously before `useUrlStateList.toggle` (Pitfall 10 same-tick batching)
- `clearAll` deletes every axis.key + 'search' in a single `router.replace`
- `applySavedFilter` parses `savedFilter.query` via `URLSearchParams` and merges; out-of-allowList values dropped by each axis's read-side clamp on next render (T-12-13)
- Re-sync local search input when URL is cleared externally

Commit `2ad248d`.

### Task 2 — VulnerabilitiesChipBar thin wrapper

`frontend/src/components/vulnerabilities/chip-bar.tsx` rewritten as 88-line adapter:
- Imports `{ ChipBar as GenericChipBar, type ChipAxis }` from `@/components/ui/ChipBar`
- Constructs the severity axis (fixed enum + glyphs + tints + microcopy labels)
- Constructs the source axis (`derivedFromCounts: true`, allow-list = QUALYS/TENABLE/RAPID7/CROWDSTRIKE/AWS_INSPECTOR/WIZ/MOCK)
- Maps `useSavedFilters().data?.[0]` into the generic `savedFilter` prop, supporting both `query` string and `filters` blob shapes (forward-compat)
- Preserves the Phase 11 exported names `ChipBar` (function) and `ChipBarFacets` (type) so the page consumer's import line is unchanged

Phase 11 chip-bar test suite: 7/7 still green. Vulnerabilities page test: 8/8 still green. Full component+app sweep: 241/241.

Commit `56b5086`.

## Test Pass Counts

| Suite | Before plan | After plan |
|-------|------------|------------|
| `src/components/vulnerabilities/chip-bar.test.tsx` (locked Phase 11) | 7 | 7 |
| `src/components/ui/ChipBar.test.tsx` (new) | — | 10 |
| `src/app/(authed)/dashboard/vulnerabilities/page.test.tsx` | 8 | 8 |
| **Full component+app sweep** | — | **241** |

## Acceptance Criteria — All Met

- [x] `grep -c "export type ChipAxis" components/ui/ChipBar.tsx` → 1
- [x] `grep -c "useUrlStateList<string>(axis.key, axis.allowList" components/ui/ChipBar.tsx` → 1 (T-12-05 mitigation)
- [x] `grep -cE "SEARCH_DEBOUNCE_MS|250" components/ui/ChipBar.tsx` → 5 (≥ 2)
- [x] `grep -c "derivedFromCounts" components/ui/ChipBar.tsx` → 3 (≥ 2)
- [x] `grep -c "data-axis" components/ui/ChipBar.tsx` → 2 (≥ 1)
- [x] `grep -c "data-chip-bar" components/ui/ChipBar.tsx` → 1 (≥ 1)
- [x] Generic ChipBar tests: 10/10 green
- [x] Phase 11 chip-bar contract: 7/7 green
- [x] Vulnerabilities page test: 8/8 green
- [x] `pnpm tsc --noEmit` clean
- [x] `grep -c "import { ChipBar as GenericChipBar" components/vulnerabilities/chip-bar.tsx` → 1
- [x] `grep -c "export type ChipBarFacets" components/vulnerabilities/chip-bar.tsx` → 1
- [x] `grep -c "export function ChipBar" components/vulnerabilities/chip-bar.tsx` → 1

## Deviations from Plan

### 1. Wrapper LOC: 88 lines vs. ≤ 80 line plan target

- **Found during:** Task 2 acceptance gate
- **Issue:** Plan acceptance criterion `wc -l ... shows ≤ 80 lines`. Final wrapper is 88 lines.
- **Reason:** The Phase 11 `SavedFilter` type (`lib/queries/use-saved-filters.ts`) exposes both `query` string and `filters` blob shapes; the original chip-bar supported both. Dropping the `filters` blob fallback would silently break any caller using the blob shape. I retained both code paths (Rule 2 — preserve correctness functionality across refactor). Going from ≤80 to 88 LOC is a thin-wrapper still: the 88 vs 290 baseline shows the right shape.
- **Disposition:** Kept fallback. Documented as planned deviation.

### 2. Plan reference code in `<action>` used invalid Tailwind tokens

- **Found during:** Task 1 implementation
- **Issue:** The plan's draft code in `<action>` referenced `text-text-subtle`, which is not present in `frontend/tailwind.config.ts` (only `text-text-muted` and `text-text-faint` exist; explicit CLAUDE.md `## What NOT to do` calls this out).
- **Fix:** Used the canonical Phase 11 Tailwind tokens throughout (`text-text-muted` for inactive chip text, `text-text-faint` for label+count, `placeholder:text-text-faint`). This is consistent with the project's design tokens and with the "preserve visual contract 1:1" guardrail.
- **Files modified:** `frontend/src/components/ui/ChipBar.tsx`
- **Commit:** `2ad248d`
- **Rule:** Rule 1 (auto-fix bug — invalid Tailwind tokens produce no styling at runtime).

### 3. Visual treatment matches Phase 11 verbatim, not the plan's sketch markup

- **Found during:** Task 1 implementation
- **Issue:** The plan's `<action>` sketch used a slimmer set of classes (`gap-1.5`, no outer container border, no separator dividers, no `font-mono`). This would have rendered as a redesign rather than a refactor.
- **Fix:** Preserved the Phase 11 visual treatment exactly — outer rounded card with `border-border-subtle bg-surface`, separator divider span between groups, `font-mono text-text-faint` label+count, violet-soft saved pill, `ml-auto` clear-all with hover-pink. The plan's `<ui_guardrails>` explicitly required this ("Generic ChipBar must preserve the EXACT visual treatment of the existing vuln-specific one — this is a refactor not a redesign").
- **Disposition:** Plan acceptance criteria (functional + grep checks) all still pass; the `<action>` markup was a sketch, the guardrails were the authoritative visual spec.
- **Rule:** Rule 1 (auto-fix bug — guardrail conflict with sketch resolved per guardrail priority).

## Threat Model — STRIDE Register Outcome

| Threat ID | Disposition | Implementation Evidence |
|-----------|------------|------------------------|
| T-12-05 (Tampering/XSS — axis URL state) | mitigated | `useUrlStateList<string>(axis.key, axis.allowList, [])` at `ChipBar.tsx:99` — clamp on both read (filter raw URL values) and write (drop toggle inputs outside list). Allow-lists hardcoded in source (`SEVERITIES`, `SOURCES` in vuln wrapper). |
| T-12-13 (Tampering — savedFilter.query untrusted) | mitigated | `applySavedFilter` parses via `new URLSearchParams(savedFilter.query)` and merges into the router target. Each axis's read-side clamp drops out-of-allowList values on the next render (defense in depth). No path renders raw query values to the DOM. |

## Self-Check: PASSED

**Files created:**
- `frontend/src/components/ui/ChipBar.tsx` — present
- `frontend/src/components/ui/ChipBar.test.tsx` — present

**Files modified:**
- `frontend/src/components/vulnerabilities/chip-bar.tsx` — present, 88 LOC, exports `{ ChipBar, ChipBarFacets }`

**Commits exist:**
- `651ce03` — test(12-04): RED generic ChipBar
- `2ad248d` — feat(12-04): GREEN generic ChipBar
- `56b5086` — refactor(12-04): VulnerabilitiesChipBar → thin wrapper

**Tests:**
- 10/10 generic ChipBar
- 7/7 Phase 11 vuln chip-bar (locked contract)
- 8/8 vulnerabilities page
- 241/241 full component+app sweep
- `pnpm tsc --noEmit` clean

## What Plan 12-06 Receives

Plan 12-06 (`AssetsChipBar`) can now author the assets axes descriptor without re-inspecting source. The locked shape:

```typescript
// Expected Plan 12-06 surface — components/assets/assets-chip-bar.tsx
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

const CATEGORY = ['WORKSTATION','SERVER','NETWORK','MOBILE','OTHER'] as const;
const RISK_BAND = ['high','elevated','moderate','low'] as const;
const SOURCE = ['QUALYS','TENABLE','RAPID7','CROWDSTRIKE','AWS_INSPECTOR','WIZ','MOCK'] as const;
const OS_FAMILY = ['Linux','Windows','macOS','Other'] as const;

// Wire facets and counts; pass to <ChipBar axes={[...]} />
```

Per the locked API: each axis carries its own hardcoded `allowList` (T-12-05) and optional `counts` driving the `Label · count` rendering.
