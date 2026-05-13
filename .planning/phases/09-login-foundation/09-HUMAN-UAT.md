---
status: complete
phase: 09-login-foundation
source: [09-VERIFICATION.md]
started: 2026-05-13T07:25:00Z
updated: 2026-05-13T17:10:00Z
completed: 2026-05-13T17:10:00Z
---

## Current Test

— all tests complete —

## Tests

### 1. Split-screen at 1280px (UX-01-01)
expected: `/login` at 1280×800 → left panel shows drifting `--gradient-mesh` + tagline + sample CVE rows; right panel shows clean dark form chrome with `Sign in` heading + SSO buttons + email/password fields. Side-by-side comparison against `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` should be visually faithful.
result: PASS — human verifier confirmed visual fidelity 2026-05-13

### 2. Mobile collapse at 360px (UX-01-01 mobile + D-41)
expected: DevTools iPhone SE / 360×640 → no horizontal scroll on `/login` or `/dashboard`; sidebar hides at viewport ≤999px (D-41 verbatim breakpoint).
result: PASS — verified at iPhone 14 Pro Max (430×932): no horizontal scroll, sidebar hidden per D-41. Known gap (out of Phase 9 scope): no mobile replacement nav — scheduled for Phase 15 (bottom-nav).

### 3. Font cold-paint (UX-01-04)
expected: DevTools Network → disable cache → Cmd+Shift+R reload `/login` → exactly two woff2 requests (Inter + JetBrains Mono); fallback-system → Inter swap visible; no FOIT; no `data-theme` hydration warnings.
result: PASS — verified on cold reload of `/login`: two distinct woff2 files (`bb3ef058b751a6ad-s.p.woff2` 41.5 kB + `e4af272ccee01ff0-s.p.woff2` 49.4 kB), both 200, both type `font`. Listed twice each because Next preloads via `<link rel=preload>` and main-app.js consumes them — same two physical files. DOMContentLoaded 112ms / Load 547ms. No data-theme hydration warnings observed.

### 4. End-to-end login (Phase 9 §5 + §6)
expected: Use seed admin credentials → click `Sign in` → button shows `Signing in…` → land on `/dashboard` inside the `(authed)` shell (sidebar 220px, brand `<Link>` to /dashboard, topbar with ⌘K). Dashboard nav item active; navigating to `/dashboard/vulnerabilities` activates Vulnerabilities nav (D-35 exact-match).
result: PASS — sign-in flow lands inside `(authed)` shell with sidebar + topbar; no white flash; D-35 active-state behavior verified.

### 5. `?next=` preservation (Phase 9 §5 + D-50)
expected: Incognito → visit `/dashboard/vulnerabilities` → redirected to `/login?next=%2Fdashboard%2Fvulnerabilities` → sign in → land at `/dashboard/vulnerabilities`.
result: PASS — `/login?next=%2Fdashboard%2Ftickets` → after sign-in landed at `/dashboard/tickets` (not `/dashboard`). `?next=` is preserved and consumed correctly.

### 6. Open-redirect mitigation (Pitfall 10)
expected: Incognito → `/login?next=//evil.com` then `/login?next=https://evil.com` then `/login?next=/\evil.com` → after login all land on `/dashboard` (NOT off-site). Runtime confirmation of the sanitizer's unit-tested behavior.
result: PASS — all three malicious `?next=` values (`//evil.com`, `https://evil.com`, `/\evil.com`) sanitized at runtime; sign-in lands on `/dashboard`. Pitfall 10 mitigation confirmed in browser, matching unit tests.

### 7. Theme toggle + persistence (D-38 + D-13)
expected: UserChip → Theme: Light → page background switches; reload → still light, no FOUC flash; Theme: Dark → switches back; `localStorage.getvul_theme` holds the value; `<html data-theme="…">` always set.
result: PASS — mechanism, persistence (`localStorage.getvul_theme`), and `<html data-theme="…">` attribute all verified; no FOUC flash on cold reload either direction. WR-03 visual brokenness in Light confirmed visually (severity/accent/danger pills stay dark-tuned on cream surface); follow-up mitigation shipped in same session — Light radio in UserChip is now `disabled` with an `In progress` badge until D-06 / UX-D-03 lands. `Theme: Dark` remains clickable so users mid-broken-light can escape.

### 8. Reduced-motion (D-12)
expected: macOS System Settings → Accessibility → Reduce motion ON → reload `/login` → drifting gradient-mesh is static; OFF → drift returns.
result: PASS — verified both directions: with macOS Reduce Motion ON the gradient mesh is static; with it OFF the drift returns. D-12 / `@media (prefers-reduced-motion: reduce)` block in globals.css working as intended.

