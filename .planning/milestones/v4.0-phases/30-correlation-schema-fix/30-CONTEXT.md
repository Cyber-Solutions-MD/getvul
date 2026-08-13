# Phase 30: Correlation Schema Fix - Context

**Gathered:** 2026-08-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the hardcoded 4-of-6-source correlation shape on `vulnerability_correlations` with a source-set model that covers all 6 `VulnSource` values (forward-compatible with a 7th), migrate existing data with no loss, and generalize `correlation_service.py` to loop over the full `VulnSource` enum instead of the 4-entry `SOURCE_COLUMN_MAP`.

Requirements CORR-01, CORR-02, CORR-03. Success criteria are locked by ROADMAP.md Phase 30. This discussion clarifies HOW to implement them; it does not add capability. Connector enrichment (ENRICH-*), risk scoring (RISK-*), and source-aware filtering/badges (SRC-*) are later phases and out of scope here.

</domain>

<decisions>
## Implementation Decisions

### Correlation schema shape
- **D-01:** `vulnerability_correlations` gains a `sources ARRAY(String)` column with a GIN index — mirroring the shipped `assets.tags` pattern (see `025_add_asset_tags.py`). This array is the **canonical** source-set: it drives `sources_count` and the resolved source-name list, so the two can never disagree (CORR-03). — **Reversibility:** one-way — new Postgres column + GIN index + the migration that drops the 4 FK columns; undoing needs a reverse migration.
- **D-02:** The array is stored in **canonical form**: deduplicated `VulnSource` `.value` strings, sorted by `VulnSource` enum declaration order (`CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7`). This makes `sources_count`, GIN `@>` containment queries, and the SC#4 regression assertion deterministic and order-independent.
- **D-03:** The 4 hardcoded FK columns (`crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id`) are **dropped**. `SOURCE_COLUMN_MAP` in `correlation_service.py` is removed; the service loops over the full `VulnSource` enum. — **Reversibility:** one-way — column drop + service rewrite; the old per-source-column pattern is exactly what CORR-01/CORR-03 exist to kill.

### Per-source vuln-id linkage
- **D-04:** Preserve the correlation→per-source-finding linkage as a new `source_vuln_ids` **JSONB** map of `{SOURCE: vuln_uuid}` (keyed by the same enum values). The `sources` ARRAY stays the canonical GIN-indexed set + count source; the JSONB map is linkage-only. — **Reversibility:** costly — adding it later would need a re-correlation to backfill.
- **D-05:** Accepted tradeoff: JSONB cannot carry a DB-level FK, so a deleted vulnerability leaves a **stale uuid** in the map. This is acceptable because correlations are fully rebuilt every sync (`run_correlations`), so any stale linkage **self-heals** on the next correlation run. No DB referential integrity on the map is required.

