---
phase: 10-dashboard
plan: 03
subsystem: ui
tags:
  - phase-10
  - frontend
  - primitives
  - card
  - stat
  - stat-strip
  - activity-feed
  - error-boundary
  - vitest
  - axe-core
  - tailwind
  - lucide-react

# Dependency graph
requires:
  - phase: 09-login-foundation
    provides: "Sunset CSS variable system in sunset.css, Tailwind 3.4 tokens in tailwind.config.ts (bg-surface, border-border-subtle, text-success/danger, pink-soft/amber-soft/violet-soft/success-soft), Phase 9 CVA pattern from button.tsx, /dev/primitives page scaffold (D-31)"
  - phase: 10-dashboard/10-02
    provides: "ActivityCategory + ActivityItem types via useRecentNotifications (consumed verbatim by ActivityFeed primitive)"
provides:
  - "Card primitive — variant=surface|elevated|outline, padding=sm|md|lg, with Card.Header / Card.Body / Card.Footer subcomponents (D-P-01)"
  - "Stat primitive — direction-aware delta color (deltaIsGood), Pitfall 8 null handling, flat (delta=0), icon prop, font-mono+tabular-nums value (D-P-02 + D-S-03..05)"
  - "StatStrip primitive — responsive ladder 1col → md:2col → xl:N capped at 4 (D-P-03 + D-M-02)"
  - "ActivityFeed primitive — category → icon-variant mapping for 4 categories, D-A-03 verbatim empty copy, Intl.RelativeTimeFormat 'Xm ago' (D-P-04 + D-A-01..05)"
  - "ErrorBoundary primitive — React 19 class component with fallback render-prop signature (err, reset) (D-P-06)"
  - "/dev/primitives state matrix entries for all 5 new primitives (D-Test-04)"
affects:
  - 10-04 (TrendChart — sibling primitive plan, may consume Card+Stat in showcase)
  - 10-05 (Dashboard page — main consumer of all 5 primitives)
  - 10-06 (Dashboard page tests — page test imports primitives directly)
  - 11+ (vulnerabilities, assets, tickets, cspm screens — Card/Stat/StatStrip reused verbatim)

# Tech tracking
tech-stack:
  added:
    - "class-variance-authority CVA pattern extended to Card primitive (Phase 9 baseline)"
    - "Intl.RelativeTimeFormat for activity feed timestamps (no hand-rolled date math per RESEARCH 'Don't Hand-Roll' table)"
    - "React 19 class component pattern for ErrorBoundary (getDerivedStateFromError + componentDidCatch)"
    - "vitest fake-timers (vi.useFakeTimers + setSystemTime) for deterministic Intl output, with vi.useRealTimers() restoration before axe assertions"
  patterns:
    - "Compound primitive via Object.assign — Card.Header / Card.Body / Card.Footer attached to forwardRef'd Card root"
    - "Direction-aware semantic color — pair text-success/danger with TrendingUp/TrendingDown icon so grayscale users get redundancy (D-S-03)"
    - "Pitfall 8 null-history fallback — render 'Δ —' for delta=null (first-week tenants without snapshot history)"
    - "Tailwind grid-cols literal lookup pattern — Children.count → static class table (NOT template strings, which Tailwind cannot tree-shake)"
    - "fallback render-prop on ErrorBoundary — (err, reset) signature decouples chrome from page-level error copy/code lookup"

