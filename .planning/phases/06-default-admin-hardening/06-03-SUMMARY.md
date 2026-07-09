---
phase: 06-default-admin-hardening
plan: 03
subsystem: auth
tags: [react, nextjs, react-hook-form, zod, jwt, force-rotation, frontend]

# Dependency graph
requires:
  - phase: 06-default-admin-hardening (plan 00)
    provides: must_change_password persisted on the default admin + /auth/me surfacing it
  - phase: 06-default-admin-hardening (plan 02)
    provides: POST /auth/change-password returning fresh flag-free TokenResponse; get_current_user 403 gate
provides:
  - User.must_change_password on useAuth() sourced from /auth/me
  - AuthProvider redirect gate that forces a flagged user onto /change-password
  - /change-password rotation page (outside (authed), on Phase 9 primitives + sunset tokens)
  - changePasswordSchema in lib/validation/auth.ts
  - Shared in-memory localStorage stub in vitest.setup.ts (Node 25/26 jsdom fix)
affects: [dashboard, auth, any-phase-touching-frontend-auth-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Force-rotation UX gate in AuthProvider (not (authed)/layout) so it fires post-login too"
    - "Raw fetch (not toast-wrapped hook) when the response body carries fresh tokens the client must persist"
    - "sanitizeNext reused verbatim for ?next on the rotation page (same-origin open-redirect guard)"

key-files:
  created:
    - frontend/src/app/change-password/page.tsx
  modified:
    - frontend/src/lib/auth.tsx
    - frontend/src/lib/validation/auth.ts
    - frontend/vitest.setup.ts

key-decisions:
  - "Redirect gate lives in AuthProvider, keyed on user.must_change_password + pathname !== '/change-password', dep array [loading, user, pathname, router] — mirrors the existing login gate"
  - "Page uses raw fetch to read the fresh flag-free tokens from the response body and overwrites getvul_token/getvul_refresh BEFORE navigating (token-replay mitigation)"
  - "localStorage collision under Node 25/26 fixed once in vitest.setup.ts instead of per-test polyfills"

patterns-established:
  - "Operational auth surfaces render a slim centered form on bg-bg (no split-screen hero) per page-layouts"
  - "Backend 4xx detail surfaced verbatim in ErrorAlert without navigating"

requirements-completed: [PROD-06-03]

# Metrics
duration: 22min
completed: 2026-07-09
---

# Phase 6 Plan 03: Force-Rotation Frontend Surface Summary

**useAuth() carries must_change_password from /auth/me and redirects flagged users to a new /change-password page that rotates the password via POST /auth/change-password, swaps in the fresh flag-free tokens, and lands on a sanitized destination — all on Phase 9 primitives + sunset tokens + copy-voice.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-07-09T09:21:00Z (approx)
- **Completed:** 2026-07-09T09:43:06Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- Added the optional `must_change_password` field to the `User` interface (sourced from `/auth/me`) plus a second `AuthProvider` `useEffect` that redirects a flagged user to `/change-password` from any other path — the operator-facing half of the Wave 2 backend 403 gate.
- Built `/change-password` as a peer of `login/` (outside the `(authed)` group, no AppShell): a three-field rotation form (current / new / confirm) on `Form`/`Input`/`Button`/`ErrorAlert`, sunset design tokens (no freehand hex), and copy-voice-compliant copy (no Please / Welcome / exclamation).
- Wired the success path to overwrite `getvul_token` / `getvul_refresh` with the fresh flag-free tokens from the response body before `router.replace(sanitizeNext(next))`, mitigating both the token-replay and open-redirect threats.
- Turned the Wave 0 RED Vitest scaffold GREEN: all 4 `change-password` cases pass; full suite 680/680 green with no regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: auth.tsx — User.must_change_password + redirect gate** - `1fd834f` (feat)
2. **Task 2: /change-password page + zod schema** - `eb87b65` (feat)

_(Task 2's commit also carries the Rule 3 localStorage blocking fix in vitest.setup.ts.)_

## Files Created/Modified
- `frontend/src/app/change-password/page.tsx` - Created. Force-rotation page (Suspense-wrapped useSearchParams, three password fields, ErrorAlert, raw fetch to /auth/change-password, fresh-token persistence, sanitized redirect).
- `frontend/src/lib/auth.tsx` - Added optional `must_change_password` to `User`; added the redirect-gate `useEffect`.
- `frontend/src/lib/validation/auth.ts` - Added `changePasswordSchema` (current/new/confirm with `.refine` match check) + `ChangePasswordInput` type.
- `frontend/vitest.setup.ts` - Installed a shared in-memory localStorage stub (Node 25/26 global-vs-jsdom collision fix).

## Decisions Made
- **Gate placement:** the redirect gate is in `AuthProvider`, not `(authed)/layout.tsx`, so it also fires post-login (mount `fetchMe` resolves the flag, then the gate redirects). Kept the dep array `[loading, user, pathname, router]` identical to the existing login gate.
- **Raw fetch over the toast-wrapped hook:** the page needs the fresh flag-free tokens straight from the response body, so it uses `fetch` directly and persists the tokens before navigating (Pitfall 3 / T-06-token-replay).
- **Button label "Update password"** and heading "Set a new password" — imperative, sentence-case, no exclamation (copy-voice). Subheading states the WHY plainly.
- **Layout:** a slim centered form on `bg-bg` (no split-screen hero) — appropriate for an operational surface per page-layouts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shared in-memory localStorage stub in vitest.setup.ts**
- **Found during:** Task 2 (running the RED `change-password` suite)
- **Issue:** Node 25/26 exposes an experimental global `localStorage` that is `undefined` unless `--localstorage-file` is passed; it shadows jsdom's Storage. The Wave 0 RED scaffold calls `localStorage.clear()` in `beforeEach` and threw `Cannot read properties of undefined (reading 'clear')` — the suite could not even start. Existing tests (auth.logout, api) worked around this by re-declaring an in-memory stub per file; the scaffold does not.
- **Fix:** Installed a single in-memory `localStorage` stub in `vitest.setup.ts` (runs for every suite) instead of duplicating the polyfill. Tests still call `localStorage.clear()` for isolation; existing per-file stubs remain compatible (they redefine a `configurable: true` property).
- **Files modified:** frontend/vitest.setup.ts
- **Verification:** `change-password` 4/4 green; full suite 680/680 green (no regressions in auth.logout / api / users tests that also use localStorage).
- **Committed in:** eb87b65 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The localStorage fix was required to run the plan's own RED target on the environment's Node version. It de-duplicates existing per-test polyfills — a net cleanup, no scope creep. The page/gate implementation followed the plan exactly.

## Issues Encountered
- The worktree ships without `node_modules` (deps live in the shared checkout) and `npm run test` could not find `vitest`. Resolved by symlinking the shared `frontend/node_modules` into the worktree to run the local `vitest` binary, then removing the symlink after verification so it was never committed.
- The worktree base needed a rebase onto `bca4fda` (Wave 2) at startup so the merged Wave 1+2 backend contract and the RED scaffold were present. Rebased per the branch-check protocol before any work.

## Threat Coverage
- **T-06-open-redirect (mitigate):** `?next` passes through `sanitizeNext` (same-origin relative paths only) before `router.replace`.
- **T-06-token-replay (mitigate):** the fresh flag-free tokens overwrite `getvul_token` / `getvul_refresh` before navigation.
- **T-06-ui-gate-only (accept + documented):** the page is a UX gate; the authoritative enforcement is the Wave 2 backend 403 in `get_current_user`.

No new threat surface introduced beyond the plan's `<threat_model>`.

## Known Stubs
None. The page is fully wired to the live `/auth/change-password` endpoint and real localStorage token storage.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The full force-rotation loop is now closed end-to-end (backend 403 + flag-free rotation from Waves 1–2, frontend gate + page here). Ready for the 06-VALIDATION manual E2E row (log in as admin@getvul.local / Admin123! → forced to /change-password → cannot reach /dashboard → rotate → land on /dashboard).
- STATE.md / ROADMAP.md updates intentionally deferred to the orchestrator (owns those writes after the wave completes).

---
*Phase: 06-default-admin-hardening*
*Completed: 2026-07-09*

## Self-Check: PASSED
- All created/modified files present (page.tsx, auth.tsx, validation/auth.ts, vitest.setup.ts, 06-03-SUMMARY.md).
- Both task commits present in git log (1fd834f, eb87b65).