### Migration strategy (existing correlation data)
- **D-06:** Translate **and** re-correlate. Correlations are derived data, fully rebuildable from `vulnerabilities`, and the old FK columns never held Qualys/Rapid7 (those were dropped at correlation-time, not stored-then-lost). The migration path:
  1. Add `sources ARRAY(String)` + GIN index and `source_vuln_ids` JSONB.
  2. Backfill both from the existing 4 FK columns (baseline — no row left empty mid-deploy).
  3. Drop the 4 FK columns.
  4. Re-run `run_correlations` **per tenant** so migrated data reflects the true complete source set, recovering the previously silently-dropped Qualys/Rapid7 records.
  5. Verify **per-tenant** with before/after counts (SC#2 requires zero loss verified per-tenant).
  — **Reversibility:** one-way — schema migration; the re-correlation step itself is idempotent and re-runnable.
- **D-07:** The per-tenant re-correlation (step 4) is a data-recovery step, not a blocking Alembic data migration over a large table (`vulnerability_correlations` is small and rebuildable). It must be idempotent so it can be re-run safely.

### Confidence tiers (recalibrated for 6-source scale)
- **D-08:** Recalibrate the confidence bands from the old `HIGH ≥3 / MEDIUM =2 / LOW else` to **`HIGH ≥4 / MEDIUM 2–3 / LOW 1`**. Since correlations only exist at 2+ sources, LOW (1) is effectively unreachable — that is intentional and acceptable. This is a **stable interim**: Phase 33's risk-exposure model consumes cross-scanner corroboration count and may re-band; this phase does not couple to that.

### API / consumer shape
- **D-09:** `get_correlation_for_vuln` and the `GET /{vuln_id}/correlation` endpoint (`router.py:674`) return the `sources` array + `sources_count` + `confidence` + the `source_vuln_ids` map, replacing the old per-source `*_vuln_id` keys. Frontend has **no consumer** of the old per-source keys (verified: no `crowdstrike_vuln_id`/`get_correlation` usage in `frontend/src`), so this is a low-blast-radius response change.

### Regression coverage
- **D-10:** SC#4 regression test: seed a finding seen only by **Qualys + Rapid7**, run correlation, assert it now correlates (canonical `sources == ['QUALYS','RAPID7']`, `sources_count == 2`, `confidence == 'MEDIUM'`, and `source_vuln_ids` maps both). This case is silently dropped pre-fix.

### Claude's Discretion
- Exact Alembic revision id/down_revision chaining, column nullability defaults, and index naming (follow `ix_assets_tags` / existing migration conventions).
- Whether the per-tenant re-correlation runs inside the migration's data step or as a separate invoked routine — researcher/planner to choose per the idempotency + "not a blocking Alembic data migration over a large table" constraint (D-07).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 30: Correlation Schema Fix" — goal, dependencies, and the 4 locked success criteria.
- `.planning/REQUIREMENTS.md` — CORR-01, CORR-02, CORR-03 (lines 16–18).

### Code under change
- `backend/app/vulnerabilities/correlation_service.py` — `run_correlations`, `_find_correlated_groups`, `_prune_stale_correlations`, `get_correlation_for_vuln`, and the `SOURCE_COLUMN_MAP` to remove.
- `backend/app/vulnerabilities/models.py` §`VulnerabilityCorrelation` (lines 84–108) and §`VulnSource` enum (lines 31–37).
- `backend/app/vulnerabilities/router.py` §`get_vuln_correlation` (lines 674–694) — the API consumer of the response shape.
- `backend/app/vulnerabilities/service.py` — reads `VulnerabilityCorrelation.sources_count` (lines 194, 227, 475); confirm those still hold after the shape change.

### Reference pattern to mirror
- `backend/alembic/versions/025_add_asset_tags.py` — the shipped `ARRAY(String)` + GIN index pattern this phase mirrors (`ix_assets_tags`, `postgresql_using="gin"`).
- `backend/app/assets/models.py:71` — `tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))` declaration to mirror on the correlation model.
- `backend/alembic/versions/001_initial_schema.py:118` — original `vulnerability_correlations` table def (the FK columns being dropped).

### Callers of run_correlations (re-correlation blast radius)
- `backend/app/connectors/sync.py:170` — per-sync correlation run.
- `backend/app/seed.py:241` and `backend/app/dev_routes.py:34` — seed / dev correlation runs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `assets.tags` ARRAY(String) + GIN (`025_add_asset_tags.py`, `assets/models.py:71`): direct template for the `sources` column + index.
- `run_correlations(db, tenant_id)` is already idempotent (upsert on `uq_correlation` + prune stale) — reuse it verbatim for the migration's per-tenant re-correlation step (D-06 step 4).
- `_find_correlated_groups` already returns `{(cve,asset): {source: vuln_id}}` for **all** sources present in `vulnerabilities` (not limited to the 4 FK columns) — the fix is that the write path currently narrows to 4. The read side already sees Qualys/Rapid7.

### Established Patterns
- `VulnSource` enum (6 values) is the single source of truth; the service must iterate it rather than the 4-entry `SOURCE_COLUMN_MAP`.
- Upsert-on-conflict against the `uq_correlation` unique constraint `(tenant_id, cve_id, asset_id)` — the array + JSONB columns join the `set_={...}` clause; the per-source FK entries leave it.
- Multi-tenant: every correlation op is `tenant_id`-scoped; SC#2 verification is per-tenant.

### Integration Points
- Migration (Alembic `backend/alembic/versions/`) adds columns, backfills, drops FK columns, and drives per-tenant re-correlation.
- `GET /{vuln_id}/correlation` response body changes shape (D-09).
- `service.py` correlation-count reads must survive the refactor unchanged.

</code_context>

<specifics>
## Specific Ideas

- Canonical enum order for the `sources` array is literally the `VulnSource` declaration order in `models.py:31-37`.
- SC#4 concrete fixture: a CVE-on-host seen only by Qualys + Rapid7 must correlate with `confidence == 'MEDIUM'` under the recalibrated bands (2 sources → MEDIUM).

</specifics>

<deferred>
## Deferred Ideas

- **Confidence-band re-tuning against corroboration in the scoring model** → Phase 33 (Risk-Exposure Model Definition) explicitly consumes cross-scanner corroboration count; D-08's bands are a stable interim, not the final scoring authority.
- **Source provenance badges / per-entity source filtering** → Phase 35 (Source-Aware Filtering & Provenance Badges). This phase only makes the source set *correct*; surfacing it is later.
- **DB-level referential integrity for the source→vuln_id linkage** → not pursued; JSONB self-heals via re-correlation (D-05). Revisit only if a hard-FK guarantee is ever required.

</deferred>

---

*Phase: 30-correlation-schema-fix*
*Context gathered: 2026-08-04*