key-files:
  created:
    - "frontend/src/components/ui/card.tsx — D-P-01 Card primitive (Card + Card.Header + Card.Body + Card.Footer via Object.assign + CVA)"
    - "frontend/src/components/ui/stat.tsx — D-P-02 Stat primitive (direction-aware delta + Pitfall 8 null handling)"
    - "frontend/src/components/ui/stat-strip.tsx — D-P-03 + D-M-02 StatStrip responsive grid"
    - "frontend/src/components/ui/activity-feed.tsx — D-P-04 + D-A-01..05 ActivityFeed with Intl.RelativeTimeFormat"
    - "frontend/src/components/ui/error-boundary.tsx — D-P-06 React 19 class ErrorBoundary with fallback render-prop"
    - "frontend/src/components/ui/card.test.tsx — 8 vitest cases incl. axe-core (D-Test-01)"
    - "frontend/src/components/ui/stat.test.tsx — 10 vitest cases incl. axe-core (D-Test-01)"
    - "frontend/src/components/ui/stat-strip.test.tsx — 7 vitest cases incl. axe-core (D-Test-01)"
    - "frontend/src/components/ui/activity-feed.test.tsx — 11 vitest cases incl. axe-core (D-Test-01)"
    - "frontend/src/components/ui/error-boundary.test.tsx — 4 vitest cases incl. axe-core (D-Test-01)"
  modified:
    - "frontend/src/app/dev/primitives/page.tsx — extended with 5 new sections (Card variants, Card padding, Stat direction matrix, StatStrip ladder, ActivityFeed categories + empty, ErrorBoundary catch+reset) per D-Test-04. Added 'use client' (now uses useState)"

key-decisions:
  - "ActivityFeed category-tint mapping uses existing Tailwind tokens bg-{pink|amber|violet|success}-soft text-{pink|amber|violet|success} from tailwind.config.ts — the plan's interface block mentioned a possible 'activity-*-tint' token family but those don't exist in sunset.css. Followed D-A-01's spirit (pink/amber/violet/success) using the actual tokens (T-10-19 hex literal gate enforced — 0 hex literals)."
  - "TDD discipline: 2 commits per multi-file task — RED 'test(...)' commit with all failing tests, then GREEN 'feat(...)' commit with all implementations. Plan task boundary preserved (one task = one R/G cycle even when spanning 3 primitive files)."
  - "Stat hint surfaces below the delta row when both delta and hint are provided (uncovered edge case in the plan's pseudo-code — supports dashboard's 'MTTR · 4.2d / Δ — / vs goal 7d' composition without breaking the delta=undefined hint-direct case)."
  - "axe-core + vi.useFakeTimers conflict — restored real timers inside the axe assertion in activity-feed.test.tsx; fake timers stay scoped to the relative-time assertions so Intl output is deterministic."

patterns-established:
  - "Phase-10 primitive shape: 'use client' + forwardRef where DOM is owned + CVA variants from button.tsx as the baseline + cn() merge for consumer className"
  - "Per-primitive axe assertion: every .test.tsx in components/ui/ MUST include at least one toHaveNoViolations() block — enforced at acceptance"
  - "Tailwind static class lookup for dynamic counts: Children.count → switch over literal class names (xl:grid-cols-1 / xl:grid-cols-2 / xl:grid-cols-3 / xl:grid-cols-4), never xl:grid-cols-${n} template (tree-shake safe)"
  - "Error boundary discipline: log only in NODE_ENV !== 'production'; fallback render-prop owns user-facing copy so the boundary itself stays generic (T-10-18)"

requirements-completed:
  - UX-02-02
  - UX-02-05
  - UX-02-06

# Metrics
duration: ~12min
completed: 2026-05-15
---

# Phase 10 Plan 03: Five Phase-10 presentation primitives Summary

**Card, Stat, StatStrip, ActivityFeed, ErrorBoundary primitives ship with axe-clean tests, sunset-token consumption (zero hex literals), and a /dev/primitives state matrix — ready for Plan 05 to compose the /dashboard page.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-15T11:30:00Z
- **Completed:** 2026-05-15T11:42:00Z
- **Tasks:** 3
- **Files created:** 10 (5 primitives + 5 test files)
- **Files modified:** 1 (/dev/primitives page extended)

## Accomplishments

