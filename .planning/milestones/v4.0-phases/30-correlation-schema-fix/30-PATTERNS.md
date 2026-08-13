# Phase 30: Correlation Schema Fix - Pattern Map

**Mapped:** 2026-08-04
**Files analyzed:** 5 new/modified + 2 verify-only (unchanged, but response-shape-dependent)
**Analogs found:** 5 / 5 — every new/modified file has at least one directly-shipped precedent in this exact repo (0 genuine "no analog" files)

This phase is unusually well-precedented: `assets.tags`/`assets.mdm_details` already prove the exact column shapes, `sla_service.py`+`scheduler.py` already prove the exact idempotent-per-tenant-backfill shape, and `correlation_service.py`'s own existing upsert already proves the exact write mechanism. The only genuinely novel code (no repo precedent) is the canonical-order enum filter and the `str(uuid)` cast — both one-liners, called out explicitly below so the planner doesn't go looking for a non-existent analog for them.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/alembic/versions/034_add_correlation_sources.py` (NEW) | migration | batch (DDL + backfill transform) | `backend/alembic/versions/025_add_asset_tags.py` (ARRAY+GIN) + `027_add_ticket_blocked_sla.py` (op.execute backfill) + `033_add_ai_batch_job.py` (JSONB column, current head) | exact (composite of 3 shipped migrations) |
| `backend/app/vulnerabilities/models.py` — `VulnerabilityCorrelation` class, lines 84-108 (MODIFIED) | model | CRUD | `backend/app/assets/models.py` (`Asset.tags` line 71, `Asset.mdm_details` line 67) | exact |
| `backend/app/vulnerabilities/correlation_service.py` (MODIFIED, in-place rewrite) | service | batch/transform (`run_correlations`) + request-response (`get_correlation_for_vuln`) | self (current file — 2 of 4 functions provably unchanged) | exact (self-modification) |
| `backend/scripts/recorrelate_all_tenants.py` (NEW) | utility / standalone script | batch (per-tenant loop) | `backend/app/vulnerabilities/sla_service.py::backfill_sla_due_dates` + `backend/app/connectors/scheduler.py` (tenant loop) + `backend/scripts/capture_ai_goldens.py` (entrypoint idiom) + `backend/app/dev_routes.py::run_correlations_endpoint` (run_correlations call-site shape) | role-match (composite of 4 shipped precedents) |
| `backend/tests/test_correlation_service.py` (NEW) | test | CRUD / request-response (direct service calls against `db_session`, no HTTP client) | `backend/tests/test_vuln_source_filter.py` + `backend/tests/test_ai_grounding_prioritization.py` (seed-helper shape) + `backend/tests/conftest.py` (fixtures) | role-match + domain-match |

### Verify-only (no code change expected — behavior/response-shape depends on the files above)

| File | Role | Data Flow | Note |
|---|---|---|---|
| `backend/app/vulnerabilities/router.py` — `get_vuln_correlation` (674-694), `correlation_stats` (638-671) | route/controller | request-response | Confirmed unchanged: `get_vuln_correlation` just spreads whatever `get_correlation_for_vuln()` returns (`{"correlated": True, **corr}`, line 694) — the dict shape change flows through automatically. No edit needed, but the planner's verification step should still exercise this route. |
| `backend/app/vulnerabilities/service.py` — `sources_count` reads (194-200, 227, 472-477) | service (read) | CRUD | `sources_count` column is untouched by this phase (kept, not renamed) — these 3 read sites need zero edits. Confirm during verification only. |

## Pattern Assignments

### `backend/alembic/versions/034_add_correlation_sources.py` (migration, batch)

**Analog A — ARRAY(String)+GIN column+index:** `backend/alembic/versions/025_add_asset_tags.py` (full file, 30 lines — this is THE shipped precedent D-01 explicitly locks mirroring)

```python
# backend/alembic/versions/025_add_asset_tags.py — full file
"""Add tags ARRAY(String) column to assets. ..."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "025_add_asset_tags"
down_revision = "024_add_containment_status"


def upgrade() -> None:
    op.add_column("assets", sa.Column("tags", ARRAY(sa.String()), nullable=True))
    # GIN index supports future tag-search containment + ILIKE queries
    op.create_index(
        "ix_assets_tags",
        "assets",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_assets_tags", table_name="assets")
    op.drop_column("assets", "tags")
```
Apply verbatim to `vulnerability_correlations`/`sources`, renaming the index to `ix_vulnerability_correlations_sources` (matches the `ix_` prefix convention used by every migration since this one).

**Analog B — `op.execute()` raw-SQL backfill UPDATE inside a migration:** `backend/alembic/versions/027_add_ticket_blocked_sla.py` lines 39-47

```python
# D-SLA-03 backfill: each ticket ROW is 1:1 with its vuln (vulnerability_id FK),
# so per-row value = that vuln's sla_due_at. The group MIN (per external_ticket_url)
# is then computed at read time in list_tickets (Plan 03).
op.execute(
    """
    UPDATE tickets t
    SET sla_due_at = v.sla_due_at
    FROM vulnerabilities v
    WHERE t.vulnerability_id = v.id
      AND v.sla_due_at IS NOT NULL
