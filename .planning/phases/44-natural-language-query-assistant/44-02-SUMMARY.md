---
phase: 44-natural-language-query-assistant
plan: 02
subsystem: api
tags: [pydantic, fastapi, sqlalchemy, ai, nlq]

# Dependency graph
requires:
  - phase: 44-01 (NLQ tracer)
    provides: "POST /api/v1/ai/query SSE spine (translate->execute->results-first->narrate), NlqFilterResponse/VulnFilterInput/AssetFilterInput/TicketFilterInput flat schemas, _resolve_hostname (built but unwired), _run_query_stream's guarded assets/tickets refuse placeholder"
provides:
  - "VulnerabilityFilter.asset_internet_facing (subquery against Asset.internet_facing, no join) + VulnerabilityFilter.sla_breached (stored derived-mirror column)"
  - "AssetFilter.internet_facing (native column, no join)"
  - "ticketing/schemas.py::TicketQueryFilter -- extra=forbid NLQ-only translation wrapper above list_tickets' existing loose kwargs"
  - "_run_query_stream real assets/tickets entity branches (replacing the Plan-01 guarded refuse placeholder): list_assets + list_tickets with server-side _resolve_hostname before list_tickets"
  - "FEW_SHOT_QUERY_TRANSLATE extended with the north-star question + all 4 UI-SPEC starter questions; SYSTEM_PROMPT_QUERY_TRANSLATE's allowed-field catalog covers all three entities"
affects: [44-03 (frontend data/components), 44-04 (Ask page), 44-05 (D-17 deep-link), 44-06 (eval/red-team gate)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Correlated IN-subquery (Vulnerability.asset_id.in_(select(Asset.id).where(...))) instead of a second .join() inside a shared _apply_filters helper, when the caller already joins the same table downstream on some-but-not-all call paths -- avoids a double-join InvalidRequestError without touching the existing outerjoin call sites"
    - "TicketFilterInput (ai/schemas.py, model-emitted) -> TicketQueryFilter (ticketing/schemas.py, extra=forbid, ticketing-layer-validated) as a documented one-way producer/consumer conversion, never used interchangeably (W4)"
    - "Unresolvable server-side hostname resolution short-circuits to a zero-results answer (rows=[], total=0) that still flows through the SAME interpreted->results->narrate pipeline, rather than a special-cased early return -- the narrate call's existing zero-results few-shot already covers it honestly"

key-files:
  created: []
  modified:
    - backend/app/vulnerabilities/schemas.py
    - backend/app/vulnerabilities/service.py
    - backend/app/assets/schemas.py
    - backend/app/assets/service.py
    - backend/app/ticketing/schemas.py
    - backend/app/ai/schemas.py
    - backend/app/ai/prompt_builder.py
    - backend/app/ai/query_assistant.py
    - backend/tests/test_ai_query_stream.py
    - backend/tests/test_vulnerabilities_filters.py

key-decisions:
  - "asset_internet_facing implemented as a correlated IN-subquery, not a .join(Asset, ...) inside _apply_filters -- list_vulnerabilities' and list_vulnerabilities_by_host's data-path queries already .outerjoin(Asset, ...) downstream of _apply_filters, but the count-query path and the two facet-count paths do not; a subquery filters identically and correctly on ALL four call paths with zero risk of a duplicate-join error, avoiding the plan's suggested (and riskier) alternative of moving the Asset join into _apply_filters unconditionally and refactoring 4 existing call sites"
  - "TicketQueryFilter.asset_hostname resolves via the SAME _resolve_hostname Plan 01 already built and tested -- an unresolved hostname produces rows=[]/total=0 and still proceeds through interpreted->results->narrate (not a special early return), so the existing narrate few-shot's 'zero results is a truthful answer' framing covers it without a new prompt branch"
  - "_map_ticket_filter (query_assistant.py) mirrors _map_vuln_filter/_map_asset_filter's naming and shape for symmetry, even though it converts between two ai-adjacent schemas rather than mapping onto a domain filter -- keeps the three entity branches structurally parallel"

patterns-established: []

requirements-completed: [NLQ-01]

# Metrics
duration: ~35min
completed: 2026-08-25
---

# Phase 44 Plan 02: Backend Query Surface Expansion (D-03 Predicates + Assets/Tickets Entities) Summary

**VulnerabilityFilter.asset_internet_facing (subquery, no double-join) + sla_breached (stored column), AssetFilter.internet_facing, and a new TicketQueryFilter close the D-03 predicate gap; `_run_query_stream`'s assets/tickets branches now execute real `list_assets`/`list_tickets` calls with server-side hostname resolution, replacing Plan 01's guarded refuse placeholder — all three NLQ entities answer end-to-end.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-25T~11:30Z (STATE.md, phase-execution continuation)
- **Completed:** 2026-08-25T12:07:16Z
- **Tasks:** 2
- **Files modified:** 9 (all modified, 0 created source files; 1 new test file)

## Accomplishments
- The north-star question ("which internet-facing hosts have an unremediated KEV older than 30 days?") and all four UI-SPEC starter questions now resolve correctly: `cisa_kev=true, status=[OPEN,IN_PROGRESS], age_days_min=30, asset_internet_facing=true` on a SINGLE vulnerabilities-entity filter (D-02), with no model-side multi-tool join.
- Proved empirically (not just cited) that a correlated IN-subquery sidesteps the Pitfall-1 double-join risk entirely — `test_filter_asset_internet_facing` exercises BOTH the count path and the data path (which already `.outerjoin(Asset, ...)`) and passes with the exact count and correct row.
- `_run_query_stream`'s assets and tickets branches are now real, not placeholders: "open tickets for asset prod-db-01" resolves the hostname server-side via `_resolve_hostname` BEFORE calling `list_tickets`, and the model never supplies or invents a UUID — proven via a `wraps`-instrumented `list_tickets` mock asserting the exact `asset_id`/`status` kwargs.
- An unresolvable hostname ("asset that doesn't exist") now yields a well-formed `total=0` zero-results answer through the full `interpreted->results->narrate` pipeline, never a D-14 refusal — matching the RESEARCH Pattern 3 / Open Question 2 resolution.

## Task Commits

Each task was committed atomically:

1. **Task 1: D-03 additive predicates (vuln join + sla_breached, asset native, ticket wrapper)** - `c515db4` (feat)
2. **Task 2: assets + tickets entity branches + hostname resolution in the orchestrator** - `c3ca9e1` (feat)

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `backend/app/vulnerabilities/schemas.py` - `VulnerabilityFilter.asset_internet_facing`/`sla_breached`
- `backend/app/vulnerabilities/service.py` - `_apply_filters` gains the `sla_breached` where-clause + the `asset_internet_facing` IN-subquery (Pitfall 1 resolution)
- `backend/app/assets/schemas.py` - `AssetFilter.internet_facing`
- `backend/app/assets/service.py` - `_apply_filters` gains the `internet_facing` where-clause (native column)
- `backend/app/ticketing/schemas.py` - new `TicketQueryFilter` (extra=forbid)
- `backend/app/ai/schemas.py` - `VulnFilterInput.asset_internet_facing`/`sla_breached`, `AssetFilterInput.internet_facing`
- `backend/app/ai/prompt_builder.py` - `FEW_SHOT_QUERY_TRANSLATE` gains the north-star question, the SLA-breach starter question, a host-scoped tickets example, and an assets example; `SYSTEM_PROMPT_QUERY_TRANSLATE`'s allowed-field catalog covers all three entities (vulnerabilities catalog still excludes any hostname field, W3)
- `backend/app/ai/query_assistant.py` - `_map_vuln_filter` extended, new `_map_asset_filter`/`_map_ticket_filter` helpers, `_run_query_stream`'s entity dispatch replaced with real `list_assets`/`list_tickets` branches + `_resolve_hostname` wiring
- `backend/tests/test_ai_query_stream.py` - replaced the guarded-placeholder assets test with `test_assets_entity_branch`; added `test_tickets_entity_branch` and `test_unresolvable_hostname_is_zero_results`
- `backend/tests/test_vulnerabilities_filters.py` (new) - `test_filter_asset_internet_facing`, `test_filter_sla_breached`, `test_asset_internet_facing_filter`, `test_ticket_query_filter_forbids_extra`

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

None — plan executed exactly as written. The plan's own `<action>` block explicitly asked to "FIRST verify empirically whether SQLAlchemy 2.0 dedups the join... if it raises/duplicates, apply the safe fallback" — the empirical verification led to a subquery (a stronger, simpler resolution than either branch of the plan's own conditional), which is within the plan's own stated discretion, not a deviation from it.

