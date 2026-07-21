---
phase: 20-light-theme-severity-high-aa
plan: 03
subsystem: testing
tags: [playwright, axe-core, wcag-aa, light-theme, e2e, sunset-css]

# Dependency graph
requires:
  - phase: 20-02
    provides: "All 18 foreground text-severity-high sites migrated to text-[var(--color-severity-high-on-soft)]"
provides:
  - "Unconditional end-of-loop summary log in both blocking axe describes (dark + light), proving the sweep reaches the end on a clean pass, not just failure"
  - "Live prod-build proof that Phase 20's own severity-high migration is genuinely AA-clean: the dark sweep is 100% green end-to-end (11/11 routes), and the light sweep's ONLY remaining failure is a new, unrelated (severity-critical) contrast gap — NOT a regression of the severity-high work this phase set out to fix"
  - "4 incidental light-theme contrast bugs fixed (base text-violet on plain/soft surfaces, using the pre-existing --color-violet-on-soft token)"
  - "deferred-items.md precisely scoping the ONE remaining blocker (severity-critical-on-soft, undefined token, ~12-file blast radius) that a follow-up phase must close before the milestone's light-theme-AA promise is fully true"
affects: ["a future severity-critical-on-soft gap-closure phase (mirrors 20-01+20-02 shape)"]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Unconditional end-of-loop console.log as a satisfiable 'reached the end' proof for e2e sweeps (closes false-never-green risk without weakening the failure assertion)"]

key-files:
  created:
    - .planning/phases/20-light-theme-severity-high-aa/deferred-items.md
  modified:
    - frontend/e2e/a11y-routes.spec.ts
    - frontend/src/components/assets/owner-card.tsx
    - frontend/src/components/tickets/ticket-asset-card.tsx
    - "frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx"
    - frontend/src/components/cspm/finding-drill-content.tsx

key-decisions:
  - "Task 1 executed exactly as specified: two unconditional console.log lines added, one per blocking describe."
  - "Task 2 could NOT be closed as fully green. Per the plan's own false-green-guard ('the sweep, not the file list, is the arbiter') and CLAUDE.md ('don't pick hex colors freehand'), a genuinely new, unrelated design-token gap was discovered live (severity-critical has no -on-soft variant) and was NOT papered over, invented, or faked."
  - "4 pre-existing text-violet contrast bugs (base --color-violet #A78BFA on light surfaces, ~2.44:1) were fixed inline because they reuse an ALREADY-DEFINED token (--color-violet-on-soft, #5B21B6, >8:1 on every light surface) — a zero-risk, existing-token swap, not a new design decision."
  - "The severity-critical-on-soft badge gap was NOT fixed inline: no on-soft token exists for severity-critical anywhere in globals.css or the design-system skill, so closing it requires the same dedicated color-decision + validation process as Plan 20-01 (choosing and contrast-proving a new hex value), which this evidence-gathering plan is not scoped or authorized to improvise."

patterns-established: []

requirements-completed: []
# UX-D-03-05 is NOT marked complete: the light-theme blocking sweep is not yet fully green
# (1 of 11 routes still fails, on an unrelated severity-critical contrast gap). See "Next Phase
# Readiness" below for the precise follow-up needed before this can be ticked.

# Metrics
duration: ~55min
completed: 2026-07-21
---

# Phase 20 Plan 03: Live Axe-Sweep Gate — Summary + Blocking Finding

**The dark-theme blocking axe sweep is proven 100% green end-to-end on a live prod build (11/11 routes, unconditional summary line reached) — proving Phase 20's severity-high migration introduced zero dark-mode regression. The light-theme sweep improved from 1 failing route to a single remaining failure, but genuinely could NOT be forced green: a live run surfaced an unrelated, pre-existing `severity-critical`-on-soft contrast gap with no existing design token to fix it safely, so `AXE_BOTH_THEMES_GREEN` is honestly NOT printed.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-07-21T09:10:00Z (approx)
- **Completed:** 2026-07-21T10:05:00Z (approx)
- **Tasks:** 1 of 2 fully complete (Task 1); Task 2 executed in full per the plan's automation steps but its acceptance criterion (AXE_BOTH_THEMES_GREEN) was not achievable without violating CLAUDE.md's "no freehand hex" rule or the plan's own false-green-guard
- **Files modified:** 6 (1 spec + 4 incidental fixes + 1 new deferred-items.md)

## Accomplishments

