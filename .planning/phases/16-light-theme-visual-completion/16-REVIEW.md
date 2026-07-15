---
phase: 16-light-theme-visual-completion
reviewed: 2026-07-15T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - frontend/src/app/globals.css
  - frontend/src/components/tickets/status-pill.tsx
  - frontend/src/components/tickets/status-pill.test.tsx
  - frontend/src/components/settings/profile-pane.tsx
  - frontend/src/components/shell/user-chip.tsx
  - frontend/e2e/a11y-routes.spec.ts
  - .claude/skills/sketch-findings-getvul/sources/themes/sunset.css
  - .claude/skills/sketch-findings-getvul/references/foundation.md
  - .claude/skills/sketch-findings-getvul/references/visual-language.md
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-07-15
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 16 completes the light theme: a ~20-token `:root[data-theme="light"]` override block in `globals.css`, migration of two components from dark-only JIT hex literals to `var(--color-*-on-soft)` references, a new blocking light-theme axe sweep in the e2e spec, enabling the previously-disabled Light toggle in `user-chip.tsx`, and mirroring the light-mode token values into the design-system skill (`sunset.css` / `foundation.md` / `visual-language.md`).

The token override architecture is sound and the BL-04 cascade pattern (base accent stays dark for fills/borders/dots, only the foreground `-on-soft` text token lifts) is correctly documented. The e2e light sweep uses a robust two-tier strategy (pre-seed `localStorage` via `addInitScript`, plus a defensive re-assert after `goto`). No security issues, no crash bugs, no injection risks.

However, the light-mode override set is **incomplete in two spots that undercut the phase's central WCAG-AA-on-both-surfaces claim**: the `--color-info` token is never overridden for light, and the amber `-on-soft` migration that was applied to violet/pink was not applied to the two `text-amber` call sites — so those elements never consume the new `--color-amber-on-soft` light value. Both are contrast risks on the cream surface. The remaining items are doc/code token-name drift and minor dead code.

## Warnings

### WR-01: `--color-info` not overridden in light mode — fails AA on cream by the phase's own analysis

**File:** `frontend/src/app/globals.css:8-60` (light block); dark base at `frontend/src/styles/sunset.css:47`
**Issue:** The light override block defines all five `--color-severity-*` tokens (including `--color-severity-info: #2563EB` because blue-400 `#60A5FA` fails 4.5:1 on `#FAF7F2`), but it does **not** override `--color-info`, which stays at the dark value `#60A5FA`. The phase's own reasoning for `severity-info` (blue-400 fails ~contrast on cream, needs blue-600) applies identically to `--color-info`. Any component rendering `text-info` / `color: var(--color-info)` as small text on a light surface will fail the AA gate this phase claims to satisfy. This is inconsistent with the otherwise-complete severity/semantic override set and with the "all ... tokens pass the axe WCAG 2.1 AA gate on both surfaces" claim in `user-chip.tsx:59-61`.
**Fix:** Add to the `:root[data-theme="light"]` block, mirroring `severity-info`:
```css
--color-info: #2563EB;  /* blue-600 — was dark #60A5FA (fails 4.5:1 on cream) */
```
Then mirror it into the skill copies (`sunset.css` light block, `foundation.md` semantic-states comment). If a deliberate decision was made that `--color-info` is never used as small text on light surfaces, document that exclusion in the light block so the omission is not read as an oversight.

### WR-02: `text-amber` (base) used where the new `--color-amber-on-soft` light override should apply — amber text on pale amber fill fails AA on cream

**File:** `frontend/src/components/tickets/status-pill.tsx:40,44` (`in_progress` / `in progress`); `frontend/src/components/settings/profile-pane.tsx:62` (`ANALYST` badge)
**Issue:** This phase migrated the violet and pink on-soft call sites from JIT hex literals to `text-[var(--color-violet-on-soft)]` / `text-[var(--color-pink-on-soft)]` so the light overrides take effect — and added a matching `--color-amber-on-soft: #92400E` (amber-800) token in `globals.css:54` plus docs in `visual-language.md:118` and `foundation.md:35`. But the two amber call sites still use `text-amber`, i.e. the **base** accent `#F59E0B` (amber-500), which is *not* overridden in the light block. On the pale amber-soft/amber-10 fill over the `#FAF7F2` cream surface, amber-500 text runs well under 4.5:1 (amber-500 on white is roughly 1.9:1). The newly-defined `--color-amber-on-soft` is therefore dead — nothing consumes it — and the In-progress ticket pill and ANALYST role badge remain sub-AA in light mode, contradicting the "all severity, accent, danger, and glow tokens pass the axe WCAG 2.1 AA gate on both surfaces" comment in `user-chip.tsx:59-61`.

