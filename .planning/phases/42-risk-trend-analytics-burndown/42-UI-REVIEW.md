# Phase 42 — UI Review

**Audited:** 2026-08-21
**Baseline:** 42-UI-SPEC.md (approved design contract)
**Screenshots:** captured (pre-existing authenticated UAT captures, `scratchpad/uat_*.png` — a fresh unauthenticated CLI capture against `localhost:3000` returns a `307` login redirect, so the provided live-session screenshots are the only usable visual evidence for this pass)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Every locked string transcribed verbatim into `microcopy.ts`; no generic-SaaS copy found. |
| 2. Visuals | 3/4 | Correct hierarchy/focal points, but the loading skeleton's shape has never been updated to match the final 5-preset + scope-dropdown control row, producing a visible layout jump on load. |
| 3. Color | 3/4 | No freehand hex anywhere; neutral boundary marker and directional success/danger correct — but the UI-SPEC's explicit "active window-toggle... violet underline/indicator" accent was never implemented; the active preset uses only generic gray chrome. |
| 4. Typography | 4/4 | Exactly the 4 declared sizes (12/14/32/40px) and 2 declared weights (400/600); mono+tabular-nums correctly applied to every score/percentage/date. |
| 5. Spacing | 2/4 | A non-multiple-of-4 `py-1.5` (6px) on the scope trigger; the declared 48px header→first-chart gap is not implemented (actual gap is 16px); an off-scale 12px (`p-3`) custom-range field wrapper. |
| 6. Experience Design | 2/4 | Screenshot-confirmed: an invalid/incomplete custom date range leaves the query permanently `disabled`, and `q.isPending` never resolves — the page shows a perpetual loading skeleton stacked directly under the "End date must be after start date." error, a visibly contradictory state. |

**Overall: 18/24**

---

## Top Priority Fixes

1. **Perpetual loading skeleton while a custom range is invalid** — user impact: a user who types a `To` date before `From` (or leaves either field mid-edit) sees a permanent shimmering "loading" block sitting directly beneath a validation error, implying the page is stuck fetching forever; this is a genuine, screenshot-reproduced UX defect (`uat_t3b_customrange.png`), not a hypothetical. Root cause: TanStack Query v5's `isPending` never transitions away from `true` for a query created with `enabled: false` (`use-analytics.ts:171`, `enabled: enabled && (!isCustom || rangeValid)`) — page.tsx's `q.isPending` branch (`page.tsx:147`) can't distinguish "really loading" from "deliberately not fetching yet." Fix: branch on `q.fetchStatus === 'idle' && q.isPending` (or an explicit `!rangeValid && isCustom` guard) to render a neutral "enter a valid range" placeholder instead of `<AnalyticsPageSkeleton />` while the custom range is incomplete/invalid.

2. **Loading skeleton shape never updated after Plans 02/03** — user impact: on every real page load, the skeleton (`analytics-page-skeleton.tsx`) renders exactly 4 generic pills and no scope-dropdown placeholder, then snaps to the real control row (scope dropdown + 5 presets) the instant data arrives — a visible layout shift on every single visit. `analytics-page-skeleton.tsx`'s own docstring still says "4th pill so the control-row shimmer already matches this page's 4-preset window toggle," which was true for Plan 01 but has been stale since Plan 03 added the 5th "Custom range" preset and the entire scope dropdown (confirmed via `key-files.modified` in `42-03-SUMMARY.md`: `analytics-page-skeleton.tsx` is not listed). Fix: add a 5th pill and a scope-dropdown-trigger-shaped block (`w-[140px] h-7` or similar) to `analytics-page-skeleton.tsx`.

3. **Missing declared "active window-toggle violet indicator" (Color contract)** — user impact: minor but a directly-quotable contract miss — 42-UI-SPEC.md's Color section explicitly reserves violet for "Scope-dropdown trigger focus ring + active window-toggle (`aria-pressed=true`) state, matching `RangeToggle`'s existing `bg-surface-2 text-text` active chrome **extended with a violet underline/indicator**" (item 3 of the reserved-accent list). `scope-window-controls.tsx:157-160` copies the pre-existing `RangeToggle` chrome byte-for-byte (`active ? 'bg-surface-2 text-text' : ...`) with no violet addition at all — confirmed absent from the live screenshot (the "30d" active pill shows only a plain gray background, no violet underline). Fix: add e.g. `active && 'border-b-2 border-violet'` or a small violet dot to the active preset button.

