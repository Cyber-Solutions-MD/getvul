---
phase: 31-connector-enrichment-rewrite
plan: 01
subsystem: backend/connectors
tags: [sqlalchemy, alembic, postgres, epss, cisa-kev, fastapi, mypy]

# Dependency graph
requires: []
provides:
  - "epss_percentile/native_priority_score/native_priority_rating/source_signals columns on vulnerabilities (alembic 035)"
  - "global epss_scores/cisa_kev reference tables, cve_id PK, no tenant_id (alembic 036, D-11)"
  - "EpssScore/CisaKev ORM models (app/vulnerabilities/models.py)"
  - "NormalizedVulnerability.native_priority_score/native_priority_rating/source_signals dataclass fields (app/connectors/base.py)"
  - "_lookup_enrichment single-choke-point EPSS/KEV ref-table lookup + wired into both _upsert_vulnerability branches (app/connectors/sync.py)"
  - "Defender's full enrichment: source_signals raw-key allowlist + explicit-null native_priority_* (app/connectors/defender.py)"
  - "VulnerabilityResponse schema fields for the 4 new columns (read-model only, no sort=/filter wiring)"
affects: ["31-02 (feed fetcher writes into the same epss_scores/cisa_kev tables)", "31-03", "31-04", "31-05 (all 4 build on this write-path + dataclass contract)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-choke-point enrichment: EPSS/KEV are looked up ONCE in _upsert_vulnerability, never per-connector (connectors have no DB access)"
    - "source_signals built from the RAW vendor dict inline in the parser (never post-processing the already-bool()-coerced dataclass) so missing-vs-negative survives"
    - "native_priority_score/rating explicitly None (not omitted) for connectors with no vendor composite, never a synthesized cross-boolean score"

key-files:
  created:
    - backend/alembic/versions/035_add_enrichment_columns.py
    - backend/alembic/versions/036_add_enrichment_ref_tables.py
    - backend/tests/test_vulnerability_enrichment.py
  modified:
    - backend/app/vulnerabilities/models.py
    - backend/app/connectors/base.py
    - backend/app/connectors/sync.py
    - backend/app/connectors/defender.py
    - backend/app/vulnerabilities/schemas.py
    - backend/app/connectors/qualys.py
    - backend/tests/test_connectors/test_defender_connector.py

key-decisions:
  - "source_signals typed dict[str, Any] | None (not the interfaces block's literal bare dict | None) in base.py/models.py/schemas.py -- strict mypy flags bare dict as a type-arg violation; fixing it in the tracer plan prevents the same regression from being copy-pasted into 5 more connectors in Plans 02-05"
  - "qualys.py's base dict given an explicit dict[str, Any] annotation (single-line, zero behavior change) to absorb the cascading NormalizedVulnerability **kwargs arg-type mismatch that widening the shared dataclass caused -- a necessary, narrowly-scoped fix outside this plan's own file list, directly caused by this plan's schema change"
  - "ENRICH-01/02/03/04/06 left [ ] Pending in REQUIREMENTS.md -- shared-ID gate: every one of these 5 IDs is also declared by at least one other not-yet-executed Phase 31 plan (ENRICH-01/02 by 31-02's real feed fetcher; ENRICH-03/04/06 by 31-03/04/05's remaining 5 connectors + cross-6 sweep). This plan proves the mechanism end-to-end on Defender only; requirements flip when their last declaring plan lands, mirroring the CORR-01/03 (Phase 30) and AIE-01/02 (Phase 28) precedents"

patterns-established:
  - "_lookup_enrichment(db, cve_id) -> (epss_score, epss_percentile, cisa_kev): the exact shape every future write-path enrichment lookup should follow -- select-then-scalar_one_or_none, miss returns (None, None, False), never raises"
  - "Per-connector source_signals allowlist: a module-level tuple of raw vendor field names, checked with `if key in record` (not `.get()`) so a vendor-omitted field never becomes a False/None entry"

requirements-completed: []  # ENRICH-01/02/03/04/06 all shared-ID gated on other Phase 31 plans -- see key-decisions

# Metrics
duration: 25min
completed: 2026-08-05
---

# Phase 31 Plan 01: Defender Enrichment Tracer Summary

**Threaded EPSS score+percentile and catalog-authoritative CISA KEV through the single `_upsert_vulnerability` choke point for every connector, and gave Defender its full `source_signals` allowlist + explicit-null native-priority pair — proving the entire enrichment schema and write-path end-to-end on one connector before the remaining 5 connectors build on it.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-05T09:53Z (approx, per STATE.md session marker)
- **Completed:** 2026-08-05T10:18Z
- **Tasks:** 3 (RED / GREEN part 1 / GREEN part 2)
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- Two new Alembic migrations (035, 036) landed the full schema spine: 4 new `vulnerabilities` columns (`epss_percentile`, `native_priority_score`, `native_priority_rating`, `source_signals`) with sort-supporting btree indexes, plus two new **global** (no `tenant_id`, D-11) reference tables `epss_scores`/`cisa_kev` keyed by `cve_id`. Applied to the dev Postgres; `alembic heads` confirms a single head.
- `_lookup_enrichment(db, cve_id)` in `sync.py` is now the single choke point where every connector's ingest gets `epss_score`/`epss_percentile`/`cisa_kev` snapshotted from the global ref tables — wired into **both** the update and insert branches of `_upsert_vulnerability`. The CISA KEV catalog is the sole authority for the `cisa_kev` column; a connector's own KEV-ish guess (e.g. Defender's `cisa_kev=False` hardcode, left untouched in the parser per the plan's explicit prohibition) is never consulted for the column, only preserved in `source_signals`.
- Defender's `_normalize_vuln` builds `source_signals` inline from the **raw** record dict (allowlist: `exploitVerified`, `publicExploit`, `exploitInKit`, `exploitTypes`, `exploitUris`, `EPSS`) — a key lands in the dict only if the vendor's API actually returned it, so "vendor returned False" and "vendor never mentioned it" are distinguishable in the same finding. `native_priority_score`/`native_priority_rating` are explicit `None` (Defender has no vendor-authored composite rating).
- Both new/extended test files prove all four Defender-slice success criteria (SC#1-4) end-to-end against a real Postgres, with a strict RED→GREEN TDD cycle (3 commits: `test` → `feat` schema → `feat` write-path).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Defender source_signals unit fixture + EPSS/KEV write-path integration test** - `2b456f4` (test)
2. **Task 2: GREEN part 1 — schema spine (migrations 035+036, models, dataclass fields, response schema)** - `188298a` (feat)
3. **Task 3: GREEN part 2 — enrichment write-path + Defender parser (+ mypy-baseline correctness fix)** - `8605290` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_TDD gate compliance: RED (`2b456f4`) → GREEN (`188298a`, `8605290`). Both gates present in git log — compliant._

## Files Created/Modified

- `backend/alembic/versions/035_add_enrichment_columns.py` - 4 new `vulnerabilities` columns + 2 sort indexes, symmetric downgrade
- `backend/alembic/versions/036_add_enrichment_ref_tables.py` - `epss_scores`/`cisa_kev` global tables (D-11 exception, documented inline)
- `backend/app/vulnerabilities/models.py` - 4 new `Vulnerability` columns + `EpssScore`/`CisaKev` ORM models (compose `Base, TimestampMixin` only, per D-11)
- `backend/app/connectors/base.py` - `native_priority_score`/`native_priority_rating`/`source_signals` (`dict[str, Any] | None`) on `NormalizedVulnerability`
- `backend/app/connectors/sync.py` - `_lookup_enrichment` helper; both `_upsert_vulnerability` branches now set `epss_score`/`epss_percentile`/`cisa_kev` from the ref-table lookup (never `v.cisa_kev`) plus `native_priority_*`/`source_signals` via the existing `getattr(v, "field", None)` defensive-read idiom
- `backend/app/connectors/defender.py` - `_SOURCE_SIGNAL_ALLOWLIST` + inline `source_signals` build in `_normalize_vuln`; `native_priority_score`/`rating` explicit `None`; `cisa_kev=False` hardcode left byte-for-byte unchanged
- `backend/app/vulnerabilities/schemas.py` - `VulnerabilityResponse` gains `epss_percentile`/`native_priority_score`/`native_priority_rating`/`source_signals` (`= None` trailing style, matching `exploit_status_id`/`exploit_status_name` precedent)
- `backend/app/connectors/qualys.py` - `base` dict given an explicit `dict[str, Any]` type annotation (mypy-only fix, zero behavior change — see Deviations)
- `backend/tests/test_connectors/test_defender_connector.py` - new unit test: source_signals missing-vs-negative + explicit-null native_priority_* + no-PII-leak (SC#3/SC#4)
- `backend/tests/test_vulnerability_enrichment.py` (new) - integration tests: ref-table hit → `epss_score`/`epss_percentile`/`cisa_kev` populated authoritatively (SC#1/SC#2); ref-table miss → `None`/`None`/`False`

## Decisions Made

- `source_signals` typed `dict[str, Any] | None` (not the interfaces block's literal bare `dict | None`) across `base.py`/`models.py`/`schemas.py` — strict mypy's `type-arg` check flags bare generic `dict`; fixing this now (in the lead tracer) prevents the same mypy-baseline regression from being copy-pasted into 5 more connectors across Plans 02-05.
- `qualys.py`'s `base = dict(...)` given an explicit `dict[str, Any]` annotation — a one-line, non-behavioral fix for a cascading `arg-type` error that widening the shared `NormalizedVulnerability` dataclass caused at its `**base` unpacking call site (a file this plan does not otherwise touch, but the regression is directly caused by this plan's change).
- ENRICH-01/02/03/04/06 left `[ ]` Pending in REQUIREMENTS.md — every one is a shared-ID declared by at least one other not-yet-executed Phase 31 plan (31-02 for ENRICH-01/02's real feed; 31-03/04/05 for ENRICH-03/04/06's remaining 5 connectors + cross-6 sweep). Mirrors the CORR-01/03 (Phase 30) and AIE-01/02 (Phase 28) shared-ID-gate precedent already established in this project.
- Wrote the SC#1/SC#2 integration test as two focused test functions (in-catalog / not-in-catalog) sharing one seed+teardown fixture, rather than one combined test — clearer failure attribution, same coverage the plan's `<behavior>` narrative describes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy-baseline regression from Task 2's bare-`dict` schema fields**
- **Found during:** Task 3 (running the plan's mandated regression checks before commit)
- **Issue:** Task 2's `source_signals: dict | None` fields in `base.py`/`models.py`/`schemas.py` (following the interfaces block's literal, unparameterized `dict` type) fail strict mypy's `type-arg` check, and cascaded into 2 new `arg-type` errors on `qualys.py`'s pre-existing `NormalizedVulnerability(cve_id=cve, **base)` call site (a file untouched by this plan). Confirmed as newly-introduced (not pre-existing) via `git stash` + `rm -rf .mypy_cache` before/after diffing against the Task-2-only committed state, per this project's own documented flake-verification protocol.
- **Fix:** Retyped all three `source_signals` fields as `dict[str, Any] | None` (adding `from typing import Any` where missing); added a matching `dict[str, Any] = {}` local-variable annotation in `defender.py`; added a single explicit `dict[str, Any]` type annotation to `qualys.py`'s `base` dict (no logic change).
- **Files modified:** `backend/app/connectors/base.py`, `backend/app/vulnerabilities/models.py`, `backend/app/vulnerabilities/schemas.py`, `backend/app/connectors/defender.py`, `backend/app/connectors/qualys.py`
- **Verification:** `mypy app/ | mypy-baseline filter --allow-unsynced` — 0 new `type-arg`/`arg-type` violations after the fix (the qualys.py annotation additionally cleared 12 pre-existing baselined `arg-type` errors as a side effect). The 3 remaining "new" lines each run are `note:` hints on `app/auth/dependencies.py` — a confirmed pre-existing, environment-level nondeterministic flake (mypy emits its jose-stub-missing hint once per run and the file it attaches to shifts with internal processing order; reproduced identically on the unmodified Task-2-only commit).
- **Committed in:** `8605290` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — mypy type-correctness bug spanning 5 files, none of them behavioral)
**Impact on plan:** Zero runtime/behavior change; purely static-typing correctness. No scope creep — the qualys.py touch is a single type annotation, directly caused by and necessary for this plan's own schema change to pass the project's mandatory mypy-baseline CI gate.

## Issues Encountered

None beyond the mypy deviation above. Postgres was reachable throughout (docker-compose dev stack, `localhost:5432`), so the integration test ran for real rather than skipping — migrations 035/036 were applied live and verified via direct schema introspection (4 new columns on `vulnerabilities`; `epss_scores`/`cisa_kev` both `cve_id`-PK'd with no `tenant_id` column).

## User Setup Required

None — no external service configuration required. The EPSS/CISA KEV feeds themselves are fetched by Plan 02's scheduler job, not this plan.

## Next Phase Readiness

- The schema + write-path contract is fully proven and ready for Plans 02-05 to build on: `_lookup_enrichment`'s signature, the `NormalizedVulnerability` dataclass fields, and the `source_signals`/`native_priority_*` typing (`dict[str, Any] | None` — downstream plans should follow this typed form, not the interfaces block's literal bare `dict`) are all locked.
- Plan 02 (daily scheduler feed refresh) can populate `epss_scores`/`cisa_kev` with real FIRST.org/CISA data against the now-existing tables; Plan 01's tests seed synthetic rows only.
- Plans 03/04/05 each add their own connector's native signal + `source_signals` allowlist to `_normalize_vuln`-equivalent functions, following Defender's exact pattern (build inline from the raw payload, allowlist by raw field name, explicit `None` for connectors with no vendor composite).
- No blockers. `alembic heads` is a single head (`036_add_enrichment_ref_tables`); full connector + vulnerability-schema regression suite green (156 tests sampled across `test_connector_normalization.py`, all 6 `test_connectors/*.py` files, `test_connector_health.py`, `test_dashboard_tiles.py`, `test_sla_service.py`, `test_top_vuln.py`, `test_vuln_facets.py`, `test_vuln_group_host.py`, `test_vuln_sort.py`, `test_vuln_source_filter.py`, `test_vulnerabilities.py`).

---
*Phase: 31-connector-enrichment-rewrite*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 10 created/modified source files confirmed present on disk; all 3 task commit hashes (`2b456f4`, `188298a`, `8605290`) confirmed in `git log`.
