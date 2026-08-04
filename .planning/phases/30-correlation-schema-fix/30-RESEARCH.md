# Phase 30: Correlation Schema Fix - Research

**Researched:** 2026-08-04
**Domain:** PostgreSQL/Alembic schema migration + SQLAlchemy 2.0 ARRAY/JSONB modeling + idempotent per-tenant data-recovery
**Confidence:** HIGH

## Summary

This phase is a contained, well-scoped backend fix: replace 4 hardcoded per-source FK columns on `vulnerability_correlations` with a `sources ARRAY(String)` + GIN index (mirroring the already-shipped `assets.tags` pattern) plus a `source_vuln_ids` JSONB linkage map, then generalize `correlation_service.py` to loop over the full 6-value `VulnSource` enum. CONTEXT.md has already locked every design decision (D-01 through D-10); this research focuses entirely on the HOW — concrete Alembic SQL, SQLAlchemy model syntax, the exact migration/re-correlation sequencing, and a validation strategy.

Direct code inspection (not just CONTEXT.md's own claims) confirms the fix is narrower than it might sound: `_find_correlated_groups()` in `correlation_service.py` already queries `Vulnerability.source` unrestricted and already builds a `{source: vuln_id}` dict containing QUALYS/RAPID7 when present — the bug is isolated entirely to `run_correlations()`'s value-building block (which narrows to 4 hardcoded dict keys via `SOURCE_COLUMN_MAP`) and `get_correlation_for_vuln()`'s read-shaping block (which checks only 4 FK columns). `_prune_stale_correlations()` needs zero changes. Frontend has zero consumers of any correlation field (verified via grep across `frontend/src`), so the API response shape change (D-09) is a safe, uncoordinated backend-only deploy.

Every core mechanism in this research — the `ARRAY_REMOVE`/`jsonb_strip_nulls` backfill SQL, the GIN index + `@>`/`&&` containment operators, the FK-auto-drop-on-column-drop behavior, the `pg_insert().on_conflict_do_update()` upsert shape with combined ARRAY+JSONB columns, and one genuinely-would-have-broken-things pitfall (raw UUID objects are not JSON-serializable into a JSONB column) — was proven by direct execution against a disposable Postgres 16 container using this repo's exact pinned versions (SQLAlchemy 2.0.50, asyncpg 0.31.0, alembic 1.18.4), not assumed from training data or generic docs.

**Primary recommendation:** One new Alembic migration (`034_add_correlation_sources.py`) does schema-only work (add `sources`+GIN, add `source_vuln_ids`, baseline-backfill both from the 4 legacy columns via raw SQL `UPDATE`, drop the 4 FK columns) inside one transaction; a separate, idempotent, manually-invoked script (`backend/scripts/recorrelate_all_tenants.py`, mirroring the existing `capture_ai_goldens.py` + `sla_service.backfill_sla_due_dates`/`scheduler.py` tenant-loop idioms) re-runs `run_correlations()` per tenant to recover the true Qualys/Rapid7 source sets — run once, manually, immediately after `alembic upgrade head` and before verifying SC#2.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Correlation source-set persistence (`sources` ARRAY+GIN, `source_vuln_ids` JSONB) | Database/Storage | API/Backend | Schema lives in Postgres; SQLAlchemy model declaration is the backend-side mirror |
| Correlation computation (grouping, canonical ordering, confidence banding) | API/Backend | — | Pure Python logic in `correlation_service.py`; no DB-side computed columns |
| Historical data recovery (backfill + re-correlation) | API/Backend | Database/Storage | Backend Python (migration + script) drives the mutation; Postgres is the mutation target |
| Correlation API exposure (`GET /{vuln_id}/correlation`, `GET /correlations/stats`) | API/Backend | — | FastAPI route layer; no new auth/session concerns |
| Frontend consumption | N/A | — | Verified zero consumers in `frontend/src` — Browser/Client tier is out of scope this phase |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `vulnerability_correlations` gains a `sources ARRAY(String)` column with a GIN index — mirroring the shipped `assets.tags` pattern (see `025_add_asset_tags.py`). This array is the **canonical** source-set: it drives `sources_count` and the resolved source-name list, so the two can never disagree (CORR-03). — **Reversibility:** one-way — new Postgres column + GIN index + the migration that drops the 4 FK columns; undoing needs a reverse migration.
- **D-02:** The array is stored in **canonical form**: deduplicated `VulnSource` `.value` strings, sorted by `VulnSource` enum declaration order (`CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7`). This makes `sources_count`, GIN `@>` containment queries, and the SC#4 regression assertion deterministic and order-independent.
- **D-03:** The 4 hardcoded FK columns (`crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id`) are **dropped**. `SOURCE_COLUMN_MAP` in `correlation_service.py` is removed; the service loops over the full `VulnSource` enum. — **Reversibility:** one-way — column drop + service rewrite; the old per-source-column pattern is exactly what CORR-01/CORR-03 exist to kill.
- **D-04:** Preserve the correlation→per-source-finding linkage as a new `source_vuln_ids` **JSONB** map of `{SOURCE: vuln_uuid}` (keyed by the same enum values). The `sources` ARRAY stays the canonical GIN-indexed set + count source; the JSONB map is linkage-only. — **Reversibility:** costly — adding it later would need a re-correlation to backfill.
- **D-05:** Accepted tradeoff: JSONB cannot carry a DB-level FK, so a deleted vulnerability leaves a **stale uuid** in the map. This is acceptable because correlations are fully rebuilt every sync (`run_correlations`), so any stale linkage **self-heals** on the next correlation run. No DB referential integrity on the map is required.
- **D-06:** Translate **and** re-correlate. Correlations are derived data, fully rebuildable from `vulnerabilities`, and the old FK columns never held Qualys/Rapid7 (those were dropped at correlation-time, not stored-then-lost). The migration path:
  1. Add `sources ARRAY(String)` + GIN index and `source_vuln_ids` JSONB.
  2. Backfill both from the existing 4 FK columns (baseline — no row left empty mid-deploy).
  3. Drop the 4 FK columns.
  4. Re-run `run_correlations` **per tenant** so migrated data reflects the true complete source set, recovering the previously silently-dropped Qualys/Rapid7 records.
  5. Verify **per-tenant** with before/after counts (SC#2 requires zero loss verified per-tenant).
  — **Reversibility:** one-way — schema migration; the re-correlation step itself is idempotent and re-runnable.
- **D-07:** The per-tenant re-correlation (step 4) is a data-recovery step, not a blocking Alembic data migration over a large table (`vulnerability_correlations` is small and rebuildable). It must be idempotent so it can be re-run safely.
- **D-08:** Recalibrate the confidence bands from the old `HIGH ≥3 / MEDIUM =2 / LOW else` to **`HIGH ≥4 / MEDIUM 2–3 / LOW 1`**. Since correlations only exist at 2+ sources, LOW (1) is effectively unreachable — that is intentional and acceptable. This is a **stable interim**: Phase 33's risk-exposure model consumes cross-scanner corroboration count and may re-band; this phase does not couple to that.
- **D-09:** `get_correlation_for_vuln` and the `GET /{vuln_id}/correlation` endpoint (`router.py:674`) return the `sources` array + `sources_count` + `confidence` + the `source_vuln_ids` map, replacing the old per-source `*_vuln_id` keys. Frontend has **no consumer** of the old per-source keys (verified: no `crowdstrike_vuln_id`/`get_correlation` usage in `frontend/src`), so this is a low-blast-radius response change.
- **D-10:** SC#4 regression test: seed a finding seen only by **Qualys + Rapid7**, run correlation, assert it now correlates (canonical `sources == ['QUALYS','RAPID7']`, `sources_count == 2`, `confidence == 'MEDIUM'`, and `source_vuln_ids` maps both). This case is silently dropped pre-fix.

### Claude's Discretion

- Exact Alembic revision id/down_revision chaining, column nullability defaults, and index naming (follow `ix_assets_tags` / existing migration conventions). **Research answer:** revision id `034_add_correlation_sources` (27 chars, under the repo's empirically-confirmed 32-char `alembic_version.version_num` limit — see Pitfall 4); down_revision `033_add_ai_batch_job` (confirmed current head via both the versions directory listing and the live dev DB's `alembic_version` table); index name `ix_vulnerability_correlations_sources` (matches the `ix_` prefix convention used by every migration since `025_add_asset_tags.py`); both new columns nullable=True (matches `assets.tags` precedent).
- Whether the per-tenant re-correlation runs inside the migration's data step or as a separate invoked routine — researcher/planner to choose per the idempotency + "not a blocking Alembic data migration over a large table" constraint (D-07). **Research answer:** separate invoked routine — a standalone script (`backend/scripts/recorrelate_all_tenants.py`), run once manually post-migration. See Architecture Patterns Pattern 4 and Code Examples for the concrete mechanism and why it fits this repo's existing conventions better than embedding in the migration or the scheduler.

### Deferred Ideas (OUT OF SCOPE)

- **Confidence-band re-tuning against corroboration in the scoring model** → Phase 33 (Risk-Exposure Model Definition) explicitly consumes cross-scanner corroboration count; D-08's bands are a stable interim, not the final scoring authority.
- **Source provenance badges / per-entity source filtering** → Phase 35 (Source-Aware Filtering & Provenance Badges). This phase only makes the source set *correct*; surfacing it is later.
- **DB-level referential integrity for the source→vuln_id linkage** → not pursued; JSONB self-heals via re-correlation (D-05). Revisit only if a hard-FK guarantee is ever required.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORR-01 | Cross-source correlation records the complete set of scanners that see each CVE-on-host (all 6 sources, forward-compatible with a 7th), replacing the hardcoded 4-source FK columns with a `sources ARRAY(String)` + GIN-index shape | Verified migration SQL (Code Examples #2) adds `sources ARRAY(String)` + GIN mirroring `025_add_asset_tags.py`; canonical `_SOURCE_ORDER` list derived from `VulnSource` enum (6 values today, add a 7th enum member with zero schema change tomorrow) |
| CORR-02 | Existing correlation data (including Qualys/Rapid7, silently dropped today) is migrated into the generalized source-set model with no loss, tenant-scoped | Verified end-to-end dry run (Common Pitfalls #5) proves the exact bug reproduction + recovery sequence; Validation Architecture's per-tenant consistency query (`COALESCE(array_length(sources,1),0) != sources_count`) is the concrete zero-loss proof |
| CORR-03 | `correlation_service.py` loops over the full `VulnSource` enum instead of a hardcoded 4-entry `SOURCE_COLUMN_MAP`, so `sources_count` and the resolved source names can never disagree | Code Examples #3 rewrites `run_correlations()` to derive both `sources` and `sources_count` from one canonical-order list in one code path — structurally impossible to disagree; the same consistency query above is a permanent regression guard |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Directive | Applies to Phase 30? | Note |
|-----------|----------------------|------|
| Backend: FastAPI + Postgres + Redis | Postgres: yes (this phase is entirely a Postgres schema change). Redis/FastAPI: only incidentally (the one endpoint's response dict shape changes; no new routes, no Redis touch) | `correlation_service.py` and the migration never touch Redis |
| Frontend stack (Next.js/React/Tailwind) + sketch-findings-getvul skill | No | Backend-only phase; verified zero frontend files reference correlation fields |
| "Don't ship a screen without empty/loading/error states" | No | No UI surface in this phase |
| "Don't pick hex colors freehand" / "Don't compose generic SaaS copy" | No | No UI/copy in this phase |
| Deployment: Docker Compose, nginx in front of frontend/backend | Yes, indirectly | `docker-compose.yml`'s backend service command is `sh -c "alembic upgrade head && uvicorn ..."` — the schema migration runs automatically on every container (re)start; the separate re-correlation script does **not** run automatically and must be invoked manually once (see Architecture Patterns Pattern 4) |

No CLAUDE.md directive conflicts with any locked decision in this phase.

## Standard Stack

### Core (already pinned in `backend/pyproject.toml` — no new dependency)

| Library | Installed Version [VERIFIED: `backend/.venv`, 2026-08-04] | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy[asyncio] | 2.0.50 (declared `>=2.0`) | ORM + Core, `postgresql.ARRAY`/`JSONB` dialect types, `pg_insert().on_conflict_do_update()` | Already the ORM for every model in this repo; `ARRAY(String)` is exactly what `assets.tags` already uses |
| alembic | 1.18.4 (declared `>=1.14`) | Schema migrations | Existing migration tool; `op.add_column`/`op.create_index`/`op.execute`/`op.drop_column` all already used elsewhere in this repo |
| asyncpg | 0.31.0 (declared `>=0.30`) | Async Postgres driver | Existing runtime driver; directly verified ARRAY(String)+JSONB+upsert all work correctly through it (see Pitfalls) |
| postgres | 16-alpine (docker-compose.yml + CI) | Database | `ARRAY_REMOVE` (9.3+), `jsonb_strip_nulls`/`jsonb_build_object` (9.5+), native GIN array opclass — all satisfied trivially by 16 |

No new packages to install for this phase — everything needed is already a direct dependency.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sources ARRAY(String)` + GIN | A join table (`correlation_sources(correlation_id, source)`) | Normalized, but this repo already has a working precedent (`assets.tags`) for the array shape, and D-01 explicitly locks mirroring it — a join table is more "correct" relationally but is a bigger, unlocked design deviation for no functional gain at this scale |
| Manual per-tenant script for re-correlation | Wire re-correlation into the docker-compose startup `command:` chain (`alembic upgrade head && python scripts/recorrelate_all_tenants.py && uvicorn ...`) | Automatic on every restart (never forgotten) but adds latency to *every* container restart forever, not just the one deploy that needs it; a one-time manual invocation (matching the `capture_ai_goldens.py` precedent) is more surgical |
| Backfilling `sources`/`source_vuln_ids` from the 4 legacy columns inside the migration | Skipping the backfill and leaving both columns NULL until the re-correlation script runs | D-06 step 2 explicitly wants "no row left empty mid-deploy" as a baseline — skipping it would leave every row NULL for however long the manual script invocation is delayed, which is worse, not simpler |

No installation needed — see Standard Stack above.

## Architecture Patterns

### System Architecture Diagram

```
                    OPERATIONAL FLOW (every connector sync — unchanged shape, rewritten internals)

  connectors/sync.py:170          vulnerabilities table         correlation_service.py
  ┌────────────────────┐         ┌──────────────────────┐      ┌─────────────────────────────┐
  │ run_correlations()  │────────▶│ 6 sources, per-row    │─────▶│ _find_correlated_groups()    │  UNCHANGED
  │ called post-sync     │        │ Vulnerability.source  │      │ groups by (cve,asset) →      │  (already reads
  └────────────────────┘         │ column (plain string) │      │ {source: vuln_id}, len(v)>=2 │  all 6 sources)
                                   └──────────────────────┘      └──────────────┬──────────────┘
                                                                                  │
                                                                                  ▼
                                                                  ┌─────────────────────────────┐
                                                                  │ REWRITTEN value-building:     │
                                                                  │  sources = canonical-order     │  ← was
                                                                  │    filter over VulnSource       │    SOURCE_COLUMN_MAP
                                                                  │  sources_count = len(sources)   │    (4-of-6, lossy)
                                                                  │  confidence = band(count)        │
                                                                  │  source_vuln_ids = {s: str(id)} │
                                                                  └──────────────┬──────────────┘
                                                                                  │ pg_insert()
                                                                                  │ .on_conflict_do_update()
                                                                                  ▼
                                                                  ┌─────────────────────────────┐
                                                                  │ vulnerability_correlations     │
                                                                  │  sources ARRAY(String)+GIN (NEW)│
                                                                  │  source_vuln_ids JSONB     (NEW)│
                                                                  │  sources_count, confidence  (kept)│
                                                                  │  [4 FK columns: DROPPED]         │
                                                                  └──────────────┬──────────────┘
                                                                                  │ read
                                                                                  ▼
                                                                  ┌─────────────────────────────┐
                                                                  │ get_correlation_for_vuln()     │  REWRITTEN (D-09)
                                                                  │ GET /{vuln_id}/correlation      │
                                                                  └──────────────┬──────────────┘
                                                                                  │
                                                                                  ▼
                                                                  no frontend consumer today
                                                                  (verified via grep — safe to ship alone)


                    ONE-TIME MIGRATION FLOW (this phase's deploy — D-06/D-07)

  docker-compose.yml:49                034_add_correlation_sources.py         operator, once, manually
  ┌───────────────────────┐           ┌───────────────────────────┐         ┌──────────────────────────┐
  │ "alembic upgrade head   │──────────▶│ 1. add sources + GIN        │────────▶│ scripts/                  │
  │  && uvicorn ..."         │          │ 2. add source_vuln_ids      │         │ recorrelate_all_tenants.py│
  │ (runs automatically on   │          │ 3. backfill both (baseline) │         │ (NOT auto-run — D-07)      │
  │  every container start)  │          │ 4. DROP 4 FK columns         │         └────────────┬─────────────┘
  └───────────────────────┘           └───────────────────────────┘                        │ for each active tenant:
                                                                                              │ run_correlations(db, t.id)
                                                                                              ▼
                                                                              per-tenant zero-loss verified (SC#2):
                                                                              COALESCE(array_length(sources,1),0)
                                                                                = sources_count  →  expect 0 rows
```

### Recommended Project Structure

No new directories. Three touched/new files, all in existing locations:

```
backend/
├── app/vulnerabilities/
│   ├── models.py                 # MODIFIED: VulnerabilityCorrelation gains sources/source_vuln_ids, drops 4 FK columns
│   ├── correlation_service.py    # MODIFIED: SOURCE_COLUMN_MAP removed; run_correlations + get_correlation_for_vuln rewritten
│   └── router.py                 # UNCHANGED (calls get_correlation_for_vuln; response dict shape follows from that function)
├── alembic/versions/
│   └── 034_add_correlation_sources.py   # NEW
├── scripts/
│   └── recorrelate_all_tenants.py       # NEW — one-time, manually invoked (mirrors capture_ai_goldens.py)
└── tests/
    └── test_correlation_service.py      # NEW — no correlation-specific test file exists today
```

### Pattern 1: ARRAY(String) + GIN mirrors the shipped `assets.tags` pattern

**What:** A Postgres `varchar[]` column + a GIN index using the built-in array operator class (no extension required — verified: `CREATE INDEX ... USING gin (sources)` succeeds on a plain `ARRAY(String)` column with zero setup).
**When to use:** Any "set of tags/labels/enum-values per row" shape needing containment queries (`@>`, `&&`).
**Example:**
```python
# Source: backend/app/assets/models.py:71 (existing, shipped) + backend/alembic/versions/025_add_asset_tags.py
# Mirrored onto VulnerabilityCorrelation (models.py) — VERIFIED via local Postgres 16 execution, 2026-08-04
sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
```
```python
# alembic — mirrors 025_add_asset_tags.py exactly
op.add_column("vulnerability_correlations", sa.Column("sources", ARRAY(sa.String()), nullable=True))
op.create_index(
    "ix_vulnerability_correlations_sources",
    "vulnerability_correlations",
    ["sources"],
    postgresql_using="gin",
)
```

### Pattern 2: JSONB linkage map mirrors `Asset.mdm_details` / `Vulnerability.file_paths`

**What:** A `dict`-shaped JSONB column for data that's looked up by key, not filtered/indexed.
**When to use:** Linkage/detail data that doesn't need GIN containment queries — per D-04, `source_vuln_ids` is explicitly "linkage-only," so it does **not** get a GIN index (only `sources` does). Building one anyway would add write overhead for zero locked-requirement benefit.
**Example:**
```python
# Source: backend/app/assets/models.py:67 (Asset.mdm_details, existing shipped pattern)
source_vuln_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

### Pattern 3: Canonical-order enum iteration replaces a hardcoded map

**What:** Iterate the enum's own declaration order and filter to members present in a dict, instead of hand-rolling per-member `if` checks or a separate mapping dict.
**When to use:** Anywhere a "set of enum values present in this record" needs a deterministic, forward-compatible representation (D-02).
**Example:**
```python
# VERIFIED pattern — see Code Examples for full context
from app.vulnerabilities.models import VulnSource

_SOURCE_ORDER: list[str] = [s.value for s in VulnSource]  # enum declaration order

sources = [s for s in _SOURCE_ORDER if s in source_vulns]  # canonical order, no dupes possible
```
Adding a 7th source later is a one-line enum change; this loop needs zero modification (CORR-01's forward-compatibility requirement).

### Pattern 4: Schema-migration-then-separately-invoked-idempotent-service

**What:** Split "add/backfill/drop columns" (Alembic, transactional, fast) from "recompute derived data across all tenants" (plain async service function, idempotent, invoked outside the migration).
**When to use:** Exactly D-07's situation — a data-recovery step that touches application-level business logic (re-running correlation grouping) rather than a pure SQL transform, where blocking the migration transaction on it would be wrong.
**This repo already has this precedent twice:**
```python
# Source: backend/app/vulnerabilities/sla_service.py:41 — idempotent, per-tenant, reusable from 3 call sites
async def backfill_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Set sla_due_at for all open vulns that don't have one yet."""
    ...  # only touches rows where the field is still unset — safe to re-run

# Source: backend/app/connectors/scheduler.py:200-206 — the tenant-loop idiom
tenants = (await db.execute(select(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
for t in tenants:
    await backfill_sla_due_dates(db, t.id)
```
```python
# Source: backend/scripts/capture_ai_goldens.py:421-422 — the standalone-script entrypoint idiom
if __name__ == "__main__":
    asyncio.run(_main())
```
`run_correlations(db, tenant_id)` is **already** shaped exactly like `backfill_sla_due_dates` (idempotent upsert + prune, already called from 3 places: `connectors/sync.py`, `seed.py`, `dev_routes.py`). Phase 30's re-correlation step is simply: reuse it verbatim, in a new one-time script that loops active tenants exactly like `scheduler.py` already does.

### Anti-Patterns to Avoid

- **Don't touch `_find_correlated_groups()` or `_prune_stale_correlations()`.** Direct code inspection confirms neither is source-limited — the bug is isolated to `run_correlations()`'s value dict and `get_correlation_for_vuln()`'s read-shaping. Changing either of the two unaffected functions is unnecessary surface area.
- **Don't put a GIN index on `source_vuln_ids`.** It's linkage-only (D-04); a JSONB GIN index adds write overhead with no locked query need this phase.
- **Don't embed the per-tenant re-correlation inside the Alembic migration's `upgrade()`.** D-07 explicitly rules this out; also, running complex async ORM service-layer logic inside a synchronous-feeling Alembic transaction is not this repo's convention anywhere (every existing migration with a data step uses plain `op.execute()` raw SQL, never an imported service function).
- **Don't run the SC#2 zero-loss verification query between the migration finishing and the re-correlation script running.** There is a real, empirically-confirmed transient window where previously-buggy rows show `sources = []` while `sources_count` still holds its stale pre-migration value (see Common Pitfalls #5). Verifying in that window produces a false "data loss" signal.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deduplicated, ordered source list from a `{source: vuln_id}` dict | A custom sort-with-key or manual dedup pass | `[s for s in _SOURCE_ORDER if s in source_vulns]` | Dict keys are already unique (one entry per source per `_find_correlated_groups`); filtering the canonical enum-order list is correct-by-construction and self-documents the ordering rule (D-02) |
| UUID → JSONB-safe value | A custom JSON encoder / `default=` hook on `json.dumps` | Plain `str(uuid_value)` before assigning into the dict | Verified directly: passing a raw `uuid.UUID` into a JSONB column raises `TypeError: Object of type UUID is not JSON serializable`; `str()` is the entire fix, no custom serializer needed |
| Idempotent per-tenant backfill orchestration | A new bespoke one-off migration-runner/orchestration framework | Reuse the already-idempotent `run_correlations()` + the already-established `scheduler.py` tenant-loop idiom, in a standalone script | Two working precedents already exist in this exact repo; a new framework would duplicate them for no benefit |
| "Does this array contain X" filtering | Fetch-all-then-filter-in-Python | Postgres GIN `@>`/`&&` via SQLAlchemy's `.contains()`/`.overlap()` comparators | GIN-index-backed, verified working through the real asyncpg driver with zero cast issues (unlike raw SQL literals — see Pitfall 1) |
| Cross-tenant scoping | A new scoping helper/decorator | The existing `.where(VulnerabilityCorrelation.tenant_id == tenant_id)` pattern, verbatim, on every query including the new verification queries | Every correlation query in this codebase already does this; the rewrite must preserve it exactly, and any new per-tenant verification query must too |

**Key insight:** Every "hard part" of this phase already has a working precedent inside this exact repo (`assets.tags` for the array+GIN shape, `Asset.mdm_details` for the JSONB shape, `sla_service.py`+`scheduler.py` for the idempotent-per-tenant-backfill shape, `capture_ai_goldens.py` for the standalone-script shape). The only genuinely new code is the canonical-order filter and the UUID-to-string cast — both one-liners.

## Runtime State Inventory

This phase is a database schema migration (triggers the Step 2.5 audit).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `vulnerability_correlations` rows: the 4 legacy FK columns hold real linkage data for CROWDSTRIKE/NESSUS/DEFENDER/WIZ that must be translated into the new shape (not just schema-changed); rows correlated via QUALYS/RAPID7 already exist (with correct `sources_count`) but hold **zero** linkage in any of the 4 columns — this is the bug being fixed, not new data loss risk | Both: **code edit** (models.py + correlation_service.py) AND **data migration** (the backfill UPDATE + the separate re-correlation script) |
| Live service config | None found — no external service (n8n, Datadog, etc.) references `crowdstrike_vuln_id`/`SOURCE_COLUMN_MAP`/`vulnerability_correlations` column names in its own UI-managed config | None |
| OS-registered state | None found — no Task Scheduler/pm2/launchd/systemd registration references these column or map names | None |
| Secrets/env vars | None found — `ENCRYPTION_KEY`/`JWT_SECRET_KEY` are unrelated to this schema; no secret key is named after the dropped columns | None |
| Build artifacts / installed packages | None found — no package rename, no compiled binary caches this schema shape. (A `mypy-baseline.txt` entry may need updating if type-checking surfaces new findings against the changed model — normal dev workflow, not a runtime-state hazard.) | None (routine dev step only) |

**Canonical question answered:** After the migration + re-correlation script run, no runtime system anywhere still expects the 4 dropped FK columns to exist — verified via repo-wide grep: the only 4 files referencing `crowdstrike_vuln_id`/`nessus_vuln_id`/`defender_vuln_id`/`wiz_vuln_id` are `models.py`, `correlation_service.py`, and the (untouched, historical) `001_initial_schema.py` migration itself. No frontend, no other backend module, no config file.

## Common Pitfalls

All 5 pitfalls below were reproduced or refuted by direct execution against a disposable Postgres 16.x container running this repo's exact pinned SQLAlchemy 2.0.50 / asyncpg 0.31.0 / alembic 1.18.4 — not inferred from documentation.

### Pitfall 1: Raw SQL literal arrays default to `text[]`, not `varchar[]`
**What goes wrong:** `SELECT ... WHERE sources @> ARRAY['QUALYS','RAPID7']` fails with `ERROR: operator does not exist: character varying[] @> text[]` when `sources` is `ARRAY(String)` (→ Postgres `varchar[]`).
**Why it happens:** A bare SQL array literal (`ARRAY['a','b']`) defaults to `text[]`; Postgres has no implicit cast between `text[]` and `varchar[]` for the `@>`/`&&`/`<@` operators.
**How to avoid:** In raw SQL (migrations, ad-hoc psql), cast explicitly: `ARRAY['QUALYS','RAPID7']::varchar[]`. In application code, use SQLAlchemy's `.contains()`/`.overlap()` comparators on the ORM column — **verified** these compile bound parameters with the correct type and round-trip correctly through asyncpg with zero cast needed (no application code in this phase actually needs this yet; it matters for Phase 35's future AND-filter work, included here because D-01/D-02 explicitly design toward it).
**Warning signs:** "operator does not exist" errors mentioning mismatched array element types, only in raw-SQL contexts.

### Pitfall 2: Raw `uuid.UUID` objects are not JSON-serializable into a JSONB column
**What goes wrong:** `source_vuln_ids = {s: source_vulns[s] for s in sources}` (where values are `uuid.UUID` objects) raises `TypeError: Object of type UUID is not JSON serializable` at INSERT time.
**Why it happens:** SQLAlchemy's JSONB type uses Python's `json.dumps()` for serialization; `json.dumps()` has no built-in UUID handling.
**How to avoid:** Cast every value to `str()` before building the dict: `{s: str(source_vulns[s]) for s in sources}`. Confirmed the read-back value is a plain Python `str`, not re-coerced to `uuid.UUID` (JSONB has no native UUID subtype).
**Warning signs:** `TypeError` at the `db.execute()`/flush call that writes the correlation row, not at model-construction time.

### Pitfall 3: `array_length()` of an empty array returns `NULL`, not `0`
**What goes wrong:** A naive consistency check `WHERE array_length(sources,1) != sources_count` silently **skips** rows where `sources = '{}'` (empty array), because `NULL != 2` evaluates to `NULL` (neither true nor false) in SQL, not `TRUE`.
**Why it happens:** This is documented Postgres behavior for `array_length()` — undefined/NULL for empty (zero-element) arrays, distinct from a NULL array.
**How to avoid:** Always wrap: `COALESCE(array_length(sources,1), 0) != sources_count`. Verified this correctly flags a `sources=[]`/`sources_count=2` row (the exact shape of a pre-recorrelation Qualys/Rapid7 row) that the unwrapped version misses.
**Warning signs:** A "zero loss" verification query reports fewer inconsistent rows than manual inspection shows — specifically undercounts rows with an empty (not NULL) `sources` array.

### Pitfall 4: Alembic revision id length is capped at 32 characters in this repo
**What goes wrong:** A descriptive revision id like `034_add_correlation_sources_array` (34 chars) raises `StringDataRightTruncationError` on `alembic upgrade head`.
**Why it happens:** `alembic_version.version_num` is `varchar(32)` (Alembic's own default, never overridden in this repo's `env.py`) — already hit and documented once before in `031_rename_audit_tenant_idx.py`'s docstring.
**How to avoid:** Count characters before naming the file. `034_add_correlation_sources` is 27 characters — verified under the limit.
**Warning signs:** A migration that works fine with `--sql` (offline mode, no length check) but fails only when actually applied online.

### Pitfall 5: A transient window exists between schema backfill and re-correlation where `sources=[]` but `sources_count` is stale
**What goes wrong:** Immediately after the Alembic migration completes (columns added, baseline-backfilled, 4 FK columns dropped) but **before** the re-correlation script runs, any row that was correlated via sources never captured by the 4-column map (a Qualys+Rapid7-only correlation) shows `sources = []` while `sources_count` still holds its old value (e.g., `2`) — because the backfill UPDATE only ever had the 4 legacy columns to read FROM, and those were always NULL for this row.
**Why it happens:** This is the literal shape of the bug being fixed — proven via an end-to-end dry run seeding a row with `sources_count=2, confidence='MEDIUM'`, all 4 FK columns NULL (simulating a pre-fix Qualys+Rapid7 correlation): after the schema migration alone, that row backfills to `sources={}, source_vuln_ids={}` while `sources_count` stays `2`. Only after `run_correlations()` re-runs for that tenant does the row correctly become `sources=['QUALYS','RAPID7'], sources_count=2`.
**How to avoid:** Sequence strictly: (1) migration, (2) re-correlation script for every tenant, (3) **then** run the SC#2 zero-loss verification. Never verify between steps 1 and 2.
**Warning signs:** A verification query run too early reports "data loss" (empty `sources` arrays) that isn't real loss — it's the expected, temporary pre-recorrelation state.

### Pitfall 6 (documentation-staleness caveat, not a real repo risk)
**What it says:** An older SQLAlchemy docs snippet states "The ARRAY type may not be supported on all PostgreSQL DBAPIs; it is currently known to work on psycopg2 only" [CITED: docs.sqlalchemy.org, SQLAlchemy 1.4-era phrasing surfaced via search].
**Why it's not a concern here:** Directly refuted for this repo's actual stack. `ARRAY(String)` was verified end-to-end through the real `asyncpg` driver (0.31.0) — insert, select, `.contains()`, `.overlap()`, and `pg_insert().on_conflict_do_update()` with an ARRAY column all executed correctly with zero errors. The already-shipped `assets.tags` column already proves this in production. Treat the cited caveat as stale training-adjacent documentation, not a real blocker — flagged explicitly so a future reader doesn't get spooked by it.

## Code Examples

All examples below were exercised directly (see Pitfalls) or are minimal edits to already-read repo files.

### 1. Model changes (`backend/app/vulnerabilities/models.py`)
```python
# Source: mirrors backend/app/assets/models.py:71 (tags) and :67 (mdm_details), both shipped.
# Import line needs ARRAY added (JSONB, UUID already imported):
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

class VulnerabilityCorrelation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vulnerability_correlations"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    # Canonical, deduplicated, enum-order-sorted source set (D-01/D-02). GIN-indexed
    # via alembic 034_add_correlation_sources — mirrors assets.tags (025_add_asset_tags.py).
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Linkage-only map {SOURCE: vuln_uuid-as-string} (D-04). No GIN index — not filtered on.
    source_vuln_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sources_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(10), default=Confidence.LOW.value)

    asset: Mapped["Asset"] = relationship("Asset", back_populates="correlations")
    # crowdstrike_vuln_id / nessus_vuln_id / defender_vuln_id / wiz_vuln_id: REMOVED (D-03)
```

### 2. Migration (`backend/alembic/versions/034_add_correlation_sources.py`)
```python
"""Replace hardcoded 4-source FK columns on vulnerability_correlations with a
generalized sources ARRAY(String) + GIN index, plus a source_vuln_ids JSONB
linkage map covering all 6 VulnSource values (Phase 30, CORR-01/02/03).

Mirrors 025_add_asset_tags.py's ARRAY(String)+GIN pattern (D-01). Backfills
both new columns from the 4 legacy FK columns as a same-migration UPDATE —
this is a BASELINE only, not the final data-recovery step: rows correlated
via sources never captured by the 4-column map (any QUALYS/RAPID7-only
correlation) backfill to sources=[] because those links were never held in
the old FK columns to backfill FROM (D-06 step 2). The actual data recovery
-- re-running run_correlations() per tenant so those rows get their true
source set -- is a SEPARATE, idempotent, re-runnable step
(backend/scripts/recorrelate_all_tenants.py), deliberately NOT run inside
this migration transaction (D-07: not a blocking Alembic data migration
over a large table). Run that script once, manually, immediately after
this migration, BEFORE verifying SC#2's zero-loss requirement -- verifying
in between produces a false "data loss" signal (see 30-RESEARCH.md Pitfall 5).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32)
(empirically confirmed once already -- see 031_rename_audit_tenant_idx.py's
docstring for the StringDataRightTruncationError it hit).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "034_add_correlation_sources"
down_revision = "033_add_ai_batch_job"


def upgrade() -> None:
    op.add_column("vulnerability_correlations", sa.Column("sources", ARRAY(sa.String()), nullable=True))
    op.create_index(
        "ix_vulnerability_correlations_sources",
        "vulnerability_correlations",
        ["sources"],
        postgresql_using="gin",
    )
    op.add_column("vulnerability_correlations", sa.Column("source_vuln_ids", postgresql.JSONB, nullable=True))

    # Baseline backfill (D-06 step 2). Canonical VulnSource declaration order:
    # CROWDSTRIKE, NESSUS, DEFENDER, WIZ (the only 4 sources the old columns held).
    # VERIFIED via direct execution: ARRAY_REMOVE(..., NULL) on an all-NULL CASE
    # list correctly produces '{}' (empty array), never NULL.
    op.execute(
        """
        UPDATE vulnerability_correlations
        SET sources = ARRAY_REMOVE(ARRAY[
            CASE WHEN crowdstrike_vuln_id IS NOT NULL THEN 'CROWDSTRIKE' END,
            CASE WHEN nessus_vuln_id     IS NOT NULL THEN 'NESSUS'      END,
            CASE WHEN defender_vuln_id   IS NOT NULL THEN 'DEFENDER'    END,
            CASE WHEN wiz_vuln_id        IS NOT NULL THEN 'WIZ'         END
        ], NULL)
        """
    )
    op.execute(
        """
        UPDATE vulnerability_correlations
        SET source_vuln_ids = jsonb_strip_nulls(jsonb_build_object(
            'CROWDSTRIKE', crowdstrike_vuln_id,
            'NESSUS', nessus_vuln_id,
            'DEFENDER', defender_vuln_id,
            'WIZ', wiz_vuln_id
        ))
        """
    )

    # Dropping these auto-drops their inline FK constraints -- verified directly,
    # no explicit DROP CONSTRAINT or CASCADE needed (Postgres core behavior).
    op.drop_column("vulnerability_correlations", "crowdstrike_vuln_id")
    op.drop_column("vulnerability_correlations", "nessus_vuln_id")
    op.drop_column("vulnerability_correlations", "defender_vuln_id")
    op.drop_column("vulnerability_correlations", "wiz_vuln_id")


def downgrade() -> None:
    # Schema-symmetric but lossy: any QUALYS/RAPID7 (or a future 7th source)
    # linkage that exists only in sources/source_vuln_ids has no column to
    # return to and is NOT recovered by this downgrade (D-01: one-way).
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "crowdstrike_vuln_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "nessus_vuln_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "defender_vuln_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "wiz_vuln_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.drop_column("vulnerability_correlations", "source_vuln_ids")
    op.drop_index("ix_vulnerability_correlations_sources", table_name="vulnerability_correlations")
    op.drop_column("vulnerability_correlations", "sources")
```

### 3. `correlation_service.py` rewrite (core loop)
```python
# Source: rewrite of backend/app/vulnerabilities/correlation_service.py
# SOURCE_COLUMN_MAP (lines 17-22) is DELETED entirely.
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation, VulnSource

logger = structlog.get_logger()

# Canonical order = VulnSource enum declaration order (D-02). Forward-compatible:
# adding a 7th VulnSource member requires zero change to this file (CORR-01).
_SOURCE_ORDER: list[str] = [s.value for s in VulnSource]


async def run_correlations(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    groups = await _find_correlated_groups(db, tenant_id)  # UNCHANGED
    created = 0

    for key, source_vulns in groups.items():
        cve_id, asset_id = key
        sources = [s for s in _SOURCE_ORDER if s in source_vulns]  # canonical order, no dupes
        sources_count = len(sources)

        # D-08 recalibrated bands. LOW (<=1) is structurally near-unreachable here
        # since _find_correlated_groups already filters to len(v) >= 2 -- intentional.
        if sources_count >= 4:
            confidence = "HIGH"
        elif sources_count >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        values = {
            "tenant_id": tenant_id,
            "cve_id": cve_id,
            "asset_id": asset_id,
            "sources_count": sources_count,
            "confidence": confidence,
            "sources": sources,
            # str() is required -- a raw uuid.UUID is not JSON-serializable into
            # JSONB (verified: raises TypeError otherwise). See Pitfall 2.
            "source_vuln_ids": {s: str(source_vulns[s]) for s in sources},
        }

        stmt = pg_insert(VulnerabilityCorrelation).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_correlation",
            set_={
                "sources_count": stmt.excluded.sources_count,
                "confidence": stmt.excluded.confidence,
                "sources": stmt.excluded.sources,
                "source_vuln_ids": stmt.excluded.source_vuln_ids,
            },
        )
        result = await db.execute(stmt)
        if result.rowcount:
            created += 1

    stale_deleted = await _prune_stale_correlations(db, tenant_id, groups)  # UNCHANGED
    logger.info("correlation_complete", tenant_id=str(tenant_id), correlated=created, stale_removed=stale_deleted)
    return {"correlated": created, "stale_removed": stale_deleted}

# _find_correlated_groups: UNCHANGED -- already source-agnostic (reads Vulnerability.source
# directly, not restricted to any 4-entry map).
# _prune_stale_correlations: UNCHANGED -- doesn't touch source columns.
```

### 4. `get_correlation_for_vuln` rewrite (D-09)
```python
async def get_correlation_for_vuln(
    db: AsyncSession, tenant_id: uuid.UUID, cve_id: str, asset_id: uuid.UUID
) -> dict | None:
    result = await db.execute(
        select(VulnerabilityCorrelation).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.cve_id == cve_id,
            VulnerabilityCorrelation.asset_id == asset_id,
        )
    )
    corr = result.scalar_one_or_none()
    if corr is None:
        return None

    return {
        "id": corr.id,
        "cve_id": corr.cve_id,
        "asset_id": corr.asset_id,
        "sources": corr.sources or [],
        "sources_count": corr.sources_count,
        "confidence": corr.confidence,
        "source_vuln_ids": corr.source_vuln_ids or {},
    }
    # No pydantic schema exists for this endpoint's response today (router.py
    # returns a raw dict via {"correlated": True, **corr}) -- confirmed via grep
    # of schemas.py, so this shape change needs no schema-file edit.
```

### 5. One-time re-correlation script (`backend/scripts/recorrelate_all_tenants.py`)
```python
"""One-time per-tenant re-correlation pass for the Phase 30 correlation-schema
migration (034_add_correlation_sources). Run ONCE, manually, immediately after
`alembic upgrade head` completes and BEFORE verifying SC#2 (zero-loss,
per-tenant) -- see 30-RESEARCH.md Pitfall 5 for why the ordering matters.

Safe to re-run: run_correlations() is idempotent (upsert-on-uq_correlation +
prune-stale), mirroring the sla_service.backfill_sla_due_dates precedent.

Usage:
    docker compose exec backend python scripts/recorrelate_all_tenants.py
    # or, outside Docker:
    DATABASE_URL=postgresql+asyncpg://... python scripts/recorrelate_all_tenants.py
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select, text

from app.db.session import async_session_factory
from app.tenants.models import Tenant
from app.vulnerabilities.correlation_service import run_correlations

logger = structlog.get_logger()


async def _main() -> None:
    async with async_session_factory() as db:
        tenants = (await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))).scalars().all()
        for t in tenants:
            # Diagnostic "before" count: rows the schema-only backfill could not
            # fill (Qualys/Rapid7-only correlations -- the bug this recovers).
            blind_spots = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM vulnerability_correlations "
                        "WHERE tenant_id = :tid AND sources = '{}'"
                    ),
                    {"tid": str(t.id)},
                )
            ).scalar_one()

            stats = await run_correlations(db, t.id)

            # SC#2 per-tenant proof: must be 0 after this call (D-06 step 5).
            inconsistent = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM vulnerability_correlations "
                        "WHERE tenant_id = :tid AND "
                        "COALESCE(array_length(sources,1), 0) != sources_count"
                    ),
                    {"tid": str(t.id)},
                )
            ).scalar_one()

            logger.info(
                "recorrelated_tenant",
                tenant_id=str(t.id),
                blind_spot_rows_recovered=blind_spots,
                inconsistent_rows_after=inconsistent,  # MUST be 0
                **stats,
            )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(_main())
```

### 6. SC#4 regression test skeleton (`backend/tests/test_correlation_service.py` — new file)
```python
"""Phase 30 -- CORR-01/02/03 regression coverage. No prior test file for
correlation_service.py existed (confirmed via grep across backend/tests/).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.vulnerabilities.correlation_service import get_correlation_for_vuln, run_correlations
from app.vulnerabilities.models import Vulnerability


async def _seed_asset(db_session, tenant_id: uuid.UUID) -> uuid.UUID:
    # Mirrors the _seed_asset helper shape in test_ai_grounding_prioritization.py
    asset = Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.commit()
    return asset.id


def _seed_vuln(tenant_id, asset_id, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id, cve_id=cve_id, asset_id=asset_id, severity="HIGH", source=source,
        source_vuln_id=str(uuid.uuid4()), status="OPEN", first_detected_at=now, last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_qualys_rapid7_only_correlation_no_longer_silently_dropped(db_session, tenant_a):
    """D-10: this exact case (2 sources, neither CROWDSTRIKE/NESSUS/DEFENDER/WIZ)
    was silently dropped pre-fix -- the old SOURCE_COLUMN_MAP had no column for
    either source, so run_correlations() built an upsert with all 4 FK columns
    NULL, structurally indistinguishable from a genuinely-uncorrelated row.
    """
    asset_id = await _seed_asset(db_session, tenant_a)
    cve_id = "CVE-2024-QR001"
    qualys_vuln = _seed_vuln(tenant_a, asset_id, "QUALYS", cve_id)
    rapid7_vuln = _seed_vuln(tenant_a, asset_id, "RAPID7", cve_id)
    db_session.add_all([qualys_vuln, rapid7_vuln])
    await db_session.commit()

    await run_correlations(db_session, tenant_a)
    await db_session.commit()

    corr = await get_correlation_for_vuln(db_session, tenant_a, cve_id, asset_id)
    assert corr is not None, "Qualys+Rapid7 pair must now correlate"
    assert corr["sources"] == ["QUALYS", "RAPID7"], "canonical enum-declaration order"
    assert corr["sources_count"] == 2
    assert corr["confidence"] == "MEDIUM"  # D-08: 2-3 sources -> MEDIUM
    assert corr["source_vuln_ids"]["QUALYS"] == str(qualys_vuln.id)
    assert corr["source_vuln_ids"]["RAPID7"] == str(rapid7_vuln.id)
```

### 7. GIN containment query (ORM-level, forward reference for Phase 35)
```python
# Source: verified via real asyncpg execution -- .contains()/.overlap() bind
# parameters with the column's own type, avoiding the raw-SQL-literal cast
# pitfall (Pitfall 1) entirely. Not needed by Phase 30's own code paths, but
# this is the exact mechanism Phase 35's AND-filter (SRC-04) will build on.
from sqlalchemy import select
from app.vulnerabilities.models import VulnerabilityCorrelation

# @> "contains" -- corroborated by ALL listed sources
stmt = select(VulnerabilityCorrelation).where(
    VulnerabilityCorrelation.sources.contains(["QUALYS", "RAPID7"])
)

# && "overlap" -- corroborated by ANY listed source
stmt = select(VulnerabilityCorrelation).where(
    VulnerabilityCorrelation.sources.overlap(["DEFENDER"])
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| 4 hardcoded per-source FK columns (`crowdstrike_vuln_id`, `nessus_vuln_id`, `defender_vuln_id`, `wiz_vuln_id`), capped at exactly the sources known when the schema was first designed | `sources ARRAY(String)` + GIN index, generalized over the full `VulnSource` enum (6 values today, forward-compatible with a 7th) | This phase (`034_add_correlation_sources`, 2026-08) | QUALYS/RAPID7 correlations are no longer silently dropped; adding a 7th scanner source in the future requires zero schema change — just an enum member |
| `SOURCE_COLUMN_MAP` dict hardcoding 4-of-6 sources, iterated implicitly via `.get()` calls | Iterate the full `VulnSource` enum directly via `_SOURCE_ORDER` | This phase | `sources_count` and the resolved source list are derived from the *same* list in the *same* code path — structurally cannot disagree (CORR-03) |
| Confidence bands `HIGH ≥3 / MEDIUM =2 / LOW else` (tuned for a world where 4 sources were trackable) | `HIGH ≥4 / MEDIUM 2–3 / LOW 1` (tuned for the real 6-source world) | This phase (D-08) | `/correlations/stats`' by-confidence distribution shifts after deploy — expected side effect, not a regression (verified: no other file duplicates these thresholds) |

**Deprecated/outdated:**
- `SOURCE_COLUMN_MAP` and the 4 FK columns: fully removed, no compatibility shim retained (D-03 — this pattern is exactly what CORR-01/03 exist to kill).

## Assumptions Log

All claims in this research were either verified via direct execution against this repo's exact pinned dependency versions (Postgres 16.x, SQLAlchemy 2.0.50, asyncpg 0.31.0, alembic 1.18.4), verified via direct repo-wide code/grep inspection, or carried forward verbatim from CONTEXT.md's already-locked decisions (D-01 through D-10, not re-litigated per instructions).

**This table is empty** — no claim in this research rests solely on unverified training knowledge. The one item that came closest (an SQLAlchemy docs snippet suggesting ARRAY only works with psycopg2) was actively checked and refuted by direct execution — see Common Pitfalls #6.

## Open Questions

1. **Exact production row-count of `vulnerability_correlations`, to gauge real migration/re-correlation runtime**
   - What we know: D-07 characterizes the table as "small and rebuildable." The live dev Postgres container (`getvul-postgres-1`) currently has 0 rows (recently cleared/reset), so this environment cannot empirically confirm production scale.
   - What's unclear: How many tenants and rows actually exist in the deployed production system, and therefore how long `recorrelate_all_tenants.py` will take to run for real.
   - Recommendation: Not a blocker — D-06/D-07 already accept this characterization as a locked decision. If the planner wants a runtime estimate, checking the actual production row count before writing the deploy runbook step is a cheap, valuable addition, but isn't required to plan the phase's tasks.

2. **Should the re-correlation script (`recorrelate_all_tenants.py`) also be exposed as an admin-gated API route, matching the `POST /sla/backfill` precedent?**
   - What we know: `POST /sla/backfill` (`require_analyst`-gated, single current tenant) is an established pattern for re-triggering a backfill on demand. `dev_routes.py`'s `POST /run-correlations` already exists but is dev-only and single-hardcoded-tenant, not suitable for production multi-tenant re-runs.
   - What's unclear: Whether ops convenience (re-run via an authenticated HTTP call instead of `docker compose exec`) is worth the extra route/RBAC surface for what's fundamentally a one-time migration-cutover step.
   - Recommendation: Default to the standalone script only (satisfies D-07 literally, lowest surface area); the planner can add a route later if repeated re-runs turn out to be needed operationally.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | Schema migration, ARRAY+GIN, JSONB | ✓ [VERIFIED: docker-compose + CI both use `postgres:16-alpine`] | 16-alpine | — |
| SQLAlchemy | Model declarations, ORM comparators, Core upsert | ✓ [VERIFIED: `backend/.venv`] | 2.0.50 (declared `>=2.0`) | — |
| Alembic | Migration authoring/execution | ✓ [VERIFIED: `backend/.venv`] | 1.18.4 (declared `>=1.14`) | — |
| asyncpg | Runtime async Postgres driver | ✓ [VERIFIED: `backend/.venv`] | 0.31.0 (declared `>=0.30`) | — |
| Docker | Local verification, CI Postgres service | ✓ [VERIFIED: `docker ps` shows a running `getvul-postgres-1` dev stack] | — | — |

No missing dependencies. Nothing new to install for this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio, `asyncio_mode = "auto"` [VERIFIED: `backend/pyproject.toml:74-82`] |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && pytest tests/test_correlation_service.py -v` (per repo memory: run per-file, not the whole `tests/` dir, to avoid unrelated cross-test flakes — see project memory "Backend pytest env") |
| Full suite command | `cd backend && pytest -v --cov=app --cov-report=xml` (matches CI's exact invocation, `.github/workflows/ci.yml:96`) |

Local env vars needed (matching CI/`.github/workflows/ci.yml:91-95` and `docker-compose.yml`'s dev defaults): `DATABASE_URL=postgresql+asyncpg://getvul:getvul@localhost:5432/getvul_test` (or the dev DB), `REDIS_URL`, `JWT_SECRET_KEY`, `ENVIRONMENT=test`. Migrations must be applied first: `alembic upgrade head` (CI does this as a separate step before `pytest`, `.github/workflows/ci.yml:86-89`).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORR-01 | `sources` ARRAY(String)+GIN column exists, replaces the 4 FK columns, covers all 6 `VulnSource` values | schema/unit | `pytest tests/test_correlation_service.py::test_qualys_rapid7_only_correlation_no_longer_silently_dropped -x` (asserts `sources == ['QUALYS','RAPID7']`, proving both non-legacy sources round-trip) | ❌ Wave 0 (new file) |
| CORR-01 | 7th-source forward-compatibility (no schema change needed to add one) | manual/design-review | N/A — proven by construction (`_SOURCE_ORDER = [s.value for s in VulnSource]` has no hardcoded length) | — |
| CORR-02 | Existing correlation data migrates with zero loss, per-tenant | integration (migration verification) | Post-deploy, per-tenant: `SELECT tenant_id, count(*) FROM vulnerability_correlations WHERE COALESCE(array_length(sources,1),0) != sources_count GROUP BY tenant_id;` — expect 0 rows for every tenant | ❌ Wave 0 (add as an assertion in the migration verification step / a smoke test) |
| CORR-03 | `sources_count` and the resolved source list can never disagree | unit | Same consistency query as CORR-02, runnable as a standing regression test: seed varied source-count fixtures (1-of-6 through 6-of-6), call `run_correlations`, assert `len(corr.sources) == corr.sources_count` for every case | ❌ Wave 0 (new file) |
| SC#4 (regression) | Qualys+Rapid7-only finding now correlates correctly | integration | `pytest tests/test_correlation_service.py::test_qualys_rapid7_only_correlation_no_longer_silently_dropped -x` | ❌ Wave 0 (new file — Code Example #6 above) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_correlation_service.py -v` (fast, isolated — correlation logic + the one new test file)
- **Per wave merge:** `pytest tests/test_correlation_service.py tests/test_vuln_source_filter.py tests/test_vulnerabilities.py -v` (adjacent vulnerability-domain files, catches any accidental `sources_count`/`service.py` read regressions at lines 194/227/475)
- **Phase gate:** Full suite green (`pytest -v --cov=app --cov-report=xml`) before `/gsd-verify-work 30`, plus the migration applied cleanly (`alembic upgrade head` exit 0) against a fresh `postgres:16-alpine` (mirrors CI exactly)

### Wave 0 Gaps
- [ ] `backend/tests/test_correlation_service.py` — does not exist today (confirmed via grep — the only prior correlation-adjacent test is `test_vuln_source_filter.py`, which tests the `VulnSource` enum and the `?source=` list filter, not `correlation_service.py` itself). Needs the SC#4 regression test (Code Example #6) plus unit coverage for the canonical-order/confidence-banding logic across 1, 2, 3, 4, 5, 6-source fixtures.
- [ ] `backend/alembic/versions/034_add_correlation_sources.py` — does not exist; this migration itself is a Wave 0 deliverable, not pre-existing infrastructure.
- [ ] `backend/scripts/recorrelate_all_tenants.py` — does not exist; needed before SC#2 can be verified per-tenant in any real (non-test-fixture) environment.
- [ ] No dedicated migration-testing harness exists in this repo (no test runs `alembic upgrade`/`downgrade` programmatically) — CI's "Run migrations" step (`alembic upgrade head`, `.github/workflows/ci.yml:86-89`) is the only automated proof the migration applies cleanly. The planner should treat "CI's migration step succeeds" as the migration's own gate, separate from the pytest suite.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth changes this phase |
| V3 Session Management | No | No session changes this phase |
| V4 Access Control | Yes (unchanged, must be preserved) | `GET /{vuln_id}/correlation` stays `require_viewer`-gated (`router.py:678`, unchanged); every correlation query — old and rewritten — filters `.where(VulnerabilityCorrelation.tenant_id == tenant_id)`. The rewritten `get_correlation_for_vuln` and `run_correlations` both take `tenant_id` as an explicit parameter and every query inside them already scopes on it (confirmed by direct read of both current and proposed code) |
| V5 Input Validation | Yes (unchanged) | `vuln_id` path param is FastAPI/pydantic UUID-typed at the route boundary; `cve_id`/`asset_id` used inside `correlation_service.py` are DB-sourced (from `vulnerabilities` rows), not raw user input — no new user-supplied input surface introduced |
| V6 Cryptography | No | No secrets/crypto touched by this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant data leakage (IDOR) via a missing `tenant_id` filter on a correlation query | Information Disclosure | Every query (existing and rewritten) filters on `tenant_id`; the new SC#2 verification queries must be run **per-tenant** (`GROUP BY tenant_id` or looped, never a bare global aggregate) so a diagnostic report itself never mixes tenant data |
| Migration-time partial-write corruption on failure | Tampering / Denial of Service | Alembic runs each migration's `upgrade()` inside a single Postgres transaction; this repo has direct prior confirmation of clean rollback-on-failure behavior (`031_rename_audit_tenant_idx.py`'s docstring documents a real `StringDataRightTruncationError` mid-migration that rolled back cleanly with no manual cleanup needed) |
| Denial of service via an expensive migration locking a large table | Denial of Service | Already addressed by D-07: the expensive/variable-cost part (re-correlation) is deliberately kept **outside** the migration transaction; the migration itself only touches `vulnerability_correlations`, confirmed small in this environment (0 rows in the current dev DB) and architecturally rebuildable, not a hot high-traffic table like `vulnerabilities` itself |

## Sources

### Primary (HIGH confidence — direct execution or direct repo code read)
- `backend/app/vulnerabilities/correlation_service.py` (full file read) — confirmed `SOURCE_COLUMN_MAP`, confirmed `_find_correlated_groups`/`_prune_stale_correlations` are already source-agnostic
- `backend/app/vulnerabilities/models.py` — `VulnerabilityCorrelation`, `VulnSource`, `Confidence` definitions
- `backend/app/vulnerabilities/router.py` (lines 1-40, 190-220, 630-695) — `get_vuln_correlation`, `correlation_stats`, `sla_backfill` route shapes
- `backend/app/vulnerabilities/service.py` (lines 180-230, 460-490) — confirmed `sources_count` reads at lines 194/227/475 need no change
- `backend/app/assets/models.py`, `backend/alembic/versions/025_add_asset_tags.py` — the `assets.tags` ARRAY(String)+GIN precedent being mirrored
- `backend/alembic/versions/001_initial_schema.py` (lines 90-135) — original `vulnerability_correlations` + `vulnerabilities` table definitions
- `backend/alembic/versions/027_add_ticket_blocked_sla.py` — same-migration `op.execute()` UPDATE...FROM backfill precedent
- `backend/alembic/versions/031_rename_audit_tenant_idx.py`, `033_add_ai_batch_job.py` — revision-id length constraint + current migration head
- `backend/app/vulnerabilities/sla_service.py`, `backend/app/connectors/scheduler.py` (lines 180-215), `backend/scripts/capture_ai_goldens.py` — the idempotent-per-tenant-backfill and standalone-script precedents
- `backend/tests/conftest.py`, `backend/tests/test_vuln_source_filter.py`, `backend/tests/test_ai_grounding_prioritization.py` — test fixture conventions (`db_session`/`tenant_a`/`client`, Asset-seeding helper shape)
- `.github/workflows/ci.yml` (lines 30-100) — CI's exact migration + pytest invocation
- `docker-compose.yml` (lines 44-64) — confirmed `alembic upgrade head` runs automatically on every backend container start
- [VERIFIED: local disposable Postgres 16-alpine containers + `backend/.venv` (SQLAlchemy 2.0.50, asyncpg 0.31.0), 2026-08-04] — 4 separate end-to-end dry runs: (1) `ARRAY_REMOVE`/`jsonb_strip_nulls` backfill SQL correctness including the empty-array edge case, (2) GIN index creation + `@>`/`&&` operators including the `varchar[]` vs `text[]` cast pitfall and its ORM-level non-issue, (3) FK-constraint auto-drop on `DROP COLUMN`, (4) full production-shaped schema (real FK constraints, both a legacy-good row and a simulated Qualys/Rapid7-bug row) through the complete migration sequence, proving the exact transient-inconsistency window described in Pitfall 5
- Repo-wide `grep` sweeps confirming: zero frontend consumers of any correlation field; zero other backend files reference the 4 FK columns, `SOURCE_COLUMN_MAP`, or hardcoded confidence thresholds; no pydantic schema class exists for the correlation response; live dev DB schema matches `models.py` exactly (including the two additional `index=True`-derived btree indexes)

### Secondary (MEDIUM confidence)
- [CITED: docs.sqlalchemy.org — PostgreSQL dialect docs] `.contains()`/`.overlap()`/`.contained_by()` map to `@>`/`&&`/`<@`; `op.create_index(..., postgresql_using="gin")` is the documented Alembic GIN pattern — both cross-confirmed by, and consistent with, direct execution above

### Tertiary (LOW confidence — flagged and refuted, not relied upon)
- An SQLAlchemy 1.4-era doc snippet claiming ARRAY "is currently known to work on psycopg2 only" — actively checked against this repo's real asyncpg 0.31.0 driver and found false for this stack; see Common Pitfalls #6

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all versions confirmed installed via `backend/.venv`
- Architecture: HIGH — every pattern mirrors an already-shipped precedent in this exact repo, and the core mechanisms (ARRAY+GIN, JSONB backfill, upsert) were proven by direct execution
- Pitfalls: HIGH — 5 of 6 pitfalls reproduced or refuted by direct execution against real Postgres 16 + this repo's pinned SQLAlchemy/asyncpg/alembic versions; the 6th is a documentation-staleness caveat explicitly checked and dismissed

**Research date:** 2026-08-04
**Valid until:** Stable — this research is grounded in already-pinned dependency versions and core Postgres/SQLAlchemy behavior unlikely to change; re-verify only if `backend/pyproject.toml`'s SQLAlchemy/alembic/asyncpg version floors are bumped materially (e.g., a SQLAlchemy 3.0 or Alembic 2.0 major version)
