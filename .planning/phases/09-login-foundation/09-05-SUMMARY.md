---
phase: 09-login-foundation
plan: 05
subsystem: ui
tags: [login, sso, auth, react-hook-form, zod, split-screen, open-redirect, user-enumeration, oidc, next-middleware]

# Dependency graph
requires:
  - phase: 09-login-foundation
    plan: 01
    provides: "sunset tokens (bg-bg, bg-bg-darker, bg-surface, bg-surface-2, bg-gradient-mesh, animate-gradient-drift, bg-severity-critical/high, bg-danger-soft, border-danger, text-danger, success-soft, etc.) — all consumed in /login layout + ErrorAlert"
  - phase: 09-login-foundation
    plan: 02
    provides: "Button (variant=cta, loading+loadingText), Input (password eye-toggle + aria-invalid border-danger flip), Form/FormField/FormControl/FormMessage (RHF compound), SsoButton (provider='google'|'microsoft' verbatim D-46 labels), GradientText (background-clip:text accent), react-hook-form@7.75 + zod@4.4 + @hookform/resolvers@5.2"
  - phase: 09-login-foundation
    plan: 03
    provides: "(authed)/layout.tsx route group + AppShell — Wave 4 confirms /login lives at /login (not /dashboard/login), so the route guard's `?next=` redirect (D-50) protects everything under /dashboard"
  - phase: 09-login-foundation
    plan: 04
    provides: "User → /login redirect path exercised by the UserChip dropdown sign-out — Wave 4's useAuth.logout still calls router.replace('/login') unchanged"
provides:
  - "/login full rewrite: split-screen sunset layout (left gradient-mesh+drift+SAMPLE_VULNS peek; right form chrome), three-mode state machine 'login' | 'forgot' | 'reset' per D-43, verbatim D-45/D-46/D-49/D-52 copy"
  - "sanitizeNext(raw) open-redirect mitigator (Pitfall 10, T-09-05-01) — exported from src/app/login/sanitize-next.ts (sibling file because Next.js 15 rejects non-default exports from page.tsx)"
  - "ErrorAlert auth-form banner (components/auth/error-alert.tsx) with role='alert' + bg-danger-soft + border-danger + text-danger per D-28 + UX-01-05"
  - "Zod schemas in src/lib/validation/auth.ts: loginSchema, forgotSchema, resetSchema per D-53 with sentence-case messages per copy-voice.md"
  - "useAuth() updated: AuthError class (D-49 status carrier); login() throws instead of returning string (caller owns post-success router.replace for ?next= sanitization); loginSSO() typed 'google'|'azure' and throws verbatim D-51 copy on backend unreachable/malformed; route-guard useEffect encodes ?next=encodeURIComponent(pathname+search) per D-50"
  - "frontend/middleware.ts — Open Question 2 legacy URL redirects (/assets, /integrations, /settings, /tickets, /vulnerabilities root + subpaths → /dashboard/* with 308)"
  - "Tailwind bg-surface-glass utility binding (consumed by left-panel vuln-peek cards)"
  - "17 unit tests covering sanitizeNext, mode-switch SSO visibility, ?reset=TOKEN deep-link, autoComplete attrs, ErrorAlert classes on 401, anti-enumeration forgot-password, D-51 SSO failure surfacing, WCAG SC 1.3.1 H1 reachability, axe-clean login mode"
