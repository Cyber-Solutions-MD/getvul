---
phase: 35-source-aware-filtering-provenance-badges
plan: 04
subsystem: api
tags: [sqlalchemy, postgres, fastapi, pydantic, query-batching, tdd, corroboration]

# Dependency graph
requires:
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 01
    provides: "backend/tests/query_count.py (before_cursor_execute statement-counting harness) + the OR/AND source_mode + page-scoped tuple_(...).in_() batching pattern to mirror"
  - phase: 35-source-aware-filtering-provenance-badges
    plan: 03
    provides: "the table-filter-discipline convention for query-count assertions (filter statements to the SUT's own tables)"
provides:
  - "CSPM MisconfigFilter.source_mode: Literal['or','and']='or' wired end-to-end (router Query param -> schema -> service)"
  - "CSPM read-time GROUP BY(tenant_id, rule_id, resource_id) HAVING count(DISTINCT source)>=len(selected) AND-corroboration branch — NO silent Misconfiguration.source.in_() fallback for AND"
  - "CSPM list_misconfigurations page-scoped batched group-sources fetch (tuple_(rule_id,resource_id).in_(page_keys)) populating MisconfigSummary.sources/sources_count with zero N+1"
  - "Ticket list_tickets(source=...) real OR-default server-side filter joined through the linked Vulnerability (SRC-02 delivered for Tickets — not display-only)"
  - "Ticket transitive union provenance: details_q extended with array_agg(DISTINCT Vulnerability.source) grouped by external_ticket_url ('own_sources', a real UNION, never func.min) + a batched (cve_id,asset_id) keys query + ONE batched VulnerabilityCorrelation fetch merged per grouped row (CONTEXT [RESOLVED A4])"
  - "TicketSummary/TicketResponse.sources/sources_count fields"
