---
status: partial
phase: 09-login-foundation
source: [09-VERIFICATION.md]
started: 2026-05-13T07:25:00Z
updated: 2026-05-13T07:25:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Split-screen at 1280px (UX-01-01)
expected: `/login` at 1280×800 → left panel shows drifting `--gradient-mesh` + tagline + sample CVE rows; right panel shows clean dark form chrome with `Sign in` heading + SSO buttons + email/password fields. Side-by-side comparison against `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` should be visually faithful.
result: [pending]

### 2. Mobile collapse at 360px (UX-01-01 mobile + D-41)
expected: DevTools iPhone SE / 360×640 → no horizontal scroll on `/login` or `/dashboard`; sidebar hides at viewport ≤999px (D-41 verbatim breakpoint).
result: [pending]

### 3. Font cold-paint (UX-01-04)
expected: DevTools Network → disable cache → Cmd+Shift+R reload `/login` → exactly two woff2 requests (Inter + JetBrains Mono); fallback-system → Inter swap visible; no FOIT; no `data-theme` hydration warnings.
result: [pending]

### 4. End-to-end login (Phase 9 §5 + §6)
expected: Use seed admin credentials → click `Sign in` → button shows `Signing in…` → land on `/dashboard` inside the `(authed)` shell (sidebar 220px, brand `<Link>` to /dashboard, topbar with ⌘K). Dashboard nav item active; navigating to `/dashboard/vulnerabilities` activates Vulnerabilities nav (D-35 exact-match).
result: [pending]

### 5. `?next=` preservation (Phase 9 §5 + D-50)
expected: Incognito → visit `/dashboard/vulnerabilities` → redirected to `/login?next=%2Fdashboard%2Fvulnerabilities` → sign in → land at `/dashboard/vulnerabilities`.
result: [pending]

### 6. Open-redirect mitigation (Pitfall 10)
expected: Incognito → `/login?next=//evil.com` then `/login?next=https://evil.com` then `/login?next=/\evil.com` → after login all land on `/dashboard` (NOT off-site). Runtime confirmation of the sanitizer's unit-tested behavior.
result: [pending]

### 7. Theme toggle + persistence (D-38 + D-13)
expected: UserChip → Theme: Light → page background switches; reload → still light, no FOUC flash; Theme: Dark → switches back; `localStorage.getvul_theme` holds the value; `<html data-theme="…">` always set.
result: [pending]

### 8. Reduced-motion (D-12)
expected: macOS System Settings → Accessibility → Reduce motion ON → reload `/login` → drifting gradient-mesh is static; OFF → drift returns.
result: [pending]

### 9a. /dev/primitives dev-mode (D-31)
expected: `npm run dev` → `/dev/primitives` renders the state matrix (Button variants/sizes/states, Input types, SsoButton both providers, GradientText accent).
result: [pending]

### 9b. /dev/primitives production 404 (D-31 + OQ 6)
expected: Stop dev → `cd frontend && npm run build && npm run start` → navigate `/dev/primitives` → 404 (NODE_ENV-gated). Restart dev after.
result: [pending]

### 10. Forgot password flow (UX-01-04)
expected: Login mode → click `Forgot password?` → mode switches, SSO row + divider HIDDEN, heading reads `Reset your password`; submit any email → see generic copy `If that email is registered, a reset token is on its way.` (Pitfall 9 anti-enumeration); `Back to sign in` returns to login mode with SSO visible again.
result: [pending]

### 11. Reset deep-link (D-43)
expected: Visit `/login?reset=test-token-123` → reset mode entered, heading `Set a new password`, SSO HIDDEN, `Reset token` field pre-filled with `test-token-123` (autocomplete=off); `New password` field autofocused.
result: [pending]

### 12. Legacy URL redirects (Wave 4 middleware)
expected: `/assets` → 308 redirect → `/dashboard/assets`; `/tickets/T-001` → 308 → `/dashboard/tickets/T-001`. middleware.ts handles five legacy roots.
result: [pending]

## Summary

total: 12
passed: 0
issues: 0
pending: 12
skipped: 0
blocked: 0

## Gaps