## Issues Encountered
None. `backend/uv.lock` appeared as an untracked file in the working tree at session start (generated by a prior `uv run` invocation, not part of this plan's `files_modified`) — left untracked, not committed, per the "never `git add -A`" discipline.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None. All three entities (vulnerabilities/assets/tickets) now execute real, tenant-scoped queries; no hardcoded empty values or placeholder copy were introduced.

## Threat Flags

None — every new surface (the `asset_internet_facing`/`sla_breached`/`internet_facing` predicates, `TicketQueryFilter`, the real assets/tickets execution branches) is already covered by the plan's own `<threat_model>` (T-44-02, T-44-07, T-44-08, T-44-04). `_resolve_hostname` (already tenant-scoped and tested in Plan 01) is the sole hostname->UUID resolution path; no model-emitted UUID is ever trusted.

## Next Phase Readiness
- NLQ-01 is now fully satisfied end-to-end: a plain-English question over vulnerabilities, assets, OR tickets returns a grounded, tenant-scoped answer with the underlying result set shown, for all four UI-SPEC starter questions and the north-star question.
- 44-03 (frontend `useQueryStream` + `ask/` components) can now build against a backend that answers all three entities — no further backend gaps block frontend work.
- 44-05 (D-17 deep-link) can rely on `VulnFilterInput`'s field set (including the two new predicates) as the stable param contract for `buildNlqDeepLink` — the vulnerabilities entity still structurally has no hostname field (W3), so the deep-link's param set stays tight.
- 44-06 (eval/red-team gate) inherits a wider representative-question surface (5 few-shot examples now, spanning all three entities) to build golden fixtures from.
- No blockers.

## Self-Check: PASSED

Verified all 9 modified/created files exist on disk at their claimed paths; verified both task commit hashes (`c515db4`, `c3ca9e1`) are present in `git log --oneline`.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
