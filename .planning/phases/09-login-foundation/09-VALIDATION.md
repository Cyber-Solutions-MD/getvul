---
phase: 9
slug: login-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth: `09-RESEARCH.md` § Validation Architecture (lines 1177–1226).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1 + @testing-library/react 10 + vitest-axe 0.1 (jsdom env) — Wave 0 installs |
| **Config file** | `frontend/vitest.config.mts` (NEW — does not exist) |
| **Setup file** | `frontend/vitest.setup.ts` (NEW — RTL matchers + axe install) |
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

> Concrete task IDs are assigned by the planner. Rows below map each phase requirement / success criterion to its verification approach. The planner MUST attach the matching command to each task's `<automated>` block in PLAN.md.

| Req / Criterion | Behavior | Wave (planned) | Test Type | Automated Command | File Exists | Status |
|-----------------|----------|----------------|-----------|-------------------|-------------|--------|
| UX-01-01 | `/login` renders split-screen at 1280px (mesh left, form right) | 4 | manual smoke + screenshot | `npm run dev` → `localhost:3000/login` at 1280px | ❌ W5 manual | ⬜ pending |
| UX-01-01 (mobile) | `/login` collapses to vertical stack at 360px | 4 | manual smoke | DevTools device toolbar → iPhone SE 360px | ❌ W5 manual | ⬜ pending |
| UX-01-02 | SSO buttons render above email form with divider | 4 | unit (DOM order) | `vitest src/app/login/page.test.tsx` | ❌ W0 / W4 | ⬜ pending |
| UX-01-03 | Gradient CTA shows loading text on submit | 1 | unit (`loading` + `loadingText`) | `vitest src/components/ui/button.test.tsx` | ❌ W1 | ⬜ pending |
| UX-01-04 | `forgot` / `reset` modes hide SSO row | 4 | unit (mode switch) | `vitest src/app/login/page.test.tsx` | ❌ W4 | ⬜ pending |
| UX-01-04 (font swap) | Inter + JetBrains Mono load with `display: swap` | 0 / 5 | manual + grep | `grep -E "display.*swap" frontend/.next/static/css/*.css` after `npm run build` | ❌ W0 / W5 | ⬜ pending |
| UX-01-05 | Form-level errors use `bg-danger-soft` + `border-danger` | 4 | unit (login.test) | `vitest src/app/login/page.test.tsx` — assert ErrorAlert classes | ❌ W4 | ⬜ pending |
| UX-F-01 | Sunset CSS variables resolve on `/login` | 0 | smoke (DOM check) | `vitest` — `getComputedStyle(document.body).getPropertyValue('--color-bg')` returns `#0E0B1A` | ❌ W0 | ⬜ pending |
| UX-F-02 | `!important` count = 0 (modulo reduced-motion media block) | 0 / 5 | grep | See Pitfall 1 in 09-RESEARCH.md — awk-scoped grep that excludes reduced-motion block | ❌ W0 / W5 | ⬜ pending |
| UX-F-02 (theme swap) | `data-theme="light"` flips body bg | 0 | unit | `vitest` — toggle attr, assert different computed `--color-bg` | ❌ W0 | ⬜ pending |
| UX-F-03 | Shell renders sidebar + topbar | 3 | unit | `vitest src/components/shell/app-shell.test.tsx` (NEW) | ❌ W3 | ⬜ pending |
| UX-F-03 (active nav) | Active nav matches `usePathname` prefix | 3 | unit | mock `usePathname`, assert active class | ❌ W3 | ⬜ pending |
| UX-F-04 (Button) | All states + no axe violations | 1 | unit + axe | `vitest src/components/ui/button.test.tsx` | ❌ W1 | ⬜ pending |
| UX-F-04 (Input) | All states + password eye-toggle | 1 | unit + axe | `vitest src/components/ui/input.test.tsx` | ❌ W1 | ⬜ pending |
| UX-F-04 (SsoButton) | Both providers + a11y | 1 | unit + axe | `vitest src/components/ui/sso-button.test.tsx` | ❌ W1 | ⬜ pending |
| UX-F-04 (GradientText) | Gradient styles applied | 1 | unit | `vitest src/components/ui/gradient-text.test.tsx` | ❌ W1 | ⬜ pending |
| Phase 9 §5 (login flow) | Form submits and routes to `/dashboard` | 5 | manual smoke | `npm run dev` + valid credentials | ❌ W5 manual | ⬜ pending |
| Phase 9 §6 (shell) | `/dashboard` renders inside `(authed)` shell post-login | 5 | manual smoke | login → land on `/dashboard`, observe sidebar | ❌ W5 manual | ⬜ pending |
| `?next=` preservation | `/login?next=/dashboard/vulnerabilities` lands at target after login | 5 | manual smoke | unauthed URL → log in → verify landing | ❌ W5 manual | ⬜ pending |
| Open-redirect mitigation | `/login?next=//evil.com` lands at `/dashboard` (not evil.com) | 4 | unit | `vitest src/app/login/page.test.tsx` — sanitization function | ❌ W4 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.mts` — Vitest entry config (NEW)
- [ ] `frontend/vitest.setup.ts` — RTL `@testing-library/jest-dom` + `vitest-axe` matcher install (NEW)
- [ ] `frontend/package.json` — add `"test": "vitest"` script (NEW; doesn't exist)
- [ ] Dev-dep install: `npm i -D vitest @vitejs/plugin-react vite-tsconfig-paths jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vitest-axe`
- [ ] Smoke test fixture: at least one passing test before primitives land (so a green baseline exists)

> CI integration is **out of scope** for Phase 9 (CI gating is PROD-02, deferred). Adding a runnable `test` script for humans + future CI is sufficient here.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Split-screen renders correctly at 1280px | UX-01-01 | Visual fidelity vs sketch — automated rendering tests can't confirm "looks like the sketch" | `npm run dev` → open `/login` at 1280px → side-by-side with `.claude/skills/sketch-findings-getvul/sources/001-login-sunset/index.html` |
| Mobile collapse doesn't horizontally-scroll at 360px | UX-01-01 | Layout regression check before Phase 15 ships real mobile UX | DevTools device toolbar → iPhone SE → confirm no horizontal scrollbar on `/login` and `/dashboard` |
| Inter + JetBrains Mono load without FOIT | UX-01-04 | Network-panel visual check; automated grep confirms `display:swap` but not zero FOIT on cold paint | Disable cache → reload `/login` → Network panel shows fonts load in `<latest>` not `block` |
| End-to-end login → dashboard flow | Phase 9 §5 | Backend `/auth/login` is a real network call; mocking misses CORS + cookie + redirect | Seed admin creds via `install.sh` → POST → land on `/dashboard` |
| `?next=` preservation through SSO callback | Phase 9 §5 + D-50 | SSO callback redirects involve browser navigation; e2e-only territory | Unauthed → open `/login?next=/dashboard/tickets` → SSO → land on `/dashboard/tickets` |
| Theme toggle persists across reload | D-38 + D-13 | `localStorage.theme` write-then-read across page boundaries | User chip → Theme: Light → reload → still light (no flash) |
| Reduced-motion honored on `/login` | D-12 + UX-07-04 spirit | OS-level `prefers-reduced-motion` requires real OS setting | macOS System Settings → Accessibility → Reduce motion → reload `/login` → gradient mesh static |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify command OR map to a Manual row above
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING infrastructure references
- [ ] No watch-mode flags in any task command
- [ ] Per-task feedback latency < 30s; per-wave < 90s
- [ ] `nyquist_compliant: true` set in frontmatter after planner completes

**Approval:** pending
