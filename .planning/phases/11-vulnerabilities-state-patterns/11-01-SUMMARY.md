---
phase: 11-vulnerabilities-state-patterns
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, pytest, faceting, idor, ticketing]

# Dependency graph
requires:
  - phase: 10-dashboard
    provides: VulnerabilityFilter + list_vulnerabilities + dev/test fixture surface (client / client_factory / db_session / tenant_a/b / analyst_user / viewer_user); ?sort=triage Literal pattern; require_analyst + require_viewer RBAC dependencies
provides:
  - "GET /api/v1/vulnerabilities now accepts ?facets=severity,source,status with contextual count payload (Pitfall 1)"
  - "GET /api/v1/vulnerabilities accepts ?group=host returning one row per asset with denormalized severity counts; pagination on host rows not vuln rows"
  - "GET /api/v1/vulnerabilities sort axes expanded: severity / cve_id / cvss_v3_score / sla_due_at, paired with ?order=asc|desc"
  - "FacetsResponse, VulnerabilityByHost, VulnerabilityListResponse Pydantic models for the frontend list-page contract"
  - "POST /api/v1/tickets contract verified — 5 pytest cases pin role-guard / body-validation / 400-without-connector / 401-unauthenticated paths"
  - "Threat-model T-11-01..06 + T-11-08 mitigations landed (Literal-bounded params, max_length=10 caps, role + tenant scope, 400 on bad facets group, audit row on ticket.create)"
affects: [11-02-PLAN, 11-03-PLAN, 11-04-PLAN, 11-05-PLAN, 11-06-PLAN, 11-07-PLAN, 11-08-PLAN]

# Tech tracking
tech-stack:
  added: []   # No new libraries — extends existing FastAPI + SQLAlchemy 2.0 surface
  patterns:
    - "FILTER-clause faceting via model_copy(update={field: None}) + GROUP BY in one query per group — 3 round trips total, each on an indexed column"
    - "By-host grouping via tenant-filtered subquery → GROUP BY hostname with severity case-counts; pagination on grouped rows"
    - "Pydantic Literal pin on sort/order/group/facets — unknown values surface as 422 (sort/order/group) or 400 (facets CSV with bad name) before the handler runs (T-11-01..03)"
    - "Severity rank inverted (CRITICAL=4 → LOW=1) so ?order=desc puts CRITICAL first — matches user mental model 'descending severity = worst first'"
    - "Subquery column-label namespacing: rename Asset.id → host_asset_id, Asset.hostname → host_hostname to dodge SQLAlchemy's 'label being renamed to anonymous label due to disambiguation' refusal in GROUP BY subqueries"
    - "Unauth client fixture pattern: create_app + LifespanManager + raw ASGITransport (no get_current_user override) so HTTPBearer raises real 401 — used for D-P-04 verification"

key-files:
  created:
    - "backend/tests/test_vuln_sort.py — 7 pytest cases pinning expanded sort + order + 422 guards + Phase 10 triage regression"
    - "backend/tests/test_vuln_facets.py — 6 pytest cases for D-F-02 contextual facets + Pitfall 1 + T-11-04 tenant scope + T-11-03 400 on unknown group"
    - "backend/tests/test_vuln_group_host.py — 6 pytest cases for D-V-01 host grouping + severity counts + host-row pagination + T-11-04 IDOR + T-11-02 422"
    - "backend/tests/test_tickets_create.py — 5 pytest cases for the existing POST /api/v1/tickets endpoint (role guard, body validation, 401 path)"
    - ".planning/phases/11-vulnerabilities-state-patterns/deferred-items.md — pre-existing rate-limiter Redis localhost issue in conftest"
  modified:
    - "backend/app/vulnerabilities/schemas.py — VulnerabilityFilter.sort Literal extended (+ cve_id, cvss_v3_score, sla_due_at), added order + group Literals, max_length=10 caps on severity/source/status, new FacetsResponse + VulnerabilityByHost + VulnerabilityListResponse"
    - "backend/app/vulnerabilities/service.py — added get_facets + list_vulnerabilities_by_host; extended sort branches in list_vulnerabilities with explicit handlers for cve_id / cvss_v3_score / sla_due_at / severity"
    - "backend/app/vulnerabilities/router.py — wired Literal-typed order / group / facets Query params on list_vulns; CSV parsing + HTTP 400 on bad facets; response_model now VulnerabilityListResponse"

