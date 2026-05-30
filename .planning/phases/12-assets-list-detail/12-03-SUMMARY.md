---
phase: 12-assets-list-detail
plan: 03
subsystem: ui
tags: [react, typescript, vitest, tailwind, svg, accessibility, design-system]

# Dependency graph
requires:
  - phase: 11-vulnerabilities-state-patterns
    provides: "test patterns (skeleton-table.test.tsx), `cn` util, vitest+jsdom+@testing-library/react+vitest-axe pipeline"
  - phase: 09-login-foundation
    provides: "sunset CSS variables (--gradient-sunset, --color-severity-*), tailwind token map in tailwind.config.ts"
provides:
  - "RiskRing primitive — SVG ring + center number + 5 edge-case branches; consumed by 12-07 RiskCard and (potentially) /dashboard"
  - "Breadcrumb + Crumb primitive — semantic nav/ol/aria-current; consumed by 12-08 detail page and Phase 13 /tickets/[id]"
  - "Avatar primitive — sunset-gradient circle with initials + XSS guard (T-12-04); consumed by 12-07 owner card, topbar, future directory pages"
  - "osFamily(string|null|undefined) → 'linux'|'windows'|'macos'|'other'; consumed by 12-06 assets chip-bar; MUST stay parity with backend OS_FAMILY_PATTERNS"
  - "OsFamily, RiskBand, RiskRingProps, BreadcrumbProps, CrumbProps, AvatarProps exported types — downstream plans import these as the locked API surface"