4. **Spacing scale deviations** — `scope-window-controls.tsx:102` uses `py-1.5` (6px) on the scope trigger, which is not a multiple of 4 and violates the Spacing Scale header's own "must be multiples of 4" rule (compare to the sibling window-toggle buttons at `py-1`/4px). Separately, the UI-SPEC declares a 48px (`2xl`) gap between the page header block (title + scope/window controls) and the first chart section, but `page.tsx:114`'s `<div className="space-y-4 p-6">` gives every top-level child (h1 → controls → chart region) a flat 16px rhythm — the declared 3x-larger separation between "controls" and "first chart" never renders. Fix: bump the trigger to `py-1` (or `py-2`) for a true 4px multiple, and wrap the header block in its own container with `mb-12` (48px) before the chart-region `<div>`.

5. **Burndown-tile padding may conflict with the declared spacing scale** (lower confidence, flagged for reconciliation rather than as a clear-cut defect) — 42-UI-SPEC.md's Spacing Scale states `lg` (24px, `p-6`) is "Chart card padding, matches every existing card/pane," but the Design System table in the same document explicitly instructs the Burndown tile to reuse `campaign-burndown-card.tsx`'s chrome verbatim, which is `p-4` (16px) — and `burndown-tile.tsx:57` correctly follows that explicit instruction. This is a self-contradiction inside the UI-SPEC itself (the generic Spacing Scale row vs. the specific Design System row), not an implementation bug — but worth a UI-SPEC erratum so a future auditor doesn't flag it as a false negative or false positive depending on which UI-SPEC section they trust.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

- `frontend/src/components/analytics/microcopy.ts` transcribes every locked string from 42-UI-SPEC.md's Copywriting Contract verbatim: page title (`Analytics`), scope labels (`All (tenant)`, per-group name), window labels (`7d`/`30d`/`90d`/`1y`/`Custom range` + sr-only expansions), section headings (`Risk-exposure trend`/`Backlog aging`/`Burndown`), the mandatory group-scope caption (`groupCaption`, l.28-29), version-boundary label/tooltip (l.55-58), the D-04 empty-state title/body (l.64-68), aging bucket labels (l.76-79) and the explicit-zero overdue tile (l.82), and all 3 burndown net-velocity/projected-clear branches (l.93-104) including the 500-day cap copy.
- No generic-SaaS patterns found: `grep -rn "Submit|Click Here|OK|Cancel|Save|No data|No results|Nothing|went wrong|try again|error occurred"` across `frontend/src/components/analytics/` and `page.tsx` returned zero matches.
- Error state correctly reuses the existing `PartialFailureBanner` pattern (no new, invented error copy) per the Copywriting Contract's explicit instruction.

### Pillar 2: Visuals (3/4)

