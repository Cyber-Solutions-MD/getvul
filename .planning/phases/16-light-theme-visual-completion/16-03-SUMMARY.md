---
phase: 16-light-theme-visual-completion
plan: 03
gap_closure: true
status: complete
completed: 2026-07-16
commits:
  - 217dd6e  # Task 1 — --color-info light override (WR-01)
  - 79703fa  # Task 2 — text-amber → --color-amber-on-soft migration (WR-02)
  - 48ffbdb  # Task 3 deviation — EmptyState.Suggestion on-soft + dark on-soft vendoring (WR-03)
requirements:
  - UX-D-03-02
  - UX-D-03-03
  - UX-D-03-04
  - UX-D-03-05
---

# 16-03 Summary — Close Phase-16 verification gaps (WR-01, WR-02) + execute the axe sweep

Closes the two confirmed Phase-16 verification gaps and executes the light+dark axe sweep against a
live production build — the SC#2 process gap the verifier flagged. One additional light-mode
contrast violation surfaced during the sweep (WR-03) and was fixed in the same pass.

## What was built

### Task 1 — `--color-info` light override (WR-01) — `217dd6e`
- `frontend/src/app/globals.css`: added `--color-info: #2563EB` (blue-600) inside the single
  `:root[data-theme="light"]` block (line 38), mirroring the already-present `--color-severity-info`.
  SourcePill google/azure/humaans `text-info` pills now clear ~5.1:1 on cream (was ~2.5:1 at the dark
  `#60A5FA`).
- `.claude/skills/sketch-findings-getvul/sources/themes/sunset.css`: mirrored the light override
  (line 157) so the design-system skill stays the single source of truth.
- `.claude/skills/sketch-findings-getvul/references/foundation.md`: annotated line 48 with the light value.

### Task 2 — amber-on-soft migration (WR-02) — `79703fa`
- `status-pill.tsx`: both `in_progress` and `'in progress'` entries lifted from base `text-amber`
  to `text-[var(--color-amber-on-soft)]` (fills/borders unchanged).
- `profile-pane.tsx`: ANALYST role badge lifted to `text-[var(--color-amber-on-soft)]`.
- `status-pill.test.tsx`: assertion updated to lock the var() migration. The previously-dead
  `--color-amber-on-soft` token is now consumed at all three sites.

### Task 3 — execute the axe sweep + fix the violation it surfaced (WR-03) — `48ffbdb`
The light describe block, run against a live prod build for the first time, surfaced a **new**
serious violation the plan's static scan had not enumerated:

> `/dashboard/connectors` — `EmptyState.Suggestion` (`data-empty-suggestion`, 4 nodes) rendered
> `text-violet` (`#A78BFA`) on `bg-violet-soft` (`#EFEAFE`) = **2.31:1** on cream (< AA 4.5).

Same class of defect as WR-02 (base accent text on a `-soft` fill). Fixed at the shared component:
- `frontend/src/components/states/empty-state.tsx`: `EmptyState.Suggestion` now consumes
  `text-[var(--color-violet-on-soft)]` (one fix covers every empty state).
- `frontend/src/components/states/empty-state.test.tsx`: assertion updated to lock the migration.

**Root-cause finding (deviation rationale):** the app's *vendored* `frontend/src/styles/sunset.css`
never carried the dark `--color-*-on-soft` tokens that the design-system skill's authoritative copy
defines (skill dark `:root`: violet `#C4B5FD`, pink `#F472B6`, amber `#F59E0B`). The app defined the
on-soft tokens **only** in the light block, so in **dark mode** every `text-[var(--color-*-on-soft)]`
consumer (status-pill open + in_progress, profile-pane ADMIN + ANALYST, and now
EmptyState.Suggestion) resolved an **undefined** variable and silently fell back to inherited text.
This means the plan's "dark is a byte-identical no-op" claim for the WR-02 amber migration did **not**
actually hold in the app. Fix: mirror the skill's authoritative dark on-soft values into the
`:root[data-theme="dark"]` block in `globals.css` (co-located with the existing Phase-15
`--color-text-faint` dark a11y override; the vendored sunset.css is marked do-not-edit / re-vendor).
Amber dark = `#F59E0B` is byte-identical to the old `text-amber`, so WR-02 is now a **true** dark
no-op as documented; violet/pink now resolve to their intended dark accents instead of inherited text.