- Five new Phase-10 presentation primitives in `frontend/src/components/ui/` with locked API shapes per D-P-01..04 + D-P-06.
- 40 new vitest cases (Card 8 + Stat 10 + StatStrip 7 + ActivityFeed 11 + ErrorBoundary 4) — all green, each test file carries at least one `toHaveNoViolations()` axe assertion (D-Test-01).
- Stat handles every delta shape per spec: `delta>0` (red TrendingUp), `delta<0` (green TrendingDown), `delta=0` (no arrow), `delta=null` ("Δ —" per Pitfall 8). Direction-aware via `deltaIsGood` so "up is bad" tiles (critical_open, sla_at_risk, kev) and "up is good" tiles colorize correctly.
- StatStrip responsive ladder (1col → md:2col → xl:N capped at 4) without caller managing breakpoints.
- ActivityFeed: 4-category icon-variant mapping (D-A-01..02) with verbatim D-A-03 empty copy, `Intl.RelativeTimeFormat` for "Xm ago" (no hand-rolled date math), href-vs-non-link variants per row.
- ErrorBoundary: React 19 class component with `(err, reset) => ReactNode` fallback render-prop; logs only in dev (T-10-18).
- `/dev/primitives` extended with 6 new `<Section>` blocks demonstrating every primitive in its full state matrix; all Phase 9 entries preserved verbatim.
- Full vitest suite green (93/93 across 13 test files) — no Phase 9 or Plan 02 regressions.
- `npm run build` green; `/dev/primitives` route compiles at 7.13 kB.

## Task Commits

Each task ran the TDD RED → GREEN cycle:

1. **Task 1 RED: Card + Stat + StatStrip tests** — `98f7053` (test)
2. **Task 1 GREEN: Card + Stat + StatStrip impl** — `e2ec9a8` (feat)
3. **Task 2 RED: ActivityFeed + ErrorBoundary tests** — `208f6f9` (test)
4. **Task 2 GREEN: ActivityFeed + ErrorBoundary impl** — `40582c1` (feat)
5. **Task 3: /dev/primitives state matrix extension** — `f7db0ca` (feat)

## Files Created/Modified

- `frontend/src/components/ui/card.tsx` — Card root + Header/Body/Footer subcomponents via Object.assign; CVA variants surface|elevated|outline, padding sm|md|lg.
- `frontend/src/components/ui/stat.tsx` — Stat tile with direction-aware delta block; renders 'Δ —' for null, no arrow for 0, signed number + TrendingUp/Down + text-success/danger otherwise. icon prop renders top-right.
- `frontend/src/components/ui/stat-strip.tsx` — StatStrip wrapping 1–6 children in a responsive grid; literal Tailwind grid-cols class lookup.
- `frontend/src/components/ui/activity-feed.tsx` — ActivityFeed with CATEGORY_META mapping (new_critical_vuln/sla_breach/sync_failure/risk_change → pink/amber/violet/success icon variants + tinted containers); Intl.RelativeTimeFormat timestamps; Next `<Link>` for items with href.
- `frontend/src/components/ui/error-boundary.tsx` — Class component with getDerivedStateFromError + componentDidCatch (dev-only log) + reset method.
- `frontend/src/components/ui/{card,stat,stat-strip,activity-feed,error-boundary}.test.tsx` — 40 vitest cases incl. 5 axe assertions.
- `frontend/src/app/dev/primitives/page.tsx` — extended with Card variants/padding, Stat direction matrix, StatStrip ladder, ActivityFeed categories/empty, ErrorBoundary catch+reset sections. Switched to `'use client'` for useState-driven Bomb child.

## Decisions Made

- **ActivityFeed tint tokens.** Plan's `<interfaces>` block referenced potential `--color-activity-*-tint` variables not in sunset.css. Followed D-A-01's spirit (pink/amber/violet/success) using the actual Tailwind tokens (`bg-pink-soft`, `bg-amber-soft`, `bg-violet-soft`, `bg-success-soft` + matching `text-*`). All four already exist in tailwind.config.ts wrapping sunset.css CSS variables; zero hex literals introduced (T-10-19 gate green). No follow-up token addition needed.
- **Stat hint placement when delta is provided.** Plan pseudo-code only rendered `hint` when `delta === undefined`, which would suppress hint text on tiles like "MTTR · 4.2d / Δ — / vs goal 7d". Added a second hint render path (after the delta row) when `delta !== undefined` so consumers can pair both. Kept the original `delta === undefined` path so existing call-sites are unchanged.
- **TDD commit granularity.** Each task with `tdd="true"` produced 2 commits: `test(...)` (RED — all task tests, failing) then `feat(...)` (GREEN — all task implementations). Multi-file tasks share a single R/G cycle rather than per-file alternation, which matches the plan's task grouping.
- **vi.useFakeTimers + axe-core interaction.** Fake timers (for deterministic Intl output) hung axe-core's internal scheduler. Restored real timers inside the axe assertion in activity-feed.test.tsx; fake-timer scope remains tight on the relative-time assertions only.