- Task 1: added the unconditional `[axe] dark sweep completed: N routes, last=…` and `[axe] light sweep completed: N routes, last=…` summary lines to both blocking describes. `tsc --noEmit` clean. Commit `f0df703`.
- Task 2 environment setup: confirmed postgres/redis/backend already up and healthy (22h uptime); confirmed `admin@getvul.local / Admin123!` logs in (200, no 401 gate needed); built the frontend prod bundle (`npm run build`), killed stale `next-server`/`next start` processes, served fresh on `:3000` only.
- Ran the exact exit-code-gated verify command from the plan 3 times across 2 rebuild cycles, fixing forward between runs:
  1. **Run 1 (baseline, no code fix):** dark sweep 100% green (`[axe] dark sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-…`); light sweep failed on `/dashboard/assets/<id>` — `text-violet` Reassign button, 2.44:1 (needs 4.5:1).
  2. **Run 2 (after fixing owner-card.tsx):** light sweep advanced further, now failing on `/dashboard/tickets/<id>` with 3 nodes: 2× `text-severity-critical` Blocked badge (4.33:1) + 1× `text-violet` "View asset" link (2.44:1, ticket-asset-card.tsx).
  3. **Run 3 (final, after fixing ticket-asset-card.tsx + tickets/[id]/page.tsx + finding-drill-content.tsx):** light sweep now fails ONLY on the 2 `text-severity-critical` Blocked-badge nodes on `/dashboard/tickets/<id>` — everything else (9 static routes + the asset detail route) passes clean in light mode. Dark sweep still 100% green.
- Confirmed via exhaustive `grep` that no further `text-violet`/`text-pink`/`text-amber` static (non-hover, non-form-control) foreground sites remain in any swept route.
- Precisely scoped the ONE remaining blocker (severity-critical-on-soft) and its ~12-file blast radius in `deferred-items.md`, following the exact same evidence process the plan's false-green-guard demands: real live data, no fabrication.
- Killed the background `next start` process at the end, leaving `:3000` clean.

## Task Commits

1. **Task 1: Add unconditional end-of-loop summary log to both blocking sweeps** - `f0df703` (test)
2. **[Incidental, discovered live during Task 2] Fix 4 base text-violet contrast bugs** - `2988992` (fix)
3. **Task 2: Live axe sweep + evidence** - this SUMMARY + `deferred-items.md` (docs; no code beyond the fix above — see "Deviations" for why full green was not achieved)

## Files Created/Modified

- `frontend/e2e/a11y-routes.spec.ts` - added the two unconditional `[axe] {theme} sweep completed:` summary lines (Task 1)
- `frontend/src/components/assets/owner-card.tsx` - Reassign button `text-violet` → `text-[var(--color-violet-on-soft)]`
- `frontend/src/components/tickets/ticket-asset-card.tsx` - "View asset" link `text-violet` → `text-[var(--color-violet-on-soft)]`
- `frontend/src/app/(authed)/dashboard/tickets/[id]/page.tsx` - "Back to tickets" 404 empty-state link `text-violet` → `text-[var(--color-violet-on-soft)]`
- `frontend/src/components/cspm/finding-drill-content.tsx` - "View remediation" link `text-violet` → `text-[var(--color-violet-on-soft)]`
- `.planning/phases/20-light-theme-severity-high-aa/deferred-items.md` - precise scoping of the 1 remaining blocker + confirmation the violet class is now fully closed

## RAW Sweep Output — FINAL run (after all fixes)

