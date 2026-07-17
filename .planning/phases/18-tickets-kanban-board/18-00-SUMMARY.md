---
phase: 18-tickets-kanban-board
plan: 00
subsystem: ui
tags: [react-query, dnd-kit, tanstack-query, tickets, optimistic-updates, vitest]

# Dependency graph
requires:
  - phase: 13-tickets-list-detail
    provides: useTickets/useMarkBlocked hooks, tickets query-key namespace, TicketSummary type
provides:
  - "@dnd-kit/core@6.3.1 installed (no sortable/v2) — ready for the DndContext board component"
  - "bucketTickets() pure projection fn (+ COLUMN_ORDER, COLUMN_LABELS, ColumnKey) — proven by 9 unit tests"
  - "useMarkBlocked optimistic list-cache patch fixed to fuzzy setQueriesData/getQueriesData (Pitfall 1) — list view AND board both reproject optimistically with rollback"
affects: [18-01, 18-02, 18-03, 18-04]

# Tech tracking
tech-stack:
  added: ["@dnd-kit/core@6.3.1"]
  patterns:
    - "Board-as-pure-projection: bucketTickets() derives kanban columns synchronously from the useTickets list cache, no local board state"
    - "Fuzzy TanStack Query cache patching: setQueriesData/getQueriesData against a queryKey PREFIX (not setQueryData/getQueryData exact-key) for optimistic updates that must apply across every filter/page/view permutation of a list query"

key-files:
  created:
    - frontend/src/components/tickets/bucket-tickets.ts
    - frontend/src/components/tickets/bucket-tickets.test.ts
    - frontend/src/lib/queries/use-mark-blocked.test.ts
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/src/lib/queries/use-mark-blocked.ts

key-decisions:
  - "Used --legacy-peer-deps for the @dnd-kit/core install — the tree-wide lucide-react@0.383.0 peer react@^18 conflict (same root cause as Phase 15-01) blocks ANY plain npm install on this project, not just dnd-kit's own peer range"
  - "use-mark-blocked.test.ts kept the plan-specified .ts extension by using React.createElement instead of JSX (JSX requires .tsx) for the QueryClientProvider wrapper"
  - "onError restore iterates ALL captured list snapshots (not just one) since setQueriesData may have touched multiple cached filter/page/view permutations simultaneously"

patterns-established:
  - "Pure fn + unit test file co-located under components/tickets/ for board projection logic (no React, no side effects) — a template for future non-visual kanban logic"

requirements-completed: [UX-D-01-01, UX-D-01-02]

# Metrics
duration: 10min
completed: 2026-07-17
---

# Phase 18 Plan 00: Foundation — @dnd-kit install, bucketTickets projection, useMarkBlocked cache-key fix Summary

**Installed @dnd-kit/core@6.3.1, authored a proven pure bucketTickets() column projection, and fixed a latent Pitfall-1 bug where useMarkBlocked's optimistic list-cache patch used an exact key that never matched the real list cache shape — making the patch a no-op for both the existing list view and the upcoming kanban board.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-07-17
- **Tasks:** 3 completed
- **Files modified:** 6 (2 new source, 2 new test, 2 dependency manifest)

## Accomplishments
- `@dnd-kit/core@6.3.1` resolves cleanly; confirmed no `@dnd-kit/sortable` or v2 (`@dnd-kit/react`/`@dnd-kit/dom`) packages were pulled in
- `bucketTickets()` proven correct for Blocked-wins (D-COL-01), the `in_progress`/`in progress` status alias, unknown/null/empty → Open, case-insensitivity, `COLUMN_ORDER` (D-COL-04), and `COLUMN_LABELS` — 9/9 unit tests green
- `useMarkBlocked` now patches every cached `['tickets','list',*]` query optimistically via `setQueriesData`/rolls back via `getQueriesData` snapshots — this was previously a silent no-op against `['tickets']` (exact key), which both degraded the existing list view (updates only appeared after the `onSuccess` refetch) and would have completely broken optimistic board drag-and-drop rollback

## Task Commits

Each task was committed atomically:

1. **Task 1: Install @dnd-kit/core** - `01788f0` (chore)
2. **Task 2: Pure bucketTickets() projection + tests** - `5457cce` (test, RED) → `48ca734` (feat, GREEN)
3. **Task 3: Fix useMarkBlocked optimistic list-cache key (Pitfall 1)** - `96efc0a` (test, RED) → `11eef1f` (fix, GREEN)

_TDD tasks (2 and 3) each have a RED test commit followed by a GREEN implementation commit, per the TDD execution flow._