key-decisions:
  - "Severity rank inverted CRITICAL=4 → LOW=1 instead of CRITICAL=1 → LOW=5 so ?order=desc surfaces CRITICAL first (mental model: 'descending severity = worst first')"
  - "FacetsResponse subkeys default to empty dicts (default_factory=dict) so callers can probe `body['facets']['severity'].get('CRITICAL', 0)` without KeyError when a group wasn't requested"
  - "VulnerabilityListResponse.items declared as `list[VulnerabilitySummary] | list[VulnerabilityByHost]` — Pydantic discriminates at runtime based on which list was passed by the handler"
  - "test_tickets_create.py 'endpoint exists' test uses the existing 400-without-connector path as the 'reachable + role-guarded + validated' signal — no Asana mock needed, no external HTTP"
  - "Per-task pytest verification used (each test runs in its own pytest invocation) because the pre-existing rate-limiter Redis localhost binding pollutes multi-test pytest runs (logged in deferred-items.md)"

patterns-established:
  - "Contextual faceting (Pitfall 1): drop the matching filter via filters.model_copy(update={field: None}) before GROUP BY that field — keeps chip-bar showing alternatives the user could switch to"
  - "By-host grouping pagination: count distinct host rows for total, offset+limit on the grouped query, NOT on the underlying vuln rows"
  - "Subquery column-label namespacing inside SQLAlchemy: never reuse a column name from the base model in `.add_columns(label())` — SQLAlchemy refuses anonymous disambiguation in GROUP BY subqueries"
  - "Pydantic Literal at the route signature for every enum-like Query param — unknown values 422 before handler runs (no try/except, no manual normalization)"

requirements-completed: [UX-03-01, UX-03-02, UX-03-03, UX-03-05]

# Metrics
duration: 20min
completed: 2026-05-22
---

# Phase 11 Plan 01: backend list-endpoint extensions Summary

**Backend list endpoint now serves faceted counts, by-host grouping, and 4 new sort axes in single round-trips; 24 RED pytest cases pin the wire contract the Phase 11 frontend depends on**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-22T09:30:43Z
- **Completed:** 2026-05-22T09:51:00Z
- **Tasks:** 4 (all `<task type="auto" tdd="true">`)
- **Files created:** 5 (4 pytest files + 1 deferred-items log)
- **Files modified:** 3 (router.py, service.py, schemas.py in `backend/app/vulnerabilities/`)

## Accomplishments

- **Contextual faceting (D-F-02 / Pitfall 1):** `GET /api/v1/vulnerabilities?facets=severity,source,status` returns a `facets` object whose per-group counts are computed under **all OTHER** filters. The severity facet ignores the severity filter (so the chip-bar can keep showing alternatives) but respects every other filter (source/status/etc).
- **By-host grouping (D-V-01):** `?group=host` returns one row per asset with `vuln_count`, `critical_count`/`high_count`/`medium_count`/`low_count`, and `top_cvss`. Pagination is on host rows — 10k vulns on 500 hosts paginate 500 rows, not 10k.
- **Expanded sort axes (D-T-01):** Added `cve_id` (lex), `cvss_v3_score` (numeric, nulls last), `sla_due_at` (datetime, nulls last) to the existing `triage` + `severity`. Paired with `?order=asc|desc`.
- **POST /tickets contract verified (D-P-04):** 5 pytest cases pin the existing endpoint's role guard, 401-without-auth path, 422-on-bad-body, 400-without-connector reachability proof, and provider-Literal validation. Frontend mutation can target this contract with confidence.
- **Threat-model mitigations landed:** T-11-01 (Literal-bound sort), T-11-02 (Literal-bound group), T-11-03 (400 with bad-name detail for unknown facet groups), T-11-04 (tenant scope in `_apply_filters` covers both grouping paths), T-11-05 (max_length=10 on severity/source/status filter lists), T-11-06 (existing `require_analyst` regression-tested).

## Task Commits

1. **Task 11-01-01: RED tests for expanded sort + order** — `27957a8` (test)
2. **Task 11-01-02: RED tests for facets, group=host, verify POST /tickets** — `6af28a9` (test)
3. **Task 11-01-03: GREEN — extend schemas + service for facets and by-host grouping** — `fab3ab9` (feat)
4. **Task 11-01-04: Wire router params + return wrapper response with facets** — `d401875` (feat)

_Note: This plan ran RED → GREEN cycles per task. The schema + service changes (Task 03) and router wiring (Task 04) together flip every RED test from Tasks 01 + 02 to GREEN._

## Files Created/Modified

**Created (`backend/tests/`):**
- `test_vuln_sort.py` — 7 pytest cases. Targets `VulnerabilityFilter.sort` Literal extension + the new `order` param. Includes Phase 10 `?sort=triage` regression guard.
- `test_vuln_facets.py` — 6 pytest cases. Pins D-F-02 contextual math (Pitfall 1), T-11-04 IDOR, T-11-03 400 on unknown facet group.
- `test_vuln_group_host.py` — 6 pytest cases. Pins one-row-per-host, denormalized severity counts, host-row pagination (not vuln-row), severity filter, T-11-04 IDOR, T-11-02 422 on `?group=floor`.
- `test_tickets_create.py` — 5 pytest cases. Verifies the existing `POST /api/v1/tickets` endpoint (D-P-04). Includes an `unauth_client` fixture that builds an `AsyncClient` WITHOUT the `get_current_user` dependency override so HTTPBearer raises the real 401.

