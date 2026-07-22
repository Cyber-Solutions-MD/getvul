---
phase: 20-light-theme-severity-high-aa
fixed_at: 2026-07-22T11:52:50Z
review_path: .planning/phases/20-light-theme-severity-high-aa/20-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 20: Code Review Fix Report

**Fixed at:** 2026-07-22T11:52:50Z
**Source review:** .planning/phases/20-light-theme-severity-high-aa/20-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
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

---

_Fixed: 2026-07-22T11:52:50Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
