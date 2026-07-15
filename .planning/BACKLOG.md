# Backlog — GetVul

Non-blocking tech debt and deferred polish. Items are candidates for a future v2.x UI-polish milestone or to fold into v1.1.

## From the v2.0 milestone audit (2026-06-30)

Source: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status `tech_debt`, 0 blockers). The one user-facing warning (CSPM finding drill had no mobile bottom sheet) was **fixed before v2.0 close** — the items below remain.

- **BL-01 — Legacy-route client navigation.** ✅ **DONE (v2.1, 2026-07-15).** `assets/page.tsx` (`router.push('/assets/${id}')`), the asset & ticket detail breadcrumbs (`href="/assets"`, `href="/tickets"`), and `ticket-asset-card.tsx` navigated via `/assets/*` `/tickets/*`, which 308-redirected (middleware) to the canonical `/dashboard/*` URLs. Fixed: all five call sites now use canonical `/dashboard/...` hrefs directly (tests updated to match). *(UX-04-01/02/05, UX-05-04)*
- **BL-02 — Dead middleware redirect.** ✅ **DONE (v2.1, 2026-07-15).** `middleware.ts` mapped `/integrations` → `/dashboard/integrations`, but the route was renamed to `/dashboard/connectors` and no page existed at the target. Fixed: the entry now points to `/dashboard/connectors`. *(UX-06-02)*
- **BL-03 — Missing descriptive page titles.** ✅ **DONE (v2.1, 2026-07-15).** `useDocumentTitle` was absent from `/dashboard/assets/[id]`, `/cspm`, `/connectors`, `/users`, `/settings` — the browser tab showed the generic "GetVul". Fixed: each page now calls `useDocumentTitle` with a descriptive title (Asset detail / CSPM findings / Connectors / Users / Settings). *(UX-07-03)*
- **BL-04 — Dark-theme contrast DESIGN-SYSTEM GAPs.** ✅ **DONE (v2.1, 2026-07-15).** Phase 15 applied app-layer overrides diverging from the locked/vendored `sunset.css` palette to meet WCAG AA on dark surfaces. Reconciled into the design-system source of truth: `sketch-findings-getvul` `sources/themes/sunset.css` + `foundation.md` now carry `--color-text-faint: #8B84A8` (was #6B6488) and new `--color-{pink,violet,amber}-on-soft` text tokens (#F472B6 / #C4B5FD / #F59E0B); `visual-language.md` gained a locked "Text on -soft fills (AA)" rule. The three app `DESIGN-SYSTEM GAP` comments now reference the reconciled source. The app-layer overrides remain until the vendored `sunset.css` is re-synced (deliberate — the vendored copy is not edited directly). *(UX-F-01/02, UX-07-03)*
- **BL-05 — Nyquist validation PARTIAL on 5 phases.** ✅ **DONE (v2.1, 2026-07-15).** Phases 9, 10, 11, 14, 15 carried `nyquist_compliant: false` — statuses were authored pre-execution and never reconciled against the shipped suite. Gap-analysis (one agent per phase) cross-referenced every Per-Task Map row against the real tests: all automated rows already map to passing tests. The one genuine gap — Phase 11 row `11-07-01` pointed at a never-written `/dev/primitives` test — was closed with a real route-gate test (`src/app/dev/primitives/page.test.tsx`, dev-render + prod-404 DCE gate, 2/2 green). Reconciled all five VALIDATION.md files (statuses → ✅, sparse maps for 14/15 expanded to the shipped checks, per-phase audit trail appended) and flipped `nyquist_compliant: true`. One human-only item stays tracked: Phase 15 Safari glyph legibility = BL-06. (Phases 12, 13 were already compliant.) *(Backend phases 01/03–07 also carry `false` but are out of BL-05 scope.)*
- **BL-06 — Safari.app severity-glyph legibility (HUMAN).** Confirm ■ ▲ ◆ ○ □ render legibly at 14px on real macOS Safari.app DPR (D-02). WebKit-in-Playwright covers presence + axe; only real-DPR human confirmation remains. Record in `.planning/phases/15-*/15-HUMAN-UAT.md` Item 1.

## Deferred design ideas (from v2.0 scope)

- **UX-D-03 — Light-theme visual polish pass.** v2.0 verified the theme toggle + architecture but deferred full per-screen light-mode visual QA (incl. light-theme WCAG contrast). The automated gate audits the shipping dark theme.
- **UX-D-06 — Page-transition motion** (cross-fade between routes) — deferred.
- **UX-D-01 — Tickets Board (kanban) view** — currently a placeholder.
- **UX-D-02 — Full add-connector wizard** — currently a multi-step form placeholder.
