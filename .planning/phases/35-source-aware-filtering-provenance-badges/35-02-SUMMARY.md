---
phase: 35-source-aware-filtering-provenance-badges
plan: 02
subsystem: ui
tags: [react, nextjs, tailwind, css-variables, chip-bar, url-state, tdd]

# Dependency graph
requires:
  - phase: 35-source-aware-filtering-provenance-badges
    provides: "Plan 01 backend contract — vuln list rows carry sources/sources_count; ?source_mode=or|and Literal-validated filter"
  - phase: 13-tickets
    provides: "ProviderMark literal-lookup gradient-mark pattern (T-13-14 XSS mitigation) mirrored by SourceBadgeGroup"
  - phase: 14-connectors
    provides: "The 6 --gradient-provider-{crowdstrike,nessus,defender,wiz,qualys,rapid7} CSS tokens (ConnectorMark, D-CONN-01) — reused verbatim, no new tokens needed"
provides:
  - "SourceBadgeGroup — shared, surface-agnostic non-overclaiming provenance component (single source = 1 neutral mark; 2+ = mark group + 'N sources' corroboration-tinted label)"
  - "Vuln table rows render SourceBadgeGroup in the desktop Status cluster + mobile Row-3 cluster, consuming sources/sources_count"
  - "chip-bar.tsx SOURCES reconciled to the real 6-value VulnSource enum (fake TENABLE/AWS_INSPECTOR/MOCK removed, real NESSUS/DEFENDER added)"
  - "OR/AND ?source_mode toggle in the vuln chip-bar, disabled below 2 selected sources, copy-voice-compliant label"
