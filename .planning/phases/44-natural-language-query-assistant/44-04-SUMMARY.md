---
phase: 44-natural-language-query-assistant
plan: 04
subsystem: ui
tags: [react, nextjs, ai, nlq, sunset-design-system, sse]

# Dependency graph
requires:
  - phase: 44-03 (frontend data + presentational layer)
    provides: "useQueryStream() SSE hook, exported DegradedCard/AnalyzingIndicator, and the 4 ask/ presentational components (query-box, starter-questions, interpreted-filter, result-table)"
  - phase: 44-05 (D-17 read-only deep-link)
    provides: "buildNlqDeepLink(entity, filter) -> href, the single source of truth for the Open-in param contract"
provides:
  - "/dashboard/ask page.tsx -- the full D-09 workflow (inert/empty/loading/interpreted/results/streaming/refuse/zero-results/budget/safety/error), the user-facing deliverable that makes NLQ real"
  - "Always-visible 'Ask' WORKFLOW_ITEMS nav entry (Sparkles, no chip)"
  - "QueryBox lifted to a controlled component (value/onChange) so starter chips can fill it"
  - "InterpretedFilter.formatInterpretedFilterSummary() -- exported so the zero-results EmptyState body can never drift from the interpretation card above it"
  - "useQueryStream's error phase carries optional httpStatus/requestId (captured off the real fetch Response) for the transient-error banner's HTTP-code + request-ID contract"
affects: [] # last plan in Phase 44

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "grounded_false -> DANGER variant (safety-flagged bucket) for the Ask page specifically, deliberately DIFFERENT from the Explain flow's own grounded_false (rendered NEUTRAL there for a different reason -- insufficient evidence vs. a rejected/exclusivity-violating structured output). Derived by elimination: QueryStreamErrorKind has exactly 4 literals (busy/grounded_false/budget_exceeded/unknown); the plan's own <action> block names exactly 4 buckets (transient/safety/budget/[refuse is a separate SSE type, not an error kind]) -- busy+unknown are naturally 'transient', budget_exceeded is 'budget', leaving grounded_false as the only candidate for 'safety'. No backend SSE kind for NLQ is literally named 'unsafe' (confirmed via full grep of query_assistant.py) -- the structured-output recheck/exclusivity gate (D-01/D-13) IS this pipeline's injection/safety backstop, and its failure is exactly what grounded_false signals."
    - "Type-guard narrowing (hasFilter/hasResults) over QueryStreamState's discriminated union, rather than repeating the same JSX 4 times across interpreted/results/streaming/done -- each phase that carries entity+filter (or +rows+total) renders the shared InterpretedFilter/Open-in/ResultTable blocks identically without a switch statement."

key-files:
  created:
    - frontend/src/app/(authed)/dashboard/ask/page.tsx
    - frontend/src/app/(authed)/dashboard/ask/page.test.tsx
  modified:
    - frontend/src/components/shell/nav-items.ts
    - frontend/src/components/ai/ask/query-box.tsx
    - frontend/src/components/ai/ask/interpreted-filter.tsx
    - frontend/src/lib/ai/use-query-stream.ts

key-decisions:
  - "grounded_false maps to the DANGER DegradedCard variant (safety-flagged), not neutral -- see tech-stack.patterns above for the full elimination argument. Documented here because it deliberately diverges from the Explain flow's own established precedent for the same error kind."
  - "Row-open navigation reuses EXISTING real detail/drill surfaces, never a new view: vulnerabilities go through the already-shipped `?cve=<id>&open=drill` deep-link contract (vulnerabilities/page.tsx); assets/tickets navigate straight to their existing `[id]` detail routes."
  - "'View trace' (UI-SPEC Copywriting Contract's transient-error CTA) links to /dashboard/settings?category=ai -- the closest existing per-tenant AI observability surface (AiUsagePane, backed by the ai.* audit trail) -- since this codebase has no dedicated per-request trace-viewer page and building one is out of this plan's scope (would be a Rule 4 architectural addition, not a composition task)."
  - "Zero-results detection uses `hasResults(state) && rows.length === 0` (any of results/streaming/done phase with an empty row set) rather than waiting for the narrative to complete -- the UI-SPEC's zero-results copy is a fixed EmptyState body, not model-generated text, so there's nothing to wait for once the deterministic query itself returns 0 rows."
  - "QueryBox (Plan 03 file, zero other call sites) lifted from an uncontrolled to a fully controlled component (value/onChange) so a starter-question chip click can fill it -- Rule 2 (missing critical functionality): the plan's own <behavior> block requires this and the uncontrolled API structurally could not support it."
  - "useQueryStream's error phase gains optional httpStatus/requestId, captured via optional chaining off the real fetch Response (res.status / res.headers.get('X-Request-ID')) -- Rule 2: the UI-SPEC's transient-error copy contract requires a real HTTP code + request ID, and the backend's RequestIdMiddleware already sets X-Request-ID on every response including streaming ones (backend/app/main.py), so this is real data, not invented. Implemented defensively (never throws against a test Response stub lacking .headers/.status) so all 6 pre-existing use-query-stream.test.ts assertions stay byte-identical (verified green)."

