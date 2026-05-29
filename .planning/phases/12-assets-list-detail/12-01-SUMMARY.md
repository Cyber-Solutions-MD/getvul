---
phase: 12-assets-list-detail
plan: 01
subsystem: api
tags: [assets, postgres, alembic, sqlalchemy, fastapi, ilike, gin-index, tags]

requires:
  - phase: 11-vulnerabilities-state-patterns
    provides: Vulnerability.sla_due_at column + OPEN/IN_PROGRESS status taxonomy that the sla_breach aggregation reads
  - phase: 04-asset-classification
    provides: assets.os_name + assets.device_category baseline columns; alembic chain up to 024_add_containment_status

provides:
  - Asset.tags ARRAY(String) column (nullable; empty list default in API layer)
  - GIN index ix_assets_tags backing tag-search containment / ILIKE
  - GET /api/v1/assets accepts os_family= (comma-separated multi-select) with a hardcoded ILIKE allow-list (linux / windows / macos / other)
  - GET /api/v1/assets items emit tags + sla_breach (and sla_breach_count alias) per row
  - GET /api/v1/assets/{id} emits top-level tags + sla_breach AND vuln_counts.sla_breach
  - Inline vulnerabilities[] array stripped from detail response (frontend now owns this via useAssetVulnerabilities in 12-05)
affects: [12-05 query hooks, 12-06 /assets list page, 12-07 risk card, 12-08 detail page composition]

tech-stack:
  added: []
  patterns:
    - "Allow-list-clamped multi-value query params (split-on-comma → set-intersect with hardcoded keys) — T-12-01 mitigation pattern reusable by other taxonomy filters"
    - "Migration-time GIN index for ARRAY/JSONB columns instead of follow-up migrations (12-RESEARCH-AGENT.md #1)"

key-files:
  created:
    - backend/alembic/versions/025_add_asset_tags.py
    - backend/tests/test_assets_tags_and_os_family.py
    - .planning/phases/12-assets-list-detail/12-01-SUMMARY.md
  modified:
    - backend/app/assets/models.py
    - backend/app/assets/schemas.py
    - backend/app/assets/router.py

key-decisions:
  - "OS_FAMILY_PATTERNS hardcoded in source as Python literals; user-supplied os_family is clamped against the allow-list and only the keys (not the patterns) flow into the query — kills T-12-01 tampering at the boundary"
  - "Emit sla_breach in BOTH list-item top level AND list-item alias sla_breach_count to satisfy both the plan's Task 2 spec (sla_breach_count) and Task 4 test (sla_breach) — minor redundancy beats picking one and silently breaking the other"
  - "GIN-index the tags ARRAY at creation time (12-RESEARCH-AGENT #1) so the future tag-search-by-prefix extension lands without a follow-up migration"
  - "Dropped the inline vulnerabilities[] array from the detail response per fold-in #3 — the v2.0 detail page reads from useAssetVulnerabilities (12-05), keeping both would double-fetch on every detail load. v1's detail page is being rewritten in 12-08; no external consumers documented"
  - "os_family accepts comma-separated multi-value (W4) so the chip-bar in 12-06 can OR families together without losing selections"

patterns-established:
  - "Allow-list-clamped multi-value filter: split on comma → strip/lower → set-intersect with hardcoded allow keys → OR ILIKE patterns. Reusable for any taxonomy-style filter"
  - "Both-shapes-emit pattern: when downstream consumers disagree on naming, emit both keys until the next consumer phase locks the canonical name"

requirements-completed: [UX-04-01, UX-04-02]

duration: 10min
completed: 2026-05-29
---

# Phase 12 Plan 01: Backend Assets Surface (tags + sla_breach + os_family) Summary

**Adds Asset.tags ARRAY(String) + GIN index, sla_breach aggregate in list/detail vuln_counts, and a hardcoded-ILIKE os_family filter on the list endpoint (T-12-01 mitigated).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-29T14:11:58Z (first task commit)
- **Completed:** 2026-05-29T14:22:00Z (final task commit)
- **Tasks:** 4
- **Files modified:** 3 (models.py, schemas.py, router.py)
- **Files created:** 2 (alembic 025, tests file)

## Accomplishments

- Asset model + Pydantic schemas extended with `tags`; AssetSummary also exposes `sla_breach_count`
- list_assets now accepts `os_family=` (comma-separated multi-select) backed by an allow-list-clamped ILIKE prefix map; T-12-01 mitigated by construction (patterns are source-literal, not user-composed)
- list_assets + get_asset both compute `sla_breach` from the existing `Vulnerability.sla_due_at` column (count vulns where `sla_due_at < now()` AND status in (OPEN, IN_PROGRESS))
- get_asset response now emits top-level `tags` + `sla_breach` AND `vuln_counts.sla_breach`; inline `vulnerabilities[]` array stripped (Phase 12 frontend reads from a dedicated useAssetVulnerabilities hook)
- Alembic revision 025_add_asset_tags applied; column + GIN index verified via direct SQLAlchemy introspection
- 10/10 backend tests pass in the new file: tags roundtrip, sla_breach aggregation correctness, 7-row parametrized OS-family matrix, and the "other" exclusion case

