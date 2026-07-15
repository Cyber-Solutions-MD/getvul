# Backlog — GetVul

Non-blocking tech debt and deferred polish. Items are candidates for a future v2.x UI-polish milestone or to fold into v1.1.

## From the v2.0 milestone audit (2026-06-30)

Source: `.planning/milestones/v2.0-MILESTONE-AUDIT.md` (status `tech_debt`, 0 blockers). The one user-facing warning (CSPM finding drill had no mobile bottom sheet) was **fixed before v2.0 close** — the items below remain.

- **BL-01 — Legacy-route client navigation.** ✅ **DONE (v2.1, 2026-07-15).** `assets/page.tsx` (`router.push('/assets/${id}')`), the asset & ticket detail breadcrumbs (`href="/assets"`, `href="/tickets"`), and `ticket-asset-card.tsx` navigated via `/assets/*` `/tickets/*`, which 308-redirected (middleware) to the canonical `/dashboard/*` URLs. Fixed: all five call sites now use canonical `/dashboard/...` hrefs directly (tests updated to match). *(UX-04-01/02/05, UX-05-04)*
- **BL-02 — Dead middleware redirect.** ✅ **DONE (v2.1, 2026-07-15).** `middleware.ts` mapped `/integrations` → `/dashboard/integrations`, but the route was renamed to `/dashboard/connectors` and no page existed at the target. Fixed: the entry now points to `/dashboard/connectors`. *(UX-06-02)*
- **BL-03 — Missing descriptive page titles.** ✅ **DONE (v2.1, 2026-07-15).** `useDocumentTitle` was absent from `/dashboard/assets/[id]`, `/cspm`, `/connectors`, `/users`, `/settings` — the browser tab showed the generic "GetVul". Fixed: each page now calls `useDocumentTitle` with a descriptive title (Asset detail / CSPM findings / Connectors / Users / Settings). *(UX-07-03)*
- **BL-04 — Dark-theme contrast DESIGN-SYSTEM GAPs.** ✅ **DONE (v2.1, 2026-07-15).** Phase 15 applied app-layer overrides diverging from the locked/vendored `sunset.css` palette to meet WCAG AA on dark surfaces. Reconciled into the design-system source of truth: `sketch-findings-getvul` `sources/themes/sunset.css` + `foundation.md` now carry `--color-text-faint: #8B84A8` (was #6B6488) and new `--color-{pink,violet,amber}-on-soft` text tokens (#F472B6 / #C4B5FD / #F59E0B); `visual-language.md` gained a locked "Text on -soft fills (AA)" rule. The three app `DESIGN-SYSTEM GAP` comments now reference the reconciled source. The app-layer overrides remain until the vendored `sunset.css` is re-synced (deliberate — the vendored copy is not edited directly). *(UX-F-01/02, UX-07-03)*
- **BL-05 — Nyquist validation PARTIAL on 5 phases.** Phases 9, 10, 11, 14, 15 have `VALIDATION.md` with `nyquist_compliant: false` — requirements are functionally verified, but the test-coverage formalization is incomplete. Run `/gsd-validate-phase <N>` per phase to close. (Phases 12, 13 are compliant.)
- **BL-06 — Safari.app severity-glyph legibility (HUMAN).** Confirm ■ ▲ ◆ ○ □ render legibly at 14px on real macOS Safari.app DPR (D-02). WebKit-in-Playwright covers presence + axe; only real-DPR human confirmation remains. Record in `.planning/phases/15-*/15-HUMAN-UAT.md` Item 1.

## Deferred design ideas (from v2.0 scope)

- **UX-D-03 — Light-theme visual polish pass.** v2.0 verified the theme toggle + architecture but deferred full per-screen light-mode visual QA (incl. light-theme WCAG contrast). The automated gate audits the shipping dark theme.
- **UX-D-06 — Page-transition motion** (cross-fade between routes) — deferred.
- **UX-D-01 — Tickets Board (kanban) view** — currently a placeholder.
- **UX-D-02 — Full add-connector wizard** — currently a multi-step form placeholder.
