---
phase: 30-correlation-schema-fix
verified: 2026-08-05T00:00:00Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 30: Correlation Schema Fix Verification Report

**Phase Goal:** Cross-source correlation records the true, complete set of scanners that see each CVE-on-host — no silent data loss, no hardcoded source limit — so every downstream v4.0 feature that reads "which sources see this finding" has a correct foundation.
**Verified:** 2026-08-05
**Status:** passed
**Re-verification:** No — initial verification

## Verification Method

This is a pure backend schema+service phase (no UI surface). Verification combined static code inspection with **live execution** against the running dev stack (`getvul-postgres-1` on `localhost:5432`, schema already at `alembic head = 034_add_correlation_sources`):

- Ran `pytest tests/test_correlation_service.py -v` directly (not trusting SUMMARY's reported "10 passed") — **confirmed 10/10 passed** against the live Postgres instance.
- Queried `information_schema.columns` and `pg_indexes` directly against the live `vulnerability_correlations` table to confirm actual schema shape (not just migration-file source).
- Ran `git diff <pre-phase-commit> <post-phase-commit> -- correlation_service.py` to confirm the claimed "only two functions changed" scoping.
- Ran the project's exact CI mypy-baseline gate command to confirm no net-new violations from this phase's files.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `vulnerability_correlations.sources` is `ARRAY(String)` with a GIN index; the 4 legacy FK columns are gone | ✓ VERIFIED | Live DB query: columns = `[asset_id, confidence, cve_id, id, source_vuln_ids, sources, sources_count, tenant_id]`; index `ix_vulnerability_correlations_sources` is `USING gin (sources)`. No `crowdstrike_vuln_id`/`nessus_vuln_id`/`defender_vuln_id`/`wiz_vuln_id` present. |
| 2 | Covers all 6 `VulnSource` values, forward-compatible with a 7th | ✓ VERIFIED | `_SOURCE_ORDER = [s.value for s in VulnSource]` in `correlation_service.py:18` — adding a 7th enum member requires zero code change. `test_confidence_bands` parametrizes 2..6 and passes for all. |
| 3 | `correlation_service.py` has no `SOURCE_COLUMN_MAP`; `sources`/`sources_count` derive from one canonical list | ✓ VERIFIED | `grep -c SOURCE_COLUMN_MAP correlation_service.py` = 0 (confirmed). `sources = [s for s in _SOURCE_ORDER if s in source_vulns]`; `sources_count = len(sources)` — same list, structurally cannot disagree. |
| 4 | A Qualys+Rapid7-only finding (previously silently dropped) now correlates — SC#4 | ✓ VERIFIED | `test_qualys_rapid7_only_correlation_no_longer_silently_dropped` — **executed live, PASSED**. `sources==['QUALYS','RAPID7']`, `sources_count==2`, `confidence=='MEDIUM'`, both `source_vuln_ids` mapped to `str(uuid)`. |
| 5 | `alembic upgrade head` applies cleanly; revision id under 32-char cap | ✓ VERIFIED | Live `alembic current` → `034_add_correlation_sources (head)`. Revision string is 27 chars. |
| 6 | `recorrelate_all_tenants.py` recovers previously-dropped correlations, tenant-scoped, proven at runtime (not just static inspection) — CORR-02 | ✓ VERIFIED | `test_recorrelate_tenant_corrects_backfill_bug_signature` — **executed live, PASSED**. Seeds the exact post-backfill bug signature (`sources=[]`, `sources_count=2`), proves the COALESCE consistency query is non-zero pre-recovery, then proves `_recorrelate_tenant` corrects (not deletes) the row and drives `inconsistent_rows_after` to 0. |
| 7 | `sources_count == len(sources)` for every source combination 1-of-6 through 6-of-6 | ✓ VERIFIED | `test_single_source_does_not_correlate` (1-source → no row) + `test_confidence_bands[2..6]` — all 6 executed live, all PASSED, each asserting `len(sources)==sources_count`. |
| 8 | Confidence banding: HIGH ≥4, MEDIUM 2-3, per D-08 | ✓ VERIFIED | `test_confidence_bands` parametrized `[(2,"MEDIUM"),(3,"MEDIUM"),(4,"HIGH"),(5,"HIGH"),(6,"HIGH")]` — all passed live. `correlation_service.py:47-52` implements exactly this banding. |
| 9 | Sources emitted in canonical `VulnSource` enum-declaration order regardless of discovery order | ✓ VERIFIED | `test_confidence_bands` asserts `corr["sources"] == sources_to_seed` (canonical `_SOURCE_ORDER` slice) — passed live for all 6 combinations. |
| 10 | Cross-tenant isolation: a tenant_a correlation is never visible to tenant_b | ✓ VERIFIED | `test_correlation_tenant_scoped` — executed live, PASSED. `get_correlation_for_vuln(db, tenant_b, cve_id, asset_id)` returns `None`. |
| 11 | `GET /{vuln_id}/correlation` stays `require_viewer`-gated, tenant-scoped, and its body carries the new shape with zero legacy keys — D-09 | ✓ VERIFIED | `test_correlation_route_returns_d09_shape` — executed live via authed `client` fixture, PASSED. `router.py:674-694` confirmed unedited (0-line diff across the whole phase) and still `Depends(require_viewer)`. |
| 12 | Migration is transactional / cleanly reversible in schema shape (documented-lossy downgrade) | ✓ VERIFIED | `034_add_correlation_sources.py::downgrade()` re-adds the 4 FK columns, drops `sources`/index/`source_vuln_ids`; docstring explicitly documents the one-way data loss for non-legacy sources. |
| 13 | `_find_correlated_groups` / `_prune_stale_correlations` left byte-for-byte unchanged | ✓ VERIFIED | `git diff <pre-phase>..<post-phase> -- correlation_service.py` shows only `run_correlations` and `get_correlation_for_vuln` bodies (plus the `_SOURCE_ORDER` constant and import) changed; both helper functions absent from the diff. |
| 14 | No orphaned references to the removed FK columns / `SOURCE_COLUMN_MAP` anywhere in the backend | ✓ VERIFIED | `grep -rn "crowdstrike_vuln_id\|nessus_vuln_id\|defender_vuln_id\|wiz_vuln_id\|SOURCE_COLUMN_MAP" app/` → 0 hits. Only remaining mentions are historical (`001_initial_schema.py`, its own creation) and the migration's own documented backfill/downgrade code + test docstring commentary. |
| 15 | No CI regression introduced by this phase (mypy gate) | ✓ VERIFIED | Ran the exact CI command `mypy app/ \| mypy-baseline filter --allow-unsynced` live: `fixed=3/new=3`, all 3 "new" being the pre-existing, previously-documented `note`-line nondeterminism on `app/auth/dependencies.py` (unrelated file, not touched by this phase). Net new unbaselined violations attributable to this phase = 0. |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/vulnerabilities/models.py` | `sources`/`source_vuln_ids` added, 4 FK columns removed | ✓ VERIFIED | Confirmed via read + live DB schema query |
| `backend/alembic/versions/034_add_correlation_sources.py` | GIN-indexed `sources` + `source_vuln_ids`, backfill, drop 4 columns | ✓ VERIFIED | Read in full; matches plan verbatim; applied live (`alembic current` = head) |
| `backend/app/vulnerabilities/correlation_service.py` | `_SOURCE_ORDER`, no `SOURCE_COLUMN_MAP` | ✓ VERIFIED | Read in full; grep-confirmed |
| `backend/tests/test_correlation_service.py` | SC#4 + 9 more tests (10 total) | ✓ VERIFIED | Read in full; **10/10 executed live and passed** |
| `backend/scripts/recorrelate_all_tenants.py` | `_recorrelate_tenant(db, tenant_id)` + `_main()`, tenant-scoped, no `compute_risk_scores` | ✓ VERIFIED | Read in full; `grep -c compute_risk_scores` = 0; `COALESCE(array_length` present; active-tenant loop present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `correlation_service.py::run_correlations` | `vulnerability_correlations.sources`/`source_vuln_ids` | `pg_insert().on_conflict_do_update(constraint='uq_correlation')` | ✓ WIRED | Confirmed in source; live test round-trips through this exact path |
| `router.py::get_vuln_correlation` | `get_correlation_for_vuln` | `{'correlated': True, **corr}` dict-spread | ✓ WIRED | Route unedited (0-line diff); live HTTP test confirms shape flows through |
| `recorrelate_all_tenants.py::_main` | `_recorrelate_tenant(db, tenant_id)` | per-active-tenant loop | ✓ WIRED | Confirmed in source; `_main()` loops `Tenant.is_active` and calls the helper inside try/except-continue |
| test file | `scripts.recorrelate_all_tenants._recorrelate_tenant` | `sys.path` insert + import | ✓ WIRED | Live test import succeeded and executed (`test_recorrelate_tenant_corrects_backfill_bug_signature` passed) |

### Behavioral Spot-Checks (Runtime, not static)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full correlation test suite against live Postgres | `pytest tests/test_correlation_service.py -v` (DATABASE_URL pointed at running `getvul-postgres-1`) | `10 passed, 1 warning in 1.99s` | ✓ PASS |
| Migration state on live DB | `alembic current` | `034_add_correlation_sources (head)` | ✓ PASS |
| Live schema shape | `information_schema.columns` + `pg_indexes` query via asyncpg | Matches expected shape exactly (no legacy columns, GIN index present) | ✓ PASS |
| CI mypy gate, exact command | `mypy app/ \| mypy-baseline filter --allow-unsynced` | `fixed=3/new=3` — pre-existing documented flake, unrelated file | ✓ PASS (no regression) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| CORR-01 | 30-01, 30-02 | Complete source set (all 6 sources), `sources ARRAY(String)`+GIN replacing 4 FK columns | ✓ SATISFIED | Live schema query; SC#4 test; D-09 HTTP-shape test |
| CORR-02 | 30-02 | Existing correlation data migrated with zero loss, tenant-scoped | ✓ SATISFIED | `test_recorrelate_tenant_corrects_backfill_bug_signature` — runtime proof, not static inspection |
| CORR-03 | 30-01, 30-02 | `correlation_service.py` loops full `VulnSource` enum; count/name list structurally cannot disagree | ✓ SATISFIED | `_SOURCE_ORDER` single-source-of-truth; `test_confidence_bands` + `test_single_source_does_not_correlate` across every combination |

No orphaned requirements: REQUIREMENTS.md maps only CORR-01/02/03 to Phase 30, all three declared across the two plans' frontmatter and all three marked `[x] Complete` in REQUIREMENTS.md, consistent with actual code/test evidence (not merely asserted).

### Anti-Patterns Found

None. Scanned all 5 phase-touched files (`models.py`, `correlation_service.py`, `034_add_correlation_sources.py`, `recorrelate_all_tenants.py`, `test_correlation_service.py`) for TODO/FIXME/placeholder/stub markers, empty-return handlers, and hardcoded-empty data flowing to output — zero matches. `get_correlation_for_vuln`'s `corr.sources or []` / `corr.source_vuln_ids or {}` are legitimate null-coalescing on a nullable ARRAY/JSONB column, not stubs (proven populated by the live tests).

### Human Verification Required

None. This phase has no UI/UX surface (pure backend schema + service + script + test), and every must-have was verifiable either through direct code inspection or live execution against the running Postgres instance. No human judgment items apply.

### Gaps Summary

No gaps. All 15 derived must-haves verified — 11 by direct live-runtime execution (pytest against the actual running dev Postgres, plus live schema/index/alembic-head queries), 4 by code inspection (git-diff scoping, grep-absence of legacy artifacts, migration downgrade symmetry). The SUMMARY claims of "10/10 tests passing" and "zero-loss recovery proven at runtime" were independently re-executed here rather than trusted, and matched exactly. Requirements CORR-01/CORR-02/CORR-03 are all satisfied with concrete, re-verified evidence; REQUIREMENTS.md's "Complete" status for all three is accurate.

---

*Verified: 2026-08-05*
*Verifier: Claude (gsd-verifier)*