## Deviations from Plan

None of the changes are scope-altering. Three small spec adjustments were applied transparently while implementing the plan:

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Stat: hint rendering when delta is provided (incl. null)**
- **Found during:** Task 1 (Stat primitive implementation)
- **Issue:** Plan's pseudo-code guarded hint rendering on `delta === undefined`, which would suppress the hint on "MTTR · 4.2d / Δ — / vs goal 7d" tiles — a documented composition in D-S that requires both delta and hint to coexist.
- **Fix:** Added a second hint-render branch for `delta !== undefined` that renders the hint below the delta row.
- **Files modified:** `frontend/src/components/ui/stat.tsx`
- **Verification:** Stat tile renders both delta block and hint without overlap; covered by /dev/primitives MTTR demo tile.
- **Committed in:** `e2ec9a8` (Task 1 GREEN)

**2. [Rule 1 - Bug] activity-feed.test.tsx: axe assertion deadlocked under vi.useFakeTimers**
- **Found during:** Task 2 GREEN verification
- **Issue:** `vi.useFakeTimers()` (set in `beforeEach` for deterministic `Intl.RelativeTimeFormat` output) prevented axe-core from settling its internal promise queue → assertion timed out at 5000ms.
- **Fix:** Called `vi.useRealTimers()` at the top of the axe-only test. Other tests continue under fake timers for stable timestamp assertions.
- **Files modified:** `frontend/src/components/ui/activity-feed.test.tsx`
- **Verification:** Full vitest run passes (93/93); axe assertion completes in <1s.
- **Committed in:** `40582c1` (Task 2 GREEN — fix was made before the impl commit and folded in)

**3. [Rule 2 - Missing Critical] /dev/primitives page needed 'use client' directive**
- **Found during:** Task 3
- **Issue:** Added `useState` for the ErrorBoundary "Click to throw" demo, but the existing page was a Server Component (no `'use client'`). Build would have failed.
- **Fix:** Added `'use client';` to line 1 of the page.
- **Files modified:** `frontend/src/app/dev/primitives/page.tsx`
- **Verification:** `npm run build` green; /dev/primitives compiles at 7.13 kB.
- **Committed in:** `f7db0ca` (Task 3)

---

**Total deviations:** 3 auto-fixed (2 missing critical, 1 bug).
**Impact on plan:** All three are correctness fixes for cases the plan didn't fully spec or implicitly required. No scope creep. All five primitives ship with the exact API the plan locks.

## Issues Encountered

- **Worktree base mismatch on startup.** The worktree HEAD was initially at `8cede77` (a pre-Phase 9 snapshot) instead of the target base `b87bcc8`. Recovered per the worktree_branch_check protocol — fast-forwarded HEAD to `b87bcc80` so the Phase 9 primitives (Button/Input/SsoButton/GradientText/Form/DropdownMenu, sunset.css token system, tailwind.config.ts tokens, vitest infra) were available. No code lost — the reset was a fast-forward, not a destructive rewind.
- **Worktree lacked symlinked node_modules.** Test execution was run against the main repo's `node_modules` (the worktree's frontend/ folder had the source tree but no `node_modules` symlink due to an environment quirk). Implementations and tests were authored in the worktree, mirrored to the main repo for verification, and committed in the worktree. Test execution results (`npm run test -- --run`: 93/93 green, `npm run build`: green) are authoritative since the source files are byte-identical across both locations.

## User Setup Required

None — no external service configuration required. All work is frontend component scaffolding consumed by future plans in this phase.

## Threat Flags