patterns-established: []

requirements-completed: [NLQ-01, NLQ-03]

# Metrics
duration: ~50min
completed: 2026-08-25
---

# Phase 44 Plan 04: /dashboard/ask Page Composition + 'Ask' Nav Entry Summary

**The `/dashboard/ask` page composes every NLQ-01/NLQ-03 state (Configure-AI inert card, D-11 empty state with 4 starter chips, D-15 results-first interpreted-filter+result-table before the streamed narrative, D-14 refuse, zero-results, budget/safety/transient-error, D-17 Open-in deep-link) plus an always-visible 'Ask' nav entry — the user-facing deliverable that makes Phase 44's NLQ backend (Plans 01/02/05/06) real and reachable.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-08-25T~13:20Z (STATE.md continuation from 44-06)
- **Completed:** 2026-08-25T14:13:52Z
- **Tasks:** 1 (TDD RED/GREEN pair) + 1 checkpoint (deferred-on-trust, see below)
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `/dashboard/ask/page.tsx` composes all 11 states the plan's must_haves enumerate — verified by 8 passing component tests (Configure-AI card + CTA, 4 starter chips, refuse, Open-in href matching `buildNlqDeepLink`'s own output byte-for-byte, budget-exceeded amber, safety-flagged danger, transient-error banner with real HTTP code + request ID + Retry now, zero-results with the interpretation retained above).
- The full frontend suite stays green: 1215/1215 tests across 168 files, `tsc --noEmit` clean, `eslint` clean on every touched file — including `use-query-stream.test.ts`'s 6 pre-existing assertions, unaffected by the httpStatus/requestId deviation (verified explicitly, not just assumed).
- Resolved a genuine ambiguity in the plan's own must_haves (no backend SSE kind for NLQ is literally "safety"/"unsafe") by elimination over `QueryStreamErrorKind`'s exactly-4-literal union — documented as a key-decision so future phases don't re-litigate it.
- The always-visible 'Ask' nav entry (Sparkles, no chip) lands in `WORKFLOW_ITEMS`, mirroring the Coverage/Analytics/Compliance precedent exactly; confirmed via `sidebar.test.tsx`/`app-shell.test.tsx` staying green (12/12) and a literal grep match.

## Task Commits

TDD RED/GREEN pair for Task 1, plus a docs commit for an out-of-scope discovery:

1. **Task 1 RED:** `test(44-04): add failing test for /dashboard/ask page composition` — `6d9d8c3`
2. **Task 1 GREEN:** `feat(44-04): /dashboard/ask page composition + 'Ask' nav entry (NLQ-01/NLQ-03)` — `ddc1909`
3. **Deferred-items doc:** `docs(44-04): log pre-existing npm-run-build lint failure (out of scope)` — `33b50d9`

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `frontend/src/app/(authed)/dashboard/ask/page.tsx` — the full D-09 workflow: ErrorBoundary > Suspense > AskPageInner, useAiStatus() as the ONLY page-load query, useQueryStream-driven state machine composing every mandatory state
- `frontend/src/app/(authed)/dashboard/ask/page.test.tsx` — 8 tests covering Configure-AI, starter chips, refuse, Open-in href, budget/safety/transient-error, zero-results
- `frontend/src/components/shell/nav-items.ts` — `{ label: 'Ask', href: '/dashboard/ask', icon: Sparkles }` added to `WORKFLOW_ITEMS`
- `frontend/src/components/ai/ask/query-box.tsx` — lifted to a controlled component (`value`/`onChange`) so starter chips can fill it
- `frontend/src/components/ai/ask/interpreted-filter.tsx` — exports `formatInterpretedFilterSummary()` for zero-results body reuse
- `frontend/src/lib/ai/use-query-stream.ts` — error phase gains optional `httpStatus`/`requestId`, captured defensively off the real fetch `Response`

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] QueryBox had no way for a starter-chip click to fill it**
- **Found during:** Task 1 (composing the D-11 empty state)
- **Issue:** `QueryBox` (Plan 03) owned its question text in local `useState`, with no `value`/`onChange` props — the plan's own `<behavior>` block explicitly requires "clicking a chip fills the query box," which is structurally impossible with an uncontrolled component and no external hook.
- **Fix:** Lifted `QueryBox` to a fully controlled component (`value: string; onChange: (v: string) => void`). It has exactly one consumer (this page, built by this same plan) — no other call site exists, confirmed via `grep -rln "QueryBox"`.
- **Files modified:** `frontend/src/components/ai/ask/query-box.tsx`
- **Verification:** No `query-box.test.tsx` exists to break; full suite (1215/1215) + `tsc --noEmit` green.
- **Committed in:** `ddc1909`