affects: [35-05-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CSPM's own page-scoped tuple_((rule_id,resource_id)).in_(page_keys) grouped-aggregate query — the same page-scoped-batching shape Plan 01 established, now applied to a computed read-time GROUP BY rather than a persisted correlation table (no CSPM correlation table exists — CONTEXT [RESOLVED A2])"
    - "Ticket transitive provenance as a THREE-stage batch: (1) extend the existing WR-05 details_q aggregate with array_agg(DISTINCT source) as the group's own-sources floor, (2) one ungrouped keys query collecting (url, cve_id, asset_id) triples for the page, (3) one batched VulnerabilityCorrelation fetch keyed by the union of all page keys — then a pure-Python per-url set union in `_resolve_sources()`, never a per-row query"

key-files:
  created:
    - backend/tests/test_cspm_corroboration.py
    - backend/tests/test_source_provenance_batched.py
  modified:
    - backend/app/cspm/schemas.py
    - backend/app/cspm/service.py
    - backend/app/cspm/router.py
    - backend/app/ticketing/schemas.py
    - backend/app/ticketing/service.py
    - backend/app/ticketing/router.py

key-decisions:
  - "CSPM AND corroboration gate key is (rule_id, resource_id) — a GROUP BY over the existing uq_misconfig_dedup(tenant_id, rule_id, resource_id, source) unique-constraint key, HAVING count(DISTINCT source) >= len(selected sources). Verified the group key gates correctly, not just result-set membership, via test_cspm_and_requires_same_group's 3-group fixture (one shared group + two singles on DIFFERENT rule_id/resource_id pairs, each individually flagged by one of the two selected tools)."
  - "CSPM AND-with-<2-selected-sources is a documented no-op falling into the OR branch — matches the Plan 01/03 convention exactly (not re-derived, same code shape: `if filters.source_mode == \"and\" and len(filters.source) >= 2`)."
  - "list_misconfigurations' batched group-sources query is scoped page-wide via tuple_((rule_id,resource_id)).in_(page_keys), tenant-scoped independently (T-35-01) — exactly ONE extra query per page load, verified page-size-invariant (test_cspm_query_count_invariant, <=4 statements for both a 5-row and 50-row page)."
  - "Ticket provenance union rule implemented as: own_sources (array_agg(DISTINCT Vulnerability.source) grouped by external_ticket_url, extending the existing details_q — zero extra query) UNION correlation.sources for every linked vuln's (cve_id,asset_id) key that has a VulnerabilityCorrelation row. This is mathematically equivalent to the per-vuln formula in CONTEXT A4 (\"union each linked vuln's [correlation.sources OR [vuln.source]]\") because own_sources already covers every linked vuln's own source as the floor, and a correlation row's sources array always ⊇ {that vuln's own source} by Phase-30 construction — verified directly by test_ticket_grouped_union's 2-vuln mixed-corroboration fixture."
  - "Ticket provenance batching costs exactly 2 NEW queries beyond the pre-existing grouped_q/details_q/count pair: one ungrouped (url, cve_id, asset_id) keys query + one batched VulnerabilityCorrelation fetch — both tenant-scoped independently (T-35-01). Verified page-size-invariant (test_list_tickets_query_count_invariant)."
  - "Tickets' ?source= filter uses the SAME subquery-filter shape the pre-existing severity_vals filter already uses in this exact function (`Ticket.vulnerability_id.in_(select(Vulnerability.id).where(...).scalar_subquery())`) rather than introducing a new join into grouped_q — minimizes surface-area change to a function with substantial pre-existing filter logic."
  - "No AND toggle for Tickets' source filter (OR-default only) — SRC-04's true multi-scanner corroboration semantics are scoped to Vulnerabilities/Assets/CSPM per the plan; ticket provenance DISPLAY still unions transitively regardless of which filter mode is (not) applied."

patterns-established: []

requirements-completed: [SRC-02, SRC-05, SRC-07, SRC-08]

coverage:
  - id: D1
    description: "CSPM ?source=A&source=B&source_mode=and returns a misconfiguration ONLY if the SAME (tenant_id, rule_id, resource_id) group is flagged by BOTH tools — a read-time GROUP BY, never a silent source.in_() OR fallback"
    requirement: "SRC-05"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_and_requires_same_group"
        status: pass
    human_judgment: false
  - id: D2
    description: "CSPM AND mode excludes a resource+rule flagged by only ONE of the selected tools even when the other selected tool flags a DIFFERENT resource+rule — proves the grouping key is (rule_id, resource_id), not result-set membership"
    requirement: "SRC-05"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_and_requires_same_group"
        status: pass
    human_judgment: false
  - id: D3
    description: "CSPM OR default (no source_mode) is unaffected — returns the union of all selected-tool rows including non-corroborated singles"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_or_default_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every CSPM list row carries sources (array_agg of tools on its (rule_id,resource_id) group) and sources_count, batched page-scoped, never per-row"
    requirement: "SRC-05"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_row_carries_group_sources"
        status: pass
    human_judgment: false
  - id: D5
    description: "list_misconfigurations issues a FIXED statement count independent of page size (one batched grouped query, never per-row)"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_query_count_invariant"
        status: pass
    human_judgment: false
  - id: D6
    description: "source_mode is bound as a real cspm/router Query param — ?source_mode=and over HTTP reaches the same corroboration-only result as calling the service directly (not silently dropped by FastAPI param parsing)"
    requirement: "SRC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_cspm_corroboration.py#test_cspm_and_reaches_service_via_http"
        status: pass
    human_judgment: false
  - id: D7
    description: "A ticket linked to a QUALYS vuln whose (cve_id,asset_id) is ALSO RAPID7-correlated shows sources=[QUALYS,RAPID7] — resolved transitively through the linked vuln's VulnerabilityCorrelation, not just the one row that triggered ticket creation"
    requirement: "SRC-07"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_provenance_batched.py#test_ticket_transitive_provenance"
        status: pass
    human_judgment: false
  - id: D8
    description: "A grouped ticket-task spanning 2 linked vulns (one QUALYS-only-no-correlation, one QUALYS+RAPID7-correlated) unions to {QUALYS,RAPID7} and is multi-source — proving the union spans ALL linked vulns, not a representative pick"
    requirement: "SRC-07"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_provenance_batched.py#test_ticket_grouped_union"
        status: pass
    human_judgment: false
  - id: D9
    description: "A ticket linked to a vuln with NO correlation row falls back to sources=[vuln.source], sources_count=1 — never null/unknown"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_provenance_batched.py#test_ticket_single_source_no_correlation"
        status: pass
    human_judgment: false
  - id: D10
    description: "?source= on the ticket list is a REAL server-side OR-default filter joined through the linked Vulnerability — not display-only. Single source narrows to that ticket; two selected sources return the union"
    requirement: "SRC-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_provenance_batched.py#test_ticket_list_filter_by_source"
        status: pass
    human_judgment: false
  - id: D11
    description: "list_tickets issues a FIXED statement count independent of page size — the transitive provenance resolution adds a bounded number of batched queries, never one-per-row"
    requirement: "SRC-08"
    verification:
      - kind: integration
        ref: "backend/tests/test_source_provenance_batched.py#test_list_tickets_query_count_invariant"
        status: pass
    human_judgment: false
  - id: D12
    description: "Regression: existing CSPM + ticketing/rule_engine + Vulnerabilities/Assets source-filter test suites remain green after all changes"
    verification:
      - kind: integration
        ref: "backend/tests/{test_cspm_corroboration,test_source_provenance_batched,test_list_tickets_reshape,test_ticket_blocked,test_ticket_comments,test_ticket_migrations,test_ticket_watch,test_ticketing_clients,test_ticketing_dispatch,test_tickets_asset_id_filter,test_tickets_create,test_rule_engine,test_asset_source_filter,test_source_filtering,test_vuln_source_filter}.py (91 tests total across the full regression run)"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-08-12
status: complete
---

# Phase 35 Plan 04: CSPM AND Corroboration + Tickets Transitive Provenance Summary

**CSPM's cross-tool AND filter now performs TRUE corroboration via a read-time `GROUP BY(tenant_id, rule_id, resource_id) HAVING count(DISTINCT source) >= N` (never a silent `source.in_()` OR fallback), every CSPM row carries page-scoped batched `sources`/`sources_count`, and the ticket list resolves provenance transitively through each linked vuln's `VulnerabilityCorrelation` — unioning ALL linked vulns' sources per grouped ticket-task row via `array_agg(DISTINCT ...)` (never `func.min`'s representative pick) — plus a real server-side OR-default `?source=` filter on Tickets, closing SRC-02 for all four entities.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-08-12T12:41:00Z (approx, context load)
- **Completed:** 2026-08-12T13:58:53Z
- **Tasks:** 3 (RED, GREEN-CSPM, GREEN-Tickets)
- **Files modified:** 8 (2 new test files, 6 modified source files)

