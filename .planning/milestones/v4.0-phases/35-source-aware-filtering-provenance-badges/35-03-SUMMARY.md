---
phase: 35-source-aware-filtering-provenance-badges
plan: 03
subsystem: api
tags: [sqlalchemy, postgres-jsonb, fastapi, query-batching, tdd, bug-fix]

# Dependency graph
requires:
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 01
    provides: "backend/tests/query_count.py (before_cursor_execute statement-counting harness) + the OR/AND source_mode pattern to mirror"
provides:
  - "backend/app/assets/constants.py — SCANNER_SOURCES/ENRICHMENT_SOURCES frozenset partition, importable by any Assets-adjacent module"
  - "Assets list filter: OR-default multi-scanner (or_(*contains)), fixing the shipped chained-.where() AND bug, with source_mode=and behind an explicit toggle"
  - "Assets list filter: enrichment_source OR-only facet (JAMF/HUMAANS/INTUNE), structurally partitioned from scanner corroboration semantics (SRC-06)"
  - "Each asset list row carries sources/sources_count, derived in-Python from the already-selected seen_by_sources column — zero extra queries"
  - "ticketing/rule_engine.py::find_matching_assets — same AND-bug fixed to OR-default, same SCANNER_SOURCES clamp"
  - "alembic 045 — GIN index on assets.seen_by_sources"