## Verification evidence

### Axe sweep — live prod build, run 2026-07-16 10:10 (AFTER fix commits `217dd6e`/`79703fa`/`48ffbdb`)

Command (from `frontend/`, live backend via `docker compose up -d postgres redis backend`, admin
`admin@getvul.local` seeded, prod build served on `:3000`):
```
npx playwright test e2e/a11y-routes.spec.ts --project=chromium-a11y --config=e2e/playwright.config.ts
```

Result — **all 5 tests passed**, both blocking axe describe blocks GREEN:
```
✓ [setup] authenticate
✓ WCAG 2.1 AA axe sweep — all routes (blocking)              (dark)  — 0 critical/serious on every route
✓ WCAG 2.1 AA axe sweep — light theme (blocking)            (light) — 0 critical/serious on every route
✓ Bottom-nav visibility + More-sheet at 360px (visible)
✓ Bottom-nav visibility + More-sheet at 360px (More sheet)
5 passed (9.2s)
```
- **"WCAG 2.1 AA axe sweep — all routes (blocking)" (dark): 0 critical/serious on every route.**
- **"WCAG 2.1 AA axe sweep — light theme (blocking)" (light): 0 critical/serious on every route.**
- Note: the spec logged "no detail routes discovered — sweeping static routes only" (both blocks) —
  detail routes require seeded entity IDs to enumerate; the static route set was swept in full. This
  is the spec's designed behavior, unchanged by this plan.

The FIRST run (before WR-03 fix) failed the light block on `/dashboard/connectors` with the
`EmptyState.Suggestion` 2.31:1 violation, proving the sweep genuinely exercises light-mode contrast
(it is not a no-op) — the process gap the verifier flagged is now closed with a real, dated run.

### Other checks
- `npx vitest run src/components/states/empty-state.test.tsx` → 9/9 green.
- `npx vitest run src/components/tickets/status-pill.test.tsx` → 7/7 green.
- `npx tsc --noEmit` → clean.
- `e2e/a11y-routes.spec.ts` was NOT modified (spec was already correct in 16-01).

## Deviations
- **WR-03 (added):** axe-surfaced `EmptyState.Suggestion` violet-on-soft violation + the app's missing
  dark on-soft token vendoring. In scope for "light-theme visual completion" and required for the
  plan's own dark-no-op correctness; fixed and committed as `48ffbdb`. Files added beyond the plan's
  `files_modified`: `frontend/src/components/states/empty-state.tsx`,
  `frontend/src/components/states/empty-state.test.tsx`.
- **WR-04 (added, verifier-surfaced):** the first phase-goal re-verification (`gaps_found` 3/4)
  flagged that base `--color-violet/pink/amber` are not overridden in light, so ~15 more base
  `text-{accent}`-on-soft-fill sites fail AA on cream — sites the axe sweep never reaches because
  they sit behind role/tab/status states not present in seed data (workspace-pane role badges,
  activity-feed, cspm/connector status pills + selection states, okta source-pill, chip bar,
  pagination active page, ticket/asset timelines, KEV badges). At the user's direction ("migrate all
  now"), applied the uniform WR-02 pattern to all of them and updated 3 unit tests that locked the
  old class strings. Committed as `6bf88d8`. Full unit suite 685/685; tsc clean; both axe describe
  blocks re-run green after the migration. NOTE: base accent text on *plain* (non-soft) backgrounds
  is a distinct, un-migrated class (e.g. `saml-pane.tsx` selected labels, `partial-failure-banner.tsx`
  icon) — the verifier did not flag these and the on-soft token is not the right fix for them; left
  for adjudication by the re-verification / a follow-up.

## Requirements closed
- UX-D-03-02 (`--color-info` light override; on-fill text lifted to on-soft) ✓
- UX-D-03-03 (severity/semantic AA on cream) ✓
- UX-D-03-04 (on-soft + faint tokens reconciled, incl. info + dark on-soft vendoring) ✓
- UX-D-03-05 (light+dark axe sweep executed green against a live prod build) ✓
