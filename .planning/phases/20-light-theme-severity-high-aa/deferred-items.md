# Phase 20 — Deferred Items (out of scope, discovered during 20-03 gate run)

## 1. `severity-critical`-on-soft has no AA-safe text token (blocks full light-theme green) — RESOLVED (Plan 20-04)

**RESOLVED in Plan 20-04.** `--color-severity-critical-on-soft` (light `#991B1B` / dark `#F87171` no-op) was
added to `globals.css` + reconciled into the design skill (`e9d94b9`), all 27 FOREGROUND
`text-severity-critical` consumer sites were migrated to it (`d021a81`), 8 affected unit tests were
updated (`ab78037`), and the live prod-build axe sweep re-run from this exact plan printed
`AXE_BOTH_THEMES_GREEN` — both the dark and light blocking describes pass end-to-end across all 11
routes, including the previously-failing `/dashboard/tickets/<id>` Blocked badge. See
`20-04-SUMMARY.md` for the full raw evidence. UX-D-03-05 is now satisfied.


- **Discovered during:** 20-03 Task 2, live prod-build axe sweep (`npx playwright test
  --config=e2e/playwright.config.ts a11y-routes`).
- **Failure:** `e2e/a11y-routes.spec.ts` "WCAG 2.1 AA axe sweep — light theme (blocking)" fails on
  `/dashboard/tickets/<id>`: `color-contrast` (serious), 2 nodes — the "Blocked" status badge
  (`text-severity-critical` `#dc2626` on `bg-severity-critical/10` over `bg-surface-2` `#f7f2ea`,
  measured contrast **4.33:1**, needs **4.5:1**). Both flagged nodes are the same badge rendered twice
  in the ticket-detail DOM (header pill + a second instance in the page body).
- **Scope check:** Phase 20's mandate (20-01/20-02) is `--color-severity-high-on-soft` specifically —
  a token that already exists (`#9A3412` light / `#FB923C` dark). No `--color-severity-critical-on-soft`
  token exists anywhere in `globals.css` or the `sketch-findings-getvul` design-system skill
  (`references/foundation.md` documents on-soft variants for violet/pink/amber/severity-high only).
  Picking a value freehand is explicitly forbidden by `CLAUDE.md` ("Don't pick hex colors freehand —
  use the CSS variables from `foundation.md`"), and defining a *new* token is architecturally identical
  in scope to Plan 20-01 (a dedicated color-decision + contrast-validation pass), not a "missed node"
  swap.
- **Blast radius, if a follow-up phase migrates `severity-critical` the same way 20-01/20-02 migrated
  `severity-high`:** at least 12 consumer files use the `text-severity-critical` + `bg-severity-critical/10`
  soft-tint pairing and would need the same foreground-only `text-` swap:
  `connectors/connector-form.tsx`, `connectors/sync-status-pill.tsx`,
  `connectors/wizard/confirm-step.tsx`, `tickets/status-pill.tsx`, `tickets/kanban-reason-prompt.tsx`,
  `tickets/blocked-toggle.tsx` (x2 sites), `tickets/ticket-bulk-bar.tsx` (x2 sites),
  `tickets/kanban-column.tsx`, `tickets/sla-pill.tsx`, `users/directory-table.tsx`.
- **Not fixed here per SCOPE BOUNDARY + CLAUDE.md:** this is a new design-token decision requiring the
  same dedicated-plan process Phase 20-01 used for severity-high (pick + validate a darker same-hue
  red, e.g. red-800, against every light surface it can render on, then reconcile into
  `sketch-findings-getvul`). Improvising a value inline in this evidence-gathering plan would violate
  both the Scope Boundary (unrelated to this plan's declared severity-high files) and CLAUDE.md's
  explicit "don't pick hex colors freehand" rule.
- **Recommendation:** open a new gap-closure phase (severity-critical-on-soft), mirroring the 20-01
  (token) + 20-02 (migration) shape, then re-run this exact live gate. Until that lands, the milestone
  headline promise ("WCAG AA in light mode on every authed route") is NOT fully met — the `/dashboard/
  tickets/<id>` route specifically fails on the Blocked-status badge.

## 2. Base accent `text-violet` on plain/soft light surfaces — 4 sites fixed inline, confirmed no others remain

- **Discovered during:** the same 20-03 live sweep, in 2 stages (first on `/dashboard/assets/<id>`,
  then again on `/dashboard/tickets/<id>` after the first fix landed and the sweep advanced further).
- **Root cause:** `--color-violet` (`#A78BFA`) has no light-mode override in `sunset.css` (only
  `--color-violet-on-soft` does, `#5B21B6` light / `#C4B5FD` dark) — this is the exact "base accent text
  on *plain* (non-soft) backgrounds" backlog class already flagged as a candidate in `PROJECT.md`
  ("not flagged by the sweep" — until this run, once severity-high stopped short-circuiting the sweep
  before reaching these routes).
- **Fixed inline (Rule 1, existing-token swap, no freehand hex):** `owner-card.tsx` (Reassign button),
  `ticket-asset-card.tsx` ("View asset" link), `tickets/[id]/page.tsx` ("Back to tickets" 404 link),
  `cspm/finding-drill-content.tsx` ("View remediation" link) — all swapped `text-violet` →
  `text-[var(--color-violet-on-soft)]`, an already-defined, already-skill-documented token. Commit
  `2988992`. 723/723 unit tests green, tsc clean, 0 KB bundle delta.
- **Confirmed no further live sites:** exhaustive `grep -rE '\btext-violet\b' src/` after the fixes
  shows only (a) a native `<input type=checkbox>` `text-violet` accent-color (not text content, not an
  axe color-contrast target), (b) `hover:text-violet`/`hover:text-pink`/`hover:text-amber` pseudo-states
  (base rest-state color is `text-text-muted`/`text-text-faint`, not swept by a static axe pass), and
  (c) a `dev/primitives` showcase route not in `STATIC_ROUTES`. No action needed on these.