affects: [09-06, 10-dashboard, 11-vulnerabilities, 12-assets, 13-tickets, 14-remaining, 15-quality-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Next.js 15 page-file export constraint workaround: helpers consumed by a page component must live in a sibling file (e.g. ./sanitize-next.ts) — Next rejects arbitrary named exports from page.tsx with a build-time type error"
    - "AuthError class pattern — Error subclass with .status property so caller can switch on HTTP code (401 → generic copy per D-49) without parsing message strings"
    - "Anti-enumeration form pattern — show the same generic confirmation regardless of backend response (Pitfall 9); applied to forgot-password and inherited by future password-reset/account-recovery flows"
    - "Open-redirect sanitizer pattern — decoded.startsWith('/') && !decoded.startsWith('//') && !decoded.startsWith('/\\\\') (Pitfall 10); ready to lift to a shared util when ?next= consumers multiply (logout-with-next, SAML-completion redirect)"
    - "Verbatim copy carried into JSX as string literals so plan grep verification can match line-for-line (D-45/D-46/D-49/D-52)"
    - "Three-mode state machine + per-mode autoFocus + autoComplete pattern (D-48) — generalizable to future multi-step auth flows (MFA enroll, account-recovery, device-trust)"
    - "Backend OIDC route name vs UI label decoupled via toBackendProvider helper — UI 'microsoft' → backend 'azure'; one obvious place to look for the indirection"

key-files:
  created:
    - frontend/src/lib/validation/auth.ts
    - frontend/src/components/auth/error-alert.tsx
    - frontend/middleware.ts
    - frontend/src/app/login/sanitize-next.ts
    - frontend/src/app/login/page.test.tsx
  modified:
    - frontend/src/app/login/page.tsx
    - frontend/src/lib/auth.tsx
    - frontend/tailwind.config.ts

key-decisions:
  - "sanitizeNext split out of page.tsx into a sibling file (src/app/login/sanitize-next.ts) because Next.js 15 rejects non-default exports from page.tsx ('sanitizeNext is not a valid Page export field'). Same semantics — the test suite imports from ./sanitize-next, the page imports from ./sanitize-next. Plan grep 'export function sanitizeNext' verified against the sibling file."
  - "useAuth.login changed signature from `Promise<string | null>` to `Promise<void>` that throws AuthError. Plan's Task 2 expected `try { await login() } catch (e) { e.status === 401 }` pattern — incompatible with v1's return-string contract. Updated the useAuth() interface as a Task 1 deviation (Rule 3 — Blocking) so /login can map 401 → D-49 generic copy without parsing message strings. AuthError class exported from lib/auth.tsx for future consumers (logout-with-error, refresh-failure UI)."
  - "loginSSO retained the existing JSON-GET contract (backend /auth/login/{provider} returns `{authorization_url, state}`) instead of switching to HEAD-pre-flight + direct navigation as the plan literally specified. The JSON-GET contract already catches backend 5xx before navigation (the `await resp.json()` step throws) — strictly safer than the plan's HEAD-pre-flight pattern would have been against the actual v1 backend. D-51 verbatim copy ('Sign-in with Google is temporarily unavailable. Try email instead.') surfaces via thrown Error in three failure branches: network throw, !resp.ok, missing authorization_url."
  - "Tailwind bg-surface-glass utility added to tailwind.config.ts color map. The --color-surface-glass CSS variable existed in globals.css (Wave 0) but was never bound to a Tailwind utility. The plan's left-panel vuln-peek rows specify `bg-surface-glass backdrop-blur-sm` — adding the binding makes the class compile. Single-line scoped change; no semantic shift."
  - "Plan's `! grep -q register` verify is over-broad — the verbatim Pitfall 9 anti-enumeration copy ('If that email is registered, a reset token is on its way.') contains 'registered' as a substring. Refined to `! grep -qE \"register\\(|mode === ['\\\"]register['\\\"]|setMode\\(['\\\"]register['\\\"]\\)\"` to test for register-mode UI (the D-42 spec target) rather than the substring. Verbatim D-49/Pitfall 9 copy retained unchanged."

patterns-established:
  - "Auth-form one-off components live in src/components/auth/ (e.g. ErrorAlert) — distinct from primitives in src/components/ui/. Future password-strength meter, mfa-challenge, account-locked banner all belong in components/auth/"
  - "Validation schemas live in src/lib/validation/ with a per-domain file (auth.ts here; future: connectors.ts, tickets.ts). Each export both the schema and its z.infer<typeof Schema> type so forms can type onSubmit values without re-deriving"
  - "Page-sibling helper pattern — when a Next 15 page file needs a named export consumed by tests, lift it to a sibling .ts file in the same directory (./sanitize-next.ts here)"
  - "next/middleware as a legacy-URL redirect layer (NOT an auth gate, NOT a tenant resolver) — the matcher scopes runtime cost to the five legacy roots; the file is intentionally side-effect-free + side-effect-free + has no localStorage / cookie / DB access"

requirements-completed:
  - UX-01-01
  - UX-01-02
  - UX-01-03
  - UX-01-04
  - UX-01-05

# Metrics
duration: 9min
completed: 2026-05-13
---

# Phase 09 Plan 05: /login Full Rewrite Summary

**/login rebuilt against the sunset design system: split-screen layout (left gradient-mesh + verbatim D-45 marketing + sample CVE peek; right form chrome with SSO-primary + email/password fallback), three-mode state machine (login/forgot/reset) per D-43, react-hook-form + zod validation, ErrorAlert form-level errors, ?reset=TOKEN deep-link, ?next= open-redirect-mitigated redirect, useAuth surfacing SSO failures per D-51, and a Next middleware preserving legacy URL bookmarks.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-13T06:48:14Z
- **Completed:** 2026-05-13T06:56:56Z
- **Tasks:** 3
- **Files:** 5 created, 3 modified

## Accomplishments

- **/login renders the variant-A split-screen sunset layout.** Left panel (`bg-bg-darker` + drifting `bg-gradient-mesh opacity-80 animate-gradient-drift`) carries the H1 tagline `See your security posture <GradientText>without opening another tool.</GradientText>` (D-45 verbatim) plus the sub-line `One dashboard. Every scanner. Real ownership. Tickets out, fewer meetings.` and four hard-coded vuln-peek cards (CVE-2024-3094 xz-utils, CVE-2021-44228 log4shell, CVE-2022-22965 Spring4Shell, CVE-2023-23397 Outlook NTLM leak — real public KEVs per D-44). Right panel hosts a max-width-sm vertical-centered form column with mode-aware heading (`Sign in` / `Reset your password` / `Set a new password`), SSO row + `or with email` divider (login mode only), and the RHF+zod form.
- **Three-mode state machine via `useState<Mode>` + `?reset=TOKEN` deep-link entry.** `LoginPanels` reads `searchParams.get('reset')` and initializes `mode = resetToken ? 'reset' : 'login'`; switching to `forgot` clears `authError` and `forgotSent` so stale state doesn't leak between modes. SSO row + divider render only when `mode === 'login'` (UX-01-02 + UX-01-04). Reset mode has no in-app mode-switch link in to it (token-gated per D-47); forgot has an explicit `Back to sign in` button.
- **react-hook-form + zod validation per D-21 + D-53.** Three `useForm<z.infer<typeof Schema>>` instances (one per mode) with `resolver: zodResolver(schema)` + `mode: 'onSubmit'`. Field errors flow through `<FormControl><Input/></FormControl>` (FormControl auto-sets `aria-invalid={!!error}` which flips Input's border to `--color-danger` per D-28) + `<FormMessage>` (renders `error?.message` in `text-danger`). Schema messages are sentence-case + specific per copy-voice.md (`Enter your password.`, `At least 8 characters.`).
- **D-48 autoFocus + autoComplete map fully applied.**

| Mode | First field | autoFocus | autoComplete |
|---|---|---|---|
| login | email | ✓ | `email` |
| login | password | — | `current-password` |
| forgot | email | ✓ | `email` |
| reset | token | — (pre-filled from `?reset=`) | `off` |
| reset | newPassword | ✓ (first fillable) | `new-password` |

- **D-49 generic 401 + pass-through other 4xx.** `LoginForm.onSubmit` catches the thrown `AuthError` and switches: `status === 401` → `'Email or password is incorrect.'` (verbatim); else → `err.message ?? 'Sign-in failed. Try again in a moment.'`. Surfaced into `<ErrorAlert>` above the SSO row.
- **D-51 SSO failure surfacing.** `useAuth.loginSSO` now throws an `Error` with the verbatim provider-named copy (`Sign-in with Google is temporarily unavailable. Try email instead.` / `…with Microsoft…`) on three failure branches: fetch network throw, `!resp.ok`, malformed JSON / missing `authorization_url`. `SsoRow.handleSso` catches and pipes the message into `setAuthError`.
- **D-50 ?next= encoding + Pitfall 10 sanitizer.** `useAuth`'s route-guard `useEffect` now redirects unauthed `/dashboard/*` hits to `/login?next=${encodeURIComponent(pathname+search)}`. `/login` reads `searchParams.get('next')` and runs `sanitizeNext()` before any `router.replace()` — same-origin path only (`decoded.startsWith('/') && !decoded.startsWith('//') && !decoded.startsWith('/\\\\')`), decode-failure falls back to `/dashboard`, null/empty falls back to `/dashboard`. `sanitizeNext` lives in `src/app/login/sanitize-next.ts` (sibling file — Next.js 15 page-export constraint).
- **Anti-enumeration forgot-password (Pitfall 9, T-09-05-03).** `ForgotForm.onSubmit` calls `fetch('/auth/forgot-password')` and unconditionally sets `forgotSent = true` in `finally` — including on network throw. Confirmation copy is the verbatim `If that email is registered, a reset token is on its way.` regardless of backend response shape.
- **Suspense boundary around `useSearchParams` (Pitfall 8).** Top-level `LoginPage` returns `<Suspense fallback={<LoginFallback />}><LoginPanels/></Suspense>`. Fallback is a minimal `Loading…` (no chrome) to avoid flash-of-skeleton on warm navigation. Verified via `npm run build` — no `useSearchParams` Suspense warning.
- **WCAG 2 SC 1.3.1 — H1 reachable to assistive tech.** Plan's instinct was `aria-hidden` on the `<section>`; that would swallow the elevator-pitch H1. Implementation aria-hides only the genuinely decorative children (`<div className="bg-gradient-mesh">` and the vuln-peek preview rows). H1 + sub-line stay landmarked. Asserted in `page.test.tsx` via `screen.getByRole('heading', { level: 1 })`.
- **frontend/middleware.ts — legacy URL preservation (Open Question 2).** Five-route `LEGACY_MAP` (`/assets`, `/integrations`, `/settings`, `/tickets`, `/vulnerabilities`) redirects root + subpaths to `/dashboard/*` with 308 (permanent + method-preserving). Matcher scopes runtime cost to only those five tree branches; doesn't run on `/`, `/login`, `/dashboard/*`, `/dev/primitives`. NO auth gating (research §Pattern 5 confirmed cookie-vs-localStorage incompatibility with middleware-level auth).
- **17 unit tests, all green.** Covers the four validation-map rows (UX-01-02 / UX-01-04 / UX-01-05 / Open-redirect mitigation) + D-43 deep-link + D-48 autoComplete + D-49 401 generic + Pitfall 9 + D-51 SSO failure + WCAG H1 reachability + axe-clean login mode. Total suite: **53 tests passing across 8 files in ~2.2s** via `npm test -- --run`.

## Task Commits

Each task was committed atomically (`--no-verify` per parallel-executor protocol — orchestrator runs hooks once after wave completion):

1. **Task 1: zod schemas + ErrorAlert + useAuth ?next= update + middleware** — `d4f9184` (feat)
2. **Task 2: /login full rewrite — split-screen + mode state machine** — `0f5dcf2` (feat)
3. **Task 3: /login unit tests** — `a586209` (test)

## Files Created/Modified

### Created (5)

- `frontend/src/lib/validation/auth.ts` — zod schemas (loginSchema, forgotSchema, resetSchema) + inferred types (D-53)
- `frontend/src/components/auth/error-alert.tsx` — auth-form-level ErrorAlert banner with role='alert' (D-28, UX-01-05)
- `frontend/middleware.ts` — Next middleware mapping legacy /assets, /integrations, /settings, /tickets, /vulnerabilities (root + subpaths) → /dashboard/* with 308 (Open Question 2)
- `frontend/src/app/login/sanitize-next.ts` — exported open-redirect sanitizer for `?next=` (Pitfall 10, T-09-05-01); sibling file to page.tsx because Next.js 15 rejects non-default page exports
- `frontend/src/app/login/page.test.tsx` — 17 unit tests across 7 describe blocks (sanitizer, mode switching, autoComplete, ErrorAlert classes, anti-enumeration, SSO failure surfacing, axe)

### Modified (3)

- `frontend/src/app/login/page.tsx` — full rewrite per plan (557 lines); v1 register-mode + Sign-up UI deleted (D-42); split-screen layout + three-mode state machine + RHF+zod + Suspense + sanitizeNext consumption
- `frontend/src/lib/auth.tsx` — AuthError class added; login() throws instead of returning string (caller owns post-success redirect for ?next= sanitization); loginSSO() typed 'google'|'azure' and throws verbatim D-51 copy on backend unreachable/malformed; route-guard useEffect encodes ?next=encodeURIComponent(pathname+search) (D-50)
- `frontend/tailwind.config.ts` — bg-surface-glass utility binding added (left-panel vuln-peek cards consume it)

## Decisions Made

- **sanitizeNext lifted to a sibling file.** Next.js 15 enforces a closed set of page-file exports (default + route-segment config). `export function sanitizeNext` in `page.tsx` failed the build with `"sanitizeNext" is not a valid Page export field.` Lifted to `src/app/login/sanitize-next.ts` — same semantics, the test suite imports from `./sanitize-next`, the page imports from `./sanitize-next`. Discovered during the Task 2 build verification gate; documented as Rule 3 (blocking) deviation.
- **useAuth.login signature changed from `Promise<string | null>` to `Promise<void>` that throws AuthError.** Plan's Task 2 expected `try { await login() } catch (e) { e.status === 401 }`. Incompatible with v1's return-string contract. Updated the interface as a Task 1 deviation (Rule 3 — Blocking) so /login can map 401 → D-49 generic copy without parsing message strings. AuthError class exported for future consumers (logout-with-error, refresh-failure UI).
- **loginSSO retained existing JSON-GET contract instead of switching to HEAD-pre-flight.** The plan literally specified `fetch('/auth/login/${provider}', { method: 'HEAD' })` + `!probe.ok` + `window.location.href = X`. The v1 backend returns `{authorization_url, state}` JSON — switching to HEAD would have broken state handoff (no `state` to store in localStorage for OIDC callback). Kept the GET-JSON contract; threw on three failure branches (network throw, `!resp.ok`, missing `authorization_url`). Strictly safer than the plan's HEAD pattern would have been against the actual backend contract.
- **Tailwind `bg-surface-glass` utility binding added.** `--color-surface-glass` CSS variable existed in `globals.css` from Wave 0 but was never bound to a Tailwind utility. The plan's left-panel vuln-peek rows specify `bg-surface-glass backdrop-blur-sm` — adding the binding makes the class compile. Single-line scoped change.
- **Plan's `! grep -q register` over-broad — refined.** The verbatim Pitfall 9 anti-enumeration copy contains "registered" as a substring. Used a more precise regex (`! grep -qE "register\(|mode === ['\"]register['\"]|setMode\(['\"]register['\"]\)"`) that tests for register-mode UI (the D-42 spec target) rather than the substring. Verbatim Pitfall 9 copy preserved.
- **LeftPanel `<section>` NOT aria-hidden.** Plan's outline suggested making the entire decorative panel aria-hidden. That would swallow the H1 tagline (the product's elevator pitch + landmark) from assistive tech, violating WCAG 2 SC 1.3.1. Only the truly decorative children (gradient mesh, vuln-peek preview rows, severity color glyphs) are aria-hidden. Asserted via `page.test.tsx` "keeps the H1 tagline reachable to assistive tech".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Next.js 15 rejects non-default exports from page.tsx**
- **Found during:** Task 2 build verification (`npm run build`)
- **Issue:** Plan specified `export function sanitizeNext` in `page.tsx` so tests can import it directly. Next.js 15 fails the build: `Type error: Page "src/app/login/page.tsx" does not match the required types of a Next.js Page. "sanitizeNext" is not a valid Page export field.`
- **Fix:** Lifted `sanitizeNext` to a sibling file `src/app/login/sanitize-next.ts`. Page imports via `import { sanitizeNext } from './sanitize-next';`. Tests import from `./sanitize-next` too. Same semantics, same exports.
- **Files modified:** `frontend/src/app/login/page.tsx`, `frontend/src/app/login/sanitize-next.ts` (new)
- **Verification:** `npm run build` exits 0; `page.test.tsx` sanitizer suite (6 tests) passes; plan grep `grep -q 'export function sanitizeNext'` re-targeted to `sanitize-next.ts`.
- **Committed in:** `0f5dcf2` (Task 2 commit)

**2. [Rule 3 — Blocking] useAuth.login return-string contract incompatible with plan's throw-and-catch pattern**
- **Found during:** Task 1 type-check after AuthState type update
- **Issue:** v1 `useAuth.login` returned `Promise<string | null>` (string = error message, null = success). Plan's Task 2 expected `try { await login() } catch (e) { if (e?.status === 401) ... }`. Cannot map 401 → generic copy via D-49 without status carrier.
- **Fix:** Added `AuthError` class with `.status` property; changed `login()` to throw `AuthError` instead of returning string. Caller (LoginForm.onSubmit) owns post-success `router.replace(sanitizeNext(...))` for ?next= sanitization. Old `router.replace('/dashboard')` removed from `login()` body.
- **Files modified:** `frontend/src/lib/auth.tsx`
- **Verification:** `npx tsc --noEmit` exits 0 after Task 2's page.tsx rewrite consumes the new contract; D-49 401 test in page.test.tsx asserts ErrorAlert renders `'Email or password is incorrect.'` on `login.mockRejectedValueOnce({ status: 401, ... })`.
- **Committed in:** `d4f9184` (Task 1 commit)

**3. [Rule 3 — Blocking] Plan's `! grep -q register` over-broad against Pitfall 9 verbatim copy**
- **Found during:** Task 2 verification gate (plan grep)
- **Issue:** Pitfall 9 anti-enumeration copy contains "registered" — `! grep -q "register"` falsely fires. The intent of D-42 is "no register-mode UI", not "no string 'register' anywhere".
- **Fix:** Refined the local verification to `! grep -qE "register\(|mode === ['\"]register['\"]|setMode\(['\"]register['\"]\)"`. Verbatim Pitfall 9 copy retained unchanged.
- **Files modified:** None (verification-fidelity adjustment)
- **Verification:** `grep -n "register" page.tsx` returns one line — the Pitfall 9 anti-enumeration string. No register-mode UI, no `setMode('register')`, no `register()` call site.
- **Committed in:** `0f5dcf2` (Task 2 commit — the artifact this verifies)

**4. [Rule 2 — Missing Critical] `bg-surface-glass` Tailwind utility binding absent**
- **Found during:** Task 2 plan-literal copy
- **Issue:** Plan's left-panel vuln-peek cards specify `className="… bg-surface-glass backdrop-blur-sm …"`. The `--color-surface-glass` CSS variable exists in globals.css (Wave 0), but `bg-surface-glass` was never bound to a Tailwind utility — the class would not compile.
- **Fix:** Added `'surface-glass': 'var(--color-surface-glass)'` to `tailwind.config.ts` colors map. Single-line scoped change.
- **Files modified:** `frontend/tailwind.config.ts`
- **Verification:** `npm run build` exits 0 with `bg-surface-glass` resolving; visually the cards render with the rgba(255,255,255,0.65) glass tint.
- **Committed in:** `0f5dcf2` (Task 2 commit)

**5. [Rule 2 — Missing Critical] loginSSO HEAD-pre-flight pattern would break the v1 OIDC state handoff**
- **Found during:** Task 1 useAuth modification
- **Issue:** Plan's literal Task 1 code: `await fetch('/auth/login/${provider}', { method: 'HEAD' })` → on `!probe.ok` throw, else `window.location.href = '${apiUrl}/auth/login/${provider}'`. The v1 backend returns `{authorization_url, state}` JSON; `window.location.href = '/auth/login/${provider}'` would re-hit the same endpoint (which doesn't redirect — it returns JSON). And there's no `state` to localStorage for the OIDC callback to match.
- **Fix:** Retained the existing GET-JSON contract (`{authorization_url, state}`) but threw the verbatim D-51 copy on three failure branches: fetch network throw, `!resp.ok`, missing `authorization_url`. Strictly safer than HEAD-pre-flight against the actual backend.
- **Files modified:** `frontend/src/lib/auth.tsx`
- **Verification:** `page.test.tsx` D-51 test asserts `<ErrorAlert>` renders the verbatim D-51 copy on `loginSSO.mockRejectedValueOnce(new Error('Sign-in with Google is temporarily unavailable. Try email instead.'))`. Grep `Sign-in with.*is temporarily unavailable` passes against `lib/auth.tsx`.
- **Committed in:** `d4f9184` (Task 1 commit)

---

**Total deviations:** 5 auto-fixed (3 Rule 3 Blocking, 2 Rule 2 Missing Critical)
**Impact on plan:** All deviations corrected real cross-version incompatibilities (Next 15 page-export constraint), contract mismatches (useAuth.login return-string vs throw-and-catch), tooling fidelity (over-broad grep), missing token bindings (bg-surface-glass), and backend-contract correctness (loginSSO HEAD-vs-JSON-GET). Zero scope creep. All plan success criteria pass.

## Issues Encountered

### Worktree base correction (process record-keeping)

- **Issue:** The parallel-executor worktree was created from `8cede77` (audit-era pre-Phase-9 state) instead of the expected base `f57b5c4` (= 09-04 SUMMARY commit). Per the prompt's `<worktree_branch_check>`, ran `git reset --hard f57b5c40...` to advance the branch to the correct base. Working tree then had the full Phase 9 carry-forward state (Wave 0+1+3+4 outputs). Same condition Wave 1 + Wave 0 hit; documented for the third time now.
- **Resolution:** `git reset --hard f57b5c4` brought the branch to the correct base; `npm install --legacy-peer-deps` re-hydrated `node_modules` (worktree had none). No work lost.

### jsdom canvas warnings (stderr noise, pre-existing)

- **Issue:** axe-core's `colorContrastMatches` rule calls `HTMLCanvasElement.getContext('2d')` for color-contrast computation; jsdom doesn't implement Canvas. Same condition Wave 1 hit; logged in Wave 0's `deferred-items.md`.
- **Resolution:** Out of plan scope. Tests still pass — axe-core falls back to skipping that contrast check. No new entry to `deferred-items.md`.

## User Setup Required

None — no external service configuration. All work is build-time + runtime inside the frontend bundle. Auth backend endpoints (`/auth/login`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/login/{google|azure}`) are unchanged from v1.

## Threat Flags

No new threat surface. Per the plan's threat register:

- T-09-05-01 (open redirect via `?next=//evil.com`) → **mitigate**, delivered via `sanitizeNext()` in `src/app/login/sanitize-next.ts`, unit-tested for protocol-relative, absolute URL, backslash trickery, decode failure cases.
- T-09-05-02 (user enumeration via login error) → **mitigate**, delivered via D-49 generic copy on 401 in `LoginForm.onSubmit`; other 4xx pass through backend `detail`. Unit-tested via mocked 401.
- T-09-05-03 (user enumeration via forgot-password) → **mitigate**, delivered via Pitfall 9 generic confirmation in `ForgotForm.onSubmit`'s `finally`. Unit-tested.
- T-09-05-04 (XSS via reflected `?next=<script>`) → **mitigate**, `?next` only used as `router.replace()` target; React text-escapes all string content.
- T-09-05-05 (password-manager autofill leak across modes) → **mitigate**, per-mode `autoComplete` attrs per D-48. Unit-tested.
- T-09-05-06 → accept (reset token in URL — inherent to magic-link pattern; backend hashes; deferred).
- T-09-05-07 (SSO copy mislead) → accept + backend-5xx mitigation delivered via `loginSSO` throw on `!resp.ok` / missing `authorization_url`. Provider name hardcoded in `toBackendProvider`/`handleSso` — no user-controlled input feeds the D-51 copy.
- T-09-05-08 → accept (CSRF on login POST — backend handles).
- T-09-05-09 → accept (password autofill on type-toggle — standard pattern with `aria-pressed`).
- T-09-05-10 → accept (token in localStorage XSS-readable — pre-existing v1 condition; backend cookie migration is out of scope).

## Known Stubs

None. All forms ship a real implementation:

- `LoginForm` calls `useAuth().login(email, password)` against `POST /auth/login`.
- `ForgotForm` calls `POST /auth/forgot-password` directly (no useAuth involvement — preserves v1 pattern + Pitfall 9 anti-enumeration without leaking through the auth context).
- `ResetForm` calls `POST /auth/reset-password` directly with `{token, new_password: newPassword}` shape (matches v1 backend contract).
- `SsoRow` calls `useAuth().loginSSO('google' | 'azure')` which hits backend `GET /auth/login/{provider}` for the OIDC start URL.
- `SAMPLE_VULNS` constant is intentionally hard-coded sample data per D-44 — it's the product peek, not a data fetch.

## Next Phase Readiness

**Ready for Plan 09-06 (Wave 5 — manual smoke + verifier handoff):**

- `/login` renders against the v1 backend unchanged at `http://localhost:3000/login` after `cd frontend && npm run dev`.
- `?reset=TOKEN` deep-link, `?next=/dashboard/vulnerabilities` redirect, `?next=//evil.com` block all exercise-able via browser.
- 53 unit tests pass; `npm run build` produces an optimized `/login` bundle of 35.2 kB (145 kB first-load JS).
- Middleware is wired but only redirects the five legacy roots; doesn't intercept `/`, `/login`, `/dashboard/*`, `/dev/primitives`.

**Carry-forward:**

- CSPM `ComplianceFramework.name` type fix (from Wave 0's deferred-items.md) — was actually fixed in the base commit `8cede77` chain; current `tsc --noEmit` is clean. Note may now be obsolete.
- `npm run lint` interactive ESLint setup (from Wave 0's deferred-items.md) — still outstanding; not exercised by this plan.
- Canvas / color-contrast in axe-core under jsdom (Wave 1's deferred concern) — still outstanding; tests pass with the warning.
- Backend `_reset_tokens` Redis migration (T-09-05-06 accept disposition) — deferred to a future v1.x backend hardening phase.
- Backend token-in-cookie migration (T-09-05-10 accept disposition) — deferred to a future v1.x backend hardening phase; would also enable middleware-level auth gating per research §Pattern 5.

## Self-Check: PASSED

Verified after writing this summary:
- `git log --oneline | grep -E 'd4f9184|0f5dcf2|a586209'` → all three task commits present on branch.
- `test -f frontend/src/lib/validation/auth.ts && test -f frontend/src/components/auth/error-alert.tsx && test -f frontend/middleware.ts && test -f frontend/src/app/login/sanitize-next.ts && test -f frontend/src/app/login/page.test.tsx` → all five created paths exist on disk.
- `npm test -- --run` → 53 tests passing across 8 files (Wave 0 foundation + Wave 1 primitives + Wave 3 shell + Wave 4 /login).
- `npm run build` → exits 0; `/login` bundle renders.
- `npx tsc --noEmit` → exits 0; zero type errors.

---
*Phase: 09-login-foundation, Plan: 05*
*Completed: 2026-05-13*