**Modified (`backend/app/vulnerabilities/`):**
- `schemas.py` — `VulnerabilityFilter.sort` Literal expanded to 5 entries; added `order` and `group` Literals; added `max_length=10` caps to severity/source/status filter lists (T-11-05). Three new response models: `FacetsResponse`, `VulnerabilityByHost`, `VulnerabilityListResponse`.
- `service.py` — `import HTTPException` added; sort branches in `list_vulnerabilities` extended; two new async functions: `get_facets` (3 grouped queries, one per facet field with model_copy to drop the matching filter) and `list_vulnerabilities_by_host` (tenant-filtered subquery → grouped query with severity case-counts, paginated on grouped rows).
- `router.py` — `list_vulns` signature gains `order`/`group`/`facets` Query params (Literal-typed for sort/order/group; CSV-parsed for facets). Body branches to `list_vulnerabilities_by_host` when `group=host` and calls `get_facets` when `facets` requested. New `response_model=VulnerabilityListResponse`.

**Created (`.planning/`):**
- `phases/11-vulnerabilities-state-patterns/deferred-items.md` — documents the pre-existing rate-limiter Redis-localhost-binding issue in `tests/conftest.py` that pollutes multi-test pytest runs.

## Decisions Made

- **Severity rank inverted** (CRITICAL=4 → LOW=1, not 1→5): so `?order=desc` surfaces CRITICAL first, matching the user mental model "descending severity = worst first". The default `else` branch in `list_vulnerabilities` (when `sort=None`) keeps the legacy rank-1=CRITICAL ordering for back-compat.
- **`FacetsResponse` subkeys default to empty dicts** (via `default_factory=dict`): so callers can probe `body['facets']['severity'].get('CRITICAL', 0)` without `KeyError` even when only a subset of groups was requested.
- **`VulnerabilityListResponse.items` typed as a union of two list shapes**, not a parameterized generic. Pydantic discriminates at runtime based on what the handler passes — simpler than typing a tagged union.
- **`test_tickets_create.py` test 1 (endpoint exists)** uses the existing 400-without-Asana-connector path as the "reachable + role-guarded + validated" signal. No Asana mock needed; no external HTTP. The 400 only fires after `require_analyst` accepts and `TicketCreateRequest` validates, so the test proves the full chain.
- **Per-task pytest verification** (each test in its own `pytest` invocation) because the pre-existing rate-limiter Redis-localhost binding in `tests/conftest.py:36` pollutes multi-test runs from the second test onwards. Documented in `deferred-items.md`; not in scope for this plan to fix (out-of-scope rule).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQLAlchemy "Label name asset_id is being renamed to an anonymous label" in `list_vulnerabilities_by_host`**
- **Found during:** Task 11-01-04 (after router wiring, first integration test against `?group=host`)
- **Issue:** The by-host subquery used `select(Vulnerability).add_columns(Asset.id.label("asset_id"))` — but `Vulnerability.asset_id` is already a column in the base `select`. SQLAlchemy refuses to silently disambiguate two `asset_id` labels in a subquery used by a downstream `GROUP BY`, raising `InvalidRequestError: Label name asset_id is being renamed to an anonymous label due to disambiguation which is not supported right now`.
- **Fix:** Renamed the Asset.id label to `host_asset_id` and Asset.hostname to `host_hostname` in the subquery; updated the outer `select` / `group_by` to reference the new names.
- **Files modified:** `backend/app/vulnerabilities/service.py` (`list_vulnerabilities_by_host`)
- **Verification:** `test_group_host_returns_one_row_per_asset` PASS after the rename
- **Committed in:** d401875 (Task 11-01-04)

