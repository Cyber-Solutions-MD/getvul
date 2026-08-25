---
phase: 44-natural-language-query-assistant
plan: 05
subsystem: frontend
tags: [react, url-state, ai, nlq, fastapi, deep-link]

# Dependency graph
requires:
  - phase: 44-02 (backend query surface expansion)
    provides: "VulnerabilityFilter.asset_internet_facing/sla_breached, AssetFilter.internet_facing, TicketFilterInput.asset_hostname + server-side _resolve_hostname — the filter fields this plan's deep-link expresses as URL params"
  - phase: 44-03 (frontend data + presentational layer)
    provides: "the interpreted-filter shape (NlqFilterResponse per-entity *FilterInput) this plan's buildNlqDeepLink consumes"
provides:
  - "buildNlqDeepLink(entity, filter) -> href — the single source of truth for the D-17 param contract, imported by both the list-page readers (this plan) and Plan 04's 'Open in {list}' button"
  - "useUrlStateBool / useUrlStateNumber — boolean + bounded-numeric URL-state hooks (use-url-state.ts/use-url-state-list.ts are string-enum-clamped only and structurally can't express these)"
  - "vulnerabilities/assets/tickets list pages now read the FULL D-17 field set (cisa_kev, exploit_available, sla_breached, asset_internet_facing, age_days_min, internet_facing, asset_id)"
  - "GET /api/v1/vulnerabilities and GET /api/v1/assets now bind the 3 filter fields their own schemas already supported but never exposed as Query params"
