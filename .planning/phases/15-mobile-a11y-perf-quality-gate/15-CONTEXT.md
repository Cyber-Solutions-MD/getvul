# Phase 15: Mobile + a11y + Perf Quality Gate - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

The milestone closer for v2.0 UI/UX Redesign. Take the six already-built screen
surfaces (login, dashboard, vulnerabilities, assets, tickets, and the four
phase-14 screens: cspm, connectors, users, settings) and prove — and where there
are gaps, *build* — that every authenticated screen meets the mobile,
accessibility, and performance bar (UX-07-01..07), so v2.0 is shippable.

This is **mostly verification + a bounded set of net-new pieces**, not new screens:

**Net-new build work (gaps confirmed during scout):**
- Mobile navigation (does not exist today — the sidebar merely *hides* below 1000px
  via D-41; nothing replaces it; the sketch explicitly deferred this pattern)
- Playwright + per-route axe + cross-browser harness (zero E2E exists today)
- `eslint-plugin-jsx-a11y` elevated to `error` (currently transitive at `warn`)
- Bottom-sheet conversion for app modals beyond the existing `DrillPanelMobile`
- Lighthouse + all-route JS-budget scripting

**Verify-only (already shipped in prior phases — do NOT rebuild):**
- Theme toggle + FOUC blocking script (UX-07-05) — `theme.tsx` + `layout.tsx` head bootstrap
- `prefers-reduced-motion` hook (UX-07-04) — exists, ~8 sites; audit for completeness
- Per-route card-view collapse + vaul drill-panel bottom sheets (Phase 11)
- `scripts/check-bundle.mjs` perf-budget enforcer (wired for `/dashboard`; extend to all routes)

Scope anchor: **frontend-only milestone.** No backend changes (per REQUIREMENTS-v2
"Out of Scope"). Backend endpoints v1 already exposes are consumed as-is.
</domain>

<decisions>
## Implementation Decisions

