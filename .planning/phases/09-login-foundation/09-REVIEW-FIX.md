---
phase: 09-login-foundation
fixed_at: 2026-07-23T14:28:00Z
review_path: .planning/phases/09-login-foundation/09-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-07-23T14:28:00Z
**Source review:** .planning/phases/09-login-foundation/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (Critical + Warning)
- Fixed: 3
- Skipped: 0

Scope was `critical_warning`. 0 Critical + 3 Warning in scope. The 3 Info findings (IN-01/02/03) were out of scope and left untouched.

## Fixed Issues

### WR-01: `<Input type="password">` a11y attribute forwarding

**Files modified:** `frontend/src/components/ui/input.test.tsx` (test-only)
**Commit:** fec0ede
**Applied fix:** Added a regression test that composes `<Form>…<FormControl><Input type="password" {...field}/></FormControl>…` and asserts the Slot-forwarded attributes land on the real `<input>`.

**Important — the described source bug is NOT present in current code.** WR-01 claims the Radix `<Slot>` in `<FormControl>` forwards `id`/`aria-invalid`/`aria-describedby` onto the password `<Input>`'s wrapper `<div>` instead of the `<input>`. I verified this empirically with a throwaway probe test (rendering the exact login composition and inspecting where `getByLabelText('Password')` resolves and where the attributes sit):

```
tag: 'INPUT'
aria-invalid: 'true'
id: '..._-form-item'          (matches the FormLabel htmlFor)
aria-describedby: '..._-form-item-description ..._-form-item-message'
```

All three attributes already land on the inner `<input>`, and the label `htmlFor` ↔ input `id` association is intact, with `aria-invalid="true"` on the input so `aria-[invalid=true]:border-danger` matches.

Root cause of the review's misread: Radix `<Slot>` does NOT forward props onto a child's "outermost DOM node." When the Slot child is a custom `forwardRef` component (`Input`), Slot passes the props to the *component* via `cloneElement`; the component decides placement. `input.tsx:41` already spreads `{...props}` (which carries the Slot-injected `id`/`aria-*`) onto the inner `<input>`, and `forwardRef` sends the ref there too. So the code is correct as shipped.

Given the review explicitly requested a regression test asserting the attributes are on the input, I added exactly that test to `input.test.tsx` to lock the behavior against future regressions. **No source (`input.tsx`) change was made** — making the review's suggested edit (manually destructuring `id`/`aria-*` off `...props`) would have been redundant and risked breaking the ref/props merge. New test passes.

### WR-02: bare `border` renders as `currentColor` in dropdown-menu

**Files modified:** `frontend/src/components/ui/dropdown-menu.tsx`
**Commit:** a9e304c
**Applied fix:** Added the explicit `border-border` token alongside the bare `border` utility on both `DropdownMenuSubContent` (line 50) and `DropdownMenuContent` (line 68). Confirmed `tailwind.config.ts` has no `theme.extend.borderColor.DEFAULT`, so the bare `border` did fall back to Preflight `currentColor`. Chose the per-usage token (smallest blast radius) over adding a global `borderColor.DEFAULT`, so no other component's borders change. Uses the design-system `--color-border` token (no freehand hex). app-shell test (the live user-chip dropdown consumer) still passes (4/4).

### WR-04: unguarded `resp.json()` surfaces raw SyntaxError

**Files modified:** `frontend/src/lib/auth.tsx`
**Commit:** 0e49997
**Applied fix:** Two guards, per the review:
- `login()` happy path: `const data = await resp.json().catch(() => null);` then `if (!data?.access_token) throw new AuthError('Sign-in failed. Try again in a moment.');` before `storeTokens`. A 2xx with empty/truncated/non-JSON body now yields the D-49 generic copy instead of leaking `SyntaxError: Unexpected end of JSON input` into `<ErrorAlert>`.
- `register()`: parse now uses `.catch(() => ({}))` and stays ordered after the `!resp.ok` check (`return data?.detail || "Registration failed"`), so a 4xx/2xx with a non-JSON body returns clean copy instead of throwing into `catch (e: any)`.

Behavior-preserving on the normal path (`data.access_token` present → `storeTokens` as before). login/page and auth tests pass.

## Verification

- `npx tsc --noEmit` on the project: exit 0 (clean, no errors in touched files).
- `vitest run` on `input.test.tsx`, `login/page.test.tsx`, `auth.logout.test.tsx`: 25/25 passed (includes the new WR-01 regression test). The `HTMLCanvasElement.prototype.getContext` errors in output are pre-existing jsdom/axe color-contrast noise, not test failures.
- `vitest run` on `app-shell.test.tsx` (dropdown consumer, WR-02 blast-radius check): 4/4 passed.
- Full vitest suite was NOT run (scoped to the touched primitives + their consumers per instructions). Given WR-02 (`border-border`) and WR-01 (test-only) are visually/behaviorally inert on the happy path, and WR-04 preserves happy-path behavior, residual regression risk is low but not exhaustively proven across the full suite.

## Residual risk / human-verification notes

- **WR-01:** No source change; the reported bug was not reproducible and is empirically disproven. If a stakeholder still wants `input.tsx` restructured to hard-pin the attributes onto the `<input>` independent of Slot's prop-merge semantics, that is a separate (optional) hardening, not a bug fix. The added test guards the current correct behavior.
- **WR-02:** Border color on the two dropdown-content surfaces now renders `--color-border` in both dark and light themes rather than `currentColor`. Visual change is intended (subtle chrome per D-09); worth a quick manual glance at the user-chip dropdown in both themes.

---

_Fixed: 2026-07-23T14:28:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