- Correct visual hierarchy top-to-bottom (scope/window controls → trend line → aging → burndown), matching the UI-SPEC's declared reading order; large Display-size numbers (`87%`, `8.6`, `4.2`) are the clear focal points on the aging/burndown sections; the sr-only section `<h2>`s intentionally de-emphasize chrome exactly as the UI-SPEC's Typography note states ("already visually de-emphasized... relative to the page `<h1>`"), so that is not a defect.
- `SEVERITY_FILLS` and the severity glyphs (■▲◆○) are correctly reused verbatim from `trend-chart.tsx` (`backlog-aging-chart.tsx:32,42-47`), confirmed rendering correctly in the tooltip screenshot (`uat_t3b_group.png`: "■ Critical: 0 / ▲ High: 1 / ◆ Medium: 2 / ○ Low: 1").
- **Defect:** `analytics-page-skeleton.tsx` renders exactly 4 pills (matching Plan 01's 4-preset window toggle) and no scope-dropdown placeholder at all. Since Plan 03 landed, the real control row has 5 presets AND a scope dropdown, so every page load produces a visible pop/reflow the instant the real controls replace the skeleton. Not caught by any of the three plans' `checkpoint:human-verify` gates (all three approved against the chart/data content, not the skeleton's shape fidelity).
- No icon-only buttons without an accessible label were found in the analytics surface (`grep -n "aria-label|<svg|Icon" scope-window-controls.tsx` — all interactive controls with icons/inputs carry an explicit `aria-label`).

### Pillar 3: Color (3/4)

- Zero freehand hex/`rgb()` anywhere in `frontend/src/components/analytics/` or the page file (`grep -rniE "#[0-9a-f]{3,8}"` and `grep -rn "rgb("` both return no matches) — full compliance with CLAUDE.md's "no freehand hex" rule and the UI-SPEC's CSS-variable-only mandate.
- Version-boundary marker is correctly neutral, never accent/severity-colored: `risk-trend-chart.tsx:201` uses `stroke="var(--color-border-strong)"` and the label chip (`VersionBoundaryLabel`, l.125-155) uses `var(--color-surface-2)` / `var(--color-text-muted)` / `var(--color-border-subtle)` only — confirmed in the live screenshot as a plain gray "v1 → v2" chip, never violet.
- Directional burndown copy correctly reuses the existing SLA/status convention (`text-success` shrinking / `text-danger` growing / muted no-change) — `burndown-tile.tsx:70-75` — no invented palette.
- **Defect (Color reserved-list item 3, half-missed):** the UI-SPEC's Color section explicitly calls for the active window-toggle (`aria-pressed=true`) state to be "`RangeToggle`'s existing `bg-surface-2 text-text` active chrome **extended with a violet underline/indicator**." `scope-window-controls.tsx:157-160` implements only the pre-existing base chrome (`active ? 'bg-surface-2 text-text' : ...`) with zero violet addition — grep for `violet` in this file (see below) turns up only the two `focus:border-violet` date-input rules, never anything tied to the `active` boolean. Confirmed absent from `uat_t1_trend.png` / `uat_t2_aging_burndown.png` (the "30d" active pill has plain gray chrome, no violet mark). The scope-trigger's separate "focus ring" half of that same list item IS satisfied, but only incidentally — via the project's pre-existing *global* `*:focus-visible` rule (`frontend/src/app/globals.css:102-103`), not anything this phase's component added; it is visible in `uat_t3b_group.png` only because Playwright left the trigger focused after the click.
- Violet usage elsewhere is appropriately restrained (trend line stroke + 2 focus-only date/search input borders) — no accent overuse.

### Pillar 4: Typography (4/4)

- Exactly the 4 declared font sizes appear across the analytics surface: `text-xs` (12px, Label), `text-sm` (14px, Body), `text-3xl` (32px, Heading/page title only), `text-4xl` (40px, Display — burndown net-per-week and the aging overdue tile). Confirmed via `grep -rohn "text-\(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl\)"` — no `text-base`/`lg`/`xl`/`2xl`/`5xl` usage anywhere.
- Exactly the 2 declared weights: `font-semibold` (600) on the page `<h1>`, the two Display numbers, and nowhere else needing emphasis; body copy is implicitly 400 (no `font-normal`/`font-medium`/`font-bold` found anywhere in the surface).
- Mono + `tabular-nums` correctly applied to every "copy-pasteable" value: the burndown headline (`burndown-tile.tsx:65`), the aging overdue tile (`backlog-aging-chart.tsx:149`), version strings in the boundary label/tooltip, and every tooltip count — matches `foundation.md`'s rule exactly.

### Pillar 5: Spacing (2/4)

- `xl` (32px) rhythm between the trend/aging/burndown sections is correctly implemented: `page.tsx:158`'s `<div className="space-y-8">` = 32px, matching the declared token exactly.
- **Defect 1:** `scope-window-controls.tsx:102` — the scope-dropdown trigger uses `py-1.5` (6px), which is not a multiple of 4 and violates the Spacing Scale header's own explicit rule ("Declared values (must be multiples of 4)"). The sibling window-toggle buttons two lines below (`scope-window-controls.tsx:158`) correctly use `py-1` (4px) for the same visual role — an internal inconsistency within the same component.
- **Defect 2:** the declared `2xl` (48px) "Page header (title + scope/window controls) to first chart section" gap is not implemented. `page.tsx:114`'s `<div className="space-y-4 p-6">` wraps the `<h1>`, `<ScopeWindowControls>`, and the entire chart-or-state region as flat siblings under one `space-y-4` (16px) rule — there is no larger break between "controls" and "first chart," so the declared 3x visual separation between those two conceptual blocks never renders. (Screenshots show the controls row sitting a normal ~16px above the trend chart, consistent with this reading of the code.)
- **Defect 3 (minor):** the custom-range field wrapper (`scope-window-controls.tsx:171`, `p-3` = 12px) uses a spacing value not present anywhere in the declared scale's enumerated token list (`xs 4 / sm 8 / md 16 / lg 24 / xl 32 / 2xl 48`) — it is at least a multiple of 4, but it is off-scale relative to the specific tokens the contract enumerates.
- No arbitrary non-4px-multiple values found elsewhere (`max-w-[220px]` and `h-[200px]` are dimension constraints, not spacing, and are consistent with the existing `trend-chart.tsx` precedent).

### Pillar 6: Experience Design (2/4)

- Loading/error/empty/populated branch order is correctly implemented and exhaustively tested (18/18 frontend + 17/17 backend tests per `42-VERIFICATION.md`, independently re-run during that verification pass) — this pillar is not being scored on test coverage, which is excellent, but on what the actually-shipped states look/feel like live, which surfaced two defects the test suite's mocked-hook harness structurally cannot catch:
  - **Defect 1 (screenshot-confirmed, the most severe finding in this review):** `uat_t3b_customrange.png` shows the "Custom range" preset selected, the `To` date before the `From` date, the correct inline validation text ("End date must be after start date."), **and, directly beneath it, a permanent shimmering loading skeleton** (a pill block + a row of 4 smaller pills + a large rectangle — `AnalyticsPageSkeleton`'s exact shape). This happens because `use-analytics.ts:171` sets `enabled: enabled && (!isCustom || rangeValid)` — while the range is invalid, the query is disabled and TanStack Query v5 never transitions its `status` away from `'pending'` for a query that has never fetched, so `page.tsx:147`'s `q.isPending` branch renders `<AnalyticsPageSkeleton />` indefinitely, not just during a real fetch. The net effect: a user who mis-orders a date range is shown an error message and a permanently "loading" page at the same time, with no way to tell the two states apart or know the page isn't actually fetching anything.
  - **Defect 2 (skeleton fidelity, restated from Visuals):** the same skeleton's control-row shimmer (4 pills, no dropdown box) has been stale since Plan 03 shipped the 5th preset + scope dropdown, so even the *correct*, real-loading case shows a mismatched placeholder shape before snapping to the real 5-option + dropdown row.
- Everything else in this pillar is strong: the D-04 empty state (below-minimum-history, and the empty-membership-group edge case fixed in `b9dc1ae` and re-verified live) renders correctly and honestly; error retry wiring (`onRetry={() => q.refetch()}`) is correct; disabled-state handling for the exclusion predicate (SUPPRESSED/FALSE_POSITIVE/actively-excepted findings) is unit-tested and live-verified per `42-VERIFICATION.md` truths #11/#19. No destructive actions exist on this read-only page, so no confirmation-dialog gap applies.

---

## Registry Safety

`components.json` exists (shadcn initialized), but 42-UI-SPEC.md's own Registry Safety table declares zero third-party registries this phase — the only registry entry is `shadcn official / dropdown-menu`, marked "already installed, reused verbatim — no re-install," with an explicit "not required (pre-existing, previously vetted)" safety gate. Registry audit: 0 third-party blocks checked, no flags (nothing new to audit).

---

## Files Audited

- `.planning/phases/42-risk-trend-analytics-burndown/42-UI-SPEC.md`
- `.planning/phases/42-risk-trend-analytics-burndown/42-CONTEXT.md`
- `.planning/phases/42-risk-trend-analytics-burndown/42-01-SUMMARY.md`, `42-02-SUMMARY.md`, `42-03-SUMMARY.md`
- `.planning/phases/42-risk-trend-analytics-burndown/42-01-PLAN.md`, `42-02-PLAN.md`, `42-03-PLAN.md` (referenced via SUMMARY cross-checks)
- `.planning/phases/42-risk-trend-analytics-burndown/42-UAT.md`, `42-VERIFICATION.md`
- `.claude/skills/sketch-findings-getvul/references/foundation.md`
- `frontend/src/app/(authed)/dashboard/analytics/page.tsx`
- `frontend/src/components/analytics/risk-trend-chart.tsx`
- `frontend/src/components/analytics/backlog-aging-chart.tsx`
- `frontend/src/components/analytics/burndown-tile.tsx`
- `frontend/src/components/analytics/scope-window-controls.tsx`
- `frontend/src/components/analytics/microcopy.ts`
- `frontend/src/components/analytics/analytics-page-skeleton.tsx`
- `frontend/src/lib/queries/use-analytics.ts`
- `frontend/src/components/ui/trend-chart.tsx` (precedent comparison)
- `frontend/src/components/campaigns/campaign-burndown-card.tsx` (precedent comparison)
- `frontend/src/app/globals.css` (global focus-visible rule check)
- Live UAT screenshots: `uat_t1_trend.png`, `uat_t2_aging_burndown.png`, `uat_t3_boundary_90d.png`, `uat_t3b_group.png`, `uat_t3b_customrange.png`, `uat_t4_fixed.png`
- `git log` / `git show` on `page.tsx` and `analytics-page-skeleton.tsx` to confirm which fixes (e.g., `b9dc1ae`) landed after the plan SUMMARYs were written, and which files were never touched by any commit
