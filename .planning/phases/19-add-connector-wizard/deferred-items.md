# Phase 19 — Deferred Items (out of scope, discovered during 19-04 gate run)

## 1. Pre-existing light-theme axe failure on `/dashboard/vulnerabilities` (unrelated to the wizard)

- **Discovered during:** 19-04 Task 2, full-gate run (`npm run test:e2e -- a11y-routes connector-wizard-a11y`)
- **Failure:** `e2e/a11y-routes.spec.ts` "WCAG 2.1 AA axe sweep — light theme (blocking)" fails on
  `/dashboard/vulnerabilities`: `color-contrast` (serious), 5 nodes — the severity-`High` badge glyph/label
  (`text-severity-high`, `#ea580c` on `#f7f2ea`, contrast 3.19, needs 4.5:1).
- **Scope check:** `/dashboard/vulnerabilities` and its severity styling were last touched in Phase 11
  (`8e9ff78 feat(11-06)`, v2.0 era) — zero files in that route were touched by any Phase 19 wave
  (19-00..19-04 only touch `connectors/`, `wizard/`, `responsive-dialog.tsx`, and the connectors page).
  This predates the wizard entirely.
- **Verified NOT a wizard/connectors regression:** isolated `/dashboard/connectors` (closed grid) in
  light theme via an ad-hoc diagnostic run — 0 critical/serious violations. The shared
  `a11y-routes.spec.ts` light-theme test iterates `STATIC_ROUTES` in array order and throws on the
  *first* failing route (`/dashboard/vulnerabilities`, which precedes `/dashboard/connectors` in the
  array), so the shared test run never reaches connectors to independently confirm it — the isolated
  diagnostic closes that gap for the purposes of this phase's gate evidence.
- **Not fixed here per SCOPE BOUNDARY:** out-of-scope pre-existing issue in a route this phase does not
  touch. Also consistent with project memory ("Nyquist validation state" / v2.0 closeout notes) —
  light-theme WCAG was the explicitly-deferred UX-D-03 polish pass; this is exactly the kind of gap
  that pass was meant to catch, now surfaced because Phase 19's gate is the first time the light-theme
  e2e sweep was actually run end-to-end against a live stack in this session.
- **Recommendation:** file as a UX-D-03 (or backlog) follow-up: fix `text-severity-high` orange to meet
  4.5:1 in light theme (same class of issue as the 3 dark-theme contrast overrides logged in STATE.md's
  "v2.0 Closeout Notes").
