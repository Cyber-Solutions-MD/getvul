"""Historical risk-exposure backfill (Phase 34 Plan 01 — RISK-07 LEAD
TRACER): idempotent, resumable, throttled, per-tenant-isolated recompute of
every tenant's pre-existing OPEN/IN_PROGRESS findings onto
`RISK_MODEL_VERSION`.

Pure synthesis of 4 already-shipped precedents (34-RESEARCH.md "Don't
Hand-Roll"), never invention:
  1. Durable job state — `AiBatchJob` (`app/ai/models.py:52-90`) +
     `poll_pending_batches` (`app/ai/batch.py:329-395`): a Postgres row,
     re-queried by status every tick, survives a process restart. An
     in-memory dict (this file's own module-level globals in
     `scheduler.py`, e.g. `_running_syncs`) is explicitly the WRONG shape.
  2. Idempotent WHERE-guard — `backfill_sla_due_dates`
     (`sla_service.py:41-61`): re-running only ever touches not-yet-migrated
     rows. THE PRIMARY IDEMPOTENCY MECHANISM here is
     `risk_model_version IS DISTINCT FROM RISK_MODEL_VERSION` — re-running
     any chunk, or the whole job from scratch, is a safe no-op once a row
     is on-version. `cursor_vuln_id` is an EFFICIENCY optimization only
     (avoids rescanning an already-done prefix), never a correctness
     requirement — this is exactly why a kill-mid-chunk-and-resume is safe
     regardless of the precise moment of the kill.
  3. Bulk `UPDATE ... FROM` — `repropagate_enrichment`
     (`enrichment_feeds.py:234-262`), the only existing `UPDATE...FROM` in
     this codebase. Adapted here to be per-tenant-scoped + chunked (that
     one is global + unchunked).
  4. Scoring logic — `score_finding`/`FindingScoreInputs`
     (`risk_exposure_service.py:141-310`), reused VERBATIM. A second
     scoring implementation would risk silently diverging from what a live
     sync computes for the same inputs (anti-pattern, never hand-rolled
     twice).

Steps 3+4 (score + persist) share ONE transaction with step 5 (cursor +
counter advance) — Pitfall 5 option (a): a crash after scoring but before
this function's single `db.commit()` rolls the WHOLE chunk back cleanly,
so `rows_migrated` can never be double-counted by a resumed retry (the
WHERE-guard in step 2 would just re-select the identical not-yet-migrated
rows next time).

Throttling is structural, not a rate-limit/sleep: one chunk (`chunk_size`,
default 500) per tenant per scheduler tick, dispatched via
`asyncio.create_task` (never inline-awaited on the tick — see
`scheduler._dispatch_risk_exposure_backfill`).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import cast

import structlog
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import RiskExposureBackfillJob, Vulnerability, VulnerabilityCorrelation
from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION, FindingScoreInputs, score_finding

logger = structlog.get_logger()

# A claimed-but-not-heartbeat-refreshed job is considered abandoned (crashed
# process) after this window and is reclaimable by the next tick — mirrors
# 34-RESEARCH.md's claim-row design (lines 192-206).
_HEARTBEAT_STALE_AFTER = timedelta(minutes=5)

# T-34-02 (DoS mitigation): status values eligible to be claimed/advanced.
# 'failed' and 'completed' are terminal -- never auto-reclaimed by the tick.
_CLAIMABLE_STATUSES = ("pending", "in_progress")


async def enqueue_backfill_job(db: AsyncSession, tenant_id: uuid.UUID) -> RiskExposureBackfillJob:
    """Create the tenant's single durable job row, status='pending',
    `rows_total_estimate` captured once (count of OPEN/IN_PROGRESS findings
    not yet on RISK_MODEL_VERSION). `UniqueConstraint(tenant_id)` makes a
    second call idempotent -- returns the existing row unchanged rather than
    raising or creating a duplicate."""
    existing = (
        await db.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    rows_total_estimate = (
        await db.execute(
            select(func.count())
            .select_from(Vulnerability)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                or_(
                    Vulnerability.risk_model_version.is_(None),
                    Vulnerability.risk_model_version != RISK_MODEL_VERSION,
                ),
            )
        )
    ).scalar_one()

    job = RiskExposureBackfillJob(
        tenant_id=tenant_id,
        status="pending",
        rows_total_estimate=rows_total_estimate,
    )
    db.add(job)
    await db.flush()
    return job


async def process_backfill_chunk(
    db: AsyncSession, tenant_id: uuid.UUID, *, now: datetime | None = None
) -> dict[str, object]:
    """Process ONE chunk for one tenant, all in ONE transaction (this
    function's single `db.commit()` at the end):

      1. Claim: an atomic `UPDATE ... WHERE status IN ('pending',
         'in_progress') AND (heartbeat NULL OR stale) RETURNING` -- the
         single-statement concurrency guard (T-34-04: race-safe even under
         overlapping ticks, no separate lock needed). Returns immediately
         (claimed=False) if another in-flight tick already owns this
         tenant's job, or if it's terminal ('completed'/'failed').
      2. Keyset-select the next chunk: Vulnerability outerjoin Asset,
         tenant-scoped + OPEN/IN_PROGRESS + version-mismatch guard +
         `id > cursor_vuln_id`, `ORDER BY id LIMIT chunk_size`. An EMPTY
         result marks the job completed (nothing left to migrate).
      3. Score each row via `score_finding` (verbatim reuse -- the bulk
         `VulnerabilityCorrelation` prefetch mirrors
         `compute_finding_risk_scores`'s own corr_by_key idiom, avoiding
         N+1 across the chunk).
      4. ONE parameterized bulk `UPDATE ... FROM (VALUES ...)` persisting
         risk_exposure_score/risk_exposure_breakdown/risk_model_version for
         the whole chunk. Its WHERE re-asserts `v.tenant_id = :tenant_id`
         (T-34-01 defense-in-depth -- a bulk UPDATE...FROM has no per-row
         tenant check of its own; correctness depends on step 2's SELECT
         already being tenant-scoped, this is belt-and-suspenders).
      5. Advance cursor_vuln_id / rows_migrated / heartbeat.
      6. `db.commit()` -- steps 3-5 all land or all roll back together.

    Returns `{'tenant_id', 'processed': int, 'done': bool, 'claimed': bool}`.
    """
    now = now or datetime.now(UTC)
    stale_before = now - _HEARTBEAT_STALE_AFTER

    claim_result = await db.execute(
        update(RiskExposureBackfillJob)
        .where(
            RiskExposureBackfillJob.tenant_id == tenant_id,
            RiskExposureBackfillJob.status.in_(_CLAIMABLE_STATUSES),
            or_(
                RiskExposureBackfillJob.last_heartbeat_at.is_(None),
                RiskExposureBackfillJob.last_heartbeat_at < stale_before,
            ),
        )
        .values(
            status="in_progress",
            last_heartbeat_at=now,
            started_at=func.coalesce(RiskExposureBackfillJob.started_at, now),
        )
        .returning(
            RiskExposureBackfillJob.id,
            RiskExposureBackfillJob.cursor_vuln_id,
            RiskExposureBackfillJob.chunk_size,
        )
    )
    claimed_row = claim_result.first()
    if claimed_row is None:
        # Already claimed by another in-flight tick this cycle, or the job
        # is terminal (completed/failed) -- nothing to do.
        return {"tenant_id": tenant_id, "processed": 0, "done": False, "claimed": False}

    job_id, cursor_vuln_id, chunk_size = claimed_row

    conditions = [
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        or_(Vulnerability.risk_model_version.is_(None), Vulnerability.risk_model_version != RISK_MODEL_VERSION),
    ]
    if cursor_vuln_id is not None:
        conditions.append(Vulnerability.id > cursor_vuln_id)

    chunk_query = (
        select(Vulnerability, Asset)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(*conditions)
        .order_by(Vulnerability.id)
        .limit(chunk_size)
    )
    rows = (await db.execute(chunk_query)).all()

    if not rows:
        await db.execute(
            update(RiskExposureBackfillJob)
            .where(RiskExposureBackfillJob.id == job_id)
            .values(status="completed", completed_at=now, last_heartbeat_at=None)
        )
        await db.commit()
        logger.info("risk_backfill_chunk", tenant_id=str(tenant_id), processed=0, done=True)
        return {"tenant_id": tenant_id, "processed": 0, "done": True, "claimed": True}

    corr_rows = (
        await db.execute(
            select(
                VulnerabilityCorrelation.cve_id,
                VulnerabilityCorrelation.asset_id,
                VulnerabilityCorrelation.sources_count,
            ).where(VulnerabilityCorrelation.tenant_id == tenant_id)
        )
    ).all()
    corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}

    computed: list[tuple[uuid.UUID, int, list[dict[str, object]], str]] = []
    for vuln, asset in rows:
        sources_count = corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)
        inputs = FindingScoreInputs(
            severity=vuln.severity,
            cvss_v3_score=vuln.cvss_v3_score,
            epss_score=vuln.epss_score,
            cisa_kev=vuln.cisa_kev,
            source=vuln.source,
            native_priority_score=vuln.native_priority_score,
            native_priority_rating=vuln.native_priority_rating,
            sources_count=sources_count,
            business_criticality=asset.business_criticality if asset is not None else "MEDIUM",
            data_sensitivity=asset.data_sensitivity if asset is not None else "INTERNAL",
            internet_facing=asset.internet_facing if asset is not None else False,
        )
        breakdown = score_finding(inputs)
        serialized_breakdown = [asdict(component) for component in breakdown.components]
        computed.append((vuln.id, breakdown.final_score, serialized_breakdown, breakdown.risk_model_version))

    # ONE bulk UPDATE...FROM (VALUES ...) for the whole chunk (not N
    # individual update() calls) -- exact bind syntax verified live against
    # this project's installed SQLAlchemy 2.0.50 + asyncpg: every VALUES
    # column needs an explicit CAST (asyncpg/Postgres can't infer a
    # consistent column type across parameterized VALUES rows otherwise --
    # confirmed via reproduction, not assumed).
    values_clauses: list[str] = []
    params: dict[str, object] = {"tenant_id": str(tenant_id)}
    for idx, (vuln_id, score, breakdown_json, version) in enumerate(computed):
        values_clauses.append(
            f"(CAST(:id_{idx} AS uuid), CAST(:score_{idx} AS int), "
            f"CAST(:breakdown_{idx} AS jsonb), CAST(:version_{idx} AS varchar))"
        )
        params[f"id_{idx}"] = str(vuln_id)
        params[f"score_{idx}"] = score
        params[f"breakdown_{idx}"] = json.dumps(breakdown_json)
        params[f"version_{idx}"] = version

    bulk_update_sql = text(
        "UPDATE vulnerabilities v SET "
        "risk_exposure_score = c.score, risk_exposure_breakdown = c.breakdown, risk_model_version = c.version "
        "FROM (VALUES " + ", ".join(values_clauses) + ") AS c(id, score, breakdown, version) "
        # T-34-01 defense-in-depth: re-assert tenant scoping even though
        # step 2's SELECT already guaranteed every id in `computed` belongs
        # to this tenant -- a bulk UPDATE...FROM has no per-row tenant
        # check of its own.
        "WHERE v.id = c.id AND v.tenant_id = CAST(:tenant_id AS uuid)"
    )
    await db.execute(bulk_update_sql, params)

    last_vuln_id = rows[-1][0].id
    await db.execute(
        update(RiskExposureBackfillJob)
        .where(RiskExposureBackfillJob.id == job_id)
        .values(
            cursor_vuln_id=last_vuln_id,
            rows_migrated=RiskExposureBackfillJob.rows_migrated + len(rows),
            # Clear the heartbeat on a SUCCESSFUL chunk commit (not leave it
            # "now") -- a fresh-but-successfully-finished chunk must be
            # immediately reclaimable by the very NEXT scheduler tick (~60s
            # later), not blocked for the full 5-minute staleness window.
            # The staleness window only has correctness value for a claim
            # that never reaches THIS commit at all (a crash/abandoned
            # transaction) -- and since claim + work + this clear are ONE
            # transaction (Pitfall 5 option (a)), a crash before commit
            # rolls the claim itself back too, so the next attempt already
            # sees whatever heartbeat value existed before this call (NULL,
            # given every prior successful chunk also cleared it) and can
            # reclaim immediately with no wait. The heartbeat field still
            # exists + the WHERE-guard still checks it (defense-in-depth
            # per the interfaces contract) -- it simply never blocks the
            # normal one-chunk-per-tick cadence.
            last_heartbeat_at=None,
        )
    )

    await db.commit()

    # The bulk UPDATE...FROM above is raw SQL, bypassing the ORM entirely --
    # any `Vulnerability` instance already loaded into THIS session's
    # identity map (e.g. the `rows` just scored, or a caller's own earlier
    # query) keeps its stale in-memory attribute values, since this
    # session's `async_session_factory` sets `expire_on_commit=False`
    # (app/db/session.py). Without this, a caller re-querying the SAME
    # session immediately after this commit would see cached
    # risk_exposure_score=None rather than the freshly-persisted score.
    db.expire_all()

    logger.info("risk_backfill_chunk", tenant_id=str(tenant_id), processed=len(rows), done=False)
    return {"tenant_id": tenant_id, "processed": len(rows), "done": False, "claimed": True}


async def dispatch_backfill_chunks(db: AsyncSession) -> dict[str, int]:
    """Select tenant_ids with a claimable job UP FRONT (plain UUIDs, never
    live ORM references) -- mirrors `poll_pending_batches`
    (`app/ai/batch.py:373-395`)'s re-select-by-ID-not-by-ORM-reference idiom,
    because `db.rollback()` (needed to recover from one tenant's failure)
    expires the WHOLE session's identity map; a later tenant's
    already-loaded ORM object would otherwise attempt an invalid lazy
    reload. Each tenant's chunk runs inside its OWN try/except (T-34
    per-tenant isolation) -- one tenant's failure sets ONLY that tenant's
    job to `status='failed'`, never poisoning any other tenant's progress.
    """
    tenant_ids = (
        (
            await db.execute(
                select(RiskExposureBackfillJob.tenant_id).where(RiskExposureBackfillJob.status.in_(_CLAIMABLE_STATUSES))
            )
        )
        .scalars()
        .all()
    )

    advanced = 0
    for tenant_id in tenant_ids:
        try:
            result = await process_backfill_chunk(db, tenant_id)
            processed = cast("int", result.get("processed", 0))
            if processed > 0 or result.get("done"):
                advanced += 1
        except Exception as e:
            await db.rollback()
            logger.error("risk_backfill_chunk_error", tenant_id=str(tenant_id), error=str(e))
            job = (
                await db.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_id))
            ).scalar_one_or_none()
            if job is not None:
                job.status = "failed"
                job.error_message = str(e)[:2000]
                await db.commit()

    return {"tenants_advanced": advanced}