"""
)
```
This is the repo's established "same-migration raw-SQL backfill" idiom (comment explaining WHY the backfill is correct, then a plain `op.execute()` string) — mirror this shape for the `sources`/`source_vuln_ids` baseline backfill (D-06 step 2), using `ARRAY_REMOVE(ARRAY[CASE WHEN ... END, ...], NULL)` and `jsonb_strip_nulls(jsonb_build_object(...))` respectively (both verified working in RESEARCH.md's direct-execution pass — reuse that exact SQL, it does not need re-deriving).

**Analog C — JSONB column declaration + current head/docstring convention:** `backend/alembic/versions/033_add_ai_batch_job.py` (current head)

```python
# lines 27-28 — this IS the down_revision target for 034
revision = "033_add_ai_batch_job"
down_revision = "032_add_ai_feedback"
```
```python
# line 50 — JSONB column via postgresql dialect import
sa.Column("custom_id_hash_map", postgresql.JSONB, nullable=False),
```
Confirmed via `ls backend/alembic/versions/` that `033_add_ai_batch_job.py` is the current head — `034_add_correlation_sources.py` must set `down_revision = "033_add_ai_batch_job"`.

**Analog D — revision-id length constraint (already hit once in this repo):** `backend/alembic/versions/031_rename_audit_tenant_idx.py` lines 17-26

```python
# NOTE on this file's own (short) name: the originally-planned revision id
# `031_add_audit_logs_tenant_created_index` is 39 characters — this repo's
# `alembic_version.version_num` column is `varchar(32)` (alembic's own
# default; every existing revision id in this repo is <= 32 chars, e.g.
# `030_add_connector_health_columns` sits exactly at 32), so that revision id
# would raise `StringDataRightTruncationError` on `alembic upgrade head`
# (confirmed empirically ...). This file's revision id is shortened to fit.
```
`034_add_correlation_sources` is 27 characters — under the limit. Do not extend the name (e.g. do not add `_array` or `_and_source_vuln_ids`).

**Original table being altered (columns being dropped):** `backend/alembic/versions/001_initial_schema.py` lines 108-135

```python
op.create_table(
    "vulnerability_correlations",
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
    sa.Column("cve_id", sa.String(20), nullable=False, index=True),
    sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
    sa.Column("crowdstrike_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
    sa.Column("nessus_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
    sa.Column("defender_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
    sa.Column("wiz_vuln_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL")),
    sa.Column("sources_count", sa.Integer, server_default="1"),
    sa.Column("confidence", sa.String(10), server_default="'LOW'"),
    sa.UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),
)
op.create_index("idx_correlation_cve", "vulnerability_correlations", ["tenant_id", "cve_id"])
```
Note the pre-existing `idx_correlation_cve` index on `(tenant_id, cve_id)` — this phase does not touch it; only the 4 FK columns are dropped (`op.drop_column` x4 — dropping auto-drops their inline FK constraints, verified directly, no explicit `DROP CONSTRAINT`/`CASCADE` needed).

---

### `backend/app/vulnerabilities/models.py` — `VulnerabilityCorrelation` (model, CRUD)

**Analog:** `backend/app/assets/models.py` (full file, 76 lines)

**Imports pattern** (lines 1-10 — `ARRAY` needs adding to `models.py`'s existing `from sqlalchemy.dialects.postgresql import JSONB, UUID` since only `JSONB, UUID` are currently imported there):
```python
from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
```

**ARRAY(String) column pattern** (`assets/models.py` lines 69-71):
```python
# Operational labels (e.g. "pci", "dmz", "tier-1") rendered as chips next to hostname.
# Phase 12 / UX-04-02. Empty list by default. GIN-indexed (alembic 025_add_asset_tags).
tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
```

**JSONB column pattern** (`assets/models.py` line 67):
```python
mdm_details: Mapped[dict | None] = mapped_column(JSONB, default=dict)
```
(Note: `source_vuln_ids` should follow the plain `Mapped[dict | None] = mapped_column(JSONB, nullable=True)` shape — no `default=dict` needed since D-06's migration-time backfill always sets a value, and app-code always populates it on every `run_correlations` upsert.)

**Relationship/back_populates pattern already wired** (`assets/models.py` lines 74-76 — no change needed on the `Asset` side, this already points at `VulnerabilityCorrelation`):
```python
correlations: Mapped[list["VulnerabilityCorrelation"]] = relationship(
    "VulnerabilityCorrelation", back_populates="asset"
)
```

**Current state being replaced** (`backend/app/vulnerabilities/models.py` lines 84-108 — the exact block to rewrite):
```python
class VulnerabilityCorrelation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "vulnerability_correlations"
    __table_args__ = (UniqueConstraint("tenant_id", "cve_id", "asset_id", name="uq_correlation"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    crowdstrike_vuln_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="SET NULL")
    )
    nessus_vuln_id: Mapped[uuid.UUID | None] = mapped_column(...)     # + defender_vuln_id, wiz_vuln_id (same shape) — ALL 4 REMOVED (D-03)
    sources_count: Mapped[int] = mapped_column(Integer, default=1)     # KEPT, unchanged
    confidence: Mapped[str] = mapped_column(String(10), default=Confidence.LOW.value)  # KEPT, unchanged

    asset: Mapped["Asset"] = relationship("Asset", back_populates="correlations")  # KEPT, unchanged
```
`VulnSource` enum (unchanged, iterate this — do not touch): `models.py` lines 31-37, declaration order `CROWDSTRIKE, NESSUS, DEFENDER, WIZ, QUALYS, RAPID7` — this literal order is D-02's canonical sort order. `Confidence` enum (unchanged): lines 40-43.

---

### `backend/app/vulnerabilities/correlation_service.py` (service, batch/transform + request-response)

**Analog:** self (current 207-line file) — this is an in-place rewrite, not a from-scratch file. Two of the four functions are provably unaffected; only the value-building block of `run_correlations` and the read-shaping block of `get_correlation_for_vuln` change.

**Imports pattern** (lines 1-14 — add `VulnSource` to the existing model import):
```python
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation  # add VulnSource here

logger = structlog.get_logger()
```

**Pattern to DELETE entirely** (lines 16-22 — `SOURCE_COLUMN_MAP`, D-03):
```python
# Source column mapping on VulnerabilityCorrelation
SOURCE_COLUMN_MAP = {
    "CROWDSTRIKE": "crowdstrike_vuln_id",
    "NESSUS": "nessus_vuln_id",
    "DEFENDER": "defender_vuln_id",
    "WIZ": "wiz_vuln_id",
}
```

**Core upsert pattern to preserve the SHAPE of but rewrite the CONTENTS of** (lines 40-82, inside `run_correlations`):
```python
for key, source_vulns in groups.items():
    cve_id, asset_id = key
    sources_count = len(source_vulns)

    if sources_count >= 3:          # → D-08 recalibrates to >=4 / 2-3 / 1
        confidence = "HIGH"
    elif sources_count == 2:        # → D-08 recalibrates to 2-3
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    values = {
        "tenant_id": tenant_id,
        "cve_id": cve_id,
        "asset_id": asset_id,
        "sources_count": sources_count,
        "confidence": confidence,
        "crowdstrike_vuln_id": source_vulns.get("CROWDSTRIKE"),   # → replace with sources=[...] + source_vuln_ids={...}
        "nessus_vuln_id": source_vulns.get("NESSUS"),
        "defender_vuln_id": source_vulns.get("DEFENDER"),
        "wiz_vuln_id": source_vulns.get("WIZ"),
    }

    stmt = pg_insert(VulnerabilityCorrelation).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_correlation",
        set_={
            "sources_count": stmt.excluded.sources_count,
            "confidence": stmt.excluded.confidence,
            "crowdstrike_vuln_id": stmt.excluded.crowdstrike_vuln_id,   # → replace 4 keys with "sources"/"source_vuln_ids"
            "nessus_vuln_id": stmt.excluded.nessus_vuln_id,
            "defender_vuln_id": stmt.excluded.defender_vuln_id,
            "wiz_vuln_id": stmt.excluded.wiz_vuln_id,
        },
    )
    result = await db.execute(stmt)
```
The `pg_insert(...).on_conflict_do_update(constraint="uq_correlation", set_={...})` upsert mechanism itself is untouched — only the dict keys inside `values`/`set_` change from 4 named FK columns to `sources`/`source_vuln_ids`. This is the ONLY other place in `backend/app` besides `ai/models.py`, `api/v1/ai/feedback.py`, and `ticketing/router.py` that uses `pg_insert`/`on_conflict_do_update` — confirmed via repo-wide grep — so there's no additional external upsert-pattern file to consult.

**Functions confirmed UNCHANGED (do not edit — already source-agnostic):**
- `_find_correlated_groups` (lines 101-141) — already queries `Vulnerability.source` unrestricted (line 115) and already returns `{source: vuln_id}` dicts containing QUALYS/RAPID7 when present (line 137-138 `if source not in groups[key]: groups[key][source] = vuln_id`). The bug this phase fixes is entirely downstream of this function.
- `_prune_stale_correlations` (lines 144-167) — operates on `(cve_id, asset_id)` keys only, never touches per-source columns.

**Read-shaping pattern to rewrite** (`get_correlation_for_vuln`, lines 170-206):
```python
async def get_correlation_for_vuln(
    db: AsyncSession, tenant_id: uuid.UUID, cve_id: str, asset_id: uuid.UUID
) -> dict | None:
    """Get correlation details for a specific CVE + asset pair."""
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

    sources = []                              # → replace this 4-if-statement block
    if corr.crowdstrike_vuln_id:               #   with `corr.sources or []` (D-09) —
        sources.append("CROWDSTRIKE")          #   the array IS the canonical list now,
    if corr.nessus_vuln_id:                    #   no per-column reconstruction needed
        sources.append("NESSUS")
    if corr.defender_vuln_id:
        sources.append("DEFENDER")
    if corr.wiz_vuln_id:
        sources.append("WIZ")

    return {
        "id": corr.id,
        "cve_id": corr.cve_id,
        "asset_id": corr.asset_id,
        "sources": sources,
        "sources_count": corr.sources_count,
        "confidence": corr.confidence,
        "crowdstrike_vuln_id": corr.crowdstrike_vuln_id,   # → replace these 4 keys with
        "nessus_vuln_id": corr.nessus_vuln_id,              #   "source_vuln_ids": corr.source_vuln_ids or {}
        "defender_vuln_id": corr.defender_vuln_id,
        "wiz_vuln_id": corr.wiz_vuln_id,
    }
```
Tenant-scoping (`.where(VulnerabilityCorrelation.tenant_id == tenant_id, ...)`) is preserved exactly, unchanged — this is the security-relevant part (V4 Access Control), do not touch the `.where()` clause shape.

**No repo precedent (genuinely new code — flagged per critical_rules, not missing an analog, just novel):**
- Canonical-order enum filter: `[s for s in _SOURCE_ORDER if s in source_vulns]` where `_SOURCE_ORDER = [s.value for s in VulnSource]`. Nothing else in the repo iterates an enum this way; it is a one-line, self-documenting pattern, not something needing a borrowed analog.
- `str(source_vulns[s])` cast before writing into the `source_vuln_ids` JSONB dict — required because a raw `uuid.UUID` is not JSON-serializable (verified in RESEARCH.md Pitfall 2). No existing JSONB-writing code in this repo (`Asset.mdm_details`, `ai_batch_jobs.custom_id_hash_map`) happens to write UUID values into its JSONB column, so there's no prior "gotcha" precedent — this is the one pitfall genuinely specific to this phase.

---

### `backend/scripts/recorrelate_all_tenants.py` (NEW — utility/standalone script, batch)

**Analog A — idempotent per-tenant backfill function shape:** `backend/app/vulnerabilities/sla_service.py::backfill_sla_due_dates`, lines 41-61
```python
async def backfill_sla_due_dates(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Set sla_due_at for all open vulns that don't have one yet."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_days = get_sla_days(tenant)

    updated = 0
    for severity, days in sla_days.items():
        result = await db.execute(
            update(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.severity == severity,
                Vulnerability.sla_due_at.is_(None),
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.first_detected_at.isnot(None),
            )
            .values(sla_due_at=Vulnerability.first_detected_at + timedelta(days=days))
        )
        updated += result.rowcount

    return {"backfilled": updated}
```
`run_correlations(db, tenant_id)` (the function this script calls, unchanged signature) is already shaped exactly like this — takes `(db, tenant_id)`, returns a stats dict, safe to re-run (upsert + prune, not additive-only, but idempotent all the same).

**Analog B — the tenant-loop idiom:** `backend/app/connectors/scheduler.py` lines 199-206
```python
from app.tenants.models import Tenant as TenantModel
from app.vulnerabilities.sla_service import backfill_sla_due_dates, check_sla_breaches

tenants = (await db.execute(_sel(TenantModel).where(TenantModel.is_active.is_(True)))).scalars().all()
for t in tenants:
    await backfill_sla_due_dates(db, t.id)
    await check_sla_breaches(db, t.id)
await db.commit()
```
This is the exact "select active tenants, loop, call idempotent per-tenant fn(s), commit once" shape to reuse — swap `backfill_sla_due_dates`/`check_sla_breaches` for `run_correlations`.

**Analog C — standalone-script docstring + entrypoint idiom:** `backend/scripts/capture_ai_goldens.py` lines 1-18 (docstring convention) + lines 397-422 (`_main()`/`__main__` shape)
```python
# lines 1-18 docstring convention: what the script is, why it's not run in CI,
# exact `Usage:` invocation line, and a "Re-capture procedure" section.
"""One-time dev-key golden-fixture capture script (AIE-01, 28-CONTEXT.md D-07).

