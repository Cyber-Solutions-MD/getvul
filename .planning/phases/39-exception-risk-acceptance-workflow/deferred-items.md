# Phase 39 — Deferred Items

Out-of-scope discoveries logged during execution per the executor's SCOPE BOUNDARY rule
(pre-existing issues in unrelated files are not auto-fixed).

## 39-01 Task 2 — pre-existing mypy-baseline drift (not caused by this plan)

**Found during:** Task 2 verification (`mypy app/ | mypy-baseline filter`).

**Observation:** Running the CI-equivalent `mypy app/ | mypy-baseline filter` reports 9 "new"
violations, all in `backend/app/ticketing/daily_sync.py` (lines 49/131/135/140/145/150) plus a
`note:` line-count mismatch in `backend/app/auth/dependencies.py:10`. None of these files are
touched by any 39-01 change.

**Root cause:** `pyproject.toml`'s own comment on the `mypy-baseline` pin warns "the
mypy-baseline is line/version-sensitive — drift silently breaks the type gate." Verified by
`git stash`-ing all of 39-01's changes and re-running the identical command against the
pre-existing tree: the same 9 violations appear with zero 39-01 code present, proving this is
baseline/tool drift already present on this branch, not something this plan introduced.

**This plan's own contribution:** one genuinely new violation was introduced and fixed inline
(`app/exceptions/service.py::active_exception_subquery` was missing a return type annotation;
added `-> Exists` from `sqlalchemy`). After that fix, the "new" count is unchanged at 9 —
matching the pre-existing-drift baseline exactly — confirming 39-01 adds zero net-new mypy
violations.

**Action:** Not fixed here (out of scope — `daily_sync.py` is untouched by this plan). Whoever
next touches `app/ticketing/daily_sync.py` or regenerates `mypy-baseline.txt` should reconcile
this drift, or it can be regenerated directly via `mypy app/ | mypy-baseline sync`.

## 39-06 Task 2 — pre-existing `components/ui/button.tsx` icon-variant padding bug (not caused by this plan)

**Found during:** Task 2, while deciding how to render the Revoke column's disabled placeholder
button.

**Observation:** `buttonVariants` (cva) has `defaultVariants: { variant: 'secondary', size: 'md' }`.
Passing `variant="icon"` alone (the documented way to get the sitewide 34x34 icon-button
treatment) does NOT zero out the `size` slot — it silently falls back to `size: 'md'`, whose
`px-4 py-2` classes concatenate with `icon`'s fixed `h-[34px] w-[34px]`. Under Tailwind's
`box-sizing: border-box` preflight, that leaves ~0px of content area for the icon child (34px
box − 32px horizontal padding − 2px border), squeezing/clipping any icon inside. The only
existing call site (`src/app/dev/primitives/showcase.tsx:108`, a dev-only, non-production
showcase route) uses `variant="icon"` with no `size` override and appears to have never been
visually inspected against this.

**This plan's own contribution:** avoided the bug entirely by hand-rolling the Revoke
placeholder's 34x34 markup directly (matching `sketch-findings-getvul/references/visual-
language.md`'s `.icon-btn` spec) instead of using `<Button variant="icon">` — see
`frontend/src/components/exceptions/exceptions-table.tsx`'s Revoke `<td>`. No production code
path in this plan calls the buggy variant.

**Action:** Not fixed here (`components/ui/button.tsx` is outside this plan's `files_modified`,
and the one existing caller is a dev-only route with no visual-regression coverage to safely
verify a fix against). Whoever next reaches for `<Button variant="icon">` in production code —
e.g. Plan 07 wiring the real Revoke mutation — should either add a `compoundVariants` entry
zeroing `size`'s padding when `variant: 'icon'`, or keep hand-rolling the 34x34 markup as this
plan does.