## Hardcoded OS_FAMILY_PATTERNS (canonical — chip-bar parity reference)

Downstream chip-bar (12-06) must render only families whose keys appear here. Frontend-side derivation may use the SAME prefixes (lower-cased) to label rows without a roundtrip.

```python
OS_FAMILY_PATTERNS = {
    "linux":   ["%linux%", "%ubuntu%", "%debian%", "%centos%", "%rhel%", "%fedora%"],
    "windows": ["%windows%"],
    "macos":   ["%macos%", "%mac os%"],
}
# "other" is computed in-handler as: os_name NOT NULL AND NOT any-of-the-above prefix.
```

Allow-list keys: `{"linux", "windows", "macos", "other"}`. Unknown values silently dropped (XSS clamp).

## Task Commits

1. **Task 1: Asset.tags column + schema fields** — `005f227` (feat)
2. **Task 2: list/detail surface tags + sla_breach + os_family filter** — `43d3a88` (feat)
3. **Task 3 [BLOCKING]: Alembic 025 + apply** — `9ec9938` (feat)
4. **Task 4: backend tests** — `1745476` (test)

## Files Created/Modified

- `backend/app/assets/models.py` — added `tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)`; extended dialects.postgresql import for ARRAY
- `backend/app/assets/schemas.py` — `AssetResponse.tags`, comment locking `vuln_counts.sla_breach` requirement, `AssetSummary.tags` + `sla_breach_count`
- `backend/app/assets/router.py` — new `os_family` query param + `OS_FAMILY_PATTERNS` allow-list block, sla_breach in both vuln_q select lists, top-level + nested keys in get_asset response, inline vulnerabilities[] removed, unused `case` import dropped
- `backend/alembic/versions/025_add_asset_tags.py` — new revision; ARRAY column + GIN index
- `backend/tests/test_assets_tags_and_os_family.py` — 4 test functions (one parametrized 7×) + autouse engine-dispose fixture

## Decisions Made

- **Dual key emission for the list item (`sla_breach` + `sla_breach_count`).** The plan's Task 2 step 4 specified `sla_breach_count` for the list item; Task 4's test asserts `target["sla_breach"] == 1`. Rather than silently choose one and break the other (or rewrite the test mid-plan), the handler emits both — the redundancy is a few bytes per row and gives downstream phases free rein to lock the canonical name later. Tracked as a deviation below.
- **Top-level AND nested `sla_breach` on the detail response.** Same logic — the plan promises `vc.sla_breach` "in the dict returned" *and* `vuln_counts.sla_breach`; emitting both lets the rail RiskCard read either shape.
- **GIN index added at creation time** rather than in a follow-up migration. Per 12-RESEARCH-AGENT.md addition #1 — supports the future tag-search containment + ILIKE work without a Phase 13+ migration churn.
- **Inline `vulnerabilities[]` array stripped from get_asset** per 12-RESEARCH-AGENT.md addition #3. The v2.0 detail page consumes the same data through `useAssetVulnerabilities` (12-05); keeping the inline array double-fetches per page load. v1's `/dashboard/assets/[id]/page.tsx` is being rewritten in plan 12-08; no external consumers documented.
- **Comma-separated multi-value `os_family`** per W4 — chip-bar UX in 12-06 needs to OR families together (`?os_family=linux,windows`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug in plan: inconsistent field naming] Emitted both `sla_breach` and `sla_breach_count` on list items**

- **Found during:** Task 4 (running the planned test_list_assets_returns_tags_and_sla_breach assertion `target["sla_breach"] == 1`)
- **Issue:** Plan's Task 2 step 4 says `"sla_breach_count": vcounts.sla_breach`. Plan's Task 4 test asserts `target["sla_breach"]`. The two are inconsistent — picking either would silently break the other.
- **Fix:** Emit both keys on each list item, with identical values from the same aggregation.
- **Files modified:** `backend/app/assets/router.py`
- **Verification:** Task 4 test_list_assets passes; the field is also documented as `sla_breach_count` on `AssetSummary` (Task 1) so the typed schema layer (Pydantic) still validates.
- **Committed in:** `43d3a88` (Task 2 commit)

**2. [Rule 3 — Blocking issue: pre-existing test infra] Added autouse engine-dispose fixture to my test file**

