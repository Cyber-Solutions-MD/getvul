"""One-time per-tenant re-correlation pass for the Phase 30 correlation-schema
migration (034_add_correlation_sources).

Why this is NOT auto-run (D-07): `vulnerability_correlations` is small and
fully rebuildable from `vulnerabilities`, but re-running `run_correlations()`
for every active tenant is application-level business logic, not a pure SQL
transform -- it does not belong inside the Alembic migration's transaction
(this repo's convention for every migration data-step is plain `op.execute()`
raw SQL, never an imported service function). This script is the separate,
manually-invoked step D-07 calls for.

Run this ONCE, manually, immediately after `alembic upgrade head` completes
and BEFORE verifying SC#2 (zero-loss, per-tenant) -- see 30-RESEARCH.md
Pitfall 5 for why the ordering matters: a transient window exists right after
the migration's baseline backfill where a previously-buggy row (a Qualys/
Rapid7-only correlation) shows `sources = []` while `sources_count` still
holds its stale value. Verifying zero-loss in that window produces a false
"data loss" signal. Only after this script runs does that row correct itself.

Safe to re-run: `run_correlations()` is idempotent (upsert on `uq_correlation`
+ prune-stale), mirroring the `sla_service.backfill_sla_due_dates` precedent.

Usage:
    docker compose exec backend python scripts/recorrelate_all_tenants.py
    # or, outside Docker (with DATABASE_URL already pointed at the target DB):
    python scripts/recorrelate_all_tenants.py
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.tenants.models import Tenant
from app.vulnerabilities.correlation_service import run_correlations

logger = structlog.get_logger()


async def _recorrelate_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Re-run correlation for one tenant and prove zero-loss for that tenant.

    Takes an INJECTED session so a test can drive this with the `db_session`
    fixture instead of a fresh `async_session_factory()` session -- this
    function itself never commits; the caller (`_main()` or a test) controls
    the transaction boundary.

    Every query below is scoped to `tenant_id` -- the zero-loss check is a
    per-tenant proof (SC#2/CORR-02), never a bare global aggregate (T-30-05).
    """
    # Diagnostic "before" count: rows the schema-only migration backfill could
    # not fill (Qualys/Rapid7-only correlations -- the exact bug this recovers,
    # see 30-RESEARCH.md Pitfall 5).
    blind_spot_rows_recovered = (
        await db.execute(
            text("SELECT count(*) FROM vulnerability_correlations WHERE tenant_id = :tid AND sources = '{}'"),
            {"tid": str(tenant_id)},
        )
    ).scalar_one()

    stats = await run_correlations(db, tenant_id)

    # SC#2 per-tenant zero-loss proof (D-06 step 5). COALESCE is required --
    # array_length() of an empty array is NULL, not 0, so an unwrapped
    # comparison would silently skip sources='{}' rows (30-RESEARCH.md
    # Pitfall 3).
    inconsistent_rows_after = (
        await db.execute(
            text(
                "SELECT count(*) FROM vulnerability_correlations "
                "WHERE tenant_id = :tid AND "
                "COALESCE(array_length(sources,1), 0) != sources_count"
            ),
            {"tid": str(tenant_id)},
        )
    ).scalar_one()

    logger.info(
        "recorrelated_tenant",
        tenant_id=str(tenant_id),
        blind_spot_rows_recovered=blind_spot_rows_recovered,
        inconsistent_rows_after=inconsistent_rows_after,  # MUST be 0
        **stats,
    )

    return {
        "tenant_id": str(tenant_id),
        "blind_spot_rows_recovered": blind_spot_rows_recovered,
        "inconsistent_rows_after": inconsistent_rows_after,
        **stats,
    }


async def _main() -> None:
    async with async_session_factory() as db:
        tenants = (await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))).scalars().all()
        for t in tenants:
            try:
                await _recorrelate_tenant(db, t.id)
            except Exception as exc:  # noqa: BLE001 -- one tenant's failure must not abort the rest
                logger.error("recorrelate_tenant_error", tenant_id=str(t.id), error=str(exc))
                continue
        await db.commit()


if __name__ == "__main__":
    asyncio.run(_main())
