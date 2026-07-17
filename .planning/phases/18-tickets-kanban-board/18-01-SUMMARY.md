---
phase: 18-tickets-kanban-board
plan: 01
subsystem: ui
tags: [e2e, playwright, vitest, axe, reduced-motion, tdd-red, kanban]

# Dependency graph
requires:
  - phase: 18-tickets-kanban-board
    plan: 00
    provides: "@dnd-kit/core install, bucketTickets() projection, useMarkBlocked cache-key fix"
provides:
  - "RED e2e board spec (tickets-kanban.spec.ts) pinning the Wave 2 board DOM contract (data-column, data-ticket-id, view=board)"
  - "RED unit spec pinning KanbanReasonPromptProps contract (Save/Cancel/whitespace-null/maxLength)"
  - "Board-view axe sweep (both themes) wired into a11y-routes.spec.ts"
  - "Board drop-tween reduced-motion suppression guard wired into reduced-motion.spec.ts"
affects: [18-02, 18-03, 18-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nyquist-first test scaffolding: RED specs authored against a not-yet-built feature's DOM/API contract before implementation, turned GREEN by later waves"
    - "Visible test.skip(true, reason) guard on empty-dataset e2e cases (mirrors reduced-motion.spec.ts IN-02 pattern) instead of a silent pass"

key-files:
  created:
    - frontend/e2e/tickets-kanban.spec.ts
    - frontend/src/components/tickets/kanban-reason-prompt.test.tsx
  modified:
    - frontend/e2e/a11y-routes.spec.ts
    - frontend/e2e/reduced-motion.spec.ts

key-decisions:
  - "Board DOM contract pinned in the e2e spec: data-column=\"open|in_progress|completed|blocked\" attribute for column containers, data-ticket-id={ticket.id} for cards — Wave 2 (18-03) must emit these exact attributes for the spec to turn GREEN"
  - "Rollback test reuses the same Blocked-column boundingBox as the happy-path drag, then installs the 500 interceptor and drags a second (still non-Blocked) card — asserting the card remains in its origin column rather than asserting a specific 'snap-back' animation state, since a fixed pointer-based e2e can't easily observe transient optimistic-then-rolled-back UI within one drag gesture"
  - "Board axe sweep skips cleanly (test.skip with a visible reason) when zero tickets are seeded, matching the existing empty-column and reduced-motion IN-02 precedent, rather than trivially passing on an empty board"
  - "Mid-drag axe coverage intentionally left to tickets-kanban.spec.ts's drag tests, not a11y-routes.spec.ts — a per-route static sweep re-navigates via page.goto and cannot hold a drag mid-flight across that reload"

requirements-completed: []
# None of UX-D-01-01..06 are actually satisfied yet — this plan only authors the
# falsifiable test scaffolding. Wave 1 (component-level: kanban-card/column/reason-prompt)
# and Wave 2 (board wiring) are what turn these RED targets GREEN and complete the
# requirements. Intentionally left empty per plan objective ("do NOT force green here").

# Metrics
duration: ~25min
completed: 2026-07-17
---

# Phase 18 Plan 01: Nyquist Test Scaffolding — RED board e2e, RED reason-prompt unit spec, axe + reduced-motion extensions Summary

**Authored the full RED test scaffolding for the tickets kanban board BEFORE the board exists: a new five-test e2e spec pinning the Wave 2 DOM contract (columns, drag, keyboard, empty-state, mobile bottom-nav non-regression), a RED unit spec pinning the reason-prompt's Save/Cancel/whitespace-coercion contract, and additive extensions to the existing axe (both-themes) and reduced-motion e2e suites covering `?view=board`.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-17
- **Tasks:** 3 completed
- **Files modified:** 4 (2 new, 2 extended)

## Accomplishments
- `frontend/e2e/tickets-kanban.spec.ts` created with all 5 exact requirement-mapped test titles (`renders four columns`, `drag into Blocked persists`, `keyboard drag`, `empty column`, `board mobile bottom-nav`) matching the 18-VALIDATION.md `-g` grep filters verbatim
- The rollback test installs a scoped `page.route('**/api/v1/tickets/*/blocked', ...)` 500 interceptor, confirming T-18-04's threat-register disposition (scoped, no persistence)
- `frontend/src/components/tickets/kanban-reason-prompt.test.tsx` created with 4 cases (Save-with-reason, Cancel = no mutation, whitespace-only → `onSave(null)`, `maxLength=500`) against the `KanbanReasonPromptProps` contract from the plan's `<interfaces>` block — confirmed RED via `npx vitest run` (module not found, as expected)
- `frontend/e2e/a11y-routes.spec.ts` extended with a new `describe` block sweeping `/dashboard/tickets?view=board` in both dark and light themes for zero critical/serious axe violations, reusing the existing light-theme `addInitScript` + defensive `data-theme` force pattern
- `frontend/e2e/reduced-motion.spec.ts` extended with `board drag drop animation is suppressed under prefers-reduced-motion`, polling `document.getAnimations()` for ~500ms after a pointer drag and asserting max duration ≤20ms (targets RESEARCH Pitfall 2 — the WAAPI `DragOverlay` drop tween is NOT caught by the CSS blanket)
- `cd frontend && npx tsc --noEmit -p tsconfig.json` confirms all 4 files compile cleanly on their own merits — the only TS errors present are the expected RED reference (`kanban-reason-prompt.test.tsx` → `./kanban-reason-prompt` module not found), scoped exactly to the not-yet-built component
- `npx vitest run src/components/tickets/` confirms the pre-existing 65 tests across 12 files remain green; only the new RED spec fails, and only for the expected reason (missing module)

## Task Commits

Each task was committed atomically:

1. **Task 1: NEW e2e board spec (RED)** - `3d13dfc` (test)
2. **Task 2: RED reason-prompt unit spec + extend axe both-themes to board view** - `e389316` (test)
3. **Task 3: Extend reduced-motion spec for board drop-tween suppression** - `b1b9aca` (test)

_This is a Wave 0 test-scaffolding plan — all three tasks are `test(...)` commits with no accompanying `feat`/`fix` GREEN commit. That is the correct and expected state per the plan objective: every assertion here targets Wave 1–2 implementation work._

## Files Created/Modified
- `frontend/e2e/tickets-kanban.spec.ts` (new) — 5 e2e tests against the board DOM contract (`data-column`, `data-ticket-id`, `view=board`), each guarded by a visible `test.skip(true, reason)` on empty seed data
- `frontend/src/components/tickets/kanban-reason-prompt.test.tsx` (new) — 4 vitest + Testing Library cases against `KanbanReasonPromptProps`
- `frontend/e2e/a11y-routes.spec.ts` (extended) — new `describe('WCAG 2.1 AA axe sweep — tickets board view (blocking)')` with dark + light theme tests
- `frontend/e2e/reduced-motion.spec.ts` (extended) — new test asserting the board's `DragOverlay` drop-tween duration stays ≤20ms under `prefers-reduced-motion: reduce`

## Decisions Made
- Board DOM contract (`data-column`, `data-ticket-id`) pinned exactly as specified in the plan's `<interfaces>` block — no deviation, since Wave 2 (18-03) owns satisfying it
- Rollback e2e drags a *second*, still-non-Blocked card after installing the 500 interceptor (rather than re-dragging the just-blocked card back), since asserting "the card remains in the Open column" after a failed mutation is more robust than trying to catch a transient optimistic-then-reverted intermediate state with fixed pointer waits
- Board axe sweep is its own new `describe` block in `a11y-routes.spec.ts` (not folded into the existing all-routes sweep) since `STATIC_ROUTES` intentionally excludes the `?view=board` query variant of `/dashboard/tickets` and this sweep needs its own skip-on-empty-data guard that the generic sweep doesn't have
- Mid-drag axe assertions were explicitly left out of `a11y-routes.spec.ts` per the plan's own guidance ("or add an in-drag axe assertion if straightforward") — a per-route static sweep re-navigates via `page.goto`, which cannot hold a drag gesture mid-flight across that reload; this coverage is deferred to the drag tests already living in `tickets-kanban.spec.ts`

## Deviations from Plan

None — plan executed exactly as written. All four files match the plan's exact `<files>` list, all task-level acceptance criteria were verified via the exact `grep`/`tsc`/`vitest` commands specified in each task's `<verify>` block.

## Known Stubs

None — this plan is 100% test scaffolding by design (no implementation, no stub data). The board component, reason-prompt component, and their wiring do not exist yet; every RED assertion in this plan's files targets that absent implementation intentionally, per the plan objective, not as an unintended stub.

## Threat Flags

None — this plan introduces no new production surface. Per the plan's own threat model (T-18-03, T-18-04), the only "new" items are test-harness constructs (reused `storageState`, a scoped in-test `page.route` mock) with no persistence or production impact.

## Issues Encountered
None. TypeScript, Vitest, and grep verification all confirmed the expected RED state on the first attempt for every task.

## User Setup Required
None — no external service configuration required. These are pure test-authoring changes; no server needs to be running to author or typecheck them (the e2e specs themselves require a prod build + running app to execute, which is out of scope for this plan per its own notes).

## Next Phase Readiness
- `frontend/e2e/tickets-kanban.spec.ts` is the falsifiable gate for Wave 1 (component primitives) and Wave 2 (board wiring): once `TicketsKanbanBoard` renders the `data-column`/`data-ticket-id` contract and `KanbanReasonPrompt` exists, these 5 tests turn GREEN without modification.
- `kanban-reason-prompt.test.tsx` is the exact contract Wave 1's `kanban-reason-prompt.tsx` must satisfy — `KanbanReasonPromptProps` (`ticketLabel`, `onSave`, `onCancel`) is already pinned; the component just needs to be authored against it.
- `a11y-routes.spec.ts` and `reduced-motion.spec.ts` extensions require no further scaffolding — they will start asserting real board behavior automatically once the board exists, no additional wiring needed from Wave 2.
- No blockers for Wave 1 (18-02, presumably `kanban-card.tsx`/`kanban-column.tsx`/`kanban-reason-prompt.tsx`) or Wave 2 (board assembly + `page.tsx` wiring).

---
*Phase: 18-tickets-kanban-board*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files confirmed present on disk:
- FOUND: frontend/e2e/tickets-kanban.spec.ts
- FOUND: frontend/src/components/tickets/kanban-reason-prompt.test.tsx
- FOUND: frontend/e2e/a11y-routes.spec.ts (modified, contains view=board)
- FOUND: frontend/e2e/reduced-motion.spec.ts (modified, contains board drag drop test)

All 3 task commits confirmed present in `git log --oneline`: `3d13dfc`, `e389316`, `b1b9aca`.