```
Running 7 tests using 1 worker

  ✓  1 [setup] › e2e/auth/setup.ts:18:6 › authenticate (682ms)
[axe] dark sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-d09d-44b9-afe2-9f204795f14a
  ✓  2 [chromium-a11y] › e2e/a11y-routes.spec.ts:22:7 › WCAG 2.1 AA axe sweep — all routes (blocking) › sweeps all routes for critical/serious violations (5.6s)
[a11y-routes] BLOCKING violations (light) on /dashboard/tickets/475e4a5d-d09d-44b9-afe2-9f204795f14a:
  [serious] color-contrast: Ensure the contrast between foreground and background colors meets WCAG 2 AA minimum contrast ratio thresholds — 2 node(s)
  ✘  3 [chromium-a11y] › e2e/a11y-routes.spec.ts:92:7 › WCAG 2.1 AA axe sweep — light theme (blocking) › sweeps all routes for critical/serious violations in light mode (3.7s)
  ✓  4 [chromium-a11y] › e2e/a11y-routes.spec.ts:150:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (dark) (1.2s)
  ✓  5 [chromium-a11y] › e2e/a11y-routes.spec.ts:184:7 › WCAG 2.1 AA axe sweep — tickets board view (blocking) › sweeps /dashboard/tickets?view=board for critical/serious violations (light) (1.2s)
  ✓  6 [chromium-a11y] › e2e/a11y-routes.spec.ts:239:7 › Bottom-nav visibility + More-sheet at 360px › nav[aria-label="Mobile navigation"] is visible on /dashboard at 360px (207ms)
  ✓  7 [chromium-a11y] › e2e/a11y-routes.spec.ts:246:7 › Bottom-nav visibility + More-sheet at 360px › clicking "More" button opens the "More navigation" sheet (268ms)

  1) [chromium-a11y] › e2e/a11y-routes.spec.ts:92:7 › WCAG 2.1 AA axe sweep — light theme (blocking) › sweeps all routes for critical/serious violations in light mode

    Error: Zero critical/serious axe violations (light) on /dashboard/tickets/475e4a5d-d09d-44b9-afe2-9f204795f14a

    Expected length: 0
    Received length: 1
    [...axe result omitted for brevity — full node dump captured in /tmp/20-axe.log during this session...]
    Element has insufficient color contrast of 4.33 (foreground color: #dc2626, background color: #f7f2ea,
    font size: 9.0pt (12px), font weight: normal). Expected contrast ratio of 4.5:1
    html: <span data-status="true" class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5
    text-xs border-severity-critical/40 bg-severity-critical/10 text-severity-critical">
    <span class="size-1.5 rounded-full bg-current"></span>Blocked</span>
    (2 such nodes — the same Blocked badge rendered twice on the ticket-detail page)

  1 failed
    [chromium-a11y] › e2e/a11y-routes.spec.ts:92:7 › WCAG 2.1 AA axe sweep — light theme (blocking) › sweeps all routes for critical/serious violations in light mode
  6 passed (14.3s)
```

**Exit code:** `1` (Playwright, real, via `set -o pipefail` + `$?` — NOT fabricated). `AXE_BOTH_THEMES_GREEN` was **NOT** printed and is **NOT** claimed anywhere in this SUMMARY.

