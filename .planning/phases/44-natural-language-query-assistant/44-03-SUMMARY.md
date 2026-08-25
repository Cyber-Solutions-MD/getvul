---
phase: 44-natural-language-query-assistant
plan: 03
subsystem: frontend
tags: [react, sse, ai, nlq, frontend-hooks, sunset-design-system]

# Dependency graph
requires:
  - phase: 44-01/44-02 (NLQ backend)
    provides: "POST /api/v1/ai/query SSE contract (interpreted->results->summary_delta*->done, plus no_key/refuse/error{kind}) proven end-to-end for all three entities (vulnerabilities/assets/tickets)"
provides:
  - "useQueryStream() -- body-carrying SSE hook (interpreted -> results -> streaming -> done state machine, D-15 results-first)"
  - "DegradedCard export from ai-explanation-section.tsx -- reusable refusal/budget/safety/configure card"
  - "4 ask/ components: query-box, starter-questions, interpreted-filter, result-table -- each unit-tested, ready for Plan 04's page composition"
affects: [44-04 (Ask page composition), 44-05 (D-17 deep-link)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A NEW sibling streaming hook (useQueryStream) rather than generalizing useExplainStream -- the two differ structurally on the one thing that matters (POST body vs. bodyless-URL-interpolated), so the shared ~50-line frame-parsing loop is copied, not abstracted, keeping each hook's own RawSseEvent union independently extensible (D-15/Pitfall 7)"
    - "Accumulator-carried-forward state machine: once `interpreted` names entity/filter, every later phase (results/streaming/done) carries entity+filter+rows+total forward so a consumer never loses the interpretation while the narrative streams (D-15 results-first, made structurally impossible to violate)"
    - "Entity-dispatch thin wrapper (ResultTable) tested via mocked child primitives -- isolates the DISPATCH decision from VulnTable/AssetsTable/TicketsTable's own already-covered internals (D-08)"
    - "Known-key -> friendly-token map with an explicit unknown-key fallback (interpreted-filter.tsx) -- a future additive predicate is never silently dropped from the analyst-visible summary"

key-files:
  created:
    - frontend/src/lib/ai/use-query-stream.ts
    - frontend/src/lib/ai/use-query-stream.test.ts
    - frontend/src/components/ai/ask/query-box.tsx
    - frontend/src/components/ai/ask/starter-questions.tsx
    - frontend/src/components/ai/ask/interpreted-filter.tsx
    - frontend/src/components/ai/ask/result-table.tsx
    - frontend/src/components/ai/ask/result-table.test.tsx
  modified:
    - frontend/src/components/ai/ai-explanation-section.tsx

key-decisions:
  - "useQueryStream() takes NO resourceType/resourceId at hook-call time (unlike useExplainStream) -- start(question) carries the free-text question instead, since there is no per-record resource to address (the question itself IS the record)"
  - "interpreted-filter.tsx renders a friendly key->token map for the known *FilterInput fields (severity, cisa_kev, exploit_available, age_days_min, asset_internet_facing/internet_facing, sla_breached, asset_hostname, device_category, status) matching the UI-SPEC's own example format exactly, with a generic key=value fallback for any unmapped/future field -- never a silent drop (must_haves prohibition)"
  - "result-table.tsx's VulnTable mount passes a no-op onSort -- the Ask page's result table has no sort UI (D-07's risk-ranked ORDER BY is already server-side and stable); VulnTable's onSort prop is required so a no-op is the correct, zero-behavior-change satisfaction of that contract, not a stub"
  - "result-table.tsx casts the streamed `rows: unknown[]` to each primitive's own row type at the ONE entity-dispatch boundary, mirroring the same cast every existing list page already performs (e.g. vulnerabilities/page.tsx's `q.data.items as VulnTableRow[]`) -- not a new pattern"

patterns-established: []

requirements-completed: []

# Metrics
duration: ~10min (task-commit window; session including design-contract reads longer)
completed: 2026-08-25
---

# Phase 44 Plan 03: Frontend Data + Presentational Layer (useQueryStream + ask/ Components) Summary

**A body-carrying `useQueryStream` SSE hook with a results-first (D-15) state machine, an exported `DegradedCard`, and four sunset-styled `ask/` components (query-box, starter-questions, interpreted-filter, result-table) — all four unit-tested, none composed into a page yet (Plan 04's job).**

## Performance

- **Duration:** ~10 min (commit-to-commit window for the 3 tasks)
- **Started:** 2026-08-25T12:09:18Z
- **Completed:** 2026-08-25T12:19:05Z
- **Tasks:** 3
- **Files modified:** 8 (7 created, 1 modified)

## Accomplishments
- `useQueryStream()` proves the D-15 results-first contract structurally, not just by assertion: `interpreted` and `results` frames drive their own distinct state phases (with entity/filter/rows/total carried forward) BEFORE any `summary_delta`/`done` frame is even read — verified with a controllable-reader test that gates each frame's arrival so the intermediate states are directly observable, not just the final one.
- Proved empirically that Pitfall 7 (the "reuse useExplainStream's bodyless POST unchanged" trap) was avoided: `useQueryStream`'s fetch call is asserted (in `use-query-stream.test.ts`) to carry `Content-Type: application/json` + `body: JSON.stringify({question})` to a FIXED `/api/v1/ai/query` URL — structurally distinct from `useExplainStream`'s bodyless, resourceId-interpolated call.
- `DegradedCard` is now importable from `ai-explanation-section.tsx` with a zero-behavior-change one-line diff (Pitfall 8) — every existing internal call site (no-key, budget-exceeded, unsafe, etc.) is byte-identical, confirmed by the full existing `ai-explanation-section.test.tsx` suite staying green.
- `ResultTable` proves D-08 (never a second table pattern) via a test that mocks the three EXISTING row primitives and asserts the dispatch decision directly — the wrapper itself contains zero table markup of its own.
- All 4 `ask/` components render with sunset design-system tokens only (no freehand hex, `bg-gradient-sunset`/`bg-violet-soft`/`--color-violet-on-soft` reused verbatim) and verbatim UI-SPEC copy (the 4 starter questions, "Interpreted as:", "{topN} of {total} total").

## Task Commits

Each task was committed atomically (TDD RED/GREEN pairs for Tasks 1 and 3):

1. **Task 1 RED:** `test(44-03): add failing test for useQueryStream` — `00d7d24`
2. **Task 1 GREEN:** `feat(44-03): implement useQueryStream hook + export DegradedCard` — `cff37d5`
3. **Task 2:** `feat(44-03): ask/ components -- query-box, starter-questions, interpreted-filter` — `f1986c7`
4. **Task 3 RED:** `test(44-03): add failing test for ResultTable` — `b900f01`
5. **Task 3 GREEN:** `feat(44-03): result-table.tsx -- entity-dispatch thin wrapper (D-08)` — `1d80f5a`

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `frontend/src/lib/ai/use-query-stream.ts` — `useQueryStream()`: POST-body SSE hook, `interpreted -> results -> streaming -> done` + `no_key`/`refuse`/`error{kind}` terminal states
- `frontend/src/lib/ai/use-query-stream.test.ts` — POST-body assertion, results-first ordering (controllable-reader), no_key/refuse/error terminal-state tests
- `frontend/src/components/ai/ai-explanation-section.tsx` — `DegradedCard` now exported (one-line diff)
- `frontend/src/components/ai/ask/query-box.tsx` — bounded (~500-char) free-text input + gradient-sunset "Ask" CTA, char-count-warning mirroring CommentInput
- `frontend/src/components/ai/ask/starter-questions.tsx` — exactly 4 curated UI-SPEC starter-question chips, click-to-fill, EmptyState.Suggestion chrome verbatim
- `frontend/src/components/ai/ask/interpreted-filter.tsx` — D-04 "Interpreted as:" card, mono predicate tokens with a known-key friendly-label map + generic fallback
- `frontend/src/components/ai/ask/result-table.tsx` — D-08 entity-dispatch thin wrapper over VulnTable/AssetsTable/TicketsTable + "{topN} of {total} total" caption
- `frontend/src/components/ai/ask/result-table.test.tsx` — entity-dispatch (mocked primitives), caption, zero-rows-slot tests

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

None — plan executed exactly as written. All 3 tasks, their `<behavior>`/`<action>` blocks, and every `must_haves` truth/backstop were implemented as specified; no Rule 1/2/3 auto-fixes were needed and no architectural (Rule 4) question arose.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan is pure frontend data/presentational code with no new backend/infra surface.

## Known Stubs

None. Every component renders real, wired behavior against its declared props — no hardcoded empty arrays/objects flowing to UI, no placeholder copy. `ResultTable`'s `onSort={() => {}}` passed to `VulnTable` is a deliberate no-op (documented in key-decisions above, not a stub): the Ask page's result table has no sort UI by design (D-07's risk-ranking is server-side and stable), and `VulnTable.onSort` is a required prop that must be satisfied regardless.

## Threat Flags

None — every new surface (the POST body construction, the rendered interpreted-filter/narrative text, the entity-dispatched result rows) is already covered by this plan's own `<threat_model>` (T-44-09 XSS via React's default escaping — no `dangerouslySetInnerHTML` anywhere in this plan's files; T-44-05 DoS/cost via the query-box's ~500-char client cap; T-44-10 info disclosure via the Bearer token living only in the `Authorization` header, never logged or URL-placed).

## Next Phase Readiness
- Plan 04 (Ask page composition) has everything it needs: `useQueryStream()` for the SSE lifecycle, `DegradedCard` for every degraded/refusal/budget/configure-AI state, and all 4 presentational `ask/` components (`QueryBox`, `StarterQuestions`, `InterpretedFilter`, `ResultTable`) ready to wire into the page's empty/loading/error/populated states per `state-patterns.md`.
- `ResultTable`'s `emptyState` prop is intentionally left for Plan 04 to fill with the "Nothing matches that" `EmptyState` (D-S-01) — this plan does not own page-level empty-state composition.
- No blockers. `NlqFilterResponse`'s flat filter shape (all three `*FilterInput` field sets) is now rendered generically by `interpreted-filter.tsx`'s key-map + fallback, so a Plan 02-style additive predicate never requires a frontend change to stay visible.

## Self-Check: PASSED

All 8 claimed created/modified files verified present on disk; all 5 task commit hashes (`00d7d24`, `cff37d5`, `f1986c7`, `b900f01`, `1d80f5a`) verified present in `git log`.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
