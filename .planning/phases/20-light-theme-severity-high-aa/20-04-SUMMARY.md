---
phase: 20-light-theme-severity-high-aa
plan: 04
subsystem: ui
tags: [design-tokens, css-custom-properties, wcag-aa, light-theme, sketch-findings-getvul, tailwind, playwright, axe-core]

# Dependency graph
requires:
  - phase: 20-01
    provides: "--color-severity-high-on-soft token + skill-reconciliation precedent (mirrored exactly for severity-critical)"
  - phase: 20-03
    provides: "Live axe-sweep gate + deferred-items.md scoping the severity-critical-on-soft gap as the ONE remaining blocker"
provides:
  - "--color-severity-critical-on-soft CSS custom property (light #991B1B, dark #F87171 no-op) in globals.css, reconciled into all 3 design-skill files"
  - "All FOREGROUND text-severity-critical sites (27 source files) migrated to text-[var(--color-severity-critical-on-soft)]; border-/bg-/ring- severity-critical utilities left bare"
  - "8 affected unit-test files updated to assert the on-soft class"
  - "LIVE proof: AXE_BOTH_THEMES_GREEN — both blocking axe describes pass end-to-end (11/11 routes each) on a live prod build"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: ["Foreground-only token migration (mirrors 20-02): swap only the `text-`/`hover:text-` utility token in combined class strings, leaving `border-`/`bg-`/`ring-` on the base accent"]

key-files:
  created: []
  modified:
    - frontend/src/app/globals.css
    - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css
    - .claude/skills/sketch-findings-getvul/references/foundation.md
    - .claude/skills/sketch-findings-getvul/references/visual-language.md
    - "frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx"
    - frontend/src/components/assets/asset-vulns-list.tsx
    - frontend/src/components/assets/assets-table.tsx
    - frontend/src/components/assets/reassign-combobox.tsx
    - frontend/src/components/assets/risk-card.tsx
    - frontend/src/components/assets/severity-ribbon.tsx
    - frontend/src/components/connectors/connector-card.tsx
    - frontend/src/components/connectors/connector-form.tsx
    - frontend/src/components/connectors/sync-status-pill.tsx
    - frontend/src/components/connectors/wizard/confirm-step.tsx
    - frontend/src/components/connectors/wizard/test-step.tsx
    - frontend/src/components/cspm/microcopy.ts
    - frontend/src/components/dashboard/top5-card.tsx
    - frontend/src/components/tickets/blocked-toggle.tsx
    - frontend/src/components/tickets/kanban-column.tsx
    - frontend/src/components/tickets/kanban-reason-prompt.tsx
    - frontend/src/components/tickets/severity-glyph.ts
    - frontend/src/components/tickets/sla-pill.tsx
    - frontend/src/components/tickets/status-pill.tsx
    - frontend/src/components/tickets/ticket-bulk-bar.tsx
    - frontend/src/components/tickets/ticket-drill-content.tsx
    - frontend/src/components/tickets/vuln-count.tsx
    - frontend/src/components/ui/RiskRing.tsx
    - frontend/src/components/ui/trend-chart.tsx
    - frontend/src/components/users/directory-table.tsx
    - frontend/src/components/vulnerabilities/chip-bar.tsx
    - frontend/src/components/vulnerabilities/drill-content.tsx
    - frontend/src/components/vulnerabilities/vuln-table.tsx
    - frontend/src/components/connectors/sync-status-pill.test.tsx
    - frontend/src/components/ui/ChipBar.test.tsx
    - frontend/src/components/ui/RiskRing.test.tsx
    - frontend/src/components/tickets/status-pill.test.tsx
    - frontend/src/components/tickets/vuln-count.test.tsx
    - frontend/src/components/tickets/sla-pill.test.tsx
    - frontend/src/components/assets/assets-table.test.tsx
    - frontend/src/components/assets/asset-vulns-list.test.tsx
    - .planning/phases/20-light-theme-severity-high-aa/deferred-items.md

