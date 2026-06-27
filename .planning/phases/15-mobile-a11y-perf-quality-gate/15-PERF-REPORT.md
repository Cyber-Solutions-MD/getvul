---
phase: 15
plan: 06
artifact: perf-report
status: pending
---

# Phase 15 — Performance Report (SC #6)

> Committed verification artifact per Plan 15-06 success criterion #6.
> Fill all `(pending)` cells by running `npm run perf:budget` and `npm run perf:lh`
> (Task 3 — human checkpoint). Do NOT paste credentials or the storageState JWT into
> this file (T-15-11 threat model).

**Run date:** (pending — fill when executed)
**Commit:** (pending — fill git rev-parse --short HEAD after run)
**Branch:** main

---

## Bundle Budget (<=250 KB gzipped per route)

Run: `cd frontend && npm run perf:budget`

| Route | First Load JS | Budget (250 KB) | Result |
|-------|--------------|-----------------|--------|
| `/` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/login` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/vulnerabilities` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/assets` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/assets/[id]` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/tickets` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/tickets/[id]` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/tickets/rules` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/cspm` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/connectors` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/users` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dashboard/settings` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |
| `/dev/primitives` | (pending — fill from `npm run perf:budget`) | 250 KB | (pending) |

**Overall budget result:** (pending — PASS / FAIL)

> If any route fails, per D-09 fix it (code-split / trim) and re-run before filling
> this table. A backend-requiring cause may be deferred with a risk note.

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

- [ ] `npm run perf:budget` exit 0 — all routes <= 250 KB
- [ ] `npm run perf:lh` — /login performance >= 90
- [ ] `npm run perf:lh` — /login accessibility >= 90
- [ ] `npm run perf:lh` — /dashboard performance >= 90
- [ ] `npm run perf:lh` — /dashboard accessibility >= 90
- [ ] No `(pending)` cells remain in this report
- [ ] No credentials or JWT pasted into this file

**Sign-off by:** (pending)
**Date:** (pending)
