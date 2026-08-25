# Phase 44 — Deferred Items

Items discovered during execution that are out of scope for the plan that found them (Scope
Boundary rule: only auto-fix issues directly caused by the current task's changes).

## 44-04: pre-existing `npm run build` lint failure (unrelated file)

**Found during:** 44-04 Task 1 final verification (`npm run build` sanity check beyond the
plan's own `<verify>` step).

**Issue:** `frontend/src/components/exceptions/approver-combobox.tsx:176` fails Next.js's
production lint gate — `jsx-a11y/click-events-have-key-events` (a visible, non-interactive
element with a click handler has no keyboard listener). This is a hard `Error`, not a
`Warning`, so `npm run build` fails at the "Linting and checking validity of types" step.

**Origin:** Introduced in Phase 39 (`8757fdd feat(39-07): approver-combobox + grant/revoke
mutation hooks + drill microcopy`), 5 phases before Phase 44. Not touched by any 44-0x plan.

**Verified pre-existing, not caused by 44-04:** `git status --short` at the time this was found
showed zero changes to `approver-combobox.tsx` or anything in `components/exceptions/`; only
44-04's own 4 files were modified/created.

**Impact on 44-04:** None — the plan's own `<verify>` step (`vitest run
"src/app/(authed)/dashboard/ask/page.test.tsx"` + `tsc --noEmit`) is unaffected and green; this
only surfaces when running the full `npm run build` production lint gate, which is broader than
this plan's verification contract.

**Recommended fix (not applied here — out of scope):** add an `onKeyDown` handler (or convert
the element to a real `<button>`) at `approver-combobox.tsx:176`, then confirm `npm run build`
passes end to end.