This script is NOT run in CI -- it is a manually-invoked, one-time developer
tool. ...

Usage (requires a personal dev key -- never committed, never used in CI):

    GETVUL_DEV_ANTHROPIC_KEY=sk-ant-... python scripts/capture_ai_goldens.py
"""
```
```python
# lines 397-422 entrypoint shape
async def _main() -> None:
    ...
    failures: list[...] = []
    for row in CAPTURE_ROWS:
        try:
            await _capture_one(row, api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            failures.append((row.capability, row.case, exc))
            print(f"SKIPPED {row.capability}/{row.case}: {exc}", file=sys.stderr)  # noqa: T201

    if failures:
        print(f"{len(failures)} of {len(CAPTURE_ROWS)} rows failed ...", file=sys.stderr)  # noqa: T201
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(_main())
```
Mirror the docstring shape (what/why/usage/when-to-rerun) and the `async def _main(): ... ; if __name__ == "__main__": asyncio.run(_main())` entrypoint exactly; adapt the per-item try/except-and-continue loop to per-tenant (a failure recorrelating one tenant should not abort the others — same resilience shape).

**Analog D — existing `run_correlations` call-site shape (closest single precedent for what the script's body actually does):** `backend/app/dev_routes.py::run_correlations_endpoint`, full function, lines 21-43
```python
@router.post("/run-correlations")
async def run_correlations_endpoint(db: AsyncSession = Depends(get_db)):
    """Run the correlation engine for the demo tenant. Dev only."""
    from sqlalchemy import select

    from app.assets.risk_score import compute_risk_scores
    from app.tenants.models import Tenant
    from app.vulnerabilities.correlation_service import run_correlations

    tenant = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
    if not tenant:
        return {"error": "No tenant found. Seed first."}

    corr_stats = await run_correlations(db, tenant.id)
    risk_stats = await compute_risk_scores(db, tenant.id)
    await db.commit()

    return {
        "message": "Correlations and risk scores computed",
        "tenant_id": str(tenant.id),
        "correlations": corr_stats,
        "risk_scores": risk_stats,
    }
```
This (and `backend/app/seed.py` lines 237-243, and `backend/app/connectors/sync.py` line 170) is the established "call `run_correlations(db, tenant_id)`, then commit" call-site convention across all 3 existing callers — the new script is a 4th caller, looped over all active tenants instead of one. Do NOT call `compute_risk_scores` from the new script — that's connector-sync/dev-seed behavior, not part of this phase's data-recovery step (out of scope per CONTEXT.md domain boundary).

**Verification queries to embed** (from RESEARCH.md, already proven correct against the empty-array edge case — Pitfall 3): use `COALESCE(array_length(sources,1), 0) != sources_count`, never the unwrapped `array_length(sources,1) != sources_count` (which silently skips `sources='{}'` rows because `NULL != 2` is `NULL`, not `TRUE`, in SQL).

---

### `backend/tests/test_correlation_service.py` (NEW — test, CRUD/request-response)

**Analog A:** `backend/tests/test_vuln_source_filter.py` (full file, 78 lines — the only prior correlation-adjacent test; tests the `VulnSource` enum + the `?source=` list filter, NOT `correlation_service.py` itself)

**Seed-helper pattern** (lines 23-34):
```python
def _seed(tenant_id, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        severity="HIGH",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )
```
(Note: this `_seed` has no `asset_id` — correlation tests need one, since `_find_correlated_groups` filters on `Vulnerability.asset_id.isnot(None)`. Use `test_ai_grounding_prioritization.py`'s `_seed_asset` pattern below for that part.)

**Sync vs async test convention** (lines 37-40 vs 43-51 — note the repo decorates async tests with `@pytest.mark.asyncio` even though `asyncio_mode = "auto"` is set in `pyproject.toml`; keep doing so for consistency):
```python
def test_vuln_source_enum_members():
    assert VulnSource.QUALYS.value == "QUALYS"
    assert VulnSource.RAPID7.value == "RAPID7"
    assert {m.value for m in VulnSource} == {"CROWDSTRIKE", "NESSUS", "DEFENDER", "WIZ", "QUALYS", "RAPID7"}


@pytest.mark.asyncio
async def test_source_filter_qualys(client, db_session, tenant_a):
    db_session.add(_seed(tenant_a, "QUALYS", "CVE-Q-001"))
    db_session.add(_seed(tenant_a, "RAPID7", "CVE-R-001"))
    await db_session.commit()
    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS")
    assert resp.status_code == 200
    sources = {i["source"] for i in resp.json()["items"]}
    assert sources == {"QUALYS"}, f"expected only QUALYS, got {sources}"
```

**Analog B — Asset+Vulnerability seed-helper shape (needed because correlation requires an `asset_id`):** `backend/tests/test_ai_grounding_prioritization.py` lines 26-38, 41-67
```python
async def _seed_asset(db_session, tenant_id: uuid.UUID, **overrides: Any) -> uuid.UUID:
    from app.assets.models import Asset

    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "department": "Finance",
    }
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return asset.id
```
Use this `_seed_asset` shape (returns `asset.id` after commit) combined with `test_vuln_source_filter.py`'s `_seed` (add an `asset_id=asset_id` field) to build the SC#4 fixture: one asset, two `Vulnerability` rows (`source="QUALYS"` and `source="RAPID7"`) sharing the same `cve_id` and `asset_id`.

**Analog C — fixtures to depend on:** `backend/tests/conftest.py`
```python
# lines 157-158, 179-189 — db_session: skips (not fails) if Postgres unreachable
@pytest_asyncio.fixture(scope="function")
async def db_session(redis_test_url) -> AsyncIterator[Any]:
    if not await _db_reachable():
        pytest.skip("Postgres not reachable — set DATABASE_URL to a live instance")
    ...
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
```
```python
# lines 215-230 — tenant_a: isolated tenant per test
@pytest_asyncio.fixture(scope="function")
async def tenant_a(db_session) -> AsyncIterator[uuid.UUID]:
    from app.tenants.models import Tenant
    tenant = Tenant(
        name=f"Tenant A {uuid.uuid4().hex[:8]}", slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        domain=f"tenant-a-{uuid.uuid4().hex[:8]}.test", idp_provider="GOOGLE", idp_tenant_id="test-a",
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant.id
```
The SC#4 regression test needs only `db_session` + `tenant_a` (no `client`/`analyst_user` needed, since it calls `run_correlations`/`get_correlation_for_vuln` directly as plain async functions, not via HTTP) — matching the shape RESEARCH.md's Code Example #6 already sketches (`test_qualys_rapid7_only_correlation_no_longer_silently_dropped(db_session, tenant_a)`). `tenant_b` (lines 233-247) is available if the planner wants to add a cross-tenant isolation test mirroring `test_source_filter_tenant_scoped` (lines 65-77 of `test_vuln_source_filter.py`).

**Full-suite command note (repo memory):** run this new test file individually — `cd backend && pytest tests/test_correlation_service.py -v` — not the whole `tests/` directory, per this repo's documented pytest-env flakiness on full-directory runs.

---

## Shared Patterns

### Multi-tenant scoping
**Source:** `backend/app/vulnerabilities/correlation_service.py` (every query, e.g. lines 118-123, 154-155, 175-179) + `backend/app/vulnerabilities/router.py` (`user.tenant_id` on every route)
**Apply to:** All 5 files — every new/rewritten query (including the new SC#2 verification queries in the migration/script) must filter `.where(VulnerabilityCorrelation.tenant_id == tenant_id)` and never run as a bare global aggregate (per RESEARCH.md's Security Domain: a global aggregate is itself a diagnostic cross-tenant leak).
```python
select(VulnerabilityCorrelation).where(
    VulnerabilityCorrelation.tenant_id == tenant_id,
    VulnerabilityCorrelation.cve_id == cve_id,
    VulnerabilityCorrelation.asset_id == asset_id,
)
```

### structlog logging
**Source:** `backend/app/vulnerabilities/correlation_service.py` lines 7, 14, 88-93
**Apply to:** `correlation_service.py` (keep the existing `logger.info("correlation_complete", tenant_id=..., correlated=..., stale_removed=...)` call, unchanged shape) and `recorrelate_all_tenants.py` (new — log per-tenant recovery stats the same way, matching `scheduler.py`'s `logger.error("sla_check_error", error=str(e))` per-tenant-loop-iteration error-logging shape at line 207 of `scheduler.py` for the try/except-per-tenant wrapper).
```python
logger = structlog.get_logger()
...
logger.info("correlation_complete", tenant_id=str(tenant_id), correlated=created, stale_removed=stale_deleted)
```

### Idempotent per-tenant backfill/recompute
**Source:** `backend/app/vulnerabilities/sla_service.py::backfill_sla_due_dates` (lines 41-61) + `backend/app/connectors/scheduler.py` (lines 199-206)
**Apply to:** `recorrelate_all_tenants.py` — the entire script IS this pattern, reusing `run_correlations` (already idempotent) instead of introducing a new backfill function.

### Postgres upsert (`pg_insert().on_conflict_do_update()`)
**Source:** `backend/app/vulnerabilities/correlation_service.py` lines 65-76 (current, self)
**Apply to:** `correlation_service.py`'s rewritten `run_correlations` — extend the existing `values`/`set_` dicts with `sources`/`source_vuln_ids`, remove the 4 FK-column keys. This is the only other upsert user in `backend/app` alongside `ai/models.py`, `api/v1/ai/feedback.py`, `ticketing/router.py` (confirmed via grep) — no cross-file pattern change needed, just the key rename within this one call.

### Alembic revision chaining + naming
**Source:** `backend/alembic/versions/033_add_ai_batch_job.py` (current head) + `031_rename_audit_tenant_idx.py` (32-char `varchar` cap on `alembic_version.version_num`)
**Apply to:** `034_add_correlation_sources.py` — `down_revision = "033_add_ai_batch_job"`; keep the revision id at or under 32 chars (`034_add_correlation_sources` = 27 chars, confirmed safe).

### pytest async test conventions
**Source:** `backend/tests/test_vuln_source_filter.py` + `backend/tests/test_ai_grounding_prioritization.py` + `backend/tests/conftest.py`
**Apply to:** `test_correlation_service.py` — `@pytest.mark.asyncio` decorator on every async test (even though `asyncio_mode = "auto"`, per repo convention), local `async def _seed_*(...)` helper functions that `db_session.add()` + `await db_session.commit()` and return an id, `db_session`/`tenant_a`/`tenant_b` fixtures from `conftest.py`, no `client` fixture needed for pure-service-layer tests.

## No Analog Found

None at the file level — every new/modified file has at least one directly-shipped precedent (see table above). Two specific **code fragments** (not files) are genuinely novel, called out here so the planner doesn't spend time searching for a non-existent precedent:

| Fragment | Location | Why no analog | Reference |
|---|---|---|---|
| Canonical-order enum filter `[s for s in _SOURCE_ORDER if s in source_vulns]` | new `correlation_service.py` | Nothing else in the repo iterates an enum's declaration order this way; it's a one-liner correct by construction (D-02) | RESEARCH.md Pattern 3 |
| `str(uuid_value)` cast before JSONB insert | new `correlation_service.py` (`source_vuln_ids` construction) | No existing JSONB-writing code in this repo (`Asset.mdm_details`, `ai_batch_jobs.custom_id_hash_map`) happens to write a raw UUID value, so there's no prior "gotcha" precedent to point to — RESEARCH.md's direct-execution pass is the only proof this is needed | RESEARCH.md Common Pitfalls #2 |

## Metadata

**Analog search scope:** `backend/app/vulnerabilities/`, `backend/app/assets/`, `backend/alembic/versions/`, `backend/app/connectors/`, `backend/scripts/`, `backend/tests/`, `backend/app/dev_routes.py`, `backend/app/seed.py`
**Files read in full or targeted-range:** 17 (`models.py`, `correlation_service.py`, `assets/models.py`, `025_add_asset_tags.py`, `sla_service.py`, `033_add_ai_batch_job.py`, `031_rename_audit_tenant_idx.py`, `027_add_ticket_blocked_sla.py`, `test_vuln_source_filter.py`, `test_ai_grounding_prioritization.py`, `router.py`, `service.py`, `scheduler.py`, `capture_ai_goldens.py`, `conftest.py`, `sync.py`, `seed.py`, `dev_routes.py`, `001_initial_schema.py`)
**Confirmed via `ls`:** `033_add_ai_batch_job.py` is the current alembic head; `backend/scripts/` contains only `capture_ai_goldens.py` today; `backend/tests/test_correlation_service.py` does not yet exist.
**Pattern extraction date:** 2026-08-04
