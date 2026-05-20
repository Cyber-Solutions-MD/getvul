---
phase: 09-login-foundation
plan: 03
subsystem: ui
tags: [route-group, git-mv, next-15, app-router, route-migration, sweep, hsl-bridge, build-unblock, suspense, useSearchParams]

# Dependency graph
requires:
  - phase: 09-login-foundation
    plan: 02
    provides: "shadcn primitives + sunset-token sweep on form.tsx + dropdown-menu.tsx already removed all HSL-bridge utilities from frontend/src/; sunset tokens + tailwind bridge available"
provides:
  - "frontend/src/app/(authed)/dashboard/ — new route-group directory holding every authenticated page (D-33). URLs unchanged: /dashboard, /dashboard/assets, /dashboard/cspm, /dashboard/users, etc. all resolve because Next 15 strips parens-named directories from the URL path"
  - "Atomic git mv commit (001a4ee) — 10 files migrated as renames with `git log --follow` history preserved (Pitfall 7 satisfied)"
  - "Unblocked npm run build path — globals.css @import path corrected, ComplianceFramework type aligned with API, /dashboard/users wrapped in Suspense for useSearchParams"
  - "Zero HSL-bridge utility class references in frontend/src/{app/(authed),components,lib} (login/page.tsx excluded per plan, Wave 4 rewrites)"
  - "Zero per-page outer chrome wrappers on (authed)/dashboard/*/page.tsx pages (was already the v1 baseline — chrome lives in dashboard/layout.tsx which Wave 3 replaces)"
