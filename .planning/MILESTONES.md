# Milestones — GetVul

A historical log of shipped milestones. Full per-milestone detail lives in `.planning/milestones/`.

---

## v2.2 Deferred UI Features — ✅ SHIPPED 2026-07-22

**Phases:** 16–22 (7 phases, 23 plans) · **Timeline:** 2026-07-15 → 2026-07-22 · **Audit:** `passed` (22/22 UX-D requirements, 9/9 integration seams, 5/5 flows)

Finished the four features deferred out of v2.0 as net-new work, each holding the phase-15 quality gate (axe WCAG 2.1 AA in **both** themes, reduced-motion, ≤250 KB First-Load JS/route) and the `sketch-findings-getvul` design contract. Phases 16–19 shipped the features; the v2.2 audit (2026-07-20) then found three verification gaps, which Phases 20–22 closed.

**Key accomplishments:**
1. **Light theme completed for real** (Phases 16, 20) — ~20 light-mode token overrides + a working `Theme: Light` toggle; added `--color-severity-high-on-soft` (#9A3412) and `--color-severity-critical-on-soft` (#991B1B), migrated all foreground severity text to the on-soft tokens, and got the blocking axe sweep GREEN across 11 routes in both themes — proven against a live prod build, not merely claimed (closing UX-D-03).
2. **Page transitions via the native View Transitions API** (Phases 17, 21) — pathname-keyed `(authed)/template.tsx` cross-fade, suppressed under `prefers-reduced-motion`, Firefox CSS fallback, 0 KB added; formally verified with a `firefox-transitions` Playwright project and a persisted perceptual human-UAT (UX-D-06).
3. **Tickets kanban board** (Phase 18) — @dnd-kit four-column board (Open / In progress / Completed / Blocked) with pointer + touch + keyboard sensors, optimistic move + rollback, kept off the route bundle via `next/dynamic({ssr:false})` (`/dashboard/tickets` at 167 kB) (UX-D-01).
4. **Add-connector wizard** (Phase 19) — guided four-step flow (provider → credentials → test → confirm) gated on a real connection test, reusing existing endpoints + sentinel-passthrough, inside the ResponsiveDialog/vaul mobile pattern (`/dashboard/connectors` at 156 kB) (UX-D-02).
5. **Test-coverage hardening** (Phase 22) — converted the two audit warnings into live, deterministic e2e assertions: the CR-01 Enter-key-drag guard + WR-02 gated-drop SR wording (which surfaced and fixed two genuine keyboard-a11y defects), and full wizard axe coverage across the Test + Confirm steps in both themes.

**Verification:** every phase shipped live-verified e2e evidence (axe both themes, kanban/wizard specs, VT specs) in its VERIFICATION.md; milestone audit passed with no gaps.

**Archive:** [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md) · [milestones/v2.2-REQUIREMENTS.md](milestones/v2.2-REQUIREMENTS.md) · [milestones/v2.2-MILESTONE-AUDIT.md](milestones/v2.2-MILESTONE-AUDIT.md)

**Tech debt carried forward (all non-blocking):** `18-HUMAN-UAT.md` bookkeeping reconciliation (items now automated in Phase 22), two cosmetic missing SUMMARY `requirements-completed` frontmatter blocks (16/17), one cosmetic dark-mode `/80`-opacity drop in `blocked-toggle.tsx`, advisory code-review warnings across P17/18/19/22 (deferrable to `/gsd-code-review-fix`), and stale Nyquist `VALIDATION.md` flags (documented-stale per project memory; real live e2e coverage shipped per phase). See [BACKLOG.md](BACKLOG.md).

---

## v2.1 Polish & Tech Debt — ✅ SHIPPED 2026-07-15

Closed the non-blocking tech debt carried in [BACKLOG.md](BACKLOG.md) from the v2.0 audit:

- **BL-01** — canonical `/dashboard/*` client-nav hrefs (removed the 308 middleware round-trips). *(PR #22)*
- **BL-02** — pointed the dead `/integrations` middleware redirect at `/dashboard/connectors`. *(PR #22)*
- **BL-03** — descriptive `useDocumentTitle` on assets-detail, cspm, connectors, users, settings. *(PR #22)*
- **BL-04** — reconciled the dark-theme contrast overrides (text-faint AA lift + accent-on-soft text tokens + "Text on -soft fills" rule) into the `sketch-findings-getvul` source of truth (sunset.css / foundation.md / visual-language.md).
- **BL-05** — closed Nyquist validation on phases 9/10/11/14/15: reconciled every VALIDATION.md against the shipped suite, wrote the one genuinely-missing test (Phase 11 `/dev/primitives` route gate), and flipped all five to `nyquist_compliant: true`.

Deferred v2.0 features (Tickets kanban board UX-D-01, full connector wizard UX-D-02, light-theme polish UX-D-03, page transitions UX-D-06) were promoted into **v2.2** (above, shipped 2026-07-22). The Safari glyph human check (BL-06) remains separately scoped (needs a Mac).

---

## v2.0 UI/UX Redesign — ✅ SHIPPED 2026-06-30

**Phases:** 9–15 (7 phases, 49 plans) · **Audit:** `tech_debt` (0 blockers, 48/48 requirements wired)

Rebuilt every authenticated screen against the Wiz-inspired sunset-palette design system as vertical slices (tokens + primitives + page + state patterns + a11y + tests), replacing v1's `!important`-hack light theme and missing primitives.

**Key accomplishments:**
1. Sunset CSS-variable token system + Tailwind rewired to consume it (zero `!important`); persistent app-shell + first primitive set (Phase 9).
2. Action-first dashboard, faceted vulnerabilities with chip-bar + 420px drill panel, and the canonical state primitives (SkeletonTable / EmptyState / PartialFailureBanner / PerSourceStatusStrip / Toast / DrillPanel) consumed verbatim by all later list screens (Phases 10–11).
3. Two-column asset & ticket detail pages (risk ring, owner card, remediation timeline, watcher stack, provider gradient marks); generalized DrillPanel for vuln/ticket/asset/finding (Phases 12–13).
4. CSPM / connectors / users / settings rebuilt; settings moved to sidebar-of-categories (Phase 14).
5. Mobile + a11y + perf quality gate (Phase 15): three-tier responsive nav, vaul bottom sheets, jsx-a11y at error, Playwright route gate, bundle budget, Lighthouse — **green on the production build** (Playwright 28 passed, 15/15 routes ≤250 KB, Lighthouse /login 97/95 + /dashboard 90/95). Mobile table card-view collapse + ~18 D-09 audit-fix defects resolved.

**Verification:** Phase 15 7/7 SC; milestone audit 48/48 wired, all E2E flows working. **Pending (non-blocking):** Safari.app glyph human spot-check.

**Archive:** [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md) · [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md) · [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md)

**Tech debt carried forward:** see [BACKLOG.md](BACKLOG.md).

---

## v1.0 Production Readiness — ✅ SHIPPED (Phase 1 2026-05-09; Phases 2–8 2026-06-30 → 2026-07-14)

All 8 phases complete. Phase 1 (Multi-Replica State) moved OIDC state + the rate limiter to Redis (PROD-01). Phases 2–8 followed: CI gating (triggers on, masks removed, gate enforcing), update-path reconciliation, doc/code parity (CSP/COOP headers, VulnSource enum), encryption-key lifecycle, default-admin hardening, health/observability (split liveness/readiness, JSON logs), and the test-coverage floor (one+ test per connector + rule engine + SLA; full backend suite 271 green).

**Late hardening (2026-07-13/14):** restored the backend CI gate end-to-end — pinned ruff/mypy, fixed the async test-harness (session-scoped event loop) + rate-limit test isolation, and fixed 4+ real bugs surfaced along the way (change-password redirect loop, tenant-settings 500, rate-limiter fail-open-under-burst, Nessus + Intune connector crashes). Also patched frontend dependency vulns (13 → 2, all high resolved). Detail in `.planning/ROADMAP.md` (v1.0 section) and `milestones/v1.0-REQUIREMENTS.md`.