## Accomplishments

- **CSPM AND corroboration is genuinely new-mechanism, no analog anywhere in `app/cspm/` before this plan.** `_apply_filters` now branches: AND mode (2+ selected sources) builds a `select(Misconfiguration.rule_id, Misconfiguration.resource_id).where(tenant_id==..., source.in_(selected)).group_by(rule_id, resource_id).having(count(DISTINCT source) >= len(selected))` subquery and restricts the outer query to `tuple_(rule_id, resource_id).in_(that subquery)` — OR stays `source.in_()`, unchanged and correct. Proved with a 3-group fixture (one shared WIZ+DEFENDER group plus two singles on different `(rule_id, resource_id)` pairs each individually matching one of the two selected tools) that the AND gate is the GROUP, not "any row from either selected source."
- **`MisconfigFilter.source_mode: Literal["or","and"]="or"` bound end-to-end**, including the router-level `Query(...)` binding CSPM previously lacked entirely — without it `?source_mode=and` would be silently dropped and the AND branch unreachable via HTTP (proved directly by `test_cspm_and_reaches_service_via_http` comparing the HTTP result to a direct service call).
- **`MisconfigSummary.sources`/`sources_count`** populated via a NEW page-scoped batched query mirroring Plan 01's `tuple_(...).in_(page_keys)` shape exactly, but over a computed `GROUP BY` (no persisted CSPM correlation table exists, per CONTEXT `[RESOLVED A2]`) rather than a stored ARRAY column — `array_agg(DISTINCT source)` + `count(DISTINCT source)`, tenant-scoped independently (T-35-01), one extra query per page load, proven page-size-invariant.
- **Ticket transitive union provenance** extends the existing WR-05 batched `details_q` (already grouped by `external_ticket_url`) with a new `array_agg(DISTINCT Vulnerability.source)` column (`own_sources` — the group's floor, a real UNION unlike the file's own documented `func.min` representative-pick aggregates alongside it), then adds two NEW batched queries: one ungrouped `(url, cve_id, asset_id)` keys fetch for the page, and ONE batched `VulnerabilityCorrelation` fetch keyed by the union of all page keys (tenant-scoped, T-35-01). A pure-Python `_resolve_sources(url)` merges `own_sources` with every matched correlation's `sources` array per grouped row — proved correct for the exact CONTEXT `[RESOLVED A4]` scenario: a grouped task spanning one corroborated and one non-corroborated linked vuln unions to both tools' sources and is multi-source.
- **SRC-02 delivered for Tickets**: `list_tickets(source=...)` is a real OR-default filter using the SAME subquery-filter shape the function's pre-existing `severity_vals` filter already uses (`Ticket.vulnerability_id.in_(select(Vulnerability.id).where(Vulnerability.source.in_(source)).scalar_subquery())`) — not display-only. `ticketing/router.py::list_all_tickets` binds `source: list[str] | None = Query(None)` and passes it through; without this binding the filter would be unreachable via HTTP, mirroring the exact CSPM `source_mode` binding gap this plan also fixed.
- Full regression suite green: all new tests (10) plus the entire pre-existing CSPM/ticketing/rule_engine/Vulnerabilities/Assets source-filter test surface (91 tests total in the combined verification run) — zero regressions. `ruff check`/`ruff format --check` clean on all 6 touched source files. `mypy` error count on touched files unchanged from baseline (149 before, 149 after — no new type-debt introduced).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — CSPM AND-grouping + ticket transitive union provenance + query-count tests** - `5633dc0` (test)
2. **Task 2: GREEN CSPM — read-time GROUP BY AND corroboration + schema + batched group sources** - `ea4df0c` (feat)
3. **Task 3: GREEN Tickets — batched transitive union provenance + schema + real source filter** - `5bb0506` (feat)