## Files Created/Modified
- `frontend/package.json` / `frontend/package-lock.json` - added `@dnd-kit/core@^6.3.1`
- `frontend/src/components/tickets/bucket-tickets.ts` - pure `bucketTickets()` fn, `COLUMN_ORDER`, `COLUMN_LABELS`, `ColumnKey` type
- `frontend/src/components/tickets/bucket-tickets.test.ts` - 9 unit tests covering every behavior bullet in the plan
- `frontend/src/lib/queries/use-mark-blocked.ts` - `onMutate`/`onError` switched from exact `setQueryData(['tickets'])`/`getQueryData` to fuzzy `setQueriesData({queryKey:['tickets','list']})`/`getQueriesData` for the list-cache half of the patch; byId patch, `onSuccess` invalidation, and the `{blocked, blocked_reason}`-only mutation body (T-13-23) are unchanged
- `frontend/src/lib/queries/use-mark-blocked.test.ts` - regression guard: seeds a `['tickets','list',{filters,page,view}]` cache, asserts the in-flight `onMutate` flip, the `onError` rollback of both list and byId caches, and the mass-assignment-safe body shape

## Decisions Made
- `--legacy-peer-deps` was required for the install despite the plan's expectation of a clean plain install — `@dnd-kit/core@6.3.1`'s own peer range (`react >=16.8.0`) is satisfied by React 19, but the pre-existing `lucide-react@0.383.0` peer `react@^18` conflict (already flagged in STATE.md from Phase 15-01) blocks any `npm install` on this tree without the flag. Using it here is consistent with existing project convention.
- `use-mark-blocked.test.ts` needed `React.createElement` (not JSX) to stay valid as a `.ts` file per the plan's exact filename — JSX syntax requires a `.tsx` extension, and renaming would have deviated from the plan's file list.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `npm install @dnd-kit/core@6.3.1` failed without `--legacy-peer-deps`**
- **Found during:** Task 1
- **Issue:** The plan's action text said `--legacy-peer-deps` should NOT be needed since dnd-kit's own peer range accepts React 19. In practice `npm install` failed with `ERESOLVE` because the pre-existing `lucide-react@0.383.0` (peer `react@^16.5.1||^17||^18`) conflict blocks resolution of the whole dependency tree for ANY new install, not just packages whose own peer range is React-19-compatible.
- **Fix:** Ran `npm install @dnd-kit/core@6.3.1 --legacy-peer-deps` instead (the orchestrator's plan notes for this phase also called this out as the expected approach, consistent with Phase 15-01 precedent).
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Verification:** `node -e "require('@dnd-kit/core')"` exits 0; `grep '@dnd-kit'` shows only `@dnd-kit/core`, no `sortable`.
- **Committed in:** `01788f0` (Task 1 commit)

**2. [Rule 1 - Bug] `use-mark-blocked.test.ts` failed to parse JSX in a `.ts` file**
- **Found during:** Task 3
- **Issue:** The test wrapper (`<QueryClientProvider client={qc}>{children}</QueryClientProvider>`) used JSX syntax, but the plan specifies the file as `use-mark-blocked.test.ts` (not `.tsx`). Vite's oxc transform rejected the JSX in a `.ts` file with a parse error.
- **Fix:** Replaced the JSX wrapper with `createElement(QueryClientProvider, { client: qc }, children)` from `react`, keeping the plan-specified `.ts` extension intact.
- **Files modified:** `frontend/src/lib/queries/use-mark-blocked.test.ts`
- **Verification:** `npx vitest run src/lib/queries/use-mark-blocked.test.ts` exits 0 (3/3 tests pass).
- **Committed in:** `96efc0a` (RED test commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were necessary to complete the plan's own stated deliverables exactly as specified (file names, install target). No scope creep — no new files, no architectural changes.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `@dnd-kit/core` is installed and ready for `DndContext`/`useDraggable`/`useDroppable` in the next wave's board component (18-01+).
- `bucketTickets()` is a proven, board-ready projection — the board component can import it directly with no further hardening.
- `useMarkBlocked` now correctly reprojects the board optimistically on block/unblock and rolls back on error — the single biggest architectural prerequisite for UX-D-01-02 (optimistic drag persistence) is satisfied.
- No blockers for Wave 1 (board rendering) or later waves (drag interaction, reason prompt, mobile degradation).

---
*Phase: 18-tickets-kanban-board*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created files confirmed present on disk (bucket-tickets.ts, bucket-tickets.test.ts, use-mark-blocked.test.ts, this SUMMARY.md). All 5 task commits (`01788f0`, `5457cce`, `48ca734`, `96efc0a`, `11eef1f`) confirmed present in `git log`.