affects: [09-04, 09-05, 09-06, 10-dashboard, 11-vulnerabilities, 12-assets, 13-tickets, 14-remaining, 15-quality-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Next.js 15 App Router route-group convention (parens-wrapped directory removed from URL path; only used to share a layout among grouped routes)"
    - "Suspense-wrapping pattern for client pages that call useSearchParams at component root (renames inner body to *Inner; exports a Suspense wrapper as default)"
    - "Atomic git mv per Pitfall 7 — content changes deferred to next commit so `git log --follow` rename detection survives"

key-files:
  created:
    - .planning/phases/09-login-foundation/09-03-SUMMARY.md
  modified:
    - frontend/src/app/(authed)/dashboard/cspm/page.tsx
    - frontend/src/app/(authed)/dashboard/users/page.tsx
    - frontend/src/app/globals.css
  renamed (git mv):
    - frontend/src/app/dashboard/page.tsx -> frontend/src/app/(authed)/dashboard/page.tsx
    - frontend/src/app/dashboard/layout.tsx -> frontend/src/app/(authed)/dashboard/layout.tsx
    - frontend/src/app/dashboard/assets/page.tsx -> frontend/src/app/(authed)/dashboard/assets/page.tsx
    - frontend/src/app/dashboard/assets/[id]/page.tsx -> frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx
    - frontend/src/app/dashboard/connectors/page.tsx -> frontend/src/app/(authed)/dashboard/connectors/page.tsx
    - frontend/src/app/dashboard/cspm/page.tsx -> frontend/src/app/(authed)/dashboard/cspm/page.tsx
    - frontend/src/app/dashboard/settings/page.tsx -> frontend/src/app/(authed)/dashboard/settings/page.tsx
    - frontend/src/app/dashboard/tickets/page.tsx -> frontend/src/app/(authed)/dashboard/tickets/page.tsx
    - frontend/src/app/dashboard/users/page.tsx -> frontend/src/app/(authed)/dashboard/users/page.tsx
    - frontend/src/app/dashboard/vulnerabilities/page.tsx -> frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx

key-decisions:
  - "Task 1 was content-pure per Pitfall 7 — 10 git-mv renames, zero file content changes, atomic in a single commit (001a4ee). git log --follow preserves the full history chain back to the original v1 dashboard scaffold."
  - "Task 2's sweep + wrapper-strip were no-ops on disk — Phase 09-02 already swept all HSL-bridge utilities (bg-popover, bg-accent, text-destructive, text-muted-foreground, bg-muted, etc.) from form.tsx and dropdown-menu.tsx, and v1's dashboard/*/page.tsx files never carried outer chrome wrappers (chrome lives in dashboard/layout.tsx, which the plan explicitly says to leave alone for Wave 3 to replace)."
  - "Three pre-existing build blockers surfaced by the npm run build verification gate were auto-fixed per Rule 3 in the Task 2 commit (bbf4d87): (a) globals.css broken @import path, (b) ComplianceFramework type missing the `name` field, (c) useSearchParams not wrapped in Suspense on /dashboard/users. All three were unrelated to the move/sweep work but blocked the plan's verification gates."
  - "5 root-level duplicate route directories (D-34) were already absent at plan-start — likely cleaned by Phase 09-01 or 09-02 or never existed at the expected base. Recorded as 'ALREADY ABSENT' in verification log; D-34 success criterion satisfied."

patterns-established:
  - "Route-group naming convention: parens-wrapped directory under app/ (e.g. (authed)/) groups routes for shared layout/middleware without affecting URL. URLs continue to resolve as if the parens directory were transparent."
  - "useSearchParams + Suspense pattern for client pages: rename existing component body to *Inner, add Suspense wrapper as default export. Necessary because Next 15 statically prerenders client pages by default; useSearchParams triggers CSR bailout requiring Suspense."
  - "Type-API alignment: frontend type definitions must match backend response shape (ComplianceFramework had `framework` while API returns `name`). Pre-existing on rolled-back branch (commit c3ae8fc); now reapplied."

requirements-completed:
  - UX-F-02

# Metrics
duration: 4min
completed: 2026-05-13
---

# Phase 09 Plan 03: Route-Group Migration + HSL-Bridge Sweep Summary

**Atomic git mv of `app/dashboard/*` -> `app/(authed)/dashboard/*` with blame intact (Pitfall 7); zero HSL-bridge utility classes remain in scope (Phase 09-02 already swept them); `npm run build` exits 0 across 14 routes after auto-fixing three pre-existing blockers (globals.css import path, ComplianceFramework type, useSearchParams Suspense).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-13T06:29:42Z
- **Completed:** 2026-05-13T06:34:31Z
- **Tasks:** 2
- **Files renamed:** 10 (via git mv)
- **Files modified:** 3 (all in Task 2 — pre-existing build blockers)
- **Files created:** 1 (this SUMMARY.md)

## Accomplishments

- **Atomic route-group migration.** `git mv frontend/src/app/dashboard frontend/src/app/(authed)/dashboard` — single command, 10 renames detected by git as `R` (not `D+A`). The diff is `10 files changed, 0 insertions(+), 0 deletions(-)`. `git log --follow -- 'frontend/src/app/(authed)/dashboard/page.tsx'` returns the full pre-phase-9 history (`1ccafb6 fix: use relative API URLs`, `2d45ab1 feat: replace all native browser dialogs`, `c15dafd feat: dashboard trend analytics`, etc.) confirming Pitfall 7 is satisfied — blame survives. The 14-route Next.js build confirms URLs continue to resolve as `/dashboard`, `/dashboard/assets`, `/dashboard/cspm`, `/dashboard/users`, etc. because the route-group convention strips parens directories from the URL path.

- **HSL-bridge sweep was a no-op on disk.** Grep against the expanded HSL-bridge utility set (`bg-background|bg-card|bg-popover|bg-accent|bg-muted|bg-input|bg-secondary|bg-primary|text-foreground|text-card-foreground|text-popover-foreground|text-muted-foreground|text-accent-foreground|text-secondary-foreground|text-primary-foreground|text-destructive|text-primary|text-secondary|text-accent|border-input|ring-ring|ring-offset-background`) across `frontend/src/{app/(authed),components,lib}` returned **0 occurrences**. Phase 09-02 had already swept the only files that carried HSL-bridge utilities (shadcn-generated `form.tsx` + `dropdown-menu.tsx`). v1's dashboard pages used Tailwind's default gray-* palette (`bg-gray-950`, `text-gray-400`, `border-gray-700`) — these are NOT HSL-bridge utilities; they resolve via Tailwind's built-in scale and remain intact as v1 interim styling per D-39 accepted-visual-debt.

- **Per-page wrapper-strip was a no-op on disk.** Inspection of all 9 dashboard pages (`page.tsx` + 7 subroute `page.tsx` + `assets/[id]/page.tsx`) showed the OUTERMOST returned element is a content container (`<div className="space-y-6">` or `<div className="space-y-4">` or `<div className="space-y-8">`) — never a full-page chrome wrapper. The chrome (`<div className="min-h-screen">` + Sidebar + Header) lives in `dashboard/layout.tsx`, which the plan explicitly instructs to leave alone (Wave 3 replaces it with `(authed)/layout.tsx`).

- **`npm run build` unblocked.** Three pre-existing issues blocked the plan's build-pass verification gate. All three were unrelated to the route-group migration or HSL-bridge sweep, but the plan requires `npm run build` to exit 0, so they were auto-fixed per Rule 3 (see Deviations).

- **All verification gates green.** `npm test -- --run` → 25 tests passing across 5 files; `npx tsc --noEmit` → 0 errors; `npm run build` → 14 routes generated, all `/dashboard/*` routes resolving from `(authed)/dashboard/*` via route-group convention; `git log --follow` → multi-commit history preserved on moved files; HSL-bridge utility count → 0.

## Task Commits

Each task was committed atomically (`--no-verify` per parallel-executor protocol — orchestrator runs hooks once after wave completion):

1. **Task 1: Atomic git mv — relocate app/dashboard/* into app/(authed)/dashboard/*** — `001a4ee` (refactor)
2. **Task 2: Sweep + wrapper-strip (no-op on disk) + auto-fix three pre-existing build blockers** — `bbf4d87` (refactor)

## Files Created/Modified

### Renamed via `git mv` (10 — atomic Task 1 commit `001a4ee`)

| Original path | New path |
|---|---|
| `frontend/src/app/dashboard/page.tsx` | `frontend/src/app/(authed)/dashboard/page.tsx` |
| `frontend/src/app/dashboard/layout.tsx` | `frontend/src/app/(authed)/dashboard/layout.tsx` |
| `frontend/src/app/dashboard/assets/page.tsx` | `frontend/src/app/(authed)/dashboard/assets/page.tsx` |
| `frontend/src/app/dashboard/assets/[id]/page.tsx` | `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` |
| `frontend/src/app/dashboard/connectors/page.tsx` | `frontend/src/app/(authed)/dashboard/connectors/page.tsx` |
| `frontend/src/app/dashboard/cspm/page.tsx` | `frontend/src/app/(authed)/dashboard/cspm/page.tsx` |
| `frontend/src/app/dashboard/settings/page.tsx` | `frontend/src/app/(authed)/dashboard/settings/page.tsx` |
| `frontend/src/app/dashboard/tickets/page.tsx` | `frontend/src/app/(authed)/dashboard/tickets/page.tsx` |
| `frontend/src/app/dashboard/users/page.tsx` | `frontend/src/app/(authed)/dashboard/users/page.tsx` |
| `frontend/src/app/dashboard/vulnerabilities/page.tsx` | `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` |

All detected as renames (`R` in `git status`) with 100% similarity. `git log --follow` preserves blame.

### Modified (3 — Task 2 commit `bbf4d87`)

- `frontend/src/app/globals.css` — `@import './styles/sunset.css'` -> `@import '../styles/sunset.css'` (sunset.css lives at `src/styles/`, not `src/app/styles/`)
- `frontend/src/app/(authed)/dashboard/cspm/page.tsx` — `ComplianceFramework.framework` -> `ComplianceFramework.name` (matches API + existing consumer code)
- `frontend/src/app/(authed)/dashboard/users/page.tsx` — Renamed `UsersPage` -> `UsersPageInner`; added `Suspense`-wrapped `UsersPage` default export (Next 15 requires Suspense for `useSearchParams` in client pages)

### Created (1)

- `.planning/phases/09-login-foundation/09-03-SUMMARY.md` — this file

## Decisions Made

- **Atomic move first, then auto-fixes.** Task 1's commit (`001a4ee`) was content-pure per Pitfall 7 — `git mv` only, no file content changes. Task 2's commit (`bbf4d87`) captures the three build-unblock fixes. This keeps blame-recovery on dashboard pages a single rename traversal away from their pre-phase-9 history.

- **5 duplicate root routes already absent.** D-34 lists `app/{assets,integrations,settings,tickets,vulnerabilities}` for deletion. At plan-start, all 5 directories were already missing from disk (likely cleaned by a prior phase or never existed at the expected base commit `3743494`). Verification log shows `ALREADY ABSENT` for each — D-34 success criterion is satisfied by current state.

- **`bg-gray-*` utilities retained on un-redesigned screens.** Per D-39 the v1 gray-scale utilities are NOT HSL-bridge — they resolve via Tailwind's default gray palette and remain visually intact. They get replaced when each screen lands in Phases 10-14. The current count of `bg-gray-950` references in `(authed)/dashboard/*/page.tsx` is non-zero (modal chrome inside connector + settings + ticket + user pages) but those are accepted visual debt, not a sweep target.

- **Suspense over `force-dynamic` for `/dashboard/users`.** Two options to unblock the Next 15 prerender error: `export const dynamic = "force-dynamic"` (opt out of static rendering entirely) or wrap the component in `<Suspense>` (preserves static shell + CSR-bails the useSearchParams subtree). Chose Suspense — preserves Next 15's prerender benefits for the rest of the page, follows the idiomatic Next 15 pattern, and reads cleanly in the diff. Renamed inner body to `UsersPageInner` per the standard Next pattern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Pre-existing `globals.css` broken `@import` path**
- **Found during:** Task 1 verification — `npm run build` failed with `Module not found: Can't resolve './styles/sunset.css'`
- **Issue:** Wave 0 (Phase 09-01 commit `fa2719c`) wrote `@import './styles/sunset.css'` in `frontend/src/app/globals.css`. That path resolves to `frontend/src/app/styles/sunset.css`, but the file actually lives at `frontend/src/styles/sunset.css`. The Wave 0 plan deferred E2E CSS verification to "Wave 5 via `npm run build` + manual cold-load" — never ran build. Phase 09-02 didn't run build either. Plan 09-03 needs the build gate to pass.
- **Fix:** Changed `@import './styles/sunset.css'` -> `@import '../styles/sunset.css'` (one directory up).
- **Files modified:** `frontend/src/app/globals.css`
- **Verification:** Tailwind compiles successfully (`Compiled successfully in 1808ms`), all 14 routes generate.
- **Committed in:** `bbf4d87` (Task 2 commit).

**2. [Rule 3 — Blocking] Pre-existing `ComplianceFramework` type/API mismatch**
- **Found during:** Task 2 — `npm run build` TypeScript validation phase
- **Issue:** Wave 0's `deferred-items.md` documented this: `ComplianceFramework` interface declares `framework: string`, but consumers at lines 571 + 580 access `fw.name`. The audit-rolled-back commit `c3ae8fc fix: CSPM compliance tab — use fw.name not fw.framework (matches API)` shows the backend returns `name`. The fix was rolled back; the type mismatch persisted. Phase 09-01 SUMMARY recommended deferring to "Phase 14 — Remaining Screens". Plan 09-03's `npm run build` gate forced the fix to land now.
- **Fix:** Renamed interface field `framework: string` -> `name: string` to match the API and existing consumers.
- **Files modified:** `frontend/src/app/(authed)/dashboard/cspm/page.tsx`
- **Verification:** `npx tsc --noEmit` → 0 errors.
- **Committed in:** `bbf4d87` (Task 2 commit).

**3. [Rule 3 — Blocking] Pre-existing `useSearchParams` not in Suspense on /dashboard/users**
- **Found during:** Task 2 — `npm run build` static-page-generation phase
- **Issue:** `frontend/src/app/(authed)/dashboard/users/page.tsx` calls `useSearchParams()` at the component root (`const searchParams = useSearchParams();`). Next 15.5 statically prerenders client pages by default; `useSearchParams` triggers a CSR bailout that MUST be wrapped in `<Suspense>` to satisfy the prerender check. The page was already broken on the v1 path (`app/dashboard/users/page.tsx`) — but Wave 0/02 never ran a production build to surface it.
- **Fix:** Imported `Suspense` from React; renamed the existing `UsersPage` to `UsersPageInner`; added new `UsersPage` default export that wraps `<UsersPageInner />` in `<Suspense fallback={null}>`. Standard Next 15 pattern.
- **Files modified:** `frontend/src/app/(authed)/dashboard/users/page.tsx`
- **Verification:** `npm run build` → /dashboard/users prerenders cleanly; all 14 routes built; `npm test` 25/25 still green.
- **Committed in:** `bbf4d87` (Task 2 commit).

---

**Total deviations:** 3 auto-fixed (all Rule 3 — Blocking)
**Impact on plan:** All three are pre-existing project bugs surfaced by the plan's `npm run build` gate. None are introduced by this plan's work. The plan's spec-defined work (move + sweep + wrapper-strip) had zero file changes beyond the 10 renames. All success criteria pass.

## Issues Encountered

### Worktree base correction (recurring)

- **Issue:** Same condition as Phase 09-01 and 09-02 — the parallel-executor worktree was created from `8cede77` (commit "comprehensive update — 24 migrations, install.sh, default admin, seed data") instead of the expected base `3743494` (09-02 SUMMARY). `git merge-base HEAD 3743494` returned `8cede77`. The branch had v1.0 backend-era commits and was missing the Phase 9 plan files entirely.
- **Resolution:** Per the prompt's `<worktree_branch_check>` block, ran `git reset --hard 374349400ef2a159a3384ff7e3c8e9b4002e42a5` to align with the expected base. After correction, the working tree contained `.planning/phases/09-login-foundation/09-{01,02}-SUMMARY.md`, the Wave 0 + Wave 1 commits, and the full Phase 9 context.
- **Time cost:** ~30 seconds. No work lost (fresh worktree). Same condition encountered three plans in a row — orchestrator may want to investigate the worktree creation flow.

### `npm install` requires `--legacy-peer-deps`

- **Issue:** `lucide-react@0.383` declares React 16/17/18 in `peerDependencies` but the project ships React 19. `npm ci` fails with `ERESOLVE`.
- **Resolution:** Used `npm install --legacy-peer-deps` — consistent with the established Phase 09-01 + 09-02 pattern.

### CSPM regression on rolled-back branch

- **Issue:** The audit-rolled-back recovery branch had commit `c3ae8fc fix: CSPM compliance tab — use fw.name not fw.framework (matches API)` which fixed the `ComplianceFramework` type. That fix was rolled back along with the rest of the v2-01 attempt. The type mismatch persisted into Wave 0/01/02 and got documented in `deferred-items.md` as future work.
- **Resolution:** Reapplied the fix in Task 2 (commit `bbf4d87`) — the plan's `npm run build` gate effectively forced the bug fix to land now rather than waiting for Phase 14.

## User Setup Required

None — all changes are file-system + git operations + build-config corrections within the frontend bundle.

## Threat Flags

No new threat surface introduced:
- **T-09-03-01 (git history corruption from non-`git mv` move) — MITIGATED:** Task 1 used `git mv` exclusively; `git log --follow -- 'frontend/src/app/(authed)/dashboard/page.tsx'` returns ≥5 commits proving rename detection succeeded.
- **T-09-03-02 (sweep deletes a class still referenced) — N/A:** Sweep was a no-op on disk; no class deletions occurred. Build passes confirming no orphaned references.
- **T-09-03-03 (wrapper-strip removes security-relevant container) — N/A:** Wrapper-strip was a no-op on disk; the dashboard `layout.tsx` (which carries the only chrome) was untouched per plan instruction. No `RequireAuth` / `withAuth` HOCs exist in the pages.
- **T-09-03-04 (deleted duplicate root-level routes yield 404s) — ACCEPTED:** The 5 root-level duplicates were already absent at plan-start; no new 404s introduced.

No new auth paths, network endpoints, file access patterns, or schema changes at trust boundaries. The Suspense wrapper change on `/dashboard/users` is a React-tree refactor with zero security surface implications.

## Known Stubs

None. All plan-spec work is complete:
- Route-group migration: 10 renames, blame intact, build resolves URLs.
- HSL-bridge sweep: 0 references in scope (Phase 09-02 already cleaned).
- Wrapper-strip: 0 outer chrome wrappers on dashboard pages (chrome lives in `layout.tsx`, plan says leave alone).
- All verification gates pass.

The 3 build-unblock fixes in Task 2 are full fixes (not stubs) — they make the code production-correct, not placeholder.

## Next Plan Readiness

**Ready for Plan 09-04 (Shell scaffold, expected next):**
- `(authed)/` route-group directory exists and is ready to accept a `layout.tsx` that wraps every authenticated page.
- `(authed)/dashboard/layout.tsx` is the placeholder the plan called out — Wave 3 replaces it with the new AppShell consumer at `(authed)/layout.tsx`.
- `components/layout/Header.tsx` + `Sidebar.tsx` exist with their HSL-bridge-free state. Wave 3 deletes them once `components/shell/` covers the surface.
- Build is green; 14 routes resolve; all `/dashboard/*` URLs work via route-group convention.

**Carry-forward:**
- ESLint migration (Wave 0 deferred-items.md) still outstanding.
- Canvas/color-contrast for axe-core under jsdom (Wave 1 deferred-items.md) — defer to Phase 15.
- v1 `bg-gray-*` utilities on un-redesigned screens (D-39 accepted visual debt) — each screen redesign in Phases 10-14 replaces them.
- Phase 09-01's deferred-items.md `ComplianceFramework.name` issue is now RESOLVED in this plan; the deferred-items.md can be updated to reflect that.

## Self-Check: PASSED

Verified after writing this summary:
- `git log --oneline | grep -E '001a4ee|bbf4d87'` → both task commits present on branch.
- `test -d 'frontend/src/app/(authed)/dashboard' && ! test -d 'frontend/src/app/dashboard'` → migration intact.
- `test -f .planning/phases/09-login-foundation/09-03-SUMMARY.md` → this file exists.
- `git log --follow --oneline -- 'frontend/src/app/(authed)/dashboard/page.tsx' | wc -l` → 5+ commits, blame preserved.
- `cd frontend && npm run build` → exits 0; 14 routes generated.
- `cd frontend && npm test -- --run` → 25 passed.
- `cd frontend && npx tsc --noEmit` → 0 errors.
- HSL-bridge utility count in `frontend/src/{app/(authed),components,lib}` → 0.

---
*Phase: 09-login-foundation, Plan: 03*
*Completed: 2026-05-13*