### 9a. /dev/primitives dev-mode (D-31)
expected: `npm run dev` → `/dev/primitives` renders the state matrix (Button variants/sizes/states, Input types, SsoButton both providers, GradientText accent).
result: PASS — full state matrix renders: Button variants (cta/secondary/ghost), sizes (Small/Medium/Large), states (Default/Disabled/Signing in…/Left icon/Right icon), asChild anchor with sunset gradient; Input types (Email/Password+eye-toggle/Error state with red border/Disabled with "locked" placeholder); SsoButton with both Google and Microsoft marks; GradientText accent ("See your security posture without opening another tool.") with closing phrase rendered in sunset gradient via background-clip:text.

### 9b. /dev/primitives production 404 (D-31 + OQ 6)
expected: Stop dev → `cd frontend && npm run build && npm run start` → navigate `/dev/primitives` → 404 (NODE_ENV-gated). Restart dev after.
result: PASS — `npm run build` then `npm run start` (NODE_ENV=production), `curl http://localhost:3000/dev/primitives` returns HTTP 404. The runtime `process.env.NODE_ENV === 'production' && notFound()` gate fires as designed; D-31 + OQ 6 satisfied. Route still appears in the build manifest (Next prerender list) but is blocked at request time.

### 10. Forgot password flow (UX-01-04)
expected: Login mode → click `Forgot password?` → mode switches, SSO row + divider HIDDEN, heading reads `Reset your password`; submit any email → see generic copy `If that email is registered, a reset token is on its way.` (Pitfall 9 anti-enumeration); `Back to sign in` returns to login mode with SSO visible again.
result: PASS — mode transition `login → forgot` hides SSO row + divider and swaps heading to `Reset your password`; bogus email submit returns the verbatim anti-enumeration copy `If that email is registered, a reset token is on its way.` (Pitfall 9 mitigation); `Back to sign in` restores login mode with SSO row visible.

### 11. Reset deep-link (D-43)
expected: Visit `/login?reset=test-token-123` → reset mode entered, heading `Set a new password`, SSO HIDDEN, `Reset token` field pre-filled with `test-token-123` (autocomplete=off); `New password` field autofocused.
result: PASS — `/login?reset=test-token-123` enters reset mode automatically; heading reads `Set a new password`; SSO row + divider hidden; `Reset token` field pre-filled with `test-token-123` (autocomplete=off); `New password` field autofocused. D-43 deep-link contract honored.

### 12. Legacy URL redirects (Wave 4 middleware)
expected: `/assets` → 308 redirect → `/dashboard/assets`; `/tickets/T-001` → 308 → `/dashboard/tickets/T-001`. middleware.ts handles five legacy roots.
result: PASS (with in-session defect-and-fix) — initial browser test surfaced `/assets` returning HTTP 404 instead of redirecting. Root cause: two Phase 9 defects the automated gate missed. (1) File location: `middleware.ts` was at `frontend/middleware.ts` but Next 15 with `src/app/` requires `frontend/src/middleware.ts` — Next silently ignored the file. (2) Matcher pattern: `/assets/:path*` only matches subpaths (`/assets/foo`), not the bare `/assets` — the bare path needs to be listed separately. Both fixed in this session (file moved into `src/`; matcher updated to explicit-list both bare path and `:path*` variants). After restart, curl-verified all 5 legacy roots return HTTP 308 to the correct `/dashboard/...` target. 53/53 tests still green; tsc clean. Reason Phase 9 verification missed it: unit tests imported the middleware function and mocked NextRequest/NextResponse, never exercising the matcher through Next's runtime, and the deliverable inventory check verified file existence at the wrong path.

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- **Mobile replacement nav** (surfaced during Test 2): at viewport ≤999px the sidebar correctly hides per D-41, but Phase 9 ships no mobile-only nav (hamburger, drawer, or bottom-nav). Mobile users can only switch screens via URL today. Already scoped to Phase 15 ("bottom-nav") per ROADMAP. Not a Phase 9 blocker.
- **Light theme visuals deferred** (surfaced during Test 7, matches WR-03): `:root[data-theme="light"]` overrides only surface/border/text base tokens — severity/accent/danger/gradient tokens stay dark-tuned, producing broken contrast on cream surface. Mitigation shipped in this session: Light radio in `UserChip` is now `disabled` with an `In progress` badge so users can't toggle into broken state. Polished light visuals remain deferred to D-06 / UX-D-03.
- **Middleware location + matcher defect** (surfaced during Test 12, fixed in same session): `middleware.ts` was at `frontend/middleware.ts`; Next 15 with `src/app/` ignores it there — must live at `frontend/src/middleware.ts`. Additionally, the matcher used `/assets/:path*` style which matches subpaths but not bare `/assets`. Both fixed; all five legacy roots now 308-redirect correctly per curl probe of the running dev server. Suggested follow-up: add an integration test (Playwright or a `fetch` probe under vitest with the actual Next server) that curls each legacy URL through the running stack — unit-mocked NextRequest/NextResponse tests can't catch matcher or file-location defects.