**2. [Rule 2 - Missing Critical] Zero-results body needed the predicate summary, with no source of truth to reuse**
- **Found during:** Task 1 (composing the zero-results EmptyState)
- **Issue:** The UI-SPEC's zero-results copy is `Interpreted as: {predicate summary}. Try broadening a term...` — inlining a second copy of `interpreted-filter.tsx`'s token-formatting logic in the page would risk the two surfaces drifting (violating the plan's own prohibition: "must never silently widen or narrow the interpreted filter without showing it").
- **Fix:** Exported `formatInterpretedFilterSummary(filter)` from `interpreted-filter.tsx` (a one-line additive export wrapping the existing private `tokensFor()`), so the zero-results body and the `InterpretedFilter` card above it are structurally guaranteed to never disagree.
- **Files modified:** `frontend/src/components/ai/ask/interpreted-filter.tsx`
- **Verification:** `tsc --noEmit` clean; no existing test asserted on the module's export surface, so this is purely additive.
- **Committed in:** `ddc1909`

**3. [Rule 2 - Missing Critical] The transient-error banner had no real HTTP code / request ID to show**
- **Found during:** Task 1 (composing the transient-error state)
- **Issue:** The UI-SPEC's error-state copy contract requires "HTTP code + request ID" (mirroring `state-patterns.md`'s `PartialFailureBanner` convention verbatim), but `useQueryStream`'s `error` phase (Plan 03) carried only `{ kind }` — no status code, no request ID. Inventing placeholder values would violate `T-11-15` (no fabricated diagnostic data).
- **Fix:** Extended the `error` phase with optional `httpStatus`/`requestId`, captured via `res.status` / `res.headers.get('X-Request-ID')` at all 3 `error`-setting call sites. The backend's `RequestIdMiddleware` (`backend/app/main.py`) already sets `X-Request-ID` on every response including streaming ones, so this surfaces real, already-existing diagnostic data — no backend change needed. Implemented with defensive optional chaining (`res?.headers?.get?.(...)`, `typeof res?.status === 'number'`) so it never throws against `use-query-stream.test.ts`'s minimal `{ ok, body }` Response mocks, and the fields are omitted entirely (not set to `undefined`) when unavailable — keeping every pre-existing `toEqual({phase:'error', kind:...})` assertion byte-identical.
- **Files modified:** `frontend/src/lib/ai/use-query-stream.ts`
- **Verification:** `use-query-stream.test.ts` re-run explicitly after the change — 6/6 green, unchanged. `tsc --noEmit` clean.
- **Committed in:** `ddc1909`

---