_No plan-metadata commit yet — created below._

## Files Created/Modified

- `backend/tests/test_cspm_corroboration.py` - 5 tests: AND requires same (rule_id,resource_id) group, OR-default unchanged, row-carries-group-sources, page-size-invariant query count, HTTP-binding proof
- `backend/tests/test_source_provenance_batched.py` - 5 tests: ticket transitive provenance via correlation, grouped-task union (CONTEXT A4), single-source no-correlation fallback, query-count invariance, real `?source=` filter proof
- `backend/app/cspm/schemas.py` - `MisconfigFilter.source_mode` + `max_length=10` caps on severity/source/status/category (previously uncapped); `MisconfigSummary.sources`/`sources_count`
- `backend/app/cspm/service.py` - `_apply_filters` AND-branch (GROUP BY/HAVING subquery, never `source.in_()` for AND); `list_misconfigurations` page-scoped batched group-sources fetch
- `backend/app/cspm/router.py` - `source_mode` bound as an explicit `Query(...)` param into `MisconfigFilter(...)`
- `backend/app/ticketing/schemas.py` - `TicketSummary`/`TicketResponse.sources`/`sources_count`
- `backend/app/ticketing/service.py` - `list_tickets(source=...)` real OR-default filter; `details_q` extended with `own_sources` array_agg; new batched keys query + batched `VulnerabilityCorrelation` fetch; `_resolve_sources()` per-url union helper
- `backend/app/ticketing/router.py` - `source: list[str] | None = Query(None)` bound and passed into `list_tickets`

## Decisions Made