affects: [35-05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared frozenset source-class partition module (app/assets/constants.py) imported by both a router and an unrelated service module (ticketing/rule_engine.py) to guarantee two independent bug-fix call sites clamp against the IDENTICAL allow-list — prevents drift between the two fixes."
    - "Query-count assertion filtered to the SUT's own table substring (here: 'assets', excluding 'vulnerabilities') to isolate the deliverable under test (the new sources/sources_count fields adding zero queries) from a separate, out-of-scope pre-existing N+1 in the same endpoint (the per-row vuln-count query) — extends Plan 01's documented table-filter discipline."

key-files:
  created:
    - backend/tests/test_asset_source_filter.py
    - backend/app/assets/constants.py
    - backend/alembic/versions/045_add_seen_by_sources_gin.py
  modified:
    - backend/app/assets/router.py
    - backend/app/ticketing/rule_engine.py

key-decisions:
  - "sources_count display rule: count of SCANNER_SOURCES present in seen_by_sources only (enrichment sources like JAMF are excluded from the count, e.g. ['CROWDSTRIKE','JAMF'] -> sources_count=1) — matches the SRC-06 partition philosophy: sources_count answers 'how many scanners corroborate this asset', not 'how many provenance entries exist'. Plan 05's assets-table wiring should read sources_count this way, not len(sources)."
  - "source_mode invalid values 422, not clamp — GET /assets?source_mode=bogus returns 422 (raised via HTTPException in the router body, since this router builds filters from raw Query params rather than a Pydantic Depends(Filter) model, unlike Vulnerabilities' Literal[...] field approach in Plan 01)."
  - "scanner=<value-not-in-SCANNER_SOURCES> (e.g. ?scanner=JAMF) matches NOTHING, not 'no filter applied' — if the raw scanner param is non-empty but every value is clamped out by the SCANNER_SOURCES allow-list, the query gets an explicit false() predicate. This was a deliberate deviation from the plan's own <interfaces> sketch (which only showed the `if scanners:` branch with no else) because leaving scanner filtering silently no-op'd would let enrichment-only assets leak into a scanner-filtered view when a caller sends only enrichment values — the exact SRC-06 leak the test suite explicitly checks for. Same false() fallback applied symmetrically to the new enrichment_source facet for consistency."
  - "Confirmed BOTH router.py (assets/router.py:180-208) AND rule_engine.py (ticketing/rule_engine.py:69-85) are de-bugged to OR-default — verified via `grep -n \"for s in scanners\"` (chained loop now appears ONLY inside the explicit source_mode==\"and\" branch in router.py, and not at all as an unconditional default anywhere) and `grep -n \"or_(\"` (present in both files)."
  - "Migration 045 (ix_assets_seen_by_sources, GIN) landed and is the sole head; upgrade/downgrade/upgrade round-trip verified clean."
  - "Asset-row sources field shape for Plan 05: `\"sources\": list[str]` (== the asset's own seen_by_sources, unfiltered — includes enrichment entries so the UI can render the full provenance picture) + `\"sources_count\": int` (scanner-only count, per the display-rule decision above)."

patterns-established: []

requirements-completed: [SRC-02, SRC-03, SRC-04, SRC-06, SRC-08]

coverage:
  - id: D1
    description: "GET /api/v1/assets?scanner=X,Y (no mode / OR default) returns the UNION of assets seen by either scanner — fixes the shipped chained-.where() AND bug"
    requirement: "SRC-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_or_default_multi_scanner_returns_union"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET .../assets?scanner=X,Y&source_mode=and returns ONLY assets seen by ALL selected scanners (explicit toggle, not the default)"
    requirement: "SRC-04"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_and_toggle_requires_all"
        status: pass
    human_judgment: false
  - id: D3
    description: "Scanner vs enrichment source partition: ?scanner= excludes enrichment-only assets (JAMF etc.); ?enrichment_source= reaches them via a separate OR-only facet"
    requirement: "SRC-06"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_enrichment_does_not_leak_into_scanner_filter"
        status: pass
    human_judgment: false
  - id: D4
    description: "Each asset list row carries sources (its seen_by_sources) and sources_count (scanner-only count)"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_asset_row_carries_sources"
        status: pass
    human_judgment: false
  - id: D5
    description: "source_mode outside {or, and} is rejected with 422"
    requirement: "SRC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_bad_source_mode_422"
        status: pass
    human_judgment: false
  - id: D6
    description: "list_assets issues the same number of assets-table statements for a 5-row and a 50-row page — the new sources/sources_count fields add zero extra queries"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "backend/tests/test_asset_source_filter.py#test_list_assets_query_count_invariant"
        status: pass
    human_judgment: false
  - id: D7
    description: "The identical chained-.where() AND bug in ticketing/rule_engine.py::find_matching_assets is fixed to OR-default with the shared SCANNER_SOURCES clamp"
    verification:
      - kind: integration
        ref: "backend/tests/test_rule_engine.py (9/9, including test_scanner_filter_matches_seen_by_sources — no regression)"
        status: pass
    human_judgment: false
  - id: D8
    description: "Migration 045 adds the seen_by_sources GIN index, single head, symmetric downgrade"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "alembic upgrade head / downgrade -1 / upgrade head round-trip (manual verification)"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-08-12
status: complete
---

# Phase 35 Plan 03: Assets OR/AND Source Filter — Multi-Select-ANDs Bug Fix Summary

**Fixed the shipped Assets source-filter bug where a multi-scanner select silently meant "seen by ALL" instead of "seen by ANY" (`or_(*contains)` OR-default, AND behind an explicit `source_mode=and` toggle), partitioned scanner from enrichment sources so JAMF/HUMAANS/Intune can no longer leak into a `?scanner=` result, added zero-extra-query `sources`/`sources_count` to every list row, fixed the identical bug in the ticket rule engine, and added the GIN index the column never had.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-08-12T11:58:30Z (approx, context load)
- **Completed:** 2026-08-12T12:30:00Z
- **Tasks:** 2 (RED, GREEN)
- **Files modified:** 5 (3 new, 2 modified)

## Accomplishments

- Replaced the pre-Phase-35 chained `.where(Asset.seen_by_sources.contains([s]))` loop in `assets/router.py::list_assets` (which SQLAlchemy silently ANDs across successive `.where()` calls) with an `or_(*contains)` OR-default branch, gating the true-AND ("seen by ALL") behavior behind a new explicit `source_mode=and` query param — this is the literal shipped-bug fix named in CONTEXT.md.
- Added `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` frozensets in a new `app/assets/constants.py`, mirroring `vulnerabilities/service.py:31`'s allow-list convention, and used them to partition the Assets filter: `?scanner=` now clamps out any non-scanner value (enrichment sources can't leak into scanner-corroboration semantics), and a new `?enrichment_source=` OR-only facet reaches JAMF/HUMAANS/Intune-tagged assets separately.
- Added `sources`/`sources_count` to every asset list row, derived purely in-Python from the already-selected `seen_by_sources` column — no new query, proven page-size-invariant by a new query-count assertion (reusing Plan 01's `count_queries()` harness).
- Fixed the byte-for-byte identical AND-bug in `ticketing/rule_engine.py::find_matching_assets` (the rule engine's own asset-matching scanner filter), importing the same `SCANNER_SOURCES` constant so both call sites can never drift apart on what counts as a "scanner."
- Added `alembic/versions/045_add_seen_by_sources_gin.py` — a GIN index on `assets.seen_by_sources`, which had never had one despite being the target of every `.contains()` filter in both fixed call sites; verified single head, clean upgrade/downgrade/upgrade round-trip.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Assets OR-default (bug regression) + AND toggle + partition + query-count tests** - `5aba112` (test)
2. **Task 2: GREEN — constants partition + OR-default fix + AND toggle + enrichment facet + batched sources + rule_engine fix + GIN migration** - `b188ab4` (feat)

_No plan-metadata commit yet — created below._

## Files Created/Modified

- `backend/tests/test_asset_source_filter.py` - 6 tests: OR-default union (the bug regression proof), AND-toggle all-required, enrichment-no-leak partition, sources/sources_count row shape, 422 on bad source_mode, page-size-invariant query count for the `assets` table
- `backend/app/assets/constants.py` - new `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` frozensets, the SRC-06 partition, importable by both fixed call sites
- `backend/app/assets/router.py` - `source_mode`/`enrichment_source` query params; replaced the buggy chained-loop scanner filter with the OR-default `or_(*contains)`/explicit-AND branch; added the `enrichment_source` OR facet; added `sources`/`sources_count` to the list response dict
- `backend/app/ticketing/rule_engine.py` - `find_matching_assets`'s scanner filter: same chained-loop AND bug fixed to `or_(*contains)` OR-default, clamped to the shared `SCANNER_SOURCES`
- `backend/alembic/versions/045_add_seen_by_sources_gin.py` - GIN index on `assets.seen_by_sources` (mirrors 034's correlation-sources GIN index), head 045

## Decisions Made

- **`sources_count` counts scanner sources only.** For an asset with `seen_by_sources=["CROWDSTRIKE","JAMF"]`, `sources_count == 1` (not 2) — it answers "how many scanners corroborate this asset," matching the SRC-06 partition philosophy rather than a raw `len(sources)`. Plan 05's frontend wiring should read it this way.
- **`source_mode` returns 422 on invalid values**, raised explicitly via `HTTPException` in the router body (this router parses raw `Query(...)` params rather than a Pydantic filter model, unlike Vulnerabilities' `Literal[...]` field approach from Plan 01) — not silently clamped to `or`.
- **Deviation from the plan's `<interfaces>` sketch:** when `?scanner=` is given but every value is clamped out by `SCANNER_SOURCES` (e.g. `?scanner=JAMF`), the query now gets an explicit `false()` predicate rather than silently falling through to "no filter applied." The plan's own interfaces snippet only showed the `if scanners:` branch with no `else`; leaving it out would mean a scanner-only request that happens to name only enrichment sources returns the ENTIRE unfiltered asset list — precisely the SRC-06 leak the plan's own test (`test_enrichment_does_not_leak_into_scanner_filter`) checks for. Applied the same `false()` fallback symmetrically to the new `enrichment_source` facet. This is a Rule 1 (bug prevention) / Rule 2 (missing critical correctness) auto-fix within the same task's own scope, not a new file or architecture change.
- **Query-count test scoped to the `assets` table substring**, following Plan 01's own documented table-filter-discipline precedent (its SUMMARY's key-decisions note). `list_assets` has a separate, pre-existing per-row vuln-count query (`vuln_q` inside a `for a in assets:` loop) that is genuinely out of scope for this plan — it predates Phase 35, is unrelated to the `sources`/`sources_count` data spine this plan adds, and fixing it would be a distinct, unplanned N+1 remediation task. Filtering the query-count assertion to `assets`-table statements isolates exactly what this plan's own SRC-08 claim is about (the new fields add zero queries) without silently masking or fixing that separate issue. Logged to `deferred-items.md` below per the scope-boundary protocol.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/2 - Bug/Missing-critical] `false()` fallback when scanner/enrichment clamp empties the list**
- **Found during:** Task 2 (GREEN) — writing the enrichment-leak test surfaced that the plan's own `<interfaces>` sketch (`if scanners: ... ` with no `else`) would leave the query unfiltered when every `?scanner=` value gets clamped out, silently returning ALL tenant assets instead of none — the exact leak SRC-06 exists to prevent.
- **Issue:** A caller sending only enrichment values (or any value outside `SCANNER_SOURCES`) via `?scanner=` would see the full unfiltered asset list, not an empty result.
- **Fix:** Added an explicit `query = query.where(false())` branch when the post-clamp scanner (or enrichment) list is empty but the raw param was non-empty.
- **Files modified:** `backend/app/assets/router.py`
- **Verification:** `test_enrichment_does_not_leak_into_scanner_filter` (asserts `?scanner=JAMF` returns `[]`), plus the ruff `SIM108` follow-up fix (converted to an explicit, commented if/else for readability parity with the scanner block — `noqa: SIM108`).
- **Committed in:** `b188ab4` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug-prevention fix, discovered while implementing the plan's own specified test behavior — no scope creep, no new files beyond what the plan already specified).
**Impact on plan:** Necessary to satisfy the plan's own `test_enrichment_does_not_leak_into_scanner_filter` behavior spec; no change to any interface described in the plan's `<interfaces>` block beyond this one additional `else` branch (applied symmetrically to both the scanner and enrichment_source blocks).

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required. Migration 045 was applied locally as part of verification (`alembic upgrade head`); this needs to run in every other environment (staging/prod) via the normal deploy migration step, same as any other alembic revision.

## Deferred Items

- **Pre-existing N+1 in `list_assets`'s per-row vuln-count query** (`assets/router.py`, the `for a in assets: vuln_q = ...` loop) is NOT page-size-invariant and predates this plan. Out of scope per the SCOPE BOUNDARY rule (unrelated to the `sources`/`sources_count` data spine this plan adds) — logged here rather than silently fixed or silently ignored. A future phase should batch this the same way Plan 01 batched `list_vulnerabilities`' correlation fetch (page-scoped `asset_id IN (page_ids)` aggregate, one query instead of one-per-row).

## Next Phase Readiness

- `app/assets/constants.py`'s `SCANNER_SOURCES`/`ENRICHMENT_SOURCES` are ready for Plan 05's frontend chip-bar work to mirror (the CONTEXT.md-flagged stale `SOURCES` allow-lists in `chip-bar.tsx`/`assets-chip-bar.tsx` should reconcile to this same 6-value scanner set, plus the 3-value enrichment set as a separate facet).
- The asset list row's `sources: list[str]` / `sources_count: int` shape (scanner-only count) is the concrete contract Plan 05's `SourceBadgeGroup` wiring on the Assets table should consume.
- `source_mode`/`enrichment_source` are real, HTTP-reachable, allow-list-clamped filter axes — Plan 05 can wire the Assets chip-bar's AND toggle and the new enrichment-source facet against this contract with no further backend changes.
- No blockers. Full regression suite for touched files green: `test_asset_source_filter.py` (6/6), `test_rule_engine.py` (9/9, no regression), `test_asset_exposure.py` + `test_asset_groups.py` + `test_asset_owner_reassign.py` + `test_assets_tags_and_os_family.py` + `test_tickets_asset_id_filter.py` (52/52 combined). `ruff check` + `ruff format --check` clean on all touched files. `mypy` error count on touched files unchanged from baseline (121 before, 121 after — no new type-debt introduced). `alembic upgrade head` / `downgrade -1` / `upgrade head` round-trips clean at head `045_add_seen_by_sources_gin`.

---
*Phase: 35-source-aware-filtering-provenance-badges*
*Completed: 2026-08-12*

## Self-Check: PASSED

All 5 created/modified files verified present on disk; both task commits (`5aba112`, `b188ab4`) verified present in `git log --oneline --all`.
