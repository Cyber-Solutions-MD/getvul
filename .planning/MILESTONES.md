# Milestones — GetVul

A historical log of shipped milestones. Full per-milestone detail lives in `.planning/milestones/`.

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

**Late hardening (2026-07-13/14):** restored the backend CI gate end-to-end — pinned ruff/mypy, fixed the async test-harness (session-scoped event loop) + rate-limit test isolation, and fixed 4+ real bugs surfaced along the way (change-password redirect loop, tenant-settings 500, rate-limiter fail-open-under-burst, Nessus + Intune connector crashes). Also patched frontend dependency vulns (13 → 2, all high resolved). Detail in `.planning/ROADMAP.md` (v1.0 section) and `REQUIREMENTS.md`.

---

## v2.1 Polish & Tech Debt — ✅ SHIPPED (2026-07-15)

Closed the non-blocking tech debt carried in [BACKLOG.md](BACKLOG.md) from the v2.0 audit:
- **BL-01** — canonical `/dashboard/*` client-nav hrefs (removed the 308 middleware round-trips). *(PR #22)*
- **BL-02** — pointed the dead `/integrations` middleware redirect at `/dashboard/connectors`. *(PR #22)*
- **BL-03** — descriptive `useDocumentTitle` on assets-detail, cspm, connectors, users, settings. *(PR #22)*
- **BL-04** — reconciled the dark-theme contrast overrides (text-faint AA lift + accent-on-soft text tokens + "Text on -soft fills" rule) into the `sketch-findings-getvul` source of truth (sunset.css / foundation.md / visual-language.md).

Deferred v2.0 features (Tickets kanban board UX-D-01, full connector wizard UX-D-02, light-theme polish UX-D-03, page transitions UX-D-06), per-phase Nyquist validation (BL-05), and the Safari glyph human check (BL-06) remain separately scoped.
