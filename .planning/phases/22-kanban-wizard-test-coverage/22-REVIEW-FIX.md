---
phase: 22-kanban-wizard-test-coverage
fixed_at: 2026-07-23T10:24:00Z
review_path: .planning/phases/22-kanban-wizard-test-coverage/22-REVIEW.md
iteration: 2
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 22: Code Review Fix Report

**Fixed at:** 2026-07-23 (iteration 2; WR-01 fixed in iteration 1 on 2026-07-22)
**Source review:** .planning/phases/22-kanban-wizard-test-coverage/22-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 5 (0 Critical + 1 Warning + 4 Info — full scope)
- Fixed: 5
- Skipped: 0

Scope note: REVIEW.md has 0 Critical, 1 Warning (WR-01), 4 Info. Iteration 1
(`critical_warning` scope) fixed WR-01. Iteration 2 (`all` scope) fixed the four
Info findings: IN-01 dead `currentCoordinates` binding, IN-02 ref-advance
ordering, IN-03 test source-lane scoping, IN-04 wizard fill-value assumption.
The WR-01 entry below is preserved unchanged from iteration 1.

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

### IN-01: `currentCoordinates` is now an unused destructured binding

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`
**Commit:** 9089f7f
**Status:** fixed

**Applied fix:** Dropped `currentCoordinates` from the coordinateGetter's
destructure — the getter now reads `return (event, { context }) => {`. The 22-01
change had already replaced its only use (`y: currentCoordinates.y` →
`y: rect.top + rect.height / 2`), leaving the binding dead. The surrounding
comment block that references the historical `currentCoordinates.y` behavior was
left intact (it documents rationale, not live code).

**Verification:** Tier 1 re-read confirms the binding is gone and the getter body
is intact. Tier 2 `npx tsc --noEmit` reports no errors referencing the file.

### IN-02: coordinateGetter advances `columnIndexRef` before the rect-availability check

**Files modified:** `frontend/src/app/(authed)/dashboard/tickets/tickets-kanban-board.tsx`
**Commit:** 8a7ccf1
**Status:** fixed: requires human verification

**Applied fix:** Reordered per the review — the target index is resolved into a
local `target`, the target column's rect is looked up and gated
(`if (!rect) return undefined;`), and only then is `columnIndexRef.current = target`
committed. Previously the ref advanced before the rect check, so an unmeasured
target rect returned `undefined` (no move) while the ref had already advanced,
desyncing the tracked index and skipping a column on the next arrow press.

**Verification:** Tier 1 re-read confirms the new ordering. Tier 2
`npx tsc --noEmit` reports no errors referencing the file. Flagged
`requires human verification` because this alters keyboard-drag traversal logic
that is exercised only by the Playwright `keyboard drag` e2e (prod build +
server) — not covered by any vitest unit test. The keyboard-drag e2e must pass
under the full sweep before treating the traversal behavior as verified.

### IN-03: keyboard-drag tests pick `cards.first()` without ensuring a non-Blocked source

**Files modified:** `frontend/e2e/tickets-kanban.spec.ts`
**Commit:** 34c8538
**Status:** fixed: requires human verification (e2e-only spec)

**Applied fix:** Both the `keyboard drag` and `keyboard drag with Enter` tests now
source the card from a read-only lane explicitly —
`page.locator('[data-column="open"] [data-ticket-id]')` — mirroring the sibling
gated-no-op test (spec line 266). The zero-card skip guards were updated to the
scoped message (`no Open tickets seeded …`). This prevents a Blocked-first seed
from turning the drop into a blocked→blocked no-op that would stall on the
never-appearing Save button (a confusing false failure).

**Verification:** Tier 1 re-read confirms the scoped locators and skip messages.
Tier 2 `npx tsc --noEmit` reports no errors referencing the spec. These are
Playwright e2e specs that require a prod build + running server to execute — the
runtime pass is NOT claimed here and needs the full e2e sweep for verification.

### IN-04: connector wizard `driveToTestStep` fills every input with the literal `'test-value'`

**Files modified:** `frontend/e2e/connector-wizard-a11y.spec.ts`
**Commit:** b5d8305
**Status:** fixed

**Applied fix:** Added a comment at the fill loop documenting the assumption that
no rendered credential field applies client-side format validation (URL,
port/number, etc.) that would keep "Next" disabled. The `connectors/test` call is
mocked so the value never matters server-side; the note flags that a future
format-validated field would require filling by input `type` instead of the
literal, or the helper stalls at the Next click. No behavioral change.

**Verification:** Tier 1 re-read confirms the comment is present and the fill loop
is intact. Tier 2 `npx tsc --noEmit` reports no errors referencing the spec. This
is a Playwright e2e helper (comment-only change); no runtime execution claimed.

**Iteration-2 unit-test check:** `npx vitest run` on
`tickets/page.test.tsx` + `kanban-reason-prompt.test.tsx` — 8/8 pass (no unit
test directly exercises the coordinateGetter; its behavior is e2e-only).

---

_Fixed: 2026-07-22 (WR-01), 2026-07-23 (IN-01..IN-04)_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
