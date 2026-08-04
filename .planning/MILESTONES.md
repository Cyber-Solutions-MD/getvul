# Milestones — GetVul

A historical log of shipped milestones. Full per-milestone detail lives in `.planning/milestones/`.

---

## v3.0 AI-Assisted Triage ("Triage Copilot") — ✅ SHIPPED 2026-08-04

**Phases:** 23–29 (7 phases, 45 plans) · **Timeline:** 2026-07-27 → 2026-08-04 (~8 days) · **Audit:** `tech_debt` (21/21 requirements satisfied, 0 broken/0 orphaned/0 missing integration seams, 11/11 flows wired) · **Closeout:** override_closeout (accepted live-verification debt — see Deferred Items in STATE.md)

Added a BYOK (bring-your-own-key, tenant-supplied Anthropic key only) LLM-assistance layer — grounded in the tenant's own correlated vuln data, guardrailed against prompt injection / PII leakage / cost blowup, and gated by evals — so a triage analyst gets help *deciding and acting*, not just *seeing*. The deterministic risk score stays authoritative; AI explains and augments it, never replaces it. The hard privacy guarantee held end-to-end: no GetVul-owned/shared/fallback key, no proxied inference, tenant-scoped cache only, features inert until the tenant configures their own key.

**Key accomplishments:**
1. **AI foundation with the privacy guarantee intact** (Phase 24) — tenant-admin BYOK key config (encrypted via the Fernet/`ConnectorConfig` pattern), a buffer-validate-replay SSE engine streaming grounded, two-tier-cited "Explain this vuln" summaries through nginx, and the full reusable guardrail scaffold (untrusted-content-as-data, schema validation, tenant-scoped cache, fail-closed cost gate, audit) — shipped together at minimum blast radius, then reused unmodified by every later phase.
2. **Grounded remediation + prioritization** (Phases 25–26) — asset-aware remediation guidance that cites the scanner's own solution text or refuses rather than inventing (cite-or-refuse + dangerous-command denylist), and a "what to fix first and why" narrative that augments — never replaces — the deterministic score, pre-generated in bulk via the Message Batches API (`asyncio.create_task`, never stalling a sync tick).
3. **Ticket auto-drafting** (Phase 27) — AI-drafted title/description/remediation/asset-context pre-fills the existing Jira/Asana create flow; a human click always creates the ticket (never auto-submitted).
4. **A real CI-enforced quality gate** (Phase 28) — DeepEval golden-set evals + a promptfoo prompt-injection red-team (17 payloads × 5 capabilities = 85 cases) as required status checks, a fail-closed per-tenant cost circuit breaker, and an admin AI usage/cost/settings pane.
5. **Ingestion reliability precursor** (Phase 23) — fixed the silently-broken Wiz + Rapid7 sync bugs, added HTTP-layer integration tests for all 6 scanners (the gap that let them ship), wired Jira ticket-create + finished GitHub ticketing, and surfaced per-connector sync health/last-error.
6. **Auth hardening** (Phase 29, backlog-promoted WR-02) — replaced the ad-hoc default-credential rejection on the forced-rotation endpoint with a real complexity + password-history + similarity/edit-distance policy, closing the Phase 06 `Admin1234!` near-variant residual.

**Verification:** all 7 phases verified `passed`; the integration checker traced 20+ cross-phase export/import chains and re-ran the AI backend suite (24 test files) + the 6-connector HTTP-layer suite (0 broken / 0 orphaned / 0 missing).

**Archive:** [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md) · [milestones/v3.0-REQUIREMENTS.md](milestones/v3.0-REQUIREMENTS.md) · [milestones/v3.0-MILESTONE-AUDIT.md](milestones/v3.0-MILESTONE-AUDIT.md)

**Tech debt carried forward (all accepted, non-blocking — see STATE.md Deferred Items + v3.0-MILESTONE-AUDIT.md):** Category A — live-Anthropic-key / live-browser verification waived on-trust at the tracer gates for Phases 24–27 (closeable via `/gsd-verify-work <N>`); Category B — Phase 28 hand-authored golden fixtures + 3 external-infra eval-gate overrides; **Category C (actionable) — the pre-existing `backend` CI job lacks `ENCRYPTION_KEY` and will fail 5 Phase 24–27 test files against a synced origin (one-line fix logged in Phase 28 deferred-items.md)**; Category D — carried Phase 23 ticketing WARNINGs (duplicate `/sync-status` route, unvalidated `TicketRuleAction.provider`); plus Nyquist VALIDATION.md doc reconciliation for phases 24–27/29 (documented-stale per project memory, real suites green). AINL-01 (natural-language query) deferred to v3.1.

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