None. The plan's threat model (T-10-16..20) was honored in full:
- T-10-16 (Tampering/XSS): No `dangerouslySetInnerHTML` introduced anywhere; ActivityFeed renders `title` / `body` via React text escaping.
- T-10-17 (Open-redirect): `ActivityFeed` passes `href` straight to Next `<Link>` without manipulation; Link enforces protocol gates at build.
- T-10-18 (Info disclosure): `ErrorBoundary.componentDidCatch` logs only when `NODE_ENV !== 'production'`; fallback render-prop receives only the Error object — sanitization is the consumer's responsibility (Plan 05 will render code+request-ID per copy-voice.md).
- T-10-19 (Hex-literal palette bypass): `grep -E "#[0-9a-fA-F]{3,6}"` over all 5 new primitive files returns 0.
- T-10-20 (Lucide barrel import): All five primitives + dev page use named imports only.

## Next Phase Readiness

- **Plan 04 (TrendChart):** Can begin in parallel — sibling primitive, no shared files.
- **Plan 05 (Dashboard page):** Unblocked. Import paths for downstream consumption: `import { Card } from '@/components/ui/card'`, `import { Stat } from '@/components/ui/stat'`, `import { StatStrip } from '@/components/ui/stat-strip'`, `import { ActivityFeed, type ActivityItem } from '@/components/ui/activity-feed'`, `import { ErrorBoundary } from '@/components/ui/error-boundary'`. No barrel file was added — paths are direct (matches Phase 9 convention).
- **Phases 11–14:** Card / Stat / StatStrip / ActivityFeed / ErrorBoundary are reusable verbatim on /vulnerabilities, /assets, /tickets, /cspm. Sketch findings note that Stat tiles appear on hero strips throughout — no Phase 10 lock-in to /dashboard.

## Self-Check: PASSED

**Files exist (worktree):**
- ✓ `frontend/src/components/ui/card.tsx`
- ✓ `frontend/src/components/ui/stat.tsx`
- ✓ `frontend/src/components/ui/stat-strip.tsx`
- ✓ `frontend/src/components/ui/activity-feed.tsx`
- ✓ `frontend/src/components/ui/error-boundary.tsx`
- ✓ `frontend/src/components/ui/card.test.tsx`
- ✓ `frontend/src/components/ui/stat.test.tsx`
- ✓ `frontend/src/components/ui/stat-strip.test.tsx`
- ✓ `frontend/src/components/ui/activity-feed.test.tsx`
- ✓ `frontend/src/components/ui/error-boundary.test.tsx`
- ✓ `frontend/src/app/dev/primitives/page.tsx` (modified)

**Commits exist:**
- ✓ `98f7053` test(10-03): add failing tests for Card, Stat, StatStrip primitives
- ✓ `e2ec9a8` feat(10-03): implement Card, Stat, StatStrip primitives
- ✓ `208f6f9` test(10-03): add failing tests for ActivityFeed + ErrorBoundary primitives
- ✓ `40582c1` feat(10-03): implement ActivityFeed + ErrorBoundary primitives
- ✓ `f7db0ca` feat(10-03): extend /dev/primitives with state matrix for 5 new Phase 10 primitives

**Verification:**
- ✓ `npm run test -- --run` → 93/93 cases green across 13 test files
- ✓ `npm run build` → green; /dev/primitives at 7.13 kB
- ✓ Acceptance greps: 5 imports from `@/components/ui/{card,stat,stat-strip,activity-feed,error-boundary}` in /dev/primitives; `delta={null}` and `items={[]}` demos present; Phase 9 entries (Button/Input/SsoButton/GradientText) preserved.
- ✓ Hex-literal gate: 0 matches across all 5 primitive files.
- ✓ Lucide barrel gate: 0 matches.
- ✓ axe-clean gate: 5+ `toHaveNoViolations` assertions across the 5 test files.

---
*Phase: 10-dashboard*
*Plan: 03 — Phase 10 new primitives (Card, Stat, StatStrip, ActivityFeed, ErrorBoundary)*
*Completed: 2026-05-15*
