---
phase: 16-light-theme-visual-completion
reviewed: 2026-07-16T10:16:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - frontend/src/app/globals.css
  - frontend/src/components/tickets/status-pill.tsx
  - frontend/src/components/settings/profile-pane.tsx
  - frontend/src/components/tickets/status-pill.test.tsx
  - frontend/src/components/states/empty-state.tsx
  - frontend/src/components/states/empty-state.test.tsx
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 16: Code Review Report (Gap-Closure — Plan 16-03)

**Reviewed:** 2026-07-16T10:16:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found (2 Info only — no Critical, no Warning)

## Summary

Re-review scoped to the Phase-16 gap-closure (plan 16-03): three light-theme WCAG AA fixes —
WR-01 (`--color-info` light override), WR-02 (`text-amber` → `--color-amber-on-soft` migration in
status-pill + profile-pane), and WR-03 (`EmptyState.Suggestion` → `--color-violet-on-soft`
plus vendoring the on-soft tokens into the globals.css dark block). The change surface is CSS
custom-property values, Tailwind class-string swaps, and unit-test assertion updates.

**The token wiring is correct and the cascade is sound.** I verified the three concerns that
matter most for this kind of change:

1. **On-soft tokens resolve in every theme.** The vendored `src/styles/sunset.css` does NOT
   define `--color-{violet,pink,amber}-on-soft` (confirmed by grep). WR-03 correctly vendors
   them into the `:root[data-theme="dark"]` block, and the light block already carries them.
   Both selectors require the `data-theme` attribute — but `src/app/layout.tsx` hard-codes
   `data-theme="dark"` on `<html>` for SSR and the FOUC bootstrap always stamps `light` or
   `dark`, so the attribute is always present. No undefined-token / silent-fallback gap remains.
   Every consumer (status-pill open + in_progress + "in progress", profile-pane OWNER/ADMIN/ANALYST,
   EmptyState.Suggestion) now resolves to an intended accent in both themes.

2. **WR-01 fixes a live regression, not a dead token.** `--color-info` is consumed by
   `Toast.tsx` (`border-info` / `text-info` on the info-variant toast). Previously it fell
   through to sunset.css `#60A5FA` (blue-400, ~2.5:1 on cream). The light override to `#2563EB`
   (blue-600) is a real AA fix and correctly mirrors `--color-severity-info`.

3. **WR-02 dark no-op claim is accurate.** Old `text-amber` mapped to `--color-amber` = `#F59E0B`;
   new dark `--color-amber-on-soft` = `#F59E0B` (globals.css line 86) — byte-identical. Dark
   rendering is unchanged; only light lifts to `#92400E`. Both the `in_progress` and the space
   variant `'in progress'` entries received the same treatment (consistent).

**Tests pass:** `status-pill.test.tsx` + `empty-state.test.tsx` = 16/16 green. Assertions were
updated to match the `var(--color-*-on-soft)` class strings rather than the old JIT hex literals.

Findings below are advisory (Info) — neither blocks the phase.

## Info

### IN-01: jsdom axe test cannot verify color contrast — the phase's core guarantee is unproven by unit tests

**File:** `frontend/src/components/states/empty-state.test.tsx:98-114`
**Issue:** The `axe — no violations` test emits `Error: Not implemented: HTMLCanvasElement.prototype.getContext`
from axe-core's `colorContrastMatches` rule. Under jsdom (no `canvas` package), axe silently
skips the color-contrast check. The test still passes, but it does NOT actually assert the AA
contrast that WR-01/WR-02/WR-03 exist to fix. This is a pre-existing harness limitation, not
introduced by this change — but it is directly relevant here: the entire phase is a contrast
remediation, and the one automated contrast assertion in scope is inert. This aligns with the
known-issue note "Axe sweep not run during execution" (AA claims should be treated as unproven
until the Playwright prod-build axe sweep runs). The class-string assertions verify the *token
reference* is present, but nothing in these unit tests verifies the *resolved contrast ratio*.
**Fix:** Treat the numeric contrast ratios in the code comments (e.g. `#92400E` "~5.5:1",
`#5B21B6` on violet-soft, `#2563EB` on cream) as claims to be confirmed by the browser-based
Playwright axe sweep against a prod build in both `data-theme="light"` and `data-theme="dark"`,
per plan 16-03's axe-sweep task. Do not mark the phase's AA guarantee complete on the strength
of the jsdom unit tests alone. (No code change required in these files.)

### IN-02: on-soft tokens are duplicated across three locations — vendoring debt is documented but worth tracking

**File:** `frontend/src/app/globals.css:53-55, 84-86`
**Issue:** The `--color-{violet,pink,amber}-on-soft` values now live in three places: the
globals.css light block, the globals.css dark block (added by WR-03), and the design-system
skill's `sunset.css` / `foundation.md` (BL-04). The dark block exists only because the app's
vendored `src/styles/sunset.css` predates these tokens. The code comments (lines 75-83) document
this clearly and flag the retirement condition ("Retire when the vendored sunset.css is re-synced").
This is acceptable, intentional debt — not a defect — but the same pattern already bit the
`--color-text-faint` override (lines 63-73), which is a second vendored-token duplication carrying
its own retire-on-resync note. Two independent "retire when sunset.css is re-vendored" overrides
now accumulate in the dark block.
**Fix:** No change needed for this phase. Consider filing a single backlog item to re-vendor
`src/styles/sunset.css` from the skill source, which would let both the `--color-text-faint`
override (lines 63-73) and the three `--color-*-on-soft` overrides (lines 84-86) be deleted at
once, collapsing the duplication back to a single source of truth.

---

_Reviewed: 2026-07-16T10:16:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
