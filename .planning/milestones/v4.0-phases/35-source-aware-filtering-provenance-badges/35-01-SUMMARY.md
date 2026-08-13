---
phase: 35-source-aware-filtering-provenance-badges
plan: 01
subsystem: api
tags: [sqlalchemy, postgres-array, fastapi, pydantic, query-batching, tdd]

# Dependency graph
requires:
  - phase: 30-vulnerability-correlation
    provides: "VulnerabilityCorrelation.sources GIN-indexed ARRAY + sources_count (034_add_correlation_sources)"
  - phase: 33-risk-exposure-scoring
    provides: "risk_exposure_service.py:320-345 bulk-dict-lookup batching precedent (the pattern this plan extends page-scoped)"
provides:
  - "VulnerabilityFilter.source_mode: Literal['or','and'] wired end-to-end (router Query param -> schema -> service)"
  - "_apply_filters OR/AND correlation-array branch (sources.overlap `&&` / sources.contains `@>`), replacing the old per-row Vulnerability.source.in_()"
  - "list_vulnerabilities page-scoped batched provenance fetch (tuple_(cve_id,asset_id).in_(page_keys)) populating VulnerabilitySummary.sources/sources_count with zero N+1"
  - "backend/tests/query_count.py — reusable before_cursor_execute statement-counting harness"