affects: [12-06-assets-list, 12-07-risk-and-owner-cards, 12-08-detail-composition, 13-tickets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Co-located *.test.tsx beside the primitive; vitest+jsdom runs them as a single file under ./node_modules/.bin/vitest"
    - "TDD RED→GREEN cycle committed as two atomic commits per primitive group"
    - "Sketch-locked SVG hex triplet (#EC4899/#A78BFA/#F59E0B) permitted ONLY inside the SVG <defs> gradient stops; never in component layout"
    - "Background images and gradients sourced via CSS variables (var(--gradient-sunset)), never literal hex"
    - "T-12-04 XSS mitigation: untrusted name/email props rendered as React text children (auto-escaped), never via dangerouslySetInnerHTML"

key-files:
  created:
    - "frontend/src/components/ui/RiskRing.tsx — 146 lines"
    - "frontend/src/components/ui/RiskRing.test.tsx — 7 tests"
    - "frontend/src/components/ui/Breadcrumb.tsx — 64 lines"
    - "frontend/src/components/ui/Breadcrumb.test.tsx — 3 tests"
    - "frontend/src/components/ui/Avatar.tsx — 53 lines"
    - "frontend/src/components/ui/Avatar.test.tsx — 6 tests"
    - "frontend/src/lib/util/os-family.ts — 35 lines"
    - "frontend/src/lib/util/os-family.test.ts — 15 cases (12 it.each + 3 single)"
  modified: []

key-decisions:
  - "Token substitution: plan referenced text-text-subtle (not a configured tailwind token); replaced with text-text-faint for the 'Risk unavailable' / 'No exposures' captions, text-text-muted for linked breadcrumbs, text-text-faint/60 for the chevron separator. The 'closest valid token per design system' rule from the prompt's <ui_guardrails> drove these choices."
  - "RiskRing ring-bg stroke uses var(--color-border-subtle) rather than the plan's var(--border-subtle); --color-* is the actual CSS variable namespace defined in foundation.md (the prior bare token would not have resolved)."
  - "Bundled Task 2 (Breadcrumb + Avatar + osFamily) into a single RED commit and a single GREEN commit. Each component is logically independent but the plan's Task 2 was authored as a single TDD task; splitting into 6 micro-commits would have produced more git noise than signal. The RED commit has 24 failing tests across 3 files; the GREEN commit makes all 24 pass."
  - "Symlinked frontend/node_modules to the main repo's existing install (identical package.json + package-lock.json) instead of re-running npm install in the worktree. npm install in the worktree failed on lucide-react@0.383.0 peerDep against React 19 because the worktree's NPM_CONFIG_LEGACY_PEER_DEPS context differs; the main-repo install already resolved this and the deps are bit-identical."

patterns-established:
  - "Co-located primitive tests in components/ui/*.test.tsx — vitest auto-discovers; no separate __tests__ directory."
  - "Threat-register-driven XSS guards: when a primitive receives any user-supplied string into the DOM (Avatar.name, Avatar.email), include a dedicated test that passes an XSS payload and asserts no live element appears."
  - "frontend/src/lib/util/ namespace created for non-query, non-component utility helpers. The first inhabitant (os-family) sets the convention: kebab-case file name, named exports, type alias as PascalCase export."
  - "Risk-band → text-tint map (BAND_TINT) instead of inline ternaries. Makes future band-aware UI (RiskCard breakdown rows) reuse the same source of truth."

requirements-completed:
  - UX-04-03
  - UX-04-02

# Metrics
duration: "~5min"
completed: "2026-05-30"
---

# Phase 12 Plan 03: Primitives — RiskRing, Breadcrumb, Avatar, osFamily Summary

**Three new UI primitives (RiskRing with full SVG math + 5 edge-case branches, semantic Breadcrumb with aria-current, Avatar with T-12-04 XSS guard) plus an osFamily helper that stays in lockstep with backend OS_FAMILY_PATTERNS — all consumed verbatim by Wave 3/4 composition plans.**

## Performance

- **Duration:** ~5 min wall-clock (RED1 → GREEN1 → RED2 → GREEN2 + verification)
- **Started:** 2026-05-30T09:19Z (after npm/symlink setup)
- **Completed:** 2026-05-30T09:25Z
- **Tasks:** 2 (Task 1 RiskRing; Task 2 Breadcrumb+Avatar+osFamily)
- **Files created:** 8 (4 sources + 4 co-located tests)
- **Tests added:** 31 (7 + 3 + 6 + 15)
- **Tests passing (full suite):** 322/322 across 53 files

## Accomplishments

- **RiskRing primitive (UX-04-03)** — SVG ring at 100-viewBox with circumference `2π × 40` (~251.3) and `stroke-dashoffset = circ × (1 − score/100)`. Single sunset gradient stroke always per locked_decisions item 5; band color drives only the center number tint via `BAND_TINT` map (D-R-01). Edge cases (D-R-03) covered: score 0 → no arc + em-dash + "No exposures"; score 100 → full arc + danger-tinted center; score null → no arc + em-dash + "Risk unavailable". Exposes `role="img"` with a descriptive `aria-label`.
- **Breadcrumb + Crumb primitive (UX-04-02)** — `<nav aria-label="Breadcrumb">` wrapping an `<ol>`. Linked crumbs render as Next `<Link>` anchors; the last crumb renders as `<li aria-current="page">` with no anchor. Chevron `›` separators are `aria-hidden="true"` and tinted at 60% opacity of the faintest text token.
- **Avatar primitive** — sunset-gradient circle (`var(--gradient-sunset)`) sized at 40px by default; initials derived from `name` first char (uppercased), falling back to email local-part, then `?`. **T-12-04 mitigation verified by test**: rendering `<Avatar name="<img onerror=alert(1)>" />` produces no `<img>` element — React's text-child auto-escaping is exercised explicitly.
- **osFamily helper** — case-insensitive substring match against the locked token lists from locked_decisions item 6 (`linux/ubuntu/debian/centos/rhel/fedora`, `windows`, `macos/mac os`). Returns `'other'` for null/undefined/empty/unknown. Designed for parity with the backend `OS_FAMILY_PATTERNS` that 12-01 Task 2 introduces.

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1 RED — Failing test for RiskRing** — `9f05453` (test)
2. **Task 1 GREEN — RiskRing implementation** — `8de7869` (feat)
3. **Task 2 RED — Failing tests for Breadcrumb, Avatar, osFamily** — `71b6aeb` (test)
4. **Task 2 GREEN — Breadcrumb + Avatar + osFamily implementations** — `7e426fa` (feat)

All commits used `--no-verify` per the parallel-executor protocol (Wave 2 runs alongside 12-04).

## Files Created

- `frontend/src/components/ui/RiskRing.tsx` — SVG ring primitive with `getRiskBand()` helper, `BAND_LABEL` / `BAND_TINT` maps, and `CIRCUMFERENCE` constant exported via the module.
- `frontend/src/components/ui/RiskRing.test.tsx` — 7 cases covering stroke-dashoffset math (scores 0/20/50/80/100/null), band tinting, single-gradient invariant, aria-label readout.
- `frontend/src/components/ui/Breadcrumb.tsx` — `Breadcrumb` + `Crumb` named exports with full TypeScript types.
- `frontend/src/components/ui/Breadcrumb.test.tsx` — 3 cases covering nav/ol semantics, aria-current on the last crumb, chevron separator aria-hidden.
- `frontend/src/components/ui/Avatar.tsx` — `Avatar` component + `initialsFor()` private helper; T-12-04 mitigation documented in JSDoc.
- `frontend/src/components/ui/Avatar.test.tsx` — 6 cases including the dedicated XSS guard test.
- `frontend/src/lib/util/os-family.ts` — `osFamily()` function + `OsFamily` type alias. New directory (`lib/util/`).
- `frontend/src/lib/util/os-family.test.ts` — 12 `it.each` pairs + 3 single-case tests = 15 cases total.

## Decisions Made

- **Token substitution (text-text-subtle → text-text-faint / text-text-muted)** — the plan's `text-text-subtle` is not a configured tailwind token in `frontend/tailwind.config.ts` (only `text`, `text-muted`, `text-faint`, `text-inverse` are mapped). Per the prompt's `<ui_guardrails>` directive ("substitute the closest valid token per the design system and note it in SUMMARY.md"), the substitution map is:
  - Plan `text-text-subtle` on captions ("No exposures", "Risk unavailable") → `text-text-faint` (the faintest text token, semantically correct for de-emphasized supporting copy).
  - Plan `text-text-subtle` on linked breadcrumbs → `text-text-muted` (visible but secondary, matching the pattern used in `Pagination.tsx` line 42).
  - Plan `text-text-subtle/60` on the chevron → `text-text-faint/60` (the faintest token at 60% alpha for non-content decoration).
- **CSS variable name correction** — RiskRing ring-bg uses `var(--color-border-subtle, …)` rather than the plan's `var(--border-subtle, …)`. The variable defined in `foundation.md` is namespaced `--color-*`; the bare `--border-subtle` would not resolve and the fallback `rgba(255,255,255,0.08)` would silently win. The fallback is preserved.
- **Sketch-locked sunset triplet** — the three hex codes `#EC4899`, `#A78BFA`, `#F59E0B` appear only inside `RiskRing.tsx`'s `<defs><linearGradient>` block. They are the sketch-locked brand gradient stops per locked_decisions item 5 and CLAUDE.md's "no freehand hex" rule applies to layout color (verified for Avatar / Breadcrumb / os-family — zero hex matches).
- **`lib/util/` directory created** — sibling to `lib/queries/`, `lib/mutations/`, `lib/validation/`. Establishes a new namespace for non-query / non-mutation client-side utilities. First inhabitant: `os-family.ts`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tailwind token `text-text-subtle` does not exist in this codebase**
- **Found during:** Task 1 (RiskRing implementation) and Task 2 (Breadcrumb implementation)
- **Issue:** The plan's inline `<action>` code references `text-text-subtle` for de-emphasized text, but `frontend/tailwind.config.ts` exposes only `text`, `text-muted`, `text-faint`, `text-inverse`. The class would compile to a no-op and silently produce default-tinted text — visually wrong and a violation of CLAUDE.md "Don't pick hex colors freehand — use the CSS variables from foundation.md" (the token system is the substitute).
- **Fix:** Substituted per the prompt's `<ui_guardrails>` rule: `text-text-faint` for the "Risk unavailable" / "No exposures" captions and the chevron 60% variant; `text-text-muted` for the linked breadcrumb anchors (matching the existing pattern in `Pagination.tsx`).
- **Files modified:** `frontend/src/components/ui/RiskRing.tsx`, `frontend/src/components/ui/Breadcrumb.tsx`
- **Verification:** All 31 tests pass; `grep` shows zero remaining occurrences of `text-text-subtle` in the new files.
- **Committed in:** `8de7869` (RiskRing) and `7e426fa` (Breadcrumb)

**2. [Rule 1 - Bug] CSS variable name `--border-subtle` is wrong; should be `--color-border-subtle`**
- **Found during:** Task 1 (RiskRing SVG ring-bg stroke)
- **Issue:** The plan's `RiskRing.tsx` code uses `stroke="var(--border-subtle, rgba(255,255,255,0.08))"`. The variable defined in `.claude/skills/sketch-findings-getvul/references/foundation.md` (and consumed by `tailwind.config.ts`) is `--color-border-subtle`. The unprefixed name would not resolve and the inline fallback would silently win, producing a ring background that ignores theme tokens.
- **Fix:** Renamed to `var(--color-border-subtle, rgba(255,255,255,0.08))`. Fallback preserved for environments where the variable is absent (e.g. unit tests with `css: false`).
- **Files modified:** `frontend/src/components/ui/RiskRing.tsx`
- **Verification:** Visual reasoning + the existing RiskRing tests do not assert on the ring-bg stroke color (they assert presence/absence of `.ring-fg`), so this fix is correctness-only and exercised at runtime.
- **Committed in:** `8de7869`

**3. [Rule 2 - Missing Critical] `pointer-events-none` on the absolute-positioned center overlay**
- **Found during:** Task 1 (RiskRing implementation review)
- **Issue:** The plan's inline `<div className="absolute inset-0 flex flex-col items-center justify-center">` sits on top of the SVG. Without `pointer-events: none`, the overlay would absorb hover/click events intended for any future interaction on the ring (or for hover-driven tooltips that 12-07 RiskCard may layer on top). This is a low-cost correctness fix that future consumers would have to discover themselves.
- **Fix:** Added `pointer-events-none` to the center overlay's className.
- **Files modified:** `frontend/src/components/ui/RiskRing.tsx`
- **Verification:** No test impact (events were never asserted). Downstream RiskCard composition (12-07) will benefit transparently.
- **Committed in:** `8de7869`

**4. [Rule 3 - Blocking] `node_modules` missing in the parallel worktree**
- **Found during:** Pre-Task-1 environment check
- **Issue:** `frontend/node_modules/` did not exist in the parallel worktree directory, blocking any `vitest` invocation. Direct `npm install --prefix` failed on `lucide-react@0.383.0` peerDep against React 19 (no `--legacy-peer-deps` configured globally).
- **Fix:** Symlinked the worktree's `frontend/node_modules` to the main-repo `frontend/node_modules` (`package.json` and `package-lock.json` are bit-identical between worktree and main repo, so the resolved tree is the same install). Verified `vitest`, `vitest-axe`, and `@testing-library/react` reachable through the symlink.
- **Files modified:** none tracked (`frontend/node_modules` is gitignored). The symlink is not committed.
- **Verification:** `./node_modules/.bin/vitest run` resolves; the full 322-test regression suite passes.
- **Committed in:** N/A — environment fix, no code change.

---

**Total deviations:** 4 auto-fixed (2× Rule 1 token/variable bugs, 1× Rule 2 missing pointer-events guard, 1× Rule 3 blocker on node_modules).
**Impact on plan:** All four fixes are correctness/environment, not scope expansion. Test count, file count, and TypeScript surface match the plan exactly. The two Rule-1 fixes are mandatory per CLAUDE.md design-system rules (no freehand colors / variables that don't exist).

## Issues Encountered

- **Worktree base mismatch:** the worktree was originally based on commit `4d8b197` (Phase 10 merge), but the plan's `<worktree_branch_check>` expected `7bfdbf94c6177c6a3b205a66cf091b9bb5f1e872` (the tip of Plan 12-02 execution). Resolved via `git reset --soft` to the expected base, then `git checkout HEAD -- .` to refresh the working tree (the soft reset moves HEAD without touching files; the checkout pulled the missing phase-11/phase-12 files into the worktree). After this, the four phase 12 planning files were present and the work proceeded normally.
- **npm install routing surprise:** an initial `cd frontend && npm install` ran but installed into the *main repo's* `frontend/node_modules` because each Bash tool call resets cwd. Worked around with `npm install --prefix <abs>` (which then hit the peerDep error) and finally settled on the symlink approach above.

## TDD Gate Compliance

- ✓ **Task 1 RED gate:** commit `9f05453` is a `test(...)` commit that adds `RiskRing.test.tsx` and verifies the test fails before any implementation lands.
- ✓ **Task 1 GREEN gate:** commit `8de7869` is a `feat(...)` commit that makes all 7 RiskRing tests pass.
- ✓ **Task 2 RED gate:** commit `71b6aeb` is a `test(...)` commit that adds 24 failing tests across `Breadcrumb.test.tsx`, `Avatar.test.tsx`, `os-family.test.ts`.
- ✓ **Task 2 GREEN gate:** commit `7e426fa` is a `feat(...)` commit that makes all 24 pass.
- No REFACTOR commits — the implementations were clean on the first GREEN pass; no behavior-preserving cleanup was warranted.

## Threat Flags

None. All three primitives stay inside the threat surface declared in the plan's `<threat_model>`:
- T-12-04 (Avatar XSS): mitigated and explicitly tested.
- T-12-12 (Breadcrumb href): accepted (Next router serializes).
- No new network endpoints, no new file access, no new schema changes — Wave 2 is pure UI primitives.

## Locked API Surface (for downstream plans)

Downstream plans 12-06, 12-07, 12-08 import from:

```ts
// frontend/src/components/ui/RiskRing.tsx
export type RiskBand = 'critical' | 'high' | 'medium' | 'low' | 'unavailable';
export function getRiskBand(score: number | null): RiskBand;
export type RiskRingProps = { score: number | null; size?: number; className?: string };
export function RiskRing(props: RiskRingProps): JSX.Element;

// frontend/src/components/ui/Breadcrumb.tsx
export type CrumbProps = { href?: string; children: ReactNode };
export function Crumb(props: CrumbProps): JSX.Element;
export type BreadcrumbProps = { children: ReactNode };
export function Breadcrumb(props: BreadcrumbProps): JSX.Element;

// frontend/src/components/ui/Avatar.tsx
export type AvatarProps = { name?: string; email?: string; size?: number; className?: string };
export function Avatar(props: AvatarProps): JSX.Element;

// frontend/src/lib/util/os-family.ts
export type OsFamily = 'linux' | 'windows' | 'macos' | 'other';
export function osFamily(osName: string | null | undefined): OsFamily;
```

## Self-Check: PASSED

**Files created (all 8 confirmed via `[ -f path ]`):**
- ✓ frontend/src/components/ui/RiskRing.tsx
- ✓ frontend/src/components/ui/RiskRing.test.tsx
- ✓ frontend/src/components/ui/Breadcrumb.tsx
- ✓ frontend/src/components/ui/Breadcrumb.test.tsx
- ✓ frontend/src/components/ui/Avatar.tsx
- ✓ frontend/src/components/ui/Avatar.test.tsx
- ✓ frontend/src/lib/util/os-family.ts
- ✓ frontend/src/lib/util/os-family.test.ts

**Commits exist (all 4 confirmed via `git log`):**
- ✓ 9f05453 test(12-03): add failing test for RiskRing (UX-04-03)
- ✓ 8de7869 feat(12-03): RiskRing primitive (UX-04-03)
- ✓ 71b6aeb test(12-03): add failing tests for Breadcrumb, Avatar, osFamily
- ✓ 7e426fa feat(12-03): Breadcrumb + Avatar + osFamily primitives

## Next Phase Readiness

- ✓ All four primitives ship with locked API surface usable by 12-06, 12-07, 12-08, and Phase 13.
- ✓ Wave 3 (assets list page in 12-06) can import `osFamily` and `Avatar` immediately.
- ✓ Wave 4 (detail composition in 12-07/12-08) can import `RiskRing`, `Breadcrumb`, and `Avatar`.
- ⚠ The `osFamily` token list (`['linux','ubuntu','debian','centos','rhel','fedora']`) MUST match the backend `OS_FAMILY_PATTERNS` introduced in 12-01 Task 2. If 12-01 deviates, this file needs a matching update. Documented in the JSDoc.
- ✓ No blockers. Wave 2 plan-12-03 is complete and independent of Wave 1.

---
*Phase: 12-assets-list-detail*
*Completed: 2026-05-30*
