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

## v1.0 Production Readiness — 🚧 PARTIAL (Phase 1 shipped 2026-05-09; Phases 2–8 deferred)

Phase 1 (Multi-Replica State) moved OIDC state + the rate limiter from in-process dicts to Redis (PROD-01). Phases 2–8 (CI gating, update-path reconciliation, doc/code parity, encryption-key lifecycle, default-admin hardening, health/observability, test-coverage floor) were parked while v2.0 took precedence and remain the candidate for a future **v1.1** milestone. Detail in `.planning/ROADMAP.md` (v1.0 section) and `REQUIREMENTS.md`.