affects: [35-02-vuln-ui, 35-03-assets, 35-04-cspm-tickets, 35-05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Page-scoped tuple_(...).in_(keys) batched provenance fetch (extends risk_exposure_service.py's tenant-wide bulk-dict precedent to be page-scoped for interactive list endpoints)"
    - "SQLAlchemy before_cursor_execute engine-level statement-count context manager for SRC-08 no-N+1 proof"
    - "Literal['or','and'] source_mode filter field mirroring the existing order: Literal['asc','desc'] shape"

key-files:
  created:
    - backend/tests/query_count.py
    - backend/tests/test_source_filtering.py
  modified:
    - backend/app/vulnerabilities/schemas.py
    - backend/app/vulnerabilities/service.py
    - backend/app/vulnerabilities/router.py

key-decisions:
  - "tuple_(cve_id, asset_id).in_(subquery) compiles cleanly against asyncpg — no EXISTS fallback needed (verified directly, not just assumed)."
  - "Observed list_vulnerabilities statement count: 4 (count query + tenant scalar fetch + data query + one batched correlation query), identical for page_size=5 and page_size=50 — proves SRC-08 page-size invariance."
  - "AND with fewer than 2 selected sources is a documented no-op (falls into the OR branch) — matches Pitfall 1's recommended convention, verified by test_and_with_single_source_is_or."
  - "The query-count harness attaches to engine.sync_engine (engine-wide), so it also captures unrelated concurrent background work (e.g. a fire-and-forget EPSS-refresh task from sibling tests sharing the session-scoped event loop). Fixed by filtering counted statements to the SUT's own tables at the call site, not by changing the harness's public API — Plans 03/04 reusing query_count.py should apply the same table-filter discipline in their own query-count assertions."

patterns-established:
  - "query_count.py public API: `from tests.query_count import count_queries; with count_queries() as statements: ...` — yields a plain list of raw SQL statement strings accumulated for the duration of the `with` block. Reused verbatim by Plans 03 (Assets) and 04 (CSPM + Tickets)."
  - "Page-scoped batching shape for Plans 03/04 to mirror: run the primary paginated query, collect natural keys from ONLY the page's rows, one extra tuple_(...).in_(keys) query scoped by tenant_id, build a dict, O(1) lookup per row when assembling the response."

requirements-completed: [SRC-01, SRC-02, SRC-03, SRC-04, SRC-08]

coverage:
  - id: D1
    description: "OR default (no source_mode) returns the union of selected sources, reaching single-source findings that have no correlation row"
    requirement: "SRC-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_or_default_returns_union"
        status: pass
    human_judgment: false
  - id: D2
    description: "AND toggle (source_mode=and) matches only findings corroborated by ALL selected sources via the correlation ARRAY @>, structurally excluding single-source findings"
    requirement: "SRC-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_and_toggle_requires_corroboration"
        status: pass
    human_judgment: false
  - id: D3
    description: "AND with fewer than 2 selected sources is a documented no-op, behaving identically to OR"
    requirement: "SRC-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_and_with_single_source_is_or"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every VulnerabilitySummary list row carries sources/sources_count, defaulting to [vuln.source]/1 when no correlation row exists — never null/unknown"
    requirement: "SRC-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_summary_carries_sources"
        status: pass
    human_judgment: false
  - id: D5
    description: "source_mode is a Pydantic Literal['or','and'] — any other value returns 422"
    requirement: "SRC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_bad_source_mode_422"
        status: pass
    human_judgment: false
  - id: D6
    description: "list_vulnerabilities issues a FIXED statement count independent of page size (exactly one batched correlation query, never per-row)"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_filtering.py#test_list_query_count_is_page_size_invariant"
        status: pass
    human_judgment: false
  - id: D7
    description: "Regression: existing single-value OR source filter behavior (test_vuln_source_filter.py) preserved"
    verification:
      - kind: integration
        ref: "backend/tests/test_vuln_source_filter.py (4 tests)"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-08-12
status: complete
---

# Phase 35 Plan 01: Vulnerabilities OR/AND Source Filter + Batched Provenance (Lead Tracer) Summary

**Vulnerabilities list filter now branches on the Phase-30 correlation ARRAY (`&&` OR-default / `@>` AND-toggle) instead of the per-row `Vulnerability.source.in_()`, and every list row carries `sources`/`sources_count` via a new page-scoped, tenant-scoped `tuple_(...).in_()` batched fetch proven no-N+1 by a new `before_cursor_execute` query-count harness.**

## Performance

- **Duration:** 28 min
- **Started:** 2026-08-12T14:04:00+03:00 (approx, context load)
- **Completed:** 2026-08-12T14:32:38+03:00
- **Tasks:** 2 (RED, GREEN)
- **Files modified:** 5 (2 new, 3 modified)

## Accomplishments

- Replaced the pre-Phase-35 per-row `Vulnerability.source.in_(filters.source)` filter with a correlation-ARRAY OR/AND branch: `sources.overlap(...)` (`&&`, OR default, unioned with the direct-source fallback for single-source findings that have no correlation row) vs `sources.contains(...)` (`@>`, AND toggle, structurally excludes single-source findings when 2+ sources are selected).
- Added `source_mode: Literal["or","and"] = "or"` to `VulnerabilityFilter`, bound as an explicit `Query(...)` param in the router (this router builds the filter from explicit params, not `Depends(Filter)` — without the router binding, `?source_mode=and` would be silently dropped and the `@>` branch would be unreachable via HTTP).
- Added `sources: list[str]` / `sources_count: int` to `VulnerabilitySummary` — the SRC-01 provenance data spine, filled via a new page-scoped batched correlation fetch in `list_vulnerabilities` (runs after the paginated data query, `tuple_(cve_id, asset_id).in_(page_keys)`, tenant-scoped per T-35-01), never a per-row query.
- Built `backend/tests/query_count.py` from scratch — a `before_cursor_execute` context-manager statement counter, the first query-count-assertion harness in this codebase — and proved `list_vulnerabilities` issues a fixed 4 statements regardless of page size (5-row vs 50-row page).
- Verified `tuple_(...).in_(subquery)` compiles cleanly against asyncpg with no EXISTS fallback required.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — query-count harness + Vulnerabilities OR/AND + sources-response tests** - `02cf988` (test)
2. **Task 2: GREEN — source_mode + sources schema fields + OR/AND correlation-array branch + page-scoped batched provenance** - `0f4be0f` (feat)

_No plan-metadata commit yet — created below._

## Files Created/Modified

- `backend/tests/query_count.py` - new `count_queries()` context manager, engine-level `before_cursor_execute` listener; public API reused by Plans 03/04
- `backend/tests/test_source_filtering.py` - 6 tests: OR-default union, AND-toggle corroboration, AND-with-1-source no-op, sources/sources_count response shape, 422 validation, page-size-invariant query count
- `backend/app/vulnerabilities/schemas.py` - `VulnerabilityFilter.source_mode`, `VulnerabilitySummary.sources`/`sources_count`
- `backend/app/vulnerabilities/service.py` - `_apply_filters` OR/AND correlation-array branch; `list_vulnerabilities` page-scoped batched provenance fetch
- `backend/app/vulnerabilities/router.py` - `source_mode` Query param bound into `VulnerabilityFilter(...)`

## Decisions Made

- `tuple_(cve_id, asset_id).in_(subquery)` compiles against asyncpg without issue — confirmed directly by running the tests, not assumed. No EXISTS-correlated-subquery fallback was needed (the RESEARCH-flagged impl-detail risk did not materialize).
- Observed `list_vulnerabilities` statement count is **4** per page load (count query, tenant scalar fetch for the risk-exposure cutover flag, data query, batched correlation query) — identical for `page_size=5` and `page_size=50`. This is the concrete number Plans 03/04 should expect their own equivalents to land near (their own primary+batch shape will differ but the "invariant across page size" property is the load-bearing assertion).
- AND-mode with fewer than 2 selected sources is a documented no-op (falls into the OR branch, matching Pitfall 1's recommended convention) — proven, not just documented, by `test_and_with_single_source_is_or`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a genuine flake in the new query-count test caused by the harness's engine-wide listener scope**
- **Found during:** Task 2 (GREEN) — running `test_list_query_count_is_page_size_invariant` repeatedly (not just once) surfaced an intermittent failure: `page_size=5 issued 4, page_size=50 issued 5`.
- **Issue:** `count_queries()` attaches `before_cursor_execute` to `engine.sync_engine`, which is engine-wide, not scoped to the calling test's own session/connection. This test suite runs with `asyncio_default_test_loop_scope=session` (all tests share one event loop), and sibling tests in the same file that use the `client` fixture start the app lifespan's fire-and-forget EPSS-cache-refresh background task. That task can still be in flight and interleave an unrelated `INSERT INTO epss_scores` during a later test's `count_queries()` window — a real, reproducible ~1-in-3 flake (confirmed via 5 consecutive full-file runs after the fix, all green; before the fix, 2 of 3 runs failed).
- **Fix:** Filtered the statements captured by `count_queries()` down to those referencing this SUT's own tables (`vulnerabilities`, `vulnerability_correlations`, `tenants`) before asserting page-size invariance, at the call site in the test — not by changing `query_count.py`'s public API (keeps the harness's documented contract, from the plan's interfaces block, intact for Plans 03/04 to reuse verbatim).
- **Files modified:** `backend/tests/test_source_filtering.py`
- **Verification:** 5 consecutive full-file `pytest tests/test_source_filtering.py` runs, all green (previously 2 of 3 failed on this exact assertion).
- **Committed in:** `0f4be0f` (part of the Task 2 GREEN commit — the test file's final state already includes this fix; RED commit `02cf988` predates the flake's discovery).
- **Note for Plans 03/04:** any new query-count assertion reusing `query_count.py` in the same test session should apply the same inclusive table-filter discipline before asserting exact counts, since the harness is intentionally engine-wide (not session/connection-scoped) per its documented contract.

---

**Total deviations:** 1 auto-fixed (1 bug fix, discovered and resolved within Task 2's own new test file — no pre-existing code touched).
**Impact on plan:** Necessary for the new harness's test to be deterministic; no scope creep, no change to any interface described in the plan's `<interfaces>` block.

## Issues Encountered

None beyond the flake documented above.

## User Setup Required

None - no external service configuration required. No migration required (confirmed: this plan only reads existing columns from `vulnerability_correlations`, added at alembic `034_add_correlation_sources`; current head remains `044_add_risk_backfill_job`).

## Next Phase Readiness

- `backend/tests/query_count.py`'s `count_queries()` context manager is ready for Plans 03 (Assets) and 04 (CSPM + Tickets) to import verbatim: `from tests.query_count import count_queries`.
- The page-scoped `tuple_(...).in_(page_keys)` batching shape (fetch primary page rows first, collect natural keys from ONLY that page, one tenant-scoped batched query, dict lookup) is the concrete pattern for Plans 03/04's own provenance/grouping queries to mirror — landed and regression-tested here.
- `source_mode` is now a real, HTTP-reachable, Literal-validated filter axis on Vulnerabilities — Plan 02 (vuln UI) can wire the frontend chip-bar's AND toggle against this contract with no further backend changes.
- No blockers. Full regression suite for touched files green: `test_vuln_source_filter.py` (4/4), `test_risk_exposure_service.py` (12/12), `test_vuln_facets.py` (6/6), `test_vuln_group_host.py` (6/6), `test_vuln_sort.py` (7/7), `test_vulnerabilities.py` (6/6), `test_dashboard_tiles.py` (5/5), `test_top_vuln.py` (2/2), `test_vulnerability_enrichment.py` (2/2). `ruff check` + `ruff format --check` clean on all touched files. `mypy` error count on touched files unchanged from baseline (158 before, 158 after — no new type-debt introduced).

---
*Phase: 35-source-aware-filtering-provenance-badges*
*Completed: 2026-08-12*

## Self-Check: PASSED

All 5 created/modified files verified present on disk; both task commits (`02cf988`, `0f4be0f`) verified present in `git log --oneline --all`.