Note the design-system rule (`visual-language.md:100-120`) explicitly lists amber-on-soft alongside violet/pink and says "Always use `text-[var(--color-*-on-soft)]` ... never hardcode" — the two amber sites violate the rule the phase itself codified.
**Fix:** Mirror the violet/pink migration for amber:
```tsx
// status-pill.tsx — in_progress / 'in progress'
classes: 'border-amber/40 bg-amber/10 text-[var(--color-amber-on-soft)]',

// profile-pane.tsx — roleBadgeClass
ANALYST: 'bg-amber-soft text-[var(--color-amber-on-soft)]',
```
Also update `status-pill.test.tsx:31-36` to assert `text-[var(--color-amber-on-soft)]` instead of `text-amber`. Confirm the dark-mode `--color-amber-on-soft` (`#F59E0B`, unchanged per `visual-language.md:108`) keeps the dark appearance byte-identical so this is a no-op in dark mode. If the light axe sweep is genuinely passing today, that means axe is not flagging these fills (likely because the fill alpha is low enough that axe skips the pair) — the contrast still fails perceptually and should be fixed rather than relied on.

## Info

### IN-01: Blocked-status token name diverges from the documented status contract

**File:** `frontend/src/components/tickets/status-pill.tsx:53-57`; doc at `.claude/skills/sketch-findings-getvul/references/visual-language.md:84-89`
**Issue:** The status workflow table documents Blocked as `--color-danger`, but `BLOCKED_CONFIG` uses the `severity-critical` family (`border/bg/text-severity-critical`). In light mode this happens to be harmless because both resolve to `#DC2626` (`globals.css:28` and `:35`), but the code deliberately mixes the "status" and "severity" color families that `visual-language.md:80` says are kept distinct, and the token names disagree with the documented contract. If the two ever diverge (e.g., danger tuned separately from severity-critical), Blocked silently drifts.
**Fix:** Either switch `BLOCKED_CONFIG` to the `danger` family to match the doc, or add a one-line note in `visual-language.md` that Blocked intentionally reuses the `severity-critical` token (they are pinned equal in both themes). Pick one so code and doc agree.

### IN-02: Dead ternary — both branches return the same value

**File:** `frontend/src/components/settings/profile-pane.tsx:191`
**Issue:** `{idp_source ? idp_source : (isPending ? '—' : '—')}` — the inner `isPending ? '—' : '—'` yields `'—'` regardless of `isPending`. The condition is inert and misleading (reads as if a loading placeholder differs from the empty state).
**Fix:** Simplify to `{idp_source ?? '—'}` (or `{idp_source || '—'}` to match the sibling fields at lines 149/181).

### IN-03: status-pill tests assert the var() token name but add no light-mode coverage; unknown/blocked-only paths untested

**File:** `frontend/src/components/tickets/status-pill.test.tsx`
**Issue:** The tests assert the class string contains `text-[var(--color-violet-on-soft)]` (lines 14, 49), which correctly locks the Phase-16 migration in place. But (a) there is no assertion that the amber path uses an on-soft var (see WR-02 — the test at :33 still asserts `text-amber`, which would need updating with the fix), and (b) the null-return branch (`externalStatus=null`/unknown with `blocked` falsy → `return null`) and the blocked-only branch (unknown status + `blocked=true` → single Blocked pill) are not exercised. Unit tests can't verify computed contrast, so the light AA guarantee rests entirely on the e2e axe sweep.
**Fix:** Add a test for `render(<StatusPill externalStatus={null} />)` asserting nothing renders, and one for `externalStatus="garbage"` + `blocked` asserting a single Blocked pill. Update the amber assertion alongside the WR-02 fix.

### IN-04: Light axe sweep duplicates route-discovery and per-route loop instead of sharing the dark harness

**File:** `frontend/e2e/a11y-routes.spec.ts:78-135`
**Issue:** The new light-theme describe block copy-pastes `discoverDetailRoutes` + the `STATIC_ROUTES` spread + the per-route `goto`/`waitForNav`/filter/expect loop from the dark block (lines 22-71). It is correct and readable, but the two loops will drift over time (e.g., the light block omits the report-only WCAG 2.2 sweep the dark block runs — possibly intentional, but undocumented). This is maintainability, not a bug.
**Fix:** Optional — extract a `sweepRoutes(page, makeAxeBuilder, { label })` helper both describe blocks call, and add a one-line comment noting the light block intentionally skips the report-only 2.2 sweep (if that omission is deliberate).

---

_Reviewed: 2026-07-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
