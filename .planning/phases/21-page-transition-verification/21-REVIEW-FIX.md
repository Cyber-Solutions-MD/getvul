---
phase: 21-page-transition-verification
fixed_at: 2026-07-21T13:56:36Z
review_path: .planning/phases/21-page-transition-verification/21-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 4
status: all_fixed
---

# Phase 21: Code Review Fix Report

**Fixed at:** 2026-07-21T13:56:36Z
**Source review:** .planning/phases/21-page-transition-verification/21-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (critical + warning): 3
- Fixed: 3 (WR-01, WR-02, WR-03)
- Skipped: 4 (IN-01..04 — Info, out of scope for this pass)

**Contract honored:** Only `frontend/e2e/page-transitions.spec.ts` was modified.
No production source (ChipBar.tsx, template.tsx, drill-panel.tsx, globals.css) or
`playwright.config.ts` was touched — Phase 21's "no production code changed" contract
is intact. Every existing test title, assertion, the legacy PopStateEvent secondary
test, and the Firefox dual-branch (native-VT / CSS-fallback) logic were preserved.

## Fixed Issues

### WR-02: searchParams-only no-fade test never proves searchParams actually changed

**Files modified:** `frontend/e2e/page-transitions.spec.ts`
**Commit:** 4a5c504
**Status:** fixed

**Applied fix:** In the `searchParams-only change does NOT trigger a page fade` test I
added a positive liveness gate around the chip click so the zero-fade result is
conditioned on a real searchParams mutation:
- Captured `searchBefore = location.search` before the click.
- After `criticalChip.click()`, added `await expect(page).toHaveURL(/[?&]severity=critical/)`.
- After the poll, added `expect(searchAfter).not.toBe(searchBefore)`.
- Kept the existing `maxNamedVtCount === 0` assertion and the `pathnameAfter === pathnameBefore`
  assertion verbatim.

**Assertion chosen and why:** `toHaveURL(/[?&]severity=critical/)` with the *lowercase*
value `critical`. I confirmed the exact param value against source rather than trusting
the reviewer's snippet:
- `vulnerabilities/chip-bar.tsx:11` defines `SEVERITIES = ['critical', ...] as const`, and
  the severity axis chips use `value: s` (lowercase).
- The chip's `onClick` calls `toggle(c.value)` (ChipBar.tsx:139), and
  `useUrlStateList` (`use-url-state-list.ts:38-39`) appends the raw allow-listed value:
  `sp.append(key, v)` → `severity=critical`. So the emitted URL is
  `/dashboard/vulnerabilities?severity=critical`, matching the regex exactly.

### WR-03: `getByRole('button', { name: /critical/i })` is data-dependent and strict-mode fragile

**Files modified:** `frontend/e2e/page-transitions.spec.ts`
**Commit:** 4a5c504
**Status:** fixed

**Applied fix:** Replaced the page-wide substring selector with a selector scoped to the
severity axis's stable container and anchored on the name:
```ts
const severityAxis = page.locator('[data-chip-bar="generic"] [data-axis="severity"]');
const criticalChip = severityAxis.getByRole('button', { name: /^Critical\b/i });
```

**Selector chosen and why (verified against ChipBar.tsx, NOT the reviewer's snippet):**
- I did **not** use the reviewer's `getByTestId('chipbar-severity-critical')` option: it
  would require adding a `data-testid` to ChipBar.tsx, a production change forbidden by
  this phase's contract.
- I did **not** use the reviewer's `getByRole('group', { name: /severity/i })` option:
  ChipBar renders the severity chips inside a plain `<div ... data-axis="severity">`
  (ChipBar.tsx:126) with **no** `role="group"` and no accessible group name. That
  container cannot be resolved by role, so the option is invalid against the real source.
- I also did **not** use the reviewer's fallback `{ name: 'Critical', exact: true }`:
  the vuln severity axis always supplies `counts` (`vulnerabilities/chip-bar.tsx:60`,
  `Object.fromEntries(SEVERITIES.map(...))`), so ChipBar renders the label as
  `"${c.label} · ${count}"` (ChipBar.tsx:132). The button's accessible name is therefore
  `"Critical · {N}"`, and an *exact* `'Critical'` match would resolve zero elements and
  break the test.
- Instead I scoped to the already-existing, non-production-changing attributes
  `data-chip-bar="generic"` (ChipBar.tsx:265) + `data-axis="severity"` (ChipBar.tsx:126).
  Within that container only one chip contains "Critical", and "Critical" is not a
  substring of High/Medium/Low/Info — so the strict-mode cross-page ambiguity WR-03
  describes (a stray "Critical" badge/CTA elsewhere) can no longer match. The `/^Critical\b/i`
  anchor additionally removes the substring-regex fragility while still matching the real
  `"Critical · {N}"` accessible name.

**Note:** WR-02 and WR-03 edit interleaved lines of the same test block, so they share a
single atomic commit (4a5c504).

### WR-01: Firefox reduced-motion native branch can pass with zero executed assertions

**Files modified:** `frontend/e2e/page-transitions.spec.ts`
**Commit:** 83ff133
**Status:** fixed

**Applied fix:** In the `Firefox transition path is suppressed under prefers-reduced-motion`
test, I inserted a navigation liveness guard immediately after the Vulnerabilities link
click and **before** the `if (supportsNativeVt)` branch:
```ts
await expect(page).toHaveURL(/\/dashboard\/vulnerabilities/);
```

**Assertion chosen and why:** The test navigates Dashboard → Vulnerabilities via the
sidebar link (`getByRole('link', { name: /vulnerab/i }).click()`), so the destination is
`/dashboard/vulnerabilities`. This guard makes the "no named animation observed = valid
suppressed state" outcome (the empty `everSeen === false` path the reviewer flagged)
reachable ONLY after a real client-side route change has landed — a broken nav (link
never fired, route errored, hydration failure) now fails at the guard instead of passing
vacuously. I left the existing native-VT duration-suppression logic, the `everSeen`
polling, the "instant swap is a valid suppressed state" comment, and the CSS-fallback
`else` branch untouched.

## Skipped Issues

All four Info findings are out of scope for this pass (fix_scope = critical_warning,
not --all). They were not attempted and no code was changed for them.

### IN-01: `boundingBox()` deep-equality is sub-pixel fragile
**File:** `frontend/e2e/page-transitions.spec.ts:221, 249`
**Reason:** skipped — Info severity, out of scope (critical_warning pass only).

### IN-02: Both Firefox `else` (CSS-fallback) branches are unexercised on the installed engine
**File:** `frontend/e2e/page-transitions.spec.ts:342-348, 398-408`
**Reason:** skipped — Info severity, out of scope. (Reviewer itself notes "No change required.")

### IN-03: Residual sampling-window flake on the `toBe(0)` no-fade assertions
**File:** `frontend/e2e/page-transitions.spec.ts:71-90`
**Reason:** skipped — Info severity, out of scope (critical_warning pass only).

### IN-04: Poll-body duplication across two helpers and the inline Firefox loop
**File:** `frontend/e2e/page-transitions.spec.ts:44-90, 304-333`
**Reason:** skipped — Info severity, out of scope (critical_warning pass only).

---

_Fixed: 2026-07-21T13:56:36Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