**2. [Rule 1 - Bug] Test seed produced cve_id strings longer than the model's `String(20)` column**
- **Found during:** Task 11-01-04 (running `test_group_host_pagination_on_host_rows_not_vuln_rows`)
- **Issue:** Pagination test seeded 12 hosts × 5 vulns with `cve_id=f"CVE-PAG-{host.hostname}-{v}"` = e.g. `"CVE-PAG-host-pag-00-0"` (21+ chars). The Vulnerability model has `cve_id: Mapped[str | None] = mapped_column(String(20))`, so the INSERT fails with `asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(20)`.
- **Fix:** Shortened the seed pattern to `f"CVE-PG{h_idx:02d}{v}"` (≤11 chars).
- **Files modified:** `backend/tests/test_vuln_group_host.py`
- **Verification:** `test_group_host_pagination_on_host_rows_not_vuln_rows` PASS after the shortening
- **Committed in:** d401875 (Task 11-01-04, same commit as Rule 1 fix #1)

---

**Total deviations:** 2 auto-fixed (2 bugs — both surfaced during integration testing and both directly caused by my Task 03/04 code)
**Impact on plan:** Both fixes were corrections to in-task code, not scope creep. No plan changes required. No new dependencies. No threat-model changes.

## Issues Encountered

- **Pre-existing test-infrastructure noise (out-of-scope, deferred):** Multi-test pytest runs ERROR from the second test onwards because `tests/conftest.py:36` hard-codes `REDIS_TEST_URL = "redis://localhost:6379/1"` which is unreachable inside the `getvul-backend-1` container (Redis there is `redis:6379` via compose hostname). The rate-limiter middleware leaks a CancelledError coroutine, polluting the next test's connection pool. Each Phase 11 test PASSES when run standalone (`pytest tests/test_X.py::test_Y`). Plan-level verify runs all-tests-in-one-pytest, which trips this issue; per-test verification confirms the assertions are correct. Logged in `.planning/phases/11-vulnerabilities-state-patterns/deferred-items.md` with a suggested 1-line conftest fix (`REDIS_TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://localhost:6379/1")`).

- **Worktree vs main-repo file-path discipline (#3099):** Initially wrote `backend/tests/test_vuln_sort.py` to the main repo path (`/Users/.../getvul/backend/tests/`) via an absolute path that resolved to the orchestrator's cwd, not the worktree. Corrected by recopying to the worktree path and removing the accidental main-repo file. Subsequent edits used relative paths or the worktree-rooted absolute path. The container is mounted to the main-repo path, so test runs require a copy from worktree → main repo before each docker exec; the orchestrator merge-back will land all files at the correct path.

## User Setup Required

None — backend-only plan, no new env vars, no new external service config.

## Next Phase Readiness

**Ready for downstream Phase 11 plans:**
- The wire contract for the frontend list page is locked. Wave 1+ plans (11-02 onward) can build against the live API rather than a mock.
- `FacetsResponse`, `VulnerabilityByHost`, `VulnerabilityListResponse` Pydantic models are importable for any backend consumer.
- The 4 RED pytest files are now GREEN and run in <0.5s each — fast feedback for any future regression.

**Recommended follow-up (not blocking):**
- A 1-line fix to `tests/conftest.py` (env-var-aware `REDIS_TEST_URL`) would unblock the multi-test pytest pattern and let the SDK harness run all 24 Phase 11 tests in a single `pytest ... -x` call. Documented in `deferred-items.md`. Estimated cost: 5 min including verification.

## Self-Check: PASSED

Verified by tooling:
- `backend/tests/test_vuln_sort.py` — exists (7 `def test_`, 16 sort URL matches, 8 `422` matches)
- `backend/tests/test_vuln_facets.py` — exists (6 `def test_`, 9 facets URL matches)
- `backend/tests/test_vuln_group_host.py` — exists (6 `def test_`, 10 `group=host` matches)
- `backend/tests/test_tickets_create.py` — exists (5 `def test_`, 13 auth-pattern matches)
- `backend/app/vulnerabilities/schemas.py` — `class FacetsResponse`, `class VulnerabilityByHost`, `class VulnerabilityListResponse`, extended sort Literal, `order: Literal["asc", "desc"]`, `group: Literal["cve", "host"]`, `max_length=10` (3 occurrences)
- `backend/app/vulnerabilities/service.py` — `async def get_facets`, `async def list_vulnerabilities_by_host`
- `backend/app/vulnerabilities/router.py` — `response_model=VulnerabilityListResponse`, `order: Literal["asc", "desc"]`, `group: Literal["cve", "host"]`, `facets: str | None = Query`, `Unknown facet group` HTTP 400 path
- Each of the 24 Phase 11 pytest cases PASSES when run standalone via `docker exec getvul-backend-1 sh -c "cd /app && pytest tests/<file>::<test> --tb=no"`
- Phase 10 regression: `test_triage_sort.py::test_triage_sort_order` PASS; `test_vulnerabilities.py` (6 schema tests) PASS

Commits verified present on branch `worktree-agent-a09a582d1ad7e9c47`:
- `27957a8` test(11-01): RED expanded sort tests for /api/v1/vulnerabilities
- `6af28a9` test(11-01): RED tests for facets, group=host, and POST /tickets contract
- `fab3ab9` feat(11-01): facets + by-host grouping + expanded sort in vuln service layer
- `d401875` feat(11-01): wire ?facets= ?group= ?order= into list_vulns router

---
*Phase: 11-vulnerabilities-state-patterns*
*Completed: 2026-05-22*