key-decisions:
  - "Light value #991B1B (red-800) chosen per the authorizing prompt's authoritative-values block: ~7.45:1 on the severity-critical /10 tint (#F7F2EA-based) — the exact failing surface (bare #DC2626 measured 4.33:1). Clears 4.5:1 with wide margin, mirrors the orange-600→orange-800 pattern from 20-01's severity-high-on-soft."
  - "Dark value #F87171 = the current --color-severity-critical dark value (sunset.css :root, unoverridden by the dark block) — a byte-identical no-op, so the dark sweep stays 100% green by construction, exactly mirroring severity-high-on-soft."
  - "Migration blast radius (27 source files) is larger than deferred-items.md's original ~12-file estimate: severity-critical is reused both as the severity-LEVEL tint (glyph maps, RiskRing, SLA overdue tone, chip-bar, severity-ribbon, assets-table BAND_TINT — the same component shapes 20-02 touched for severity-high) AND as the generic 'error/blocked/failed' status accent across connectors (sync-status-pill, connector-form, connector-card, wizard confirm/test steps) and tickets (status-pill, blocked-toggle, kanban-column, kanban-reason-prompt, ticket-bulk-bar). The live grep was treated as ground truth per the plan's instruction, not the deferred-items.md estimate."
  - "blocked-toggle.tsx's text-severity-critical/80 opacity variant was migrated to the plain text-[var(--color-severity-critical-on-soft)] token, dropping the /80 opacity modifier — Tailwind opacity modifiers do not apply to raw var() colors, and the darker on-soft value is already AA-compliant without the decorative dimming."
  - "The live axe sweep (not a static grep) is the arbiter, per the 20-03 false-green-guard convention. It confirmed the migration closed the phase's headline gap with no new violations in either theme."

patterns-established: []

requirements-completed: [UX-D-03-05]

# Metrics
duration: ~50min
completed: 2026-07-21
---

# Phase 20 Plan 04: severity-critical-on-soft Gap Closure — AXE_BOTH_THEMES_GREEN Summary

**Added the missing `--color-severity-critical-on-soft` design token (light `#991B1B` / dark `#F87171` no-op), migrated all 27 foreground `text-severity-critical` consumer files to it, and proved live on a production build that BOTH the dark and light blocking axe sweeps now pass end-to-end across all 11 swept routes — closing the phase's headline requirement UX-D-03-05.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-07-21T13:15:00Z (approx)
- **Completed:** 2026-07-21T14:05:00Z (approx)
- **Tasks:** 5 (gap-closure steps, authorized inline — no separate PLAN.md)
- **Files modified:** 39 (4 token/skill + 27 source + 8 test) + `deferred-items.md`

## Accomplishments

- Added `--color-severity-critical-on-soft` to `frontend/src/app/globals.css`: light `#991B1B` (red-800, ~7.45:1 on the `#F7F2EA`-based severity-critical `/10` tint — the exact surface the 20-03 live sweep measured at 4.33:1 with the bare `#DC2626`); dark `#F87171` (byte-identical to the existing `--color-severity-critical` dark value, a true no-op).
- Reconciled the token into all three design-skill files (`sunset.css`, `foundation.md`, `visual-language.md`), mirroring the exact style/placement used for `severity-high-on-soft` in Plan 20-01.
- Migrated every FOREGROUND `text-severity-critical` (and `hover:text-severity-critical`) occurrence across 27 source files to `text-[var(--color-severity-critical-on-soft)]`, leaving all `border-`/`bg-`/`ring-` severity-critical utilities untouched (mechanical rule identical to Plan 20-02).
- Updated 8 affected unit-test files (`sync-status-pill.test.tsx`, `ChipBar.test.tsx`, `RiskRing.test.tsx`, `status-pill.test.tsx`, `vuln-count.test.tsx`, `sla-pill.test.tsx`, `assets-table.test.tsx`, `asset-vulns-list.test.tsx`) to assert the on-soft class.
- Full static gate green: `npx vitest run` → 723/723 tests passed; `npx tsc --noEmit` → clean.
- **Ran the live prod-build axe sweep and it printed `AXE_BOTH_THEMES_GREEN`** — the exact same exit-code-gated command from 20-03, unmodified, on a real Playwright run against a real `next start -p 3000` server backed by the live docker stack (postgres/redis/backend, already up 24h+ from the prior session). Both the dark "all routes (blocking)" and light "light theme (blocking)" describes passed, each reaching `[axe] {theme} sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-...` — the same `/dashboard/tickets/<id>` route that failed in 20-03 (on the exact Blocked-badge nodes migrated here) now passes clean in light mode.
- `next build` route table: all 16 routes ≤250 KB First Load JS, 0 KB delta vs. the 20-03 baseline (pure CSS-class-string swaps).
- Marked `deferred-items.md` item 1 (severity-critical-on-soft) RESOLVED with commit references.

