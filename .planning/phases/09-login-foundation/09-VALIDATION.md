---
phase: 9
slug: login-foundation
status: planned
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
updated: 2026-05-12
plans:
  - 09-01-PLAN.md  # Wave 0 — foundation (sunset.css, globals.css, tailwind, next/font, theme.tsx, vitest stack)
  - 09-02-PLAN.md  # Wave 1 — primitives (shadcn init + Button/Input/Form/DropdownMenu + SsoButton + GradientText + /dev/primitives)
  - 09-03-PLAN.md  # Wave 2 — v1 sweep + (authed) route-group migration
  - 09-04-PLAN.md  # Wave 3 — shell scaffold (AppShell + Sidebar + Topbar + UserChip)
  - 09-05-PLAN.md  # Wave 4 — /login full rewrite + ?next= sanitizer + middleware
  - 09-06-PLAN.md  # Wave 5 — verification + manual smoke
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth: `09-RESEARCH.md` § Validation Architecture (lines 1177–1226).
> Plan IDs assigned by the planner after 09-01..09-06 PLAN.md files were written.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1 + @testing-library/react 10 + vitest-axe 0.1 (jsdom env) — installed by 09-01 Task 3 |
| **Config file** | `frontend/vitest.config.mts` (NEW — created by 09-01 Task 3) |
| **Setup file** | `frontend/vitest.setup.ts` (NEW — RTL matchers + vitest-axe install) |
| **Quick run command** | `cd frontend && npm test -- --run --reporter=dot` |
| **Full suite command** | `cd frontend && npm test -- --run && npm run lint && npm run build` |
| **Estimated runtime** | ~30s quick (primitives only) · ~90s full (incl. lint + Next build) |

---

## Sampling Rate

- **After every task commit:** `cd frontend && npm test -- --run --reporter=dot` (≤30s)
- **After every plan wave:** Full suite — `npm test -- --run && npm run lint && npm run build`
- **Before `/gsd-verify-work`:** Full suite green + manual smoke checklist (rows marked Manual below)
- **Max feedback latency:** 30 seconds per-task; 90 seconds per-wave

---

## Per-Task Verification Map

> Concrete plan + task IDs assigned. The corresponding `<automated>` blocks in each PLAN.md
> contain the matching commands verbatim.

