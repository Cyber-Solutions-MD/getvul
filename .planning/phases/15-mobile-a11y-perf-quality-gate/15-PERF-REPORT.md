---
phase: 15
plan: 06
artifact: perf-report
status: partial
---

# Phase 15 — Performance Report (SC #6)

> Committed verification artifact per Plan 15-06 success criterion #6.
> Bundle Budget below is COMPLETE (run headless — no backend needed).
> Lighthouse Mobile remains pending the live run (Task 3 — needs the stack on :3000).
> Do NOT paste credentials or the storageState JWT into this file (T-15-11 threat model).

**Run date:** 2026-06-27 (bundle budget)
**Commit:** addb572
**Branch:** main

---

## Bundle Budget (<=250 KB gzipped per route) — ✅ PASS

Run: `cd frontend && npm run perf:budget` (`next build` + `scripts/check-bundle-all.mjs`)

| Route | First Load JS | Budget (250 KB) | Result |
|-------|--------------|-----------------|--------|
| `/` | 102.0 kB | 250 KB | ✅ PASS |
| `/login` | 144.0 kB | 250 KB | ✅ PASS |
| `/dashboard` | 138.0 kB | 250 KB | ✅ PASS |
| `/dashboard/vulnerabilities` | 158.0 kB | 250 KB | ✅ PASS |
| `/dashboard/assets` | 129.0 kB | 250 KB | ✅ PASS |
| `/dashboard/assets/[id]` | 161.0 kB | 250 KB | ✅ PASS |
| `/dashboard/tickets` | 166.0 kB | 250 KB | ✅ PASS |
| `/dashboard/tickets/[id]` | 137.0 kB | 250 KB | ✅ PASS |
| `/dashboard/tickets/rules` | 125.0 kB | 250 KB | ✅ PASS |
| `/dashboard/cspm` | 157.0 kB | 250 KB | ✅ PASS |
| `/dashboard/connectors` | 153.0 kB | 250 KB | ✅ PASS |
| `/dashboard/users` | 128.0 kB | 250 KB | ✅ PASS |
| `/dashboard/settings` | 156.0 kB | 250 KB | ✅ PASS |
| `/dev/primitives` | 102.0 kB | 250 KB | ✅ PASS |
| `/_not-found` | 103.0 kB | 250 KB | ✅ PASS |

**Overall budget result:** ✅ PASS — 15/15 routes within budget.
**Largest route:** `/dashboard/tickets` at 166.0 kB (84 KB headroom under the 250 KB ceiling).

> Build was green only after the D-09 audit fixes in commit `addb572` (tsconfig e2e
> exclusion, Playwright baseURL placement, `(authed)` force-dynamic for the
> useSearchParams-prerender class, connectors Suspense wrapper, nav-drawer Tailwind
> class disambiguation). No route required code-splitting; no items deferred to backlog.

---

## Lighthouse Mobile (>=90 perf, >=90 a11y)

Run: `cd frontend && npm run perf:lh`
(Requires stack running: `docker-compose up -d` + frontend on :3000, OR let lhci manage via startServerCommand.)

| URL | Performance Score | Accessibility Score | Result |
|-----|------------------|---------------------|--------|
| `/login` | (pending — fill from `npm run perf:lh`) | (pending — fill from `npm run perf:lh`) | (pending) |
| `/dashboard` | (pending — fill from `npm run perf:lh`) | (pending — fill from `npm run perf:lh`) | (pending) |

**Target:** >= 90 performance AND >= 90 accessibility on both URLs.
**Lighthouse config:** `frontend/lhci.config.js` — mobile preset, formFactor: mobile, throttling: 150ms RTT / 1.6 Mbps / 4x CPU.

> If any score is below 90, per D-09 fix and re-run. Only backend-requiring causes
> may be deferred with a risk note.

---

## Verification Sign-Off

- [x] `npm run perf:budget` exit 0 — all routes <= 250 KB (2026-06-27, commit addb572)
- [ ] `npm run perf:lh` — /login performance >= 90
- [ ] `npm run perf:lh` — /login accessibility >= 90
- [ ] `npm run perf:lh` — /dashboard performance >= 90
- [ ] `npm run perf:lh` — /dashboard accessibility >= 90
- [ ] No `(pending)` cells remain in this report
- [ ] No credentials or JWT pasted into this file

**Sign-off by:** (pending)
**Date:** (pending)