## Task Commits

Each step was committed atomically:

1. **Step 1: Add token + reconcile into design skill** - `e9d94b9` (feat)
2. **Step 2: Migrate foreground severity-critical sites** - `d021a81` (feat)
3. **Step 3: Update test assertions** - `ab78037` (test)
4. **Step 4: Live axe gate** - evidence-only, no code change beyond steps 1-3 (see raw output below)
5. **Step 5: Record evidence** - this SUMMARY + `deferred-items.md` update (docs commit, see below)

## Files Created/Modified

**Token + skill (Step 1):**
- `frontend/src/app/globals.css` - `--color-severity-critical-on-soft: #991B1B` (light) / `#F87171` (dark, no-op)
- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css` - mirrored light value + dark no-op comment
- `.claude/skills/sketch-findings-getvul/references/foundation.md` - on-soft annotation + severity-table note extended
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` - new `severity-critical` row in the light-mode "Text on -soft fills" table + prose note

**Foreground migration (Step 2) — 27 files**, grouped by the two reuse classes discovered live:

*Severity-level tint (mirrors 20-02's severity-high component set):*
- `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` - SEVERITY_GLYPH `critical` entry
- `frontend/src/components/ui/RiskRing.tsx` - BAND_TINT `critical`
- `frontend/src/components/ui/trend-chart.tsx` - legend arrow span
- `frontend/src/components/tickets/severity-glyph.ts` - SEVERITY_CLASS `critical`
- `frontend/src/components/tickets/vuln-count.tsx` - Critical count span + doc comment
- `frontend/src/components/tickets/ticket-drill-content.tsx` - glyph map `critical`
- `frontend/src/components/dashboard/top5-card.tsx` - GLYPH_COLOR `CRITICAL`
- `frontend/src/components/users/directory-table.tsx` - score>=80 branch
- `frontend/src/components/assets/asset-vulns-list.tsx` - CRITICAL tint + KEV badge text
- `frontend/src/components/assets/assets-table.tsx` - BAND_TINT `critical`
- `frontend/src/components/assets/severity-ribbon.tsx` - Critical ribbon entry tint
- `frontend/src/components/assets/risk-card.tsx` - `tintClass="text-severity-critical"`
- `frontend/src/components/assets/reassign-combobox.tsx` - mutation-error alert text
- `frontend/src/components/cspm/microcopy.ts` - CRITICAL tint
- `frontend/src/components/vulnerabilities/chip-bar.tsx` - severity glyph map `critical`
- `frontend/src/components/vulnerabilities/drill-content.tsx` - severity pill text + KEV badge text (2 sites)
- `frontend/src/components/vulnerabilities/vuln-table.tsx` - GLYPH_COLOR `critical`, slaBand overdue tone, 2× KEV badge text (4 sites)

*Status/error accent reuse (new class discovered live, not in 20-02's scope):*
- `frontend/src/components/connectors/connector-form.tsx` - test-result failure block + form-level error block (2 sites)
- `frontend/src/components/connectors/sync-status-pill.tsx` - `failed` pillClass
- `frontend/src/components/connectors/connector-card.tsx` - Delete button hover accent
- `frontend/src/components/connectors/wizard/confirm-step.tsx` - submit-error block
- `frontend/src/components/connectors/wizard/test-step.tsx` - test-failure block
- `frontend/src/components/tickets/status-pill.tsx` - BLOCKED_CONFIG classes
- `frontend/src/components/tickets/kanban-reason-prompt.tsx` - Save button text
- `frontend/src/components/tickets/blocked-toggle.tsx` - Blocked badge text, reason `/80`-opacity span (opacity dropped), Mark-blocked hover accent, Save button text (4 sites — includes the exact nodes the 20-03 sweep flagged)
- `frontend/src/components/tickets/ticket-bulk-bar.tsx` - Mark-blocked button (toolbar + modal confirm, 2 sites)
- `frontend/src/components/tickets/kanban-column.tsx` - `blocked` column accent

**Test updates (Step 3) — 8 files:**
- `frontend/src/components/connectors/sync-status-pill.test.tsx`, `frontend/src/components/ui/ChipBar.test.tsx`, `frontend/src/components/ui/RiskRing.test.tsx`, `frontend/src/components/tickets/status-pill.test.tsx`, `frontend/src/components/tickets/vuln-count.test.tsx`, `frontend/src/components/tickets/sla-pill.test.tsx`, `frontend/src/components/assets/assets-table.test.tsx` (CSS attribute selector updated from `text-severity-critical` substring to `severity-critical-on-soft` substring), `frontend/src/components/assets/asset-vulns-list.test.tsx`

## RAW Sweep Output — LIVE run (proof of AXE_BOTH_THEMES_GREEN)

Environment: docker stack (postgres/redis/backend) already up 24h+ and healthy from the prior 20-03 session; `admin@getvul.local / Admin123!` login confirmed 200 (no 401 gate needed); `npm run build` succeeded; stale `next-server`/`next start` processes killed; fresh `next start -p 3000` served on :3000 only; stale `e2e/.auth/state.json` deleted so the setup project re-authenticates against the current build.

Exact command (verbatim from the 20-03 precedent, unmodified):

```
set -o pipefail; cd frontend && npx playwright test --config=e2e/playwright.config.ts a11y-routes 2>&1 | tee /tmp/20-axe.log; test "$?" = "0" && grep -qE "✓.*light theme \(blocking\)" /tmp/20-axe.log && grep -qE "✓.*all routes \(blocking\)" /tmp/20-axe.log && grep -q "\[axe\] light sweep completed:" /tmp/20-axe.log && echo AXE_BOTH_THEMES_GREEN
```

Raw output:

```
Running 7 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (681ms)
[axe] dark sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-d09d-44b9-afe2-9f204795f14a
  ✓  2 [chromium-a11y] › e2e/a11y-routes.spec.ts:22:7 › WCAG 2.1 AA axe sweep — all routes (blocking) › sweeps all routes for critical/serious violations (5.8s)
[axe] light sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-d09d-44b9-afe2-9f204795f14a
  ✓  3 [chromium-a11y] › e2e/a11y-routes.spec.ts:92:7 › WCAG 2.1 AA axe sweep — light theme (blocking) › sweeps all routes for critical/serious violations in light mode (3.8s)
  ✓  4 [chromium-a11y] › e2e/a11y-routes.spec.ts:150:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (dark) (1.2s)
  ✓  5 [chromium-a11y] › e2e/a11y-routes.spec.ts:184:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (light) (1.2s)
  ✓  6 [chromium-a11y] › e2e/a11y-routes.spec.ts:239:7 › Bottom-nav visibility + More-sheet at 360px › nav[aria-label="Mobile navigation"] is visible on /dashboard at 360px (215ms)
  ✓  7 [chromium-a11y] › e2e/a11y-routes.spec.ts:246:7 › Bottom-nav visibility + More-sheet at 360px › clicking "More" button opens the "More navigation" sheet (283ms)

  7 passed (14.2s)
AXE_BOTH_THEMES_GREEN
```

**Interpretation:** `AXE_BOTH_THEMES_GREEN` printed because ALL of the following held simultaneously: Playwright's real exit code was `0` (via `set -o pipefail` + `test "$?" = "0"`, zsh-portable); the light "light theme (blocking)" describe shows a passing `✓` line; the dark "all routes (blocking)" describe shows a passing `✓` line; the unconditional `[axe] light sweep completed:` summary line is present. Both themes reached `N = 11 routes` (9 static + 2 discovered detail routes: one asset `[id]`, one ticket `[id]`) — identical to the 20-03 baseline, confirming no route was skipped or added. The last route swept in both themes is `/dashboard/tickets/475e4a5d-...` — the exact route whose Blocked-badge nodes failed at 4.33:1 in 20-03 — and it now passes clean in light mode.

## Build Route Table (First-Load JS budget)

```
Route (app)                                 Size  First Load JS
┌ ○ /                                      124 B         102 kB
├ ○ /_not-found                            998 B         103 kB
├ ○ /change-password                     1.37 kB         143 kB
├ ƒ /dashboard                           9.74 kB         138 kB
├ ƒ /dashboard/assets                    5.12 kB         130 kB
├ ƒ /dashboard/assets/[id]               9.72 kB         161 kB
├ ƒ /dashboard/connectors                14.3 kB         156 kB
├ ƒ /dashboard/cspm                      9.43 kB         157 kB
├ ƒ /dashboard/settings                  14.5 kB         156 kB
├ ƒ /dashboard/tickets                      7 kB         167 kB
├ ƒ /dashboard/tickets/[id]              9.71 kB         138 kB
├ ƒ /dashboard/tickets/rules             3.72 kB         126 kB
├ ƒ /dashboard/users                     6.63 kB         129 kB
├ ƒ /dashboard/vulnerabilities           7.08 kB         158 kB
├ ○ /dev/primitives                        124 B         102 kB
└ ○ /login                               4.01 kB         146 kB
+ First Load JS shared by all             102 kB
```

All 16 routes ≤ 250 KB. Delta vs. the 20-03 baseline: **0 KB** (pure CSS-class-string swaps, no new imports/dependencies). Server was killed and `:3000` left clean after the run (`curl` to `:3000` returns connection-refused / empty status post-cleanup).

## Decisions Made

- Used the authoritative light (`#991B1B`) and dark (`#F87171`) values supplied inline in the gap-closure authorization, rather than inventing new hex values — consistent with CLAUDE.md's "don't pick hex colors freehand" and the exact process 20-01 used for severity-high.
- Extended the migration beyond `deferred-items.md`'s original ~12-file blast-radius estimate to the full 27-file set the live `grep -rn 'text-severity-critical' frontend/src` returned, because the plan explicitly treats the live grep (and ultimately the live sweep) as ground truth, not the earlier scoping estimate.
- Migrated the `text-severity-critical/80` opacity variant in `blocked-toggle.tsx` to the plain on-soft token (dropping the opacity), per the plan's explicit instruction that Tailwind opacity modifiers don't apply to raw `var()` colors and the darker on-soft is already AA without it.

## Deviations from Plan

None beyond the explicitly-authorized broader blast radius above (itself anticipated by the plan's "the sweep, not the file list, is the arbiter" framing). No architectural changes, no new tokens beyond the one specified, no test behavior changes beyond updating the migrated class assertions.

## Issues Encountered

None. Docker stack, admin login, prod build, and the Playwright sweep all worked cleanly in this session (stack was already up and healthy from the prior 20-03 session, so no `docker-compose up` cold-start was needed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **UX-D-03-05 is now fully satisfied**: the milestone's headline promise ("WCAG AA in light mode on every authed route") is met at HEAD, proven by a live, exit-code-gated, un-fakeable sweep covering both themes across all 11 routes.
- `deferred-items.md` item 1 marked RESOLVED below with commit references; item 2 (base `text-violet`) was already resolved in 20-03.
- No known remaining light-theme AA gaps in this phase's scope. Phase 20 is ready for phase-level verification/closure by the orchestrator.
- No blockers.

---
*Phase: 20-light-theme-severity-high-aa*
*Completed: 2026-07-21*

## Self-Check: PASSED

All 39 modified files (globals.css, 3 skill files, 27 source files, 8 test files) confirmed present on disk with the expected token/class strings; all 3 task commit hashes (`e9d94b9`, `d021a81`, `ab78037`) confirmed in git log; the live axe-sweep evidence pasted above is the raw, unedited console output from the run executed in this session (not fabricated — see the false-green-guard discussion in 20-03-PLAN.md, which this run satisfies identically).
