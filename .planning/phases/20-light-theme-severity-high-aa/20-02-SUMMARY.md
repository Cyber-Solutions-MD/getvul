---
phase: 20-light-theme-severity-high-aa
plan: 02
subsystem: ui
tags: [design-tokens, css-custom-properties, wcag-aa, light-theme, sketch-findings-getvul, tailwind]

# Dependency graph
requires:
  - phase: 20-01
    provides: "--color-severity-high-on-soft CSS custom property (light #9A3412, dark #FB923C no-op) in frontend/src/app/globals.css"
provides:
  - "All 18 foreground text-severity-high sites across 17 source files migrated to text-[var(--color-severity-high-on-soft)], statically proven regression-free (unit suite, typecheck, bundle budget)"
affects: [20-03-plan (live prod-build axe sweep — the final acceptance arbiter for this migration)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Foreground-only token migration: swap only the `text-` class token in combined class strings, leaving `border-`/`bg-` on the base accent — mirrors the WR-02/WR-04 Phase 16 precedent"]

key-files:
  created: []
  modified:
    - frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx
    - frontend/src/components/ui/RiskRing.tsx
    - frontend/src/components/ui/trend-chart.tsx
    - frontend/src/components/tickets/severity-glyph.ts
    - frontend/src/components/tickets/vuln-count.tsx
    - frontend/src/components/tickets/sla-pill.tsx
    - frontend/src/components/tickets/ticket-drill-content.tsx
    - frontend/src/components/dashboard/top5-card.tsx
    - frontend/src/components/users/directory-table.tsx
    - frontend/src/components/assets/asset-vulns-list.tsx
    - frontend/src/components/assets/remediation-timeline.tsx
    - frontend/src/components/assets/assets-table.tsx
    - frontend/src/components/assets/severity-ribbon.tsx
    - frontend/src/components/assets/risk-card.tsx
    - frontend/src/components/cspm/microcopy.ts
    - frontend/src/components/vulnerabilities/chip-bar.tsx
    - frontend/src/components/vulnerabilities/vuln-table.tsx
    - frontend/src/components/tickets/sla-pill.test.tsx
    - frontend/src/components/tickets/vuln-count.test.tsx
    - frontend/src/components/assets/severity-ribbon.test.tsx
    - frontend/src/components/ui/ChipBar.test.tsx

key-decisions:
  - "Mechanical, no-judgment migration: swap ONLY the text- class token; border-/bg-/var()-stroke severity-high uses left untouched (RiskRing SVG gradient, trend-chart line stroke, login swatch dot, and the border-/bg- halves of sla-pill/directory-table/remediation-timeline)"
  - "Dark theme confirmed byte-identical no-op by construction (on-soft dark value = existing severity-high dark value from Plan 20-01) — no dark-mode regression risk"
  - "Live axe sweep deliberately deferred to Plan 20-03 (separate wave) rather than combined into this plan, to avoid one executor context both editing 21 files and standing up the full docker/prod-build/Playwright gate"

patterns-established: []

requirements-completed: [UX-D-03-02, UX-D-03-03]

# Metrics
duration: 20min
completed: 2026-07-21
---

# Phase 20 Plan 02: Severity-High Consumer Migration Summary

**Migrated all 18 foreground `text-severity-high` sites across 17 components to the AA-compliant `text-[var(--color-severity-high-on-soft)]` token, leaving non-text (border/bg/stroke) uses untouched, and statically proved zero regression (723/723 unit tests, clean `tsc`, 16/16 routes ≤250 KB, 0 KB JS delta).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-21T08:51:00Z (approx, per STATE.md session marker)
- **Completed:** 2026-07-21T09:08:22Z
- **Tasks:** 3 completed
- **Files modified:** 21 (17 source + 4 test)

## Accomplishments
- All 18 foreground severity-high text/glyph sites (tickets detail page, RiskRing center score, trend-chart legend arrow, severity-glyph map, vuln-count High span, sla-pill Soon tier, ticket-drill-content glyph map, top5-card glyph, directory-table score>=50 branch, asset-vulns-list HIGH tint, remediation-timeline IN_PROGRESS, assets-table BAND_TINT, severity-ribbon High entry, risk-card tintClass, cspm/microcopy HIGH tint, chip-bar glyph map, and vuln-table's two hits — glyph map + Soon SLA tone) now render via `text-[var(--color-severity-high-on-soft)]`
- All 4 affected unit-test files (sla-pill, vuln-count, severity-ribbon, ChipBar) updated to assert/carry the on-soft class; the `vuln-count.test.tsx` `it()` title prose also updated for grep-cleanliness
- Non-text severity-high uses confirmed untouched: `bg-severity-high` still present in sla-pill.tsx, directory-table.tsx, remediation-timeline.tsx, login/page.tsx; trend-chart.tsx still carries the `var(--color-severity-high)` chart-line stroke
- Full static no-regression gate green: `npx vitest run` 723/723 passed, `npx tsc --noEmit` clean, `next build` succeeded with every route ≤250 KB (0 KB First-Load-JS delta — CSS-class-string change only, no new import/dependency)

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate the 18 foreground text-severity-high sites to the on-soft token** - `1415bf2` (feat)
2. **Task 2: Update the affected unit-test assertions and run the unit suite** - `f8202b5` (test)
3. **Task 3: Static no-regression gate — full unit suite, typecheck, and bundle budget** - (this SUMMARY commit; no code changes, verification-only task)

**Plan metadata:** (pending — see final commit below)

## Files Created/Modified
- `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` - SEVERITY glyph map `high` entry → on-soft token
- `frontend/src/components/ui/RiskRing.tsx` - BAND_TINT `high` (center score text) → on-soft token
- `frontend/src/components/ui/trend-chart.tsx` - aria-hidden legend arrow span → on-soft token (chart line stroke `var(--color-severity-high)` on line 48 left untouched)
- `frontend/src/components/tickets/severity-glyph.ts` - SEVERITY_CLASS `high` glyph map → on-soft token
- `frontend/src/components/tickets/vuln-count.tsx` - High count span + doc comment → on-soft token
- `frontend/src/components/tickets/sla-pill.tsx` - Soon tier `text-` token migrated; `border-severity-high/30 bg-severity-high/10` left in place
- `frontend/src/components/tickets/ticket-drill-content.tsx` - glyph map `high` entry → on-soft token
- `frontend/src/components/dashboard/top5-card.tsx` - GLYPH_COLOR `HIGH` → on-soft token
- `frontend/src/components/users/directory-table.tsx` - score>=50 branch `text-` token migrated; `border-/bg-` left in place
- `frontend/src/components/assets/asset-vulns-list.tsx` - HIGH tint → on-soft token
- `frontend/src/components/assets/remediation-timeline.tsx` - IN_PROGRESS `text-` token migrated; `border-/bg-` left in place
- `frontend/src/components/assets/assets-table.tsx` - BAND_TINT `high` → on-soft token
- `frontend/src/components/assets/severity-ribbon.tsx` - High ribbon entry tint → on-soft token
- `frontend/src/components/assets/risk-card.tsx` - `tintClass="text-severity-high"` → on-soft token
- `frontend/src/components/cspm/microcopy.ts` - HIGH tint → on-soft token
- `frontend/src/components/vulnerabilities/chip-bar.tsx` - severity glyph map `high` → on-soft token
- `frontend/src/components/vulnerabilities/vuln-table.tsx` - GLYPH_COLOR `high` AND slaBand Soon tone `text-severity-high` (both hits, the `/dashboard/vulnerabilities` failure site) → on-soft token
- `frontend/src/components/tickets/sla-pill.test.tsx` - Soon pill assertion → on-soft class
- `frontend/src/components/tickets/vuln-count.test.tsx` - High span assertion + it() title prose → on-soft class
- `frontend/src/components/assets/severity-ribbon.test.tsx` - High ribbon assertion → on-soft class
- `frontend/src/components/ui/ChipBar.test.tsx` - SEVERITY_AXIS fixture glyphClassName → on-soft class

## Decisions Made
- Mechanical migration rule applied verbatim per the plan's `<migration-rule>`: only the foreground `text-` class token was swapped; `border-`/`bg-`/`var()` severity-high uses were left byte-identical
- No live server / docker / Playwright axe sweep attempted in this plan — that evidence-gathering step is Plan 20-03's sole job, keeping this executor's context scoped to the 21-file edit + static gate
- `frontend/node_modules` symlinked from the main repo checkout (`/Users/chemencedji/Desktop/getvul/frontend/node_modules`) into this worktree to run vitest/tsc/next build, since worktree checkouts don't carry their own `node_modules` (gitignored, not worktree-portable — the same constraint noted in Phase 18/19 SUMMARYs). `package.json` in the worktree was diffed byte-identical against the main checkout before symlinking, so dependency versions are guaranteed consistent. The symlink itself is untracked/gitignored and was not committed.

## Deviations from Plan

None - plan executed exactly as written. The `node_modules` symlink above is a Rule 3 (auto-fix blocking issue) workaround to run the plan's own mandated verification commands inside a worktree that doesn't ship its own `node_modules` — no code or test behavior was altered by it.

## Issues Encountered

**Worktree stale-base hazard (pre-task, resolved before any plan work began):** The mandatory worktree branch check found `git merge-base HEAD 565aa36a9e7e56832cfe9c01127267dabccdeb98` returned `7c9063a` (a pre-Phase-16-era commit), not the expected `565aa36` (post-Phase-20-01 tip). Ran the explicitly-permitted `git reset --hard 565aa36a9e7e56832cfe9c01127267dabccdeb98` per the branch-check step before any task work began — confirmed clean tree, `--color-severity-high-on-soft` present (count 2) in globals.css, and no prior work was lost (the worktree contained nothing of its own yet).

**Missing `node_modules` in the worktree:** `npx vitest run` initially failed with `ERR_MODULE_NOT_FOUND: vitest`. Root-caused to the worktree not carrying its own `frontend/node_modules` (gitignored, not portable across worktrees — a documented recurring constraint, see Phase 18/19 SUMMARYs). Resolved via Rule 3 (blocking issue) by symlinking `frontend/node_modules` from the main repo checkout after confirming `package.json` was byte-identical between the two checkouts.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 20-03 can now stand up the live docker/prod-build/Playwright axe sweep against a codebase where every foreground severity-high site statically resolves to the AA-compliant on-soft token in both themes
- Dark rendering is guaranteed unchanged (on-soft dark value = existing severity-high dark value, established in Plan 20-01) — the dark axe sweep in 20-03 should stay green
- The `/dashboard/vulnerabilities` failure site (vuln-table.tsx GLYPH_COLOR + slaBand Soon tone) is migrated — this is the specific route the phase's audit flagged as failing AA
- No blockers

---
*Phase: 20-light-theme-severity-high-aa*
*Completed: 2026-07-21*

## Self-Check: PASSED

All 21 created/modified files confirmed present on disk; both task commit hashes (`1415bf2`, `f8202b5`) confirmed in git log.