See `key-decisions` in frontmatter for the full list. The single most consequential decision: **the ticket union formula is implemented as `own_sources (array_agg over the whole group) ∪ (correlation.sources for every linked vuln with a correlation row)`**, rather than iterating per-linked-vuln and picking `correlation.sources OR [vuln.source]` as CONTEXT's interfaces snippet literally describes. These are mathematically equivalent given Phase 30's invariant that a correlation row's `sources` array always includes the originating vuln's own source — verified directly by the mixed-corroboration test, not just asserted. This shape was chosen because it lets `details_q`'s existing GROUP BY do the "own sources" aggregation for free (zero extra query), matching the plan's explicit recommendation to extend `details_q` with an `array_agg(...) grouped by url` (interfaces block, Step A) while still satisfying Step C's per-vuln union semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ticket provenance implementation restructured mid-Task-3 to use a real `array_agg` (not a purely per-row Python union) to satisfy the plan's own no-representative-pick verification gate**
- **Found during:** Task 3 (GREEN Tickets) — the first implementation attempt collected raw `(url, cve_id, asset_id, source)` rows in a single ungrouped query and did the entire union in Python with no SQL `array_agg` call anywhere in the file. All 5 behavior tests passed, but the plan's own `<verify>` gate (`grep -q "array_agg" backend/app/ticketing/service.py`) failed — the anti-pattern check the plan itself specifies (`No-representative-pick gate`) requires a real `array_agg` usage, not just avoidance of `func.min`.
- **Issue:** A purely-Python union, while behaviorally correct and tested, does not surface the SQL-level "real UNION over the full group" signal the plan's verification explicitly checks for, and forgoes a free aggregation opportunity in the already-existing `details_q` GROUP BY.
- **Fix:** Extended the existing WR-05 `details_q` (already `GROUP BY external_ticket_url`) with `func.array_agg(func.distinct(Vulnerability.source)).label("own_sources")` — this computes the group's own-sources floor with ZERO extra queries (reusing an existing query). The correlation merge then only needs a lighter-weight `(url, cve_id, asset_id)` keys query (no `source` column needed there) plus the batched correlation fetch, and a `_resolve_sources()` helper merges `own_sources` with matched correlations per url. Net effect: same 2 new queries as the first attempt, but one of the "sources" signals is now a genuine SQL `array_agg`, not a Python re-derivation.
- **Files modified:** `backend/app/ticketing/service.py`
- **Verification:** All 5 `test_source_provenance_batched.py` tests still green after the restructure; `grep -q "array_agg" backend/app/ticketing/service.py` now passes; `grep -q "func.min(Vulnerability.source)"` still absent (no regression to the anti-pattern check); full ticketing regression suite (91 tests) green.
- **Committed in:** `5bb0506` (Task 3 GREEN commit — the file's final state already includes this restructure; no separate commit needed since Task 3's tests were still RED-adjacent internally before the grep gate was checked, all within the same task).

---

**Total deviations:** 1 auto-fixed (1 bug/gate-compliance fix, discovered and resolved within Task 3's own scope before its commit — no pre-existing code touched beyond the plan's own specified `list_tickets` function).
**Impact on plan:** Necessary to satisfy the plan's own `<verification>` block (`No-representative-pick gate`); no scope creep, no change to the function's public signature or behavior beyond what Task 3 already specified. Final behavior is identical to the first (correct) attempt; only the SQL/Python query split changed.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required. No migration required (confirmed: CSPM's grouping is entirely read-time per CONTEXT `[RESOLVED A2]`, and ticket provenance reads only existing `vulnerability_correlations` columns from alembic `034_add_correlation_sources`). Alembic head remains `045_add_seen_by_sources_gin` (Plan 03's head) — unchanged by this plan.

## Next Phase Readiness

- **CSPM contract for Plan 05's frontend wiring:** `MisconfigSummary.sources: list[str]` (the (rule_id,resource_id) group's tools) + `sources_count: int` (count of distinct tools in that group) — same shape convention as Vulnerabilities (Plan 01) and Assets (Plan 03). `source_mode` is now a real, HTTP-reachable, `Literal`-validated filter axis — Plan 05's CSPM chip-bar AND toggle needs no further backend changes.
- **Ticket contract for Plan 05's frontend wiring:** `TicketSummary`/`TicketResponse.sources: list[str]` (transitively-resolved union across ALL linked vulns in the grouped row) + `sources_count: int`. A real `?source=` OR-default filter is now reachable at `GET /api/v1/tickets?source=QUALYS&source=RAPID7` — Plan 05's Tickets chip-bar source facet needs no further backend changes (no AND toggle needed/available for Tickets per this plan's scope).
- All 4 entities (Vulnerabilities, Assets, CSPM, Tickets) now carry the SRC-01/05/07 provenance data spine and the SRC-02/03/04 OR/AND filter contract (Tickets: OR-only, by design) with SRC-08 no-N+1 proof via the shared `count_queries()` harness — Plan 05 (frontend `SourceBadgeGroup` + chip-bar wiring) has zero backend blockers.
- No blockers.

---
*Phase: 35-source-aware-filtering-provenance-badges*
*Completed: 2026-08-12*

## Self-Check: PASSED

All 8 created/modified files verified present on disk; all 3 task commits (`5633dc0`, `ea4df0c`, `5bb0506`) verified present in `git log --oneline --all`.