### a11y / cross-browser toolchain
- **D-01:** Adopt **full Playwright** — add `@playwright/test` + `@axe-core/playwright`.
  Config defines three browser projects (Chromium, WebKit, Firefox). One automated
  suite sweeps **every authenticated route × 4 viewport widths (360 / 390 / 768 / 1280)**,
  asserting (a) no horizontal scroll and (b) zero critical/serious axe violations.
  Cross-browser smoke covers `/login` + `/dashboard` + `/vulnerabilities` + one detail
  page across all three engines (satisfies SC #1, #3, #7 literally + gives a durable gate).
- **D-02:** **Safari = WebKit automated gate + manual Safari.app spot-check.** Playwright's
  WebKit project is the automated Safari proxy. PLUS a short manual Safari.app pass on the
  smoke routes, recorded in `15-HUMAN-UAT.md`, specifically confirming the severity glyphs
  (■ ▲ ◆ ○ □) render legibly at 14px on real Safari DPR.
- **D-03:** **axe blocking bar = WCAG 2.1 AA.** Tag axe with `wcag2a`, `wcag2aa`, `wcag21aa`
  as the build-blocking set (zero critical/serious). Also run WCAG 2.2 AA checks (24×24
  touch targets, focus-not-obscured) but surface as **report/warnings only** — the
  "internal target" per UX-07-03's public-vs-internal split.
- **D-04:** Elevate `eslint-plugin-jsx-a11y` to **`error`** level (currently transitive via
  `eslint-config-next` at `warn`). Fix any violations this surfaces.

### Mobile navigation model
- **D-05:** **Three responsive tiers by breakpoint:**
  - `<768px` (phone) → 4-slot **bottom-nav** (Dashboard / Vulnerabilities / Tickets / More)
    with `env(safe-area-inset-bottom)` padding and ≥24×24 touch targets.
  - `768–999px` (tablet) → topbar **hamburger** opens a slide-in **drawer** with the full
    9-item nav.
  - `≥1000px` → existing 220px **sidebar** (D-41 unchanged).
  - 768px chosen to align with Tailwind `md` and the existing card-collapse boundary.
- **D-06:** The bottom-nav **"More"** slot opens a **vaul bottom sheet** listing the remaining
  destinations (Assets, CSPM, Connectors, Users, Settings). Active route uses the
  **gradient-strip active indicator** consistent with the desktop sidebar.
- **D-07:** **All app modals/dialogs convert to vaul bottom sheets on mobile** (matching the
  existing `DrillPanelMobile` treatment). Audit and convert: `ConfirmModal`, the connector
  credential form, reassign-owner, and any settings dialogs — not just drill panels.

### Lighthouse + perf-budget gate
- **D-08:** **Scripted local run + committed report.** An npm script runs Lighthouse CI
  (mobile preset) against `/login` + `/dashboard` (must report ≥90 performance AND ≥90
  accessibility), and `scripts/check-bundle.mjs` is **extended to assert ≤250 KB gzipped
  initial JS across ALL routes** from `next build`. Results committed as the verification
  artifact (`15-PERF-REPORT.md`). No CI infra dependency (repo-wide CI gating is the
  deferred Phase 2). Charts are already route-split — verify, don't re-split.

### Audit-fix scope policy
- **D-09:** **Fix everything the audit surfaces** before the phase closes — no deferral of
  cosmetic or moderate-severity items. The phase ends when the defect list is empty.
  **Only exception:** a defect that genuinely requires a backend change (out of scope for
  this frontend-only milestone) is logged to a v1.x backlog with a risk note rather than
  fixed here.

### Verify-only confirmations (no rebuild)
- **D-10:** **UX-07-05 (theme/FOUC) is verify-only.** `theme.tsx` + the `layout.tsx` head
  bootstrap already read `localStorage('getvul_theme')` and fall back to
  `prefers-color-scheme`. This phase verifies: no white flash on cold `/login` load in
  dark-OS mode, localStorage persistence, and first-visit `prefers-color-scheme` honoring.
- **D-11:** **UX-07-04 (reduced-motion) is an audit, not a build.** The hook exists. This
  phase audits that EVERY motion site (gradient-mesh drift, mount-stagger, pulsing dot)
  honors `prefers-reduced-motion: reduce` (cross-fade only, no stagger, no pulse), adding
  coverage anywhere it's missing.

### Claude's Discretion
- Exact Playwright config structure, test-file organization, and route-enumeration approach.
- Which specific Lighthouse CI package/runner to use.
- How `check-bundle.mjs` is extended to iterate all routes.
- Drawer slide-in animation specifics and bottom-nav icon choices (lucide-react, already a dep).
- Whether existing `vitest-axe` component tests are retained alongside Playwright route tests
  (recommended: keep component-level, add route-level — they're complementary).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 15 section, Success Criteria #1–#7 (the literal bar)
- `.planning/REQUIREMENTS-v2.md` — UX-07-01..07 (full requirement text); "Out of Scope"
  (no v2.x backend change — frontend-only); UX-D-03/UX-D-06 (deferred, see Deferred Ideas)

### Design contract (sketch findings — auto-loaded per CLAUDE.md)
- `.claude/skills/sketch-findings-getvul/references/interaction-patterns.md` — bottom-nav,
  bulk-bar, drill-down panel, chip-bar touch-target sizing
- `.claude/skills/sketch-findings-getvul/references/app-shell.md` — sidebar/topbar chrome;
  D-41 (sidebar hides ≤999px); "hamburger entry point — pattern deferred to mobile sketch"
  (the pattern this phase now builds)
- `.claude/skills/sketch-findings-getvul/references/foundation.md` — motion tokens (4
  cubic-beziers + 4 durations), reduce-motion substitutions, color tokens (incl. light theme)
- `.claude/skills/sketch-findings-getvul/references/visual-language.md` — severity glyphs
  (■ ▲ ◆ ○ □) and their legibility requirements
- `.claude/skills/sketch-findings-getvul/references/state-patterns.md` — loading/empty/error
  (verify present on every route during the audit)

### Existing code to extend / verify (see code_context)
- `frontend/scripts/check-bundle.mjs` — perf-budget enforcer to extend to all routes
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/theme.tsx` + `frontend/src/app/layout.tsx` — theme toggle + FOUC head
  bootstrap (UX-07-05 done; verify-only per D-10).
- `frontend/src/hooks/use-prefers-reduced-motion.ts` — reduced-motion hook (~8 call sites;
  audit completeness per D-11).
- `frontend/src/components/vulnerabilities/drill-panel-mobile.tsx` — the vaul bottom-sheet
  precedent that the "all modals" conversion (D-07) should follow.
- `frontend/scripts/check-bundle.mjs` — `next build`-output JS-budget parser; extend to all
  routes for D-08.
- `frontend/src/app/(authed)/dashboard/dashboard.a11y.test.tsx` — existing `vitest-axe`
  pattern (component-level; Playwright route-level is additive per D-01).
- `vaul` (dep) — bottom sheets; `lucide-react` (dep) — nav icons.

### Established Patterns
- `vitest-axe` is the current a11y test tool (jsdom, component-level). D-01 adds Playwright
  route-level on top; jsdom cannot catch real-layout horizontal-scroll regressions.
- `eslint-config-next` provides `jsx-a11y` transitively at `warn` — D-04 elevates to `error`.
- D-41 responsive rule: sidebar visible ≥1000px, hidden ≤999px (Tailwind arbitrary variant
  `max-[999px]`, not `lg`). New mobile tiers (D-05) plug into this existing boundary.

### Integration Points
- `frontend/src/components/shell/app-shell.tsx` — where the `<768px` bottom-nav and the
  `768–999px` topbar-hamburger→drawer wire in (currently just `Sidebar` + `Topbar` + `main`).
- `frontend/src/components/shell/sidebar.tsx` / `topbar.tsx` — nav source-of-truth (9
  destinations) to mirror into bottom-nav + drawer + "More" sheet.
- `frontend/package.json` scripts — add `playwright test`, `perf:lh`, `perf:budget`.
- ESLint config — elevate `jsx-a11y` to `error`.
</code_context>

<specifics>
## Specific Ideas

- Viewport widths are **exactly 360 / 390 / 768 / 1280** — these are the audited breakpoints,
  not approximations.
- Severity glyphs **■ ▲ ◆ ○ □** must render legibly at **14px and below** — the manual
  Safari.app spot-check (D-02) exists specifically to confirm this on real Safari DPR.
- Bottom-nav slots are fixed: **Dashboard / Vulnerabilities / Tickets / More** (per SC #2).
- The phase's verification report (`15-PERF-REPORT.md`) is a committed artifact, per SC #6.
</specifics>

<deferred>
## Deferred Ideas

- **UX-D-03 — Light-theme visual polish pass:** This phase verifies the theme *toggle* works
  and the architecture supports light mode, but does NOT perform a full per-screen light-mode
  visual QA sweep. That remains the deferred UX-D-03 polish phase.
- **UX-D-06 — Page-transition motion:** cross-fade between routes stays deferred; scope here
  is static-route polish only.
- **Backend-requiring defects:** any audit finding that can only be fixed with a backend
  change is logged to a v1.x backlog with a risk note (per D-09), not fixed in this
  frontend-only milestone.

---

*Phase: 15-mobile-a11y-perf-quality-gate*
*Context gathered: 2026-06-03*
</deferred>