- **Found during:** Task 4 (`pytest -x` was failing tests 2+ in the file with `RuntimeError: Event loop is closed`)
- **Issue:** `app.db.session.engine` is a module-level async engine whose asyncpg pool binds to whichever event loop made the first connection. pytest-asyncio creates a fresh event loop per test (function-scoped), so the second test's connection is bound to a dead loop and either skips (via conftest's `_db_reachable()` returning False) or hard-errors during `session.flush()`. Pre-existing across the whole suite (verified by reproducing in `test_snooze.py`).
- **Fix:** Added an autouse `_reset_engine_pool` fixture LOCAL to this test file (not conftest) that calls `await engine.dispose()` before each test, forcing a fresh pool bound to the current loop. Scoped to this file so the global conftest stays untouched.
- **Files modified:** `backend/tests/test_assets_tags_and_os_family.py`
- **Verification:** `pytest -x tests/test_assets_tags_and_os_family.py -q` now reports `10 passed`. Other test files unaffected.
- **Committed in:** `1745476` (Task 4 commit)

### Plan-criterion that is intentionally NOT met

- **`alembic check` exits 0** — does NOT pass post-12-01 because the codebase has a pre-existing model-vs-migration drift across many unrelated tables (saved_filters table, vulnerability indexes, asset comment defaults, vulnerability_correlations NOT NULL constraints, etc.). The drift is independent of this plan — direct introspection confirms `tags` column + `ix_assets_tags` GIN index are correctly applied. Fixing the global drift is out of 12-01 scope; documented for a future cleanup phase (recommend a new plan: "alembic baseline / autogenerate sync").

---

**Total deviations:** 2 auto-fixed (1 Rule 1 — plan inconsistency, 1 Rule 3 — pre-existing test infra)
**Impact on plan:** Both fixes were necessary to land the success criteria. No scope creep — both stayed in the files Task 4 already touches.

## Issues Encountered

- **Python 3.14 default in worktree venv.** Initial `python3 -m venv .venv` picked up Python 3.14.5; the project targets 3.12 (`pyproject.toml [tool.mypy] python_version = "3.12"`). Rebuilt the venv with `python3.12 -m venv .venv`. Made no difference to the asyncio loop-closed bug (it reproduced under both), but kept the suite aligned with project conventions.
- **No virtual env or running DB at agent start.** Spun up Postgres + Redis via `docker compose up -d postgres redis`, then ran `alembic upgrade head` to bring the empty DB from 0 → 024 → 025. None of this was destructive; it's the standard dev-bootstrap path the project docs describe.

## User Setup Required

None — backend-only schema delta; no new env vars, no third-party services touched.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none — all surface changes in this plan are covered by T-12-01..03 in the canonical STRIDE register; no new boundaries introduced) | — | — |

## Self-Check: PASSED

- File `backend/app/assets/models.py` — FOUND, `tags` column declared
- File `backend/app/assets/schemas.py` — FOUND, AssetResponse.tags + AssetSummary.tags + sla_breach_count present
- File `backend/app/assets/router.py` — FOUND, os_family param + OS_FAMILY_PATTERNS + sla_breach + tags emitted; inline vulnerabilities[] removed
- File `backend/alembic/versions/025_add_asset_tags.py` — FOUND, revision = "025_add_asset_tags", down_revision = "024_add_containment_status", GIN index present
- File `backend/tests/test_assets_tags_and_os_family.py` — FOUND, 4 test_ functions, 10/10 passing
- Commit `005f227` — FOUND in `git log` (Task 1)
- Commit `43d3a88` — FOUND in `git log` (Task 2)
- Commit `9ec9938` — FOUND in `git log` (Task 3)
- Commit `1745476` — FOUND in `git log` (Task 4)
- `alembic current` reports `025_add_asset_tags (head)` — VERIFIED
- `pytest -x tests/test_assets_tags_and_os_family.py -q` → 10 passed — VERIFIED

## Next Phase Readiness

- 12-02 (owner reassign + tickets asset_id filter) can run independently — same wave, no shared files with 12-01.
- 12-05 (assets query hooks) can now consume `tags`, `sla_breach`, and `os_family` from the API without further roundtrips.
- 12-06 (assets chip-bar) has the canonical OS_FAMILY_PATTERNS map reference in this Summary for parity.
- 12-07 (RiskCard) can read `vuln_counts.sla_breach` for row 2 (UX-04-03).
- 12-08 (detail page composition) must NOT expect the inline `vulnerabilities[]` array — it now uses useAssetVulnerabilities.

---

*Phase: 12-assets-list-detail*
*Plan: 01*
*Completed: 2026-05-29*