| Req / Criterion | Behavior | Plan / Task | Test Type | Automated Command | Status |
|-----------------|----------|-------------|-----------|-------------------|--------|
| UX-01-01 | `/login` renders split-screen at 1280px (mesh left, form right) | 09-05 Task 2 → 09-06 Task 2 | manual smoke + screenshot | `npm run dev` → `localhost:3000/login` at 1280px | ⬜ pending |
| UX-01-01 (mobile) | `/login` collapses to vertical stack at 360px | 09-05 Task 2 → 09-06 Task 2 | manual smoke | DevTools device toolbar → iPhone SE 360px | ⬜ pending |
| UX-01-02 | SSO buttons render above email form with divider; hidden on forgot/reset | 09-05 Task 3 | unit (DOM order + mode switch) | `vitest src/app/login/page.test.tsx --run` | ⬜ pending |
| UX-01-03 | Gradient CTA shows loading text on submit | 09-02 Task 2 | unit (`loading` + `loadingText`) | `vitest src/components/ui/button.test.tsx --run` | ⬜ pending |
| UX-01-04 | `forgot` / `reset` modes hide SSO row | 09-05 Task 3 | unit (mode switch) | `vitest src/app/login/page.test.tsx --run` | ⬜ pending |
| UX-01-04 (font swap) | Inter + JetBrains Mono load with `display: swap` | 09-01 Task 2 → 09-06 Task 1 | manual + grep | `grep -E "display.*swap" frontend/.next/static/css/*.css` after `npm run build` | ⬜ pending |
| UX-01-05 | Form-level errors use `bg-danger-soft` + `border-danger` | 09-05 Task 3 | unit (login.test) | `vitest src/app/login/page.test.tsx --run` — assert ErrorAlert classes | ⬜ pending |
| UX-F-01 | Sunset CSS variables resolve and Inter+JetBrains Mono load via next/font | 09-01 Task 3 → 09-06 Task 1 | smoke (DOM check + grep) | `vitest src/__tests__/foundation.test.ts --run` + cold-paint manual | ⬜ pending |
| UX-F-02 | `!important` count = 0 (modulo reduced-motion media block) | 09-01 Task 1 → 09-06 Task 1 | grep | TOTAL=`grep -c '!important' globals.css`; EXEMPT=`awk '/@media (prefers-reduced-motion/,/^}$/' globals.css \| grep -c '!important'`; test $((TOTAL-EXEMPT)) -eq 0 | ⬜ pending |
| UX-F-02 (theme swap) | `data-theme="light"` flips body bg | 09-01 Task 3 | unit | `vitest src/__tests__/foundation.test.ts --run` — toggle attr, assert different `--color-bg` | ⬜ pending |
| UX-F-03 | Shell renders sidebar + topbar | 09-04 Task 2 | unit | `vitest src/components/shell/app-shell.test.tsx --run` | ⬜ pending |
| UX-F-03 (active nav) | Active nav matches `usePathname` exact/prefix per D-35 | 09-04 Task 2 | unit (mock usePathname) | `vitest src/components/shell/sidebar.test.tsx --run` | ⬜ pending |
| UX-F-04 (Button) | All states + no axe violations | 09-02 Task 2 | unit + axe | `vitest src/components/ui/button.test.tsx --run` | ⬜ pending |
| UX-F-04 (Input) | All states + password eye-toggle | 09-02 Task 2 | unit + axe | `vitest src/components/ui/input.test.tsx --run` | ⬜ pending |
| UX-F-04 (SsoButton) | Both providers + a11y | 09-02 Task 2 | unit + axe | `vitest src/components/ui/sso-button.test.tsx --run` | ⬜ pending |
| UX-F-04 (GradientText) | Gradient styles applied | 09-02 Task 2 | unit | `vitest src/components/ui/gradient-text.test.tsx --run` | ⬜ pending |
| Phase 9 §5 (login flow) | Form submits and routes to `/dashboard` | 09-06 Task 2 | manual smoke | `npm run dev` + valid credentials | ⬜ pending |
| Phase 9 §6 (shell) | `/dashboard` renders inside `(authed)` shell post-login | 09-06 Task 2 | manual smoke | login → land on `/dashboard`, observe sidebar | ⬜ pending |
| `?next=` preservation | `/login?next=/dashboard/vulnerabilities` lands at target after login | 09-06 Task 2 | manual smoke | unauthed URL → log in → verify landing | ⬜ pending |
| Open-redirect mitigation | `/login?next=//evil.com` lands at `/dashboard` (not evil.com) | 09-05 Task 3 → 09-06 Task 2 | unit + manual | `vitest src/app/login/page.test.tsx --run` — `sanitizeNext` cases | ⬜ pending |
| autoComplete attrs (D-48) | login/forgot/reset use correct credential autoFill hints | 09-05 Task 3 | unit | `vitest src/app/login/page.test.tsx --run` — autocomplete assertions | ⬜ pending |
| Anti-enumeration forgot copy (Pitfall 9) | Forgot-password always shows generic confirmation | 09-05 Task 3 | unit | `vitest src/app/login/page.test.tsx --run` — generic copy assertion | ⬜ pending |
| Phase gate | Test + lint + build + tsc all green | 09-06 Task 1 | composite | `npm test -- --run && npm run lint && npm run build && npx tsc --noEmit` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (delivered by 09-01)

