---
phase: 20-light-theme-severity-high-aa
fixed_at: 2026-07-23T00:00:00Z
review_path: .planning/phases/20-light-theme-severity-high-aa/20-REVIEW.md
iteration: 2
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 20: Code Review Fix Report

**Fixed at:** 2026-07-23T00:00:00Z
**Source review:** .planning/phases/20-light-theme-severity-high-aa/20-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Dropped `/80` opacity modifier on the blocked-reason text alters dark-mode rendering

**Files modified:** `frontend/src/components/tickets/blocked-toggle.tsx`
**Commit:** 8d2ecc1
**Applied fix:** Kept the full-opacity `text-[var(--color-severity-critical-on-soft)]` and
added an explanatory comment documenting the dark-mode change as intentional rather than a
silent side effect.

Resolution rationale (per the reviewer's guidance and phase context):

- **Did not restore `/80` de-emphasis.** In light mode the AA fix requires the full-strength
  on-soft token (`#991B1B`); reintroducing reduced opacity on the reason text risks dropping
  it back below AA contrast — directly undoing this phase's goal.
- **Did not introduce a `var()` alpha modifier.** `text-[var(--color-severity-critical-on-soft)]/80`
  does not reliably emit alpha for `var()` arbitrary values in Tailwind 3.4, so it would be a
  broken no-op. Explicitly avoided.
- **Chose the simplest correct path** the reviewer sanctioned: accept full opacity (no
  correctness or a11y regression) and record the dark-mode rendering change intentionally via
  an in-line comment above the span.

**Verification:** Tier 1 re-read confirmed the comment and JSX intact. Ran
`vitest run src/components/tickets/blocked-toggle.test.tsx` — 4/4 passed.

### IN-01: Unconditional `console.log` diagnostics added to the axe e2e spec

**Files modified:** `frontend/e2e/a11y-routes.spec.ts`
**Commit:** 11142ae
**Applied fix:** Converted the two unconditional "reached-the-end proof" `console.log`
lines (dark sweep at :73, light sweep at :138) into non-noisy Playwright annotations via
`test.info().annotations.push({ type: 'axe-sweep-completed', description: ... })`. The
annotation description preserves the exact original information — sweep flavor (dark/light),
route count (`routes.length`), and last route swept — so the "the axe sweep actually ran to
completion" evidence survives in the Playwright test report without polluting CI stdout.
Applied the review's suggested downgrade path (`testInfo.annotations`) rather than deleting
the proof, which directly addresses the documented "axe sweep not actually run during
execution" hazard the diagnostics were guarding against. Added an inline comment on each site
explaining why the annotation replaces the console.log.

**Verification:** Tier 1 re-read confirmed both annotations present with intact surrounding
test structure. Tier 2: `npx tsc --noEmit -p tsconfig.json` reported zero errors referencing
`a11y-routes.spec.ts`; `npx eslint e2e/a11y-routes.spec.ts` clean. NOTE: this is a Playwright
e2e spec — full runtime verification (the annotations actually appearing after a completed
sweep) requires a production build + running server and was NOT executed here. The change is
diagnostic-only (no assertion logic touched), so a static/lint pass is sufficient to confirm
correctness; the runtime pass is deferred to the full quality-gate sweep.

---

_Fixed: 2026-07-23T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