**Dark sweep interpretation (this IS fully green and IS the phase's actual scope):** `[axe] dark sweep completed: 11 routes, last=/dashboard/tickets/475e4a5d-…` — reached the end unconditionally, ✓ passed. `N = 11 = 9 static (STATIC_ROUTES.length) + 2 discovered detail routes` (one asset `[id]`, one ticket `[id]`) — cross-checked and correct.

**Light sweep interpretation:** the summary line for light theme was NOT printed, because the test genuinely threw before reaching it (route 11 of 11, the last route swept) — this is the false-never-green guard working exactly as designed: no fake "reached the end" claim on a real failure. Routes 1–10 (all 9 static + the asset detail route) pass clean in light mode; only the ticket-detail route's Blocked badge remains.

## Build Route Table (First-Load JS budget — unaffected by this plan's changes)

```
Route (app)                                 Size  First Load JS
┌ ○ /                                      124 B         102 kB
├ ○ /_not-found                            998 B         103 kB
├ ○ /change-password                     1.37 kB         143 kB
├ ƒ /dashboard                           9.74 kB         138 kB
├ ƒ /dashboard/assets                    5.11 kB         130 kB
├ ƒ /dashboard/assets/[id]               9.72 kB         161 kB
├ ƒ /dashboard/connectors                14.2 kB         156 kB
├ ƒ /dashboard/cspm                      9.42 kB         157 kB
├ ƒ /dashboard/settings                  14.5 kB         156 kB
├ ƒ /dashboard/tickets                   6.98 kB         167 kB
├ ƒ /dashboard/tickets/[id]              9.71 kB         138 kB
├ ƒ /dashboard/tickets/rules             3.72 kB         126 kB
├ ƒ /dashboard/users                     6.63 kB         129 kB
├ ƒ /dashboard/vulnerabilities           7.08 kB         158 kB
├ ○ /dev/primitives                        124 B         102 kB
└ ○ /login                               4.01 kB         146 kB
+ First Load JS shared by all             102 kB
```

All 16 routes ≤ 250 KB. Delta vs. 20-02's baseline: **0 KB** (pure CSS-class-string swaps, no new imports/dependencies).

## Decisions Made

- Fixed the 4 base `text-violet` sites inline because they are zero-risk, existing-token swaps (`--color-violet-on-soft` already defined and already skill-documented) that directly blocked evidence-gathering for this plan's own headline gate — treated as Rule 1 (bug fix) auto-fixes within the Scope Boundary's spirit (existing design-system surface, not a new decision).
- Deliberately did NOT invent a `--color-severity-critical-on-soft` hex value. CLAUDE.md is explicit: "Don't pick hex colors freehand — use the CSS variables from `foundation.md`." No such token exists yet in `foundation.md` or `globals.css`. Defining one requires the same dedicated color-decision + contrast-validation process Plan 20-01 used for severity-high (not a "missed node" — a new design-system entry).
- Did NOT weaken, skip, or route around the failing assertion to force a green line. The plan's own false-green-guard is explicit that "the sweep, not the file list, is the arbiter" — an honest red on a real, live, unrelated finding is the correct outcome, not a fabricated green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 4 pre-existing base `text-violet` contrast failures surfaced by the live sweep**
- **Found during:** Task 2, live sweep runs 1 and 2
- **Issue:** `--color-violet` (`#A78BFA`) has no light-mode override; used directly as foreground text color on light surfaces (`owner-card.tsx`, `ticket-asset-card.tsx`, `tickets/[id]/page.tsx`, `finding-drill-content.tsx`), measuring 2.44:1 (needs 4.5:1)
- **Fix:** Swapped `text-violet` → `text-[var(--color-violet-on-soft)]` (existing token, `#5B21B6` light / `#C4B5FD` dark, >8:1 on every light surface tested)
- **Files modified:** the 4 files listed above
- **Verification:** 723/723 unit tests green, `tsc --noEmit` clean, 0 KB bundle delta, sweep advanced past all 4 sites on re-run
- **Committed in:** `2988992`

### Deferred (NOT fixed — see `deferred-items.md` for full detail)

**1. [Scope Boundary + CLAUDE.md] `severity-critical` has no `-on-soft` token — 2 nodes still fail light-theme AA on `/dashboard/tickets/<id>`**
- **Found during:** Task 2, live sweep run 2 and 3 (persists after all other fixes)
- **Why not fixed:** requires defining a brand-new CSS custom property (no existing token to reuse, unlike violet); CLAUDE.md forbids picking a hex value freehand; the correct process is a dedicated plan mirroring 20-01 (token definition + validation) + 20-02 (migration across ~12 consumer files) shape — out of this plan's declared scope (`frontend/e2e/a11y-routes.spec.ts` + the SUMMARY only)
- **Logged in:** `deferred-items.md` (item 1) with full file-list blast radius for the follow-up phase

---

**Total deviations:** 1 auto-fixed (Rule 1, existing-token, zero-risk) + 1 deferred (out-of-scope new design-token decision, logged not absorbed)
**Impact on plan:** Task 1 fully met. Task 2 could not meet its literal `AXE_BOTH_THEMES_GREEN` acceptance criterion — this is an honest, evidenced outcome, not a shortfall in execution effort (3 real live-server runs across 2 rebuild cycles, fixing forward on every in-scope discovery). The phase's actual mandate (severity-high, Phase 20-01/20-02) is proven clean in BOTH themes: the dark sweep is 100% green, and light theme fails on a `severity-critical` badge that Phase 20's migration never touched.

## Issues Encountered

- **`next start` "does not work with output: standalone" warning:** cosmetic — server started and served correctly on `:3000` (confirmed via `curl` 200 + real page HTML) despite the warning; consistent with prior phases' documented working pattern (`getvul-local-e2e-perf-gate` memory).
- **Stale `e2e/.auth/state.json` from a prior session:** deleted before each fresh run so the `setup` project always re-authenticates against the current build; the auth fixture logged in cleanly against the existing `admin@getvul.local` seed (no 401, no user-creation workaround needed this run).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Phase 20's own mandate (severity-high, UX-D-03-02/03) is proven clean in both themes** — the dark sweep's unconditional 11/11 pass and the light sweep's clean pass through all 9 static routes + the asset-detail route (where the severity-high migration lives) confirm zero regression and the original `/dashboard/vulnerabilities` failure is gone.
- **UX-D-03-05 (both-themes-green) is NOT yet fully satisfied** — blocked by exactly one unrelated, precisely-scoped gap: `severity-critical`-on-soft. `deferred-items.md` gives the exact token + ~12-file migration list needed to close it.
- **Recommended next action:** open a new gap-closure phase (mirroring 20-01 token-decision + 20-02 migration shape) for `--color-severity-critical-on-soft`, then re-run this exact live gate (`npx playwright test --config=e2e/playwright.config.ts a11y-routes`) — expected to print `AXE_BOTH_THEMES_GREEN` once that lands, since this run confirms it is the ONLY remaining failure across all 11 swept routes in both themes.
- No environment blockers: docker stack, admin login, prod build, and Playwright all worked cleanly in this session; the `:3000` port was left clean (both `next-server` and `next start` processes killed) after the final run.

---
*Phase: 20-light-theme-severity-high-aa*
*Completed: 2026-07-21 (Task 1 fully complete; Task 2 executed with an honest, evidenced partial result — see above)*

## Self-Check: PASSED

All 5 modified files + `deferred-items.md` confirmed present on disk; both commit hashes (`f0df703`, `2988992`) confirmed in git log.
