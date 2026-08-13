---
phase: 30-correlation-schema-fix
reviewed: 2026-08-05T08:20:18Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - backend/app/vulnerabilities/models.py
  - backend/app/vulnerabilities/correlation_service.py
  - backend/alembic/versions/034_add_correlation_sources.py
  - backend/scripts/recorrelate_all_tenants.py
  - backend/tests/test_correlation_service.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-08-05T08:20:18Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 30 replaces the hardcoded 4-of-6 FK-column correlation shape with a canonical `sources ARRAY(String)` + GIN and a `source_vuln_ids` JSONB linkage map, generalizes `correlation_service.py` over the full `VulnSource` enum, and adds a per-tenant re-correlation recovery script plus a substantial regression suite.

I verified every invariant the task called out and all held:

- **Tenant isolation (T-30-01/02/05):** every read/write in `run_correlations`, `_find_correlated_groups`, `_prune_stale_correlations`, `get_correlation_for_vuln`, and both diagnostic queries in `_recorrelate_tenant` carries `.where(tenant_id == tenant_id)` / `WHERE tenant_id = :tid`; the upsert conflict target `uq_correlation` includes `tenant_id`; the zero-loss check is per-tenant, never a global aggregate. No cross-tenant path found.
- **`sources_count == len(sources)`:** both derive from the single `sources = [s for s in _SOURCE_ORDER if s in source_vulns]` list; structurally cannot disagree for enum-member sources. `_SOURCE_ORDER` is the one canonical list; `SOURCE_COLUMN_MAP` is gone (grep confirms no remaining references in `app/` or `scripts/`).
- **UUID → str for JSONB:** `source_vuln_ids = {s: str(source_vulns[s]) for s in sources}` casts every value; migration backfill uses `jsonb_build_object(...)` which coerces UUID columns to JSON strings — consistent.
- **Migration 034:** revision id is 27 chars (< 32 cap); down_revision `033_add_ai_batch_job` is the prior head and 034 is the only new head (single-head chain confirmed); upgrade/downgrade are schema-symmetric; GIN index is on `sources` only, `source_vuln_ids` has none; the only data loss is the documented one-way FK-column drop.
- **Route auth (T-30-02/07):** `GET /{vuln_id}/correlation` is untouched — still `require_viewer`-gated and derives tenant from `user.tenant_id`; only the returned dict shape changed via the `{**corr}` spread. No frontend consumer of the endpoint exists, so the D-09 shape change breaks nothing downstream.

One robustness defect is worth fixing before this ships as the foundation for Phases 33/35, plus three minor observations.

## Warnings

### WR-01: Source-count divergence can silently reintroduce the CORR-01 drop for any non-enum source

**File:** `backend/app/vulnerabilities/correlation_service.py:41-42` (and `_find_correlated_groups:140-141`)
**Issue:**
The correlation pipeline uses **two independent source-of-truth lists** with no enforced link between them:

1. `_find_correlated_groups` is source-agnostic — it groups by the raw `Vulnerability.source` string and keeps every group with `len(v) >= 2` (line 141).
2. `run_correlations` then re-filters that group through the enum: `sources = [s for s in _SOURCE_ORDER if s in source_vulns]` where `_SOURCE_ORDER = [s.value for s in VulnSource]`.

If any `Vulnerability.source` value that is **not** a `VulnSource` member ever reaches step 2, the group passes the `>= 2` filter but `sources`/`sources_count` collapse below the discovered count. A finding seen by `{QUALYS, <non-enum-source>}` would upsert a correlation row with `sources = ['QUALYS']`, `sources_count = 1`, `confidence = 'LOW'`, and a `source_vuln_ids` map missing the second scanner — silently dropping that linkage. That is precisely the CORR-01 failure class this phase exists to kill, now gated on the *unenforced* invariant `Vulnerability.source ∈ VulnSource`.

`Vulnerability.source` is a bare `String(30)` (models.py:62), not enum-constrained at the DB or ORM layer. Today it is safe only because `CONNECTOR_CLASSES` (sync.py:62-69) keys exactly equal the six `VulnSource` values — but those two lists are decoupled. The product vision (CLAUDE.md: "Tenable, Qualys, Rapid7, **AWS Inspector**") and the plan's own "adding a 7th source" forward-compat goal make a new scanner plausible; a dev who adds a connector class without adding the enum member reintroduces the silent drop, and the `sources_count == len(sources)` COALESCE guard would **not** catch it (both shrink together, so the row looks internally consistent).

This is also why the `confidence = "LOW"` branch (lines 51-52), documented as "structurally near-unreachable", is in fact reachable exactly when this divergence occurs — LOW is the tell of a dropped source.

**Fix:** Derive the group membership from the same canonical set so the two counts cannot diverge — filter unknown sources in `_find_correlated_groups` and count only recognized ones, e.g.:
```python
_VALID_SOURCES = frozenset(s.value for s in VulnSource)
...
for cve_id, asset_id, source, vuln_id in rows:
    if source not in _VALID_SOURCES:
        logger.warning("correlation_unknown_source", source=source, tenant_id=str(tenant_id))
        continue
    key = (cve_id, asset_id)
    groups.setdefault(key, {}).setdefault(source, vuln_id)
```
This makes the `>= 2` group filter and the emitted `sources` list count the same set, so an unrecognized scanner can never quietly shrink a correlation below the threshold that qualified it.

## Info

### IN-01: `created` stat counts updates as new correlations

**File:** `backend/app/vulnerabilities/correlation_service.py:77-82, 95-98`
**Issue:** `on_conflict_do_update` returns `rowcount == 1` for both inserts and updates, so `created` (returned as `"correlated"`) is really "rows upserted", not "rows newly created". The inline comment acknowledges this. Harmless for the phase's invariants, but the stat name overstates new-correlation counts for any operator reading the log/return.
**Fix:** Rename the key to `"upserted"` (or use the `RETURNING (xmax = 0)` insert/update discriminator) so the stat's name matches its meaning.

### IN-02: `blind_spot_rows_recovered` overstates recovery

**File:** `backend/scripts/recorrelate_all_tenants.py:59-64, 91-96`
**Issue:** The counter is the number of `sources = '{}'` rows *before* `run_correlations`, but some of those rows may be **pruned** (deleted) by `_prune_stale_correlations` rather than recovered when their underlying group no longer has 2+ sources. The returned/logged `blind_spot_rows_recovered` therefore counts "empty-array rows seen", not "rows corrected". Only a diagnostic value, but the name implies all were recovered.
**Fix:** Rename to `blind_spot_rows_before` (or additionally compute a true `recovered` delta) to avoid a misleading recovery signal in operator logs.

### IN-03: GIN index built before backfill UPDATE

**File:** `backend/alembic/versions/034_add_correlation_sources.py:36-58`
**Issue:** `create_index(..., postgresql_using="gin")` runs before the `UPDATE ... SET sources = ...` backfill, so the empty GIN index is incrementally maintained during the backfill instead of being built once over the final data. Purely a one-time migration-runtime cost (out of the v1 review scope), noted only for completeness — not a correctness issue. The `vulnerability_correlations` table is documented as small/rebuildable, so impact is negligible.
**Fix (optional):** Create the GIN index after the two backfill `op.execute` UPDATEs.

---

_Reviewed: 2026-08-05T08:20:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