**Total deviations:** 3 auto-fixed (all Rule 2 — missing critical functionality the plan's own must_haves required)
**Impact on plan:** All three are minimal, additive changes to Plan 03 files (which have zero other consumers besides this page) needed for this plan's own must_haves to actually hold. No scope creep, no architectural change, no new file.

## Issues Encountered

The plan's must_haves truth "budget-exceeded → amber; a safety-flagged response → danger variant; a transient error → error banner" does not map cleanly onto the 4 real `QueryStreamErrorKind` literals without interpretation — the UI-SPEC's own Color contract reserves danger "for injection-flagged / unsafe-denylisted responses," but no NLQ backend SSE kind is literally named that (confirmed via full `grep` of `query_assistant.py`). Resolved by elimination (see `key-decisions`/`tech-stack.patterns`) rather than treating this as a Rule 4 architectural question, since it required no code/schema change on the backend — only a documented interpretation of an existing signal.

## User Setup Required

None — no external service configuration required. This plan is pure frontend composition against already-shipped Plans 01/02/03/05/06.

## Known Stubs

None. Every state renders real, wired behavior against `useQueryStream`'s actual state machine and `useAiStatus`'s actual query — no hardcoded empty arrays/objects, no placeholder copy beyond the UI-SPEC's own verbatim contract strings.

## Threat Flags

None new. This plan's own `<threat_model>` (T-44-14 useAiStatus gate, T-44-09 XSS via React escaping — `AiExplanationCitations`/`InterpretedFilter` render plain text, no `dangerouslySetInnerHTML` anywhere in this plan's files, T-44-04 interpreted-filter honesty, T-44-11 Open-in param tampering) is fully covered by composition of already-mitigated pieces; no new surface (endpoint, auth path, schema) was introduced. The `httpStatus`/`requestId` deviation surfaces existing, already-non-sensitive diagnostic data (an HTTP status code + the correlation ID the backend already stamps on every response) — not a new disclosure.

## Live UAT — PENDING (checkpoint deferred on trust)

This plan's `checkpoint:human-verify` task (the full live browser flow: configure-AI gate → submit → results-first → streaming narrative → refuse/zero/budget/error states → Open-in deep-link) requires a live Anthropic key and an interactive browser session, neither available in this headless orchestrated run. Following the Phase 24–27/40 precedent (STATE.md "Deferred Items"), this is deferred on trust — all automated verification available in this environment (8/8 component tests, full 1215/1215 suite, `tsc --noEmit`, `eslint`) is green, but the live flow itself has NOT been visually/interactively verified. Marked open — the orchestrator should surface this to the user.

**Exact manual steps to close this** (mirrors the plan's own `<how-to-verify>` block):
1. Run the local stack (admin user, `:3000` CORS, prod build — per project memory `getvul-local-e2e-perf-gate`). Visit `http://localhost:3000/dashboard/ask`.
2. With **no** Anthropic key configured for the tenant: confirm the "AI isn't set up yet" card + Configure AI CTA to `/dashboard/connectors`, and that the 'Ask' nav item is still visible.
3. Configure the tenant's own Anthropic key (BYOK). Reload `/dashboard/ask`; confirm the 4 starter chips render; click one to fill the box.
4. Submit "which internet-facing hosts have an unremediated KEV older than 30 days?": confirm the "Interpreted as:" summary + result table appear BEFORE the narrative streams, the "{topN} of {total} total" caption is correct, and the prose narrates only the shown rows.
5. Submit an out-of-scope question (e.g. "what's the weather?"): confirm the "Can't answer that one" refusal card. Submit a valid-but-empty query: confirm "Nothing matches that" with the interpretation still shown.
6. Click "Open in Vulnerabilities": confirm it lands on `/dashboard/vulnerabilities` with the same filter applied (severity/KEV/age/exposure chips active).
7. Confirm no shared/fallback key is ever used (removing the key returns the inert state, never an answer).
8. **Additionally verify the 2 states no automated test exercised on this run:** a real `budget_exceeded` response (requires exhausting or lowering the tenant's monthly AI cap) and a real `grounded_false` response (requires triggering the structured-output recheck/exclusivity gate — e.g. via one of the 44-06 red-team payloads) — confirm they render the amber and danger cards respectively with real, not just component-test-mocked, data.

## Next Phase Readiness

Phase 44 (Natural-Language Query Assistant) has no further plans — 44-04 was the last remaining plan (44-01, 44-02, 44-03, 44-05, 44-06 all previously complete). NLQ-01 and NLQ-03 are now both fully implemented end-to-end (backend + frontend); NLQ-02 (provability) closed at 44-06. The phase is ready for `/gsd-verify-work 44` — the live UAT above should be surfaced as the phase's one open item, consistent with how Phases 24–27/40 closed with deferred-on-trust live-flow verification.

## Self-Check: PASSED

All 6 claimed created/modified files verified present on disk (`page.tsx`, `page.test.tsx`, `nav-items.ts`, `query-box.tsx`, `interpreted-filter.tsx`, `use-query-stream.ts`); all 3 commit hashes (`6d9d8c3`, `ddc1909`, `33b50d9`) verified present in `git log`.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