affects: [35-03-assets, 35-04-cspm-tickets, 35-05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SourceBadgeGroup: literal SOURCE_GRADIENTS/SOURCE_GLYPH Record lookup (never string-concatenated into a CSS var name) + single-vs-multi non-overclaiming state machine — the reusable shape Plan 05 replicates on Assets/CSPM/Tickets"
    - "Sibling-toggle-next-to-a-ChipAxis pattern: since ChipAxis has no mode field, the OR/AND control is rendered as a second row below <GenericChipBar>, reading the same useUrlStateList('source', ...) value the axis itself uses to compute its own disabled state"

key-files:
  created:
    - frontend/src/components/vulnerabilities/source-badge-group.tsx
    - frontend/src/components/vulnerabilities/source-badge-group.test.tsx
  modified:
    - frontend/src/components/vulnerabilities/vuln-table.tsx
    - frontend/src/components/vulnerabilities/chip-bar.tsx
    - frontend/src/components/vulnerabilities/chip-bar.test.tsx
    - frontend/src/components/vulnerabilities/microcopy.ts

key-decisions:
  - "The 6 --gradient-provider-{crowdstrike,nessus,defender,wiz,qualys,rapid7} scanner CSS tokens already existed in globals.css (shipped with ConnectorMark, Phase 14) — SourceBadgeGroup reuses them verbatim. No token gap; no neutral-fallback-for-all-scanners path needed."
  - "Single-source rendering keeps the provider's own gradient mark (colored, same as multi-source) — 'neutral/muted' in SRC-01 means the ABSENCE of the corroboration wrapper/tint/copy, not a grayscale mark. Verified directly against the plan's own marks_use_css_var_not_hex behavior spec, which expects --gradient-provider- on every mark including the single-source case."
  - "OR/AND toggle rendered as a second row beneath the generic <ChipBar>, not injected into ChipAxis (no mode field exists there, and the generic ui/ChipBar.tsx primitive was intentionally left unmodified — out of this plan's files_modified list)."
  - "Toggle copy: 'Any selected' / 'All selected' (button label reflects the CURRENT mode; click flips it) — avoids AND/OR jargon per copy-voice.md, verified by a dedicated test asserting no bare AND/OR text renders."
  - "Updated chip-bar.test.tsx's baseFacets fixture from the fake TENABLE to the real NESSUS — the pre-existing 'source chips are rendered from facets.source (not hardcoded)' test depended on a source string that is no longer in the allow-list, so its coverage would have silently broken without the swap (Rule 1 — the test itself, not app code, but flagged here since it's a fixture correctness fix in scope of Task 2's own commit)."

patterns-established:
  - "SourceBadgeGroup public contract for Plan 05: `<SourceBadgeGroup sources={string[]} count={number} className={string} />`, import path `@/components/vulnerabilities/source-badge-group` — presentational, zero vuln-specific imports, ready to reuse verbatim on Assets/CSPM/Tickets rows."

requirements-completed: [SRC-01, SRC-02, SRC-03, SRC-04]

coverage:
  - id: D1
    description: "SourceBadgeGroup renders a single-source finding as ONE neutral provider mark with no 'confirmed'/'verified' copy and no corroboration tint (SRC-01)"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/source-badge-group.test.tsx#renders_single_source_neutral"
        status: pass
    human_judgment: false
  - id: D2
    description: "SourceBadgeGroup renders a 2+-source finding as the mark group plus a subtle 'N sources' label using the --color-success corroboration tint"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/source-badge-group.test.tsx#renders_multi_source_corroborated"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every provider mark's background resolves through a literal SOURCE_GRADIENTS lookup (CSS var, never raw hex); no <img>/logo asset ever renders; unknown source codes fall through to a neutral fallback mark instead of a crash or wrong-provider gradient"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/source-badge-group.test.tsx#marks_use_css_var_not_hex, #unknown_source_neutral_fallback"
        status: pass
    human_judgment: false
  - id: D4
    description: "Zero-source input renders a neutral empty state (em-dash), never throws"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/source-badge-group.test.tsx#zero_sources_no_crash"
        status: pass
    human_judgment: false
  - id: D5
    description: "SourceBadgeGroup is wired inline into the vuln table's desktop Status/badge cluster and mobile Row-3 cluster, consuming row.sources/row.sources_count"
    requirement: "SRC-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/vuln-table.test.tsx (full suite, unchanged, still green after wiring)"
        status: pass
    human_judgment: false
  - id: D6
    description: "chip-bar SOURCES lists exactly the 6 real VulnSource values; the previously-fake TENABLE/AWS_INSPECTOR/MOCK are gone and NESSUS/DEFENDER are present"
    requirement: "SRC-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/chip-bar.test.tsx#'source axis never renders the fake TENABLE/AWS_INSPECTOR/MOCK values', #'source axis renders the real NESSUS/DEFENDER connectors'"
        status: pass
    human_judgment: false
  - id: D7
    description: "OR/AND ?source_mode toggle is disabled below 2 selected sources, enabled at 2+, sets source_mode=and on click, and its copy avoids AND/OR jargon"
    requirement: "SRC-04"
    verification:
      - kind: unit
        ref: "frontend/src/components/vulnerabilities/chip-bar.test.tsx#'the source_mode toggle is disabled...', #'...is enabled once 2+ sources are selected...', #'toggle copy avoids AND/OR jargon...'"
        status: pass
    human_judgment: false
  - id: D8
    description: "Manual visual verification that single vs multi source never reads as 'confirmed' and the badge column empty state renders correctly on a live page"
    verification: []
    human_judgment: true
    rationale: "Deferred to phase UAT per the plan's own <verification> block — no live-page visual/browser check was run in this execution session, only component-level unit tests."

duration: 8min
completed: 2026-08-12
status: complete
---

# Phase 35 Plan 02: Vuln UI — SourceBadgeGroup + OR/AND Source Filter (Frontend Tracer) Summary

**Shared, non-overclaiming SourceBadgeGroup component (single-source = 1 neutral provider mark, 2+ sources = mark group + "N sources" corroboration-tinted label) wired into the Vulnerabilities table, plus a reconciled 6-value scanner list and an OR/AND `?source_mode` toggle in the vuln chip-bar — the first UI surface to consume Plan 01's `sources`/`sources_count` API contract.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-12T14:38:00+03:00 (approx, context load)
- **Completed:** 2026-08-12T14:46:00+03:00
- **Tasks:** 2
- **Files modified:** 6 (2 new, 4 modified)

## Accomplishments

- Built `SourceBadgeGroup` — a shared, surface-agnostic component with literal `SOURCE_GRADIENTS`/`SOURCE_GLYPH` lookup maps (never string-concatenated into a CSS var name, mirroring `ProviderMark`'s T-13-14 mitigation) and a single-vs-multi state machine: 1 source renders one gradient mark with zero corroboration chrome, 2+ sources render the mark group plus a `"N sources"` label using the SLA-ok green tint (`rgba(74,222,128,0.12)` / `var(--color-success)` / `rgba(74,222,128,0.3)` border) reused per CONTEXT.md [RESOLVED A3].
- Discovered the 6 `--gradient-provider-{crowdstrike,nessus,defender,wiz,qualys,rapid7}` scanner CSS tokens **already exist** in `globals.css` (shipped with `ConnectorMark` in Phase 14) — no token gap, no neutral-fallback-for-known-scanners path needed. Only genuinely unknown codes (e.g. an Assets-surface enrichment value like `JAMF`) hit the neutral fallback mark.
- Wired `SourceBadgeGroup` into `vuln-table.tsx`'s existing KEV/exploit badge cluster on both the desktop `<td data-col="status">` cell and the mobile Row-3 card cluster, reading `row.sources ?? [row.source]` / `row.sources_count` (both new optional fields added to `VulnTableRow`, backward-compatible with pre-Phase-35 test fixtures that lack them).
- Reconciled `chip-bar.tsx`'s `SOURCES` allow-list to the real 6-value `VulnSource` enum (`vulnerabilities/models.py:32-38`) — dropped `TENABLE`/`AWS_INSPECTOR`/`MOCK`, added `NESSUS`/`DEFENDER`.
- Added a sibling OR/AND toggle (`useUrlState('source_mode', ['or','and'], 'or')`) rendered below the generic `<ChipBar>`, reading the same `?source=` list the source axis uses so it self-disables below 2 selections — the exact Pitfall 1 no-op case the 35-01 backend already documents and tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: SourceBadgeGroup component + test** - `818be09` (feat)
2. **Task 2: Wire SourceBadgeGroup into vuln-table + OR/AND toggle + reconciled SOURCES** - `0a0f216` (feat)

**Plan metadata:** _created below._

## Files Created/Modified

- `frontend/src/components/vulnerabilities/source-badge-group.tsx` - new shared component (SOURCE_GRADIENTS/SOURCE_GLYPH literal maps, SourceMark subcomponent, single/multi/empty state machine)
- `frontend/src/components/vulnerabilities/source-badge-group.test.tsx` - 6 tests: single-source neutral, multi-source corroborated, CSS-var-not-hex + no-`<img>`, unknown-source fallback, zero-source no-crash, count-fallback-to-length
- `frontend/src/components/vulnerabilities/vuln-table.tsx` - `SourceBadgeGroup` wired into desktop + mobile clusters; `sources`/`sources_count` added to `VulnTableRow`
- `frontend/src/components/vulnerabilities/chip-bar.tsx` - `SOURCES` reconciled to 6 real values; `useUrlState`/`useUrlStateList` imports added; OR/AND toggle rendered
- `frontend/src/components/vulnerabilities/chip-bar.test.tsx` - swapped stale `TENABLE` fixture value for `NESSUS`; added 5 new Phase 35 tests (reconciled list + toggle disabled/enabled/label/no-jargon)
- `frontend/src/components/vulnerabilities/microcopy.ts` - added `chips.sourceModeLabel`/`sourceModeAny`/`sourceModeAll`/`sourceModeDisabledHint`

## Decisions Made

- Confirmed (not assumed) that the 6 scanner gradient tokens already exist in `globals.css`, shipped alongside `ConnectorMark` — this eliminated the plan's contingent "add the tokens or use a neutral-fallback-for-everything" branch entirely; only genuinely unrecognized codes use the fallback.
- "Neutral/muted" for the single-source state means no corroboration wrapper/tint/copy is added around the mark — the mark itself keeps its provider color, matching the plan's own `marks_use_css_var_not_hex` behavior spec (which expects a `--gradient-provider-` background on every rendered mark, including the single-source case).
- The OR/AND toggle lives in `chip-bar.tsx` as a second row beneath the generic `<ChipBar>` rather than as a `ChipAxis` field (no such field exists) or a change to `components/ui/ChipBar.tsx` (out of this plan's file scope) — it reads the same URL-backed source selection the axis itself uses, so its disabled state tracks the axis without any prop-drilling between the two.
- Toggle copy: the button's own label reflects the *current* mode ("Any selected" while OR is active, "All selected" once toggled to AND) rather than a fixed "AND"/"OR" control label — matches copy-voice.md's no-jargon rule, verified by a dedicated test asserting neither bare token renders.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a pre-existing chip-bar test fixture referencing the removed fake `TENABLE` source**
- **Found during:** Task 2 verification — running the full `src/components/vulnerabilities/` suite after reconciling `SOURCES` broke `chip-bar.test.tsx`'s original `'renders search input, severity chips, source chips, Clear all'` test, which asserted `TENABLE` renders (it's excluded by the axis's `allowList` now that `SOURCES` no longer contains it).
- **Issue:** The test's `baseFacets` fixture hardcoded a source value (`TENABLE`) that is exactly the fake value this plan's own SRC-03 requirement mandates removing — the test was asserting the bug, not just incidentally using a stale value.
- **Fix:** Swapped `TENABLE: 192` → `NESSUS: 192` in the shared `baseFacets` fixture and its two dependent assertions (lines 60, 108) to a real `VulnSource` value, preserving the test's original intent (source chips are data-driven from facets, filtered through the allow-list).
- **Files modified:** `frontend/src/components/vulnerabilities/chip-bar.test.tsx`
- **Verification:** `npx vitest run src/components/vulnerabilities/` — 98/98 tests pass (was 92/93 with 1 failure before the fixture fix).
- **Committed in:** `0a0f216` (Task 2 commit — the fixture fix ships with the SOURCES reconciliation it's paired to, not a separate commit).

---

**Total deviations:** 1 auto-fixed (1 bug — a test fixture referencing removed fake data, discovered and fixed within Task 2's own scope).
**Impact on plan:** Necessary corollary of SRC-03's reconciliation; no scope creep, no change to any interface described in the plan's `<interfaces>` block.

## Issues Encountered

None beyond the fixture fix documented above.

## User Setup Required

None - no external service configuration required. No CSS token changes required (all 6 scanner gradients pre-existed from Phase 14's `ConnectorMark` work).

## Next Phase Readiness

- `SourceBadgeGroup` (`frontend/src/components/vulnerabilities/source-badge-group.tsx`) is a presentational, surface-agnostic component with zero vuln-specific imports — Plan 05 can import it verbatim for Assets/CSPM/Tickets rows: `import { SourceBadgeGroup } from '@/components/vulnerabilities/source-badge-group'`, prop contract `{ sources: string[]; count?: number; className?: string }`.
- Unknown source codes (the Assets-surface enrichment values like `JAMF`/`HUMAANS`/`INTUNE` that CONTEXT.md's locked decision says must not be conflated with scanner sources) already render safely via the neutral fallback mark — verified by the `unknown_source_neutral_fallback` test — so Plan 05's Assets integration needs no changes to `SourceBadgeGroup` itself, only to what it's fed.
- `?source_mode` is now a real, HTTP-reachable filter axis end-to-end: `chip-bar.tsx` writes it, the 35-01 backend `VulnerabilityFilter.source_mode` reads it. No further backend work needed for Vulnerabilities.
- Full frontend regression suite green: `npx vitest run` — 138 test files, 937 tests passed. `npx tsc --noEmit` clean. `npx eslint` clean on all touched files.
- No blockers for Plan 05 (Assets/CSPM/Tickets frontend) or Plans 03/04 (Assets/CSPM/Tickets backend, independent of this plan).

---
*Phase: 35-source-aware-filtering-provenance-badges*
*Completed: 2026-08-12*

## Self-Check: PASSED

All 6 created/modified files verified present on disk; both task commits (`818be09`, `0a0f216`) verified present in `git log --oneline --all`.