affects: [44-04 (Ask page composition — consumes buildNlqDeepLink for the 'Open in {list}' CTA)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-entity FIELD_MAP (allow-list + rename table), not a generic key-passthrough, in buildNlqDeepLink — handles the 2 cases where a *FilterInput field name doesn't match the target page's URL param 1:1 (device_category->category, resolved_asset_id->asset_id) and safely omits any unmapped field (e.g. tickets' raw asset_hostname) rather than leaking an unread param into the URL"
    - "useUrlStateBool/useUrlStateNumber mirror useUrlState's exact shape (raw read -> allow-list/bounded-parse clamp -> fall back to default; setValue deletes the param when writing back the default) — same XSS-clamp discipline, just for boolean/numeric value shapes instead of string-enum"

key-files:
  created:
    - frontend/src/lib/ai/nlq-deep-link.ts
    - frontend/src/lib/ai/nlq-deep-link.test.ts
    - frontend/src/hooks/use-url-state-scalar.ts
    - frontend/src/hooks/use-url-state-scalar.test.ts
  modified:
    - frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx
    - frontend/src/app/(authed)/dashboard/assets/page.tsx
    - frontend/src/app/(authed)/dashboard/tickets/page.tsx
    - frontend/src/lib/queries/use-vulnerabilities.ts
    - frontend/src/lib/queries/use-assets.ts
    - frontend/src/lib/queries/use-tickets.ts
    - backend/app/vulnerabilities/router.py
    - backend/app/assets/router.py
    - backend/app/ai/query_assistant.py

key-decisions:
  - "buildNlqDeepLink's FIELD_MAP is an explicit per-entity allow-list + rename table, not a generic passthrough — AssetFilterInput.device_category maps to the assets page's existing `category` axis param, tickets' resolved_asset_id maps to `asset_id`, and asset_hostname is deliberately dropped (superseded by resolved_asset_id, not a URL param any page reads)"
  - "Rule 3 (blocking): GET /api/v1/vulnerabilities never bound sla_breached/asset_internet_facing as Query params despite VulnerabilityFilter already supporting both (Plan 02, built for the AI-only path) — fixed by adding the 2 Query params + passing them into the existing VulnerabilityFilter(...) constructor call, mirroring the router's own cisa_kev/exploit_available pattern"
  - "Rule 3 (blocking): GET /api/v1/assets builds its query entirely inline and never calls the AssetFilter/service.py::list_assets path Plan 02 wired internet_facing into (that service function is used ONLY by the AI query-assistant) — fixed by binding internet_facing as a Query param and adding one .where() clause directly in the router, matching the existing min_risk pattern"
  - "Rule 2 (missing critical functionality): query_assistant.py's tickets branch computed resolved_asset_id (via _resolve_hostname) but never surfaced it in the interpreted SSE frame sent to the frontend — only the raw asset_hostname string reached the client, leaving buildNlqDeepLink with no UUID to express ?asset_id= for 'Open in Tickets.' Fixed additively (interpreted_filter[\"resolved_asset_id\"] = ...) — a plain-dict key, not a schema field, so it can't reintroduce a model-supplied-UUID trust issue; D-01/D-02 still hold (the model itself never sees or invents a UUID)"
  - "Rule 1 (bug fix): vulnerabilities/page.tsx's hasActiveFilters + the empty-filtered 'Clear all' CTA were extended to include the 5 new boolean/numeric predicates — without this, a deep-link carrying ONLY e.g. ?cisa_kev=true with zero matching rows fell through every render branch to `null` (no empty state at all, violating the mandatory empty-state contract), and 'Clear all' couldn't clear a deep-linked predicate it didn't know about"

patterns-established: []

requirements-completed: [NLQ-01]

# Metrics
duration: ~25min
completed: 2026-08-25
---

# Phase 44 Plan 05: D-17 Read-Only Deep-Link (buildNlqDeepLink + Boolean/Numeric URL-State + List-Page Wiring) Summary

**`buildNlqDeepLink(entity, filter)` closes the answer-to-triage loop by mapping the SAME interpreted filter the assistant used onto the exact URL params the Vulnerabilities/Assets/Tickets list pages read — plus two backend router fixes (found mid-implementation) that were silently dropping 3 of the 6 D-17 predicate params before this plan.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-25T~15:10Z (STATE.md, phase-execution continuation)
- **Completed:** 2026-08-25T15:36:00Z
- **Tasks:** 2
- **Files modified:** 13 (4 created, 9 modified)

## Accomplishments
- `buildNlqDeepLink('vulnerabilities', {cisa_kev:true, age_days_min:30, asset_internet_facing:true})` returns exactly `/dashboard/vulnerabilities?cisa_kev=true&age_days_min=30&asset_internet_facing=true` — proven by an exact-string test, matching the plan's own north-star example verbatim.
- `useUrlStateBool`/`useUrlStateNumber` fill the gap `44-PATTERNS.md`'s RESEARCH flagged: `useUrlState`/`useUrlStateList` are string-enum-`includes()`-clamped only and structurally cannot express a boolean or a bounded-numeric range — both new hooks mirror the exact same clamp-to-default-on-anything-else discipline (T-44-11), proven against a literal `<script>` XSS payload in both test files.
- All three list pages now read the full D-17 field set — confirmed via the plan's own grep acceptance criteria: `cisa_kev|sla_breached|asset_internet_facing|age_days_min` all match on `vulnerabilities/page.tsx`; `internet_facing` matches on `assets/page.tsx`; `tickets/page.tsx` reads a UUID-shape-clamped `asset_id`.
- Discovered and fixed (Rule 3, blocking) that 3 of the D-17 field set's 6 fields would have been a silent no-op even after this plan's frontend wiring: `GET /api/v1/vulnerabilities` never bound `sla_breached`/`asset_internet_facing` as Query params, and `GET /api/v1/assets` builds its query entirely inline (bypassing the `AssetFilter`/`service.py` path Plan 02 wired `internet_facing` into) — both fixed with the minimal, pattern-matching change (bind the Query param, pass/apply it), not a schema or architecture change.
- Discovered and fixed (Rule 2) that the tickets entity's interpreted SSE frame never carried the server-resolved asset UUID (`_resolve_hostname`'s result) — only the raw hostname string — leaving `buildNlqDeepLink` with nothing to put in `?asset_id=` for "Open in Tickets." Now additive (`interpreted_filter["resolved_asset_id"]`).

## Task Commits

Each task was committed atomically (TDD RED/GREEN pair for Task 1; a discrete deviation-fix commit between the two GREEN/frontend-wiring commits):

1. **Task 1 RED:** `test(44-05): add failing tests for buildNlqDeepLink + boolean/numeric URL-state helpers` — `faef3fb`
2. **Task 1 GREEN:** `feat(44-05): implement buildNlqDeepLink + boolean/numeric URL-state helpers` — `b4bf6b3`
3. **Deviation fix (Rule 3/Rule 2):** `fix(44-05): wire missing D-17 query params into vuln/asset routers + surface resolved ticket asset_id` — `32142ff`
4. **Task 2:** `feat(44-05): wire the D-17 field set into vulnerabilities/assets/tickets list pages` — `5970e74`

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `frontend/src/lib/ai/nlq-deep-link.ts` — `buildNlqDeepLink(entity, filter)`, the single source of truth for the D-17 param contract
- `frontend/src/lib/ai/nlq-deep-link.test.ts` — exact-string param-mapping tests for all 3 entities, list serialization, null omission, tickets hostname->asset_id supersession
- `frontend/src/hooks/use-url-state-scalar.ts` — `useUrlStateBool`/`useUrlStateNumber`
- `frontend/src/hooks/use-url-state-scalar.test.ts` — XSS-clamp + round-trip coverage
- `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx` — reads `cisa_kev`/`exploit_available`/`sla_breached`/`asset_internet_facing`/`age_days_min`; `hasActiveFilters` + "Clear all" CTA extended (Rule 1)
- `frontend/src/app/(authed)/dashboard/assets/page.tsx` — reads `internet_facing`
- `frontend/src/app/(authed)/dashboard/tickets/page.tsx` — reads a UUID-clamped `asset_id`
- `frontend/src/lib/queries/use-vulnerabilities.ts` — `VulnerabilitiesFilters`/`buildSearchParams` extended with `sla_breached`/`asset_internet_facing`/`age_days_min`
- `frontend/src/lib/queries/use-assets.ts` — `AssetsFilters`/`buildSearchParams` extended with `internet_facing`
- `frontend/src/lib/queries/use-tickets.ts` — `TicketsFilters`/`buildSearchParams` extended with `asset_id`
- `backend/app/vulnerabilities/router.py` — binds `sla_breached`/`asset_internet_facing` Query params into `VulnerabilityFilter(...)` (Rule 3)
- `backend/app/assets/router.py` — binds `internet_facing` Query param + one `.where()` clause (Rule 3)
- `backend/app/ai/query_assistant.py` — tickets branch's `interpreted_filter` gains `resolved_asset_id` (Rule 2)

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `GET /api/v1/vulnerabilities` never bound `sla_breached`/`asset_internet_facing` as Query params**
- **Found during:** Task 2 (wiring vulnerabilities/page.tsx)
- **Issue:** `VulnerabilityFilter` already has both fields (Plan 02), but the router builds the filter object from explicit `Query(...)` params — an unbound field is silently dropped before it ever reaches `VulnerabilityFilter`, so a deep-linked `?sla_breached=true`/`?asset_internet_facing=true` would have had zero filtering effect (FastAPI ignores unrecognized query params, no error).
- **Fix:** Added `sla_breached: bool | None = Query(None)` and `asset_internet_facing: bool | None = Query(None)`, passed both into the existing `VulnerabilityFilter(...)` constructor call.
- **Files modified:** `backend/app/vulnerabilities/router.py`
- **Verification:** `test_vulnerabilities_filters.py` (4/4) + `test_vulnerabilities.py` (regression) green; `ruff` clean; `mypy` shows no new errors on this file.
- **Committed in:** `32142ff`

**2. [Rule 3 - Blocking] `GET /api/v1/assets` never applied `internet_facing` despite `AssetFilter` supporting it**
- **Found during:** Task 2 (wiring assets/page.tsx)
- **Issue:** `AssetFilter.internet_facing` (Plan 02) is wired into `app/assets/service.py::_apply_filters`, but that service function is used ONLY by the AI query-assistant's `list_assets` call — the real `GET /api/v1/assets` route (consumed by `/dashboard/assets`) builds its query entirely inline in `router.py` and never calls that service path. Same silent-no-op risk as above.
- **Fix:** Added `internet_facing: bool | None = Query(None)` + one `query.where(Asset.internet_facing == internet_facing)` clause, matching the existing `min_risk` inline-filter pattern.
- **Files modified:** `backend/app/assets/router.py`
- **Verification:** `test_assets_tags_and_os_family.py` (regression) green; `ruff` clean; `mypy` shows no new errors on this file.
- **Committed in:** `32142ff`

**3. [Rule 2 - Missing Critical] Tickets' interpreted filter never surfaced the resolved asset UUID**
- **Found during:** Task 1 (designing `buildNlqDeepLink`'s tickets branch)
- **Issue:** `query_assistant.py` computes `resolved_asset_id` via `_resolve_hostname` to execute the tickets query, but the `interpreted` SSE frame sent to the frontend only ever contained the raw `asset_hostname` string (from `ticket_filter_input.model_dump()`, captured before resolution runs) — the frontend had no UUID to express `?asset_id=` for the tickets deep-link, even though the orchestrator already resolves one server-side every time.
- **Fix:** Added `interpreted_filter["resolved_asset_id"] = str(resolved_asset_id) if resolved_asset_id is not None else None` after resolution, before the `interpreted` SSE frame is yielded — an additive plain-dict key, not a schema field.
- **Files modified:** `backend/app/ai/query_assistant.py`
- **Verification:** `test_ai_query_stream.py` (25/25, including `test_tickets_entity_branch`/`test_unresolvable_hostname_is_zero_results`, neither of which asserts exact dict equality on `interpreted["filter"]`) green.
- **Committed in:** `32142ff`

**4. [Rule 1 - Bug] Vulnerabilities page's empty-state gating didn't account for the 5 new predicates**
- **Found during:** Task 2 (wiring vulnerabilities/page.tsx)
- **Issue:** The page's render branches are `pending -> error -> isEmptyFiltered -> items.length>0 -> null`. `isEmptyFiltered` was derived from `hasActiveFilters`, which only checked `severity`/`source`/`status`/`search`. A deep-link carrying ONLY a new boolean/numeric predicate (e.g. `?cisa_kev=true`) with zero matching rows would have `hasActiveFilters===false`, so `isEmptyFiltered` is `false`, and the final `null` branch renders — no empty state at all, violating the mandatory empty/loading/error-state contract (`state-patterns.md`, CLAUDE.md).
- **Fix:** Extended `hasActiveFilters` to include the 5 new predicates; extended the "Clear all" CTA's `onClick` to also reset all 5 (via the hooks' setters) so the empty-filtered state remains escapable.
- **Files modified:** `frontend/src/app/(authed)/dashboard/vulnerabilities/page.tsx`
- **Verification:** Existing `page.test.tsx` (regression) green; manual trace of the render-branch logic for a `cisa_kev`-only, zero-result deep-link.
- **Committed in:** `5970e74`

---

**Total deviations:** 4 auto-fixed (2 Rule 3 blocking, 1 Rule 2 missing-critical, 1 Rule 1 bug)
**Impact on plan:** All four were necessary for the plan's own stated must_haves ("the target list page actually reads and filters on" the full field set, and the mandatory empty-state contract) to actually hold end-to-end. No scope creep — every fix is a minimal, pattern-matching change to existing code the plan's own files already touch or directly depend on; none introduce a new table, schema, or architectural surface.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None. Every new/modified code path renders/serializes real, wired behavior; no hardcoded empty values or placeholder copy were introduced. The `resolved_asset_id` interpreted-filter key is a genuine additive field, not a stub — it is `null` only in the genuinely-unresolvable-hostname case, which already flows through the pre-existing, tested zero-results path (Plan 02).

## Threat Flags

None — every new/modified surface stays within this plan's own `<threat_model>`: T-44-11 (reflected XSS / param injection via list-page URL params) is mitigated by `useUrlStateBool`/`useUrlStateNumber`'s clamp-to-default and the tickets page's UUID-shape regex clamp, proven against a literal `<script>` payload in `use-url-state-scalar.test.ts`. T-44-12 (cross-tenant via a crafted param) remains `accept`-disposed and unaffected — every new/fixed backend Query param only ever populates a filter object; both routers still scope every query by the authenticated session's `tenant_id` server-side, unchanged.

## Next Phase Readiness
- Plan 04 (Ask page composition) can now import `buildNlqDeepLink` directly for its "Open in {list}" CTA — the param contract is proven against the actual list pages' own filter objects (not just asserted in isolation), and the backend fixes mean every param the deep-link emits has a real filtering effect, not just a URL that looks right.
- Plan 06 (eval/red-team CI gate) is unaffected by this plan — no prompt/model-facing surface changed.
- No blockers. NLQ-01 remains `[x]` complete in REQUIREMENTS.md (already marked at 44-02; this plan closes the loop D-17 promised on top of that, not a new requirement).

## Self-Check: PASSED

All 13 claimed created/modified files verified present on disk; all 4 task/deviation commit hashes (`faef3fb`, `b4bf6b3`, `32142ff`, `5970e74`) verified present in `git log`.

---
*Phase: 44-natural-language-query-assistant*
*Completed: 2026-08-25*
