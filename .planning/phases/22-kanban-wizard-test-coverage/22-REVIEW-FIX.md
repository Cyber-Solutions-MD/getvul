---
phase: 22-kanban-wizard-test-coverage
fixed_at: 2026-07-22T14:55:00Z
review_path: .planning/phases/22-kanban-wizard-test-coverage/22-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 22: Code Review Fix Report

**Fixed at:** 2026-07-22
**Source review:** .planning/phases/22-kanban-wizard-test-coverage/22-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1 (Critical + Warning only)
- Fixed: 1
- Skipped: 0

Scope note: REVIEW.md has 0 Critical, 1 Warning (WR-01), 4 Info. Only WR-01 is
in the `critical_warning` scope. The four Info findings (IN-01 dead
`currentCoordinates` binding, IN-02 ref-advance ordering, IN-03 test source-lane
scoping, IN-04 wizard fill-value assumption) were not addressed.

## Fixed Issues

### WR-01: "Moved to Blocked" is announced at drop, before the reason prompt is confirmed

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`, `frontend/e2e/tickets-kanban.spec.ts`
**Commit:** d6f90c8
**Status:** fixed: requires human verification (screen-reader live-region timing is only fully provable under the Playwright e2e prod build + server)

**Applied fix:**
The false-success announcement was corrected by splitting the two "committed"
transitions by *when* they actually mutate:

1. In `announcements.onDragEnd`, the read-only→Blocked drop now announces a
   PENDING state — `"Ticket X ready to block — confirm the reason to finish."`
   — instead of `"Moved…"`, because `handleDragEnd` only opens
   `KanbanReasonPrompt` (`setPendingBlock`) for that transition; no mutation
   fires at drop. Blocked→read-only (the genuine immediate-commit / unblock
   path) keeps the `"Moved ticket X to the {column} column."` wording. All other
   drops still return `"returned to its column."`.

2. Added a dedicated polite live region (`role="status" aria-live="polite"`,
   `data-block-announcer`, `sr-only`) driven by new `blockCommitAnnouncement`
   state. The confirmed `"Moved ticket X to the Blocked column."` is now emitted
   from the reason prompt's `onSave` — i.e. only once the mutation actually
   fires. `onCancel` never populates it, so a Cancel leaves no stale
   false-success (the card snaps back and nothing was ever spoken as done).

3. Updated the WR-02 e2e assertion (`tickets-kanban.spec.ts`, formerly line
   201): the dnd-kit live region is now asserted to contain the PENDING wording
   at drop, and a new `[data-block-announcer]` locator is asserted to contain
   the confirmed `"Moved ticket … to the Blocked column"` only after Save. The
   sibling gated-no-op test's `not.toContainText(/^Moved ticket/i)` guard on the
   dnd-kit region is unaffected (read-only→read-only still returns "returned to
   its column").

**Verification performed:**
- Tier 1: re-read all modified sections; fix text present, surrounding code
  intact.
- Tier 2: `npx tsc --noEmit` reports no errors referencing either modified file.
- Unit tests: `npx vitest run kanban-reason-prompt.test.tsx` — 4/4 pass (onSave
  signature/behavior unchanged, prompt component untouched).

**Why human verification is flagged:** The corrected behavior depends on
screen-reader live-region announcement timing (drop → pending in the dnd-kit
region, Save → confirmed in the new polite region). That end-to-end assertion
lives in `tickets-kanban.spec.ts` and can only be proven by running the full
Playwright e2e sweep, which requires a production build + running server (not
run here). Please run the kanban e2e (`keyboard drag` + `gated no-op drop`
tests) against a prod build before treating the a11y wording as verified. Note
also the em-dash (`—`) in both the announcement string and the e2e regex must
stay byte-identical for the assertion to match.

---

_Fixed: 2026-07-22_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