- [ ] `frontend/vitest.config.mts` — Vitest entry config (NEW) — 09-01 Task 3
- [ ] `frontend/vitest.setup.ts` — RTL `@testing-library/jest-dom` + `vitest-axe` matcher install (NEW) — 09-01 Task 3
- [ ] `frontend/package.json` — add `"test": "vitest"` script (NEW; doesn't exist) — 09-01 Task 3
- [ ] Dev-dep install: `npm i -D vitest @vitejs/plugin-react vite-tsconfig-paths jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vitest-axe class-variance-authority` — 09-01 Task 3
- [ ] Smoke test fixture: `frontend/src/__tests__/foundation.test.ts` baseline before primitives land — 09-01 Task 3

> CI integration is **out of scope** for Phase 9 (CI gating is PROD-02, deferred). Adding a runnable `test` script for humans + future CI is sufficient here.

---

## Manual-Only Verifications

| Behavior | Requirement | Plan / Task | Why Manual | Test Instructions |
|----------|-------------|-------------|------------|-------------------|
| Split-screen renders correctly at 1280px | UX-01-01 | 09-06 Task 2 (row 1) | Visual fidelity vs sketch — automated rendering tests can't confirm "looks like the sketch" | `npm run dev` → open `/login` at 1280px → side-by-side with `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` |
| Mobile collapse doesn't horizontally-scroll at 360px | UX-01-01 | 09-06 Task 2 (row 2) | Layout regression check before Phase 15 ships real mobile UX | DevTools device toolbar → iPhone SE → confirm no horizontal scrollbar on `/login` and `/dashboard` |
| Inter + JetBrains Mono load without FOIT | UX-01-04 | 09-06 Task 2 (row 3) | Network-panel visual check; automated grep confirms `display:swap` but not zero FOIT on cold paint | Disable cache → reload `/login` → Network panel shows fonts load with `display: swap` not `block` |
| End-to-end login → dashboard flow | Phase 9 §5 | 09-06 Task 2 (row 4) | Backend `/auth/login` is a real network call; mocking misses CORS + cookie + redirect | Seed admin creds via `install.sh` → POST → land on `/dashboard` |
| `?next=` preservation | Phase 9 §5 + D-50 | 09-06 Task 2 (row 5) | Browser navigation involves localStorage + middleware; e2e-only territory | Unauthed → open `/login?next=/dashboard/vulnerabilities` → log in → verify landing |
| Open-redirect mitigation (runtime) | Pitfall 10 | 09-06 Task 2 (row 6) | Defense-in-depth — confirm unit-tested sanitizer also defends in real browser | `/login?next=//evil.com` + `/login?next=https://evil.com` → after login lands at `/dashboard` |
| Theme toggle persists across reload | D-38 + D-13 | 09-06 Task 2 (row 7) | `localStorage.getvul_theme` write-then-read across page boundaries + FOUC-free cold paint | User chip → Theme: Light → reload → still light (no flash) |
| Reduced-motion honored on `/login` | D-12 | 09-06 Task 2 (row 8) | OS-level `prefers-reduced-motion` requires real OS setting | macOS System Settings → Accessibility → Reduce motion → reload `/login` → gradient mesh static |
| `/dev/primitives` accessible in dev, 404 in prod | D-31 | 09-06 Task 2 (row 9) | NODE_ENV gate behavior differs between `npm run dev` and `npm run build && npm start` | Visit URL in each mode |
| Forgot password generic-success copy | Pitfall 9 | 09-06 Task 2 (row 10) | Anti-enumeration defense — confirm UI shows generic regardless of backend response in real submit | Enter unregistered email → click Send reset link → see generic copy |
| `?reset=TOKEN` deep-link enters reset mode | D-43 | 09-06 Task 2 (row 11) | Deep-link behavior involves useSearchParams + mode initialization | Visit `/login?reset=test-token-123` → reset mode + token pre-filled |
| Legacy URL redirects | Open Question 2 | 09-06 Task 2 (row 12) | Middleware-driven redirect; 308 status preservation | `/assets` → `/dashboard/assets`; `/tickets/T-001` → `/dashboard/tickets/T-001` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify command OR map to a Manual row above
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING infrastructure references (delivered in 09-01)
- [ ] No watch-mode flags in any task command
- [ ] Per-task feedback latency < 30s; per-wave < 90s
- [ ] `nyquist_compliant: true` set in frontmatter after checker validates (planner does NOT flip — that's plan-check's outcome)

**Approval:** pending checker pass

---

## Plan → Wave → Decision Coverage Matrix

| Plan | Wave | Tasks | Primary Decisions Implemented |
|------|------|-------|-------------------------------|
| 09-01 | 0 | 3 | D-01, D-02, D-03, D-04 (config), D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17, D-20, D-30 (infra) |
| 09-02 | 1 | 3 | D-18, D-19, D-21, D-22, D-23, D-24, D-25, D-26, D-27, D-28, D-29, D-30 (tests), D-31, D-32 |
| 09-03 | 2 | 2 | D-04 (sweep), D-05, D-33, D-34, D-39 |
| 09-04 | 3 | 2 | D-35, D-36, D-37, D-38, D-40, D-41 |
| 09-05 | 4 | 3 | D-42, D-43, D-44, D-45, D-46, D-47, D-48, D-49, D-50, D-51, D-52, D-53 + Pitfalls 8, 9, 10 |
| 09-06 | 5 | 2 | All — verification + sign-off |

**Coverage check:** D-01..D-53 each appear in at least one plan task (no orphans). UX-01-01..05 + UX-F-01..04 each appear in at least one plan's `requirements` frontmatter (9/9 covered).
