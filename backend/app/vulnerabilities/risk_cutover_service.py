"""Phase 34 Plan 03 (RISK-09) — pre/post threshold diff report + per-tenant
re-tuning acknowledgment that GATES the (deferred, human) cutover flip.

This module is a read-only reporting + ack-gate artifact ONLY. It never
retargets `TicketRule.conditions["min_risk_score"]` or
`SavedFilter.filters["min_risk_score"]` — `app/ticketing/rule_engine.py` and
`app/vulnerabilities/saved_filters.py` keep comparing against the OLD
`Asset.risk_score` unconditionally (34-CONTEXT.md RESOLVED A5, Pitfall 4).
`enable_cutover` is the only path that can set
`Tenant.cutover_risk_exposure_scoring = True`, and it is structurally unable
to do so unless BOTH gates pass:

    (a) the tenant's `RiskExposureBackfillJob.status == "completed"`
    (b) a FRESH ack exists — `risk_cutover_threshold_ack_at` is set AND its
        stored `risk_cutover_threshold_ack_diff_hash` matches the CURRENT
        diff's hash (changing a threshold after acking invalidates the ack).

`enable_cutover` is never actually invoked against live tenant data in this
environment (34-CONTEXT.md, locked) — this plan builds + fixture-tests the
machinery only.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.audit import audit
from app.auth.schemas import CurrentUser
from app.tenants.models import Tenant
from app.ticketing.models import TicketRule
from app.vulnerabilities.models import RiskExposureBackfillJob
from app.vulnerabilities.saved_filters import SavedFilter


async def _backfill_status(db: AsyncSession, tenant_id: uuid.UUID) -> str | None:
    """The tenant's single `RiskExposureBackfillJob` row status, or None if
    the job has never been enqueued (also treated as "not ready" — Pitfall 3:
    never a misleading undercounted diff for a tenant that hasn't backfilled
    at all)."""
    job = (
        await db.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_id))
    ).scalar_one_or_none()
    return job.status if job is not None else None


def _diff_hash(items: list[dict[str, Any]]) -> str:
    """Sha256 hex digest over the sorted-JSON items — mirrors
    `app/ai/cache.py::record_hash`'s `json.dumps(..., sort_keys=True)`
    hashing idiom. `items` is already list-sorted by the caller
    (`compute_threshold_diff`) so the hash is stable across repeated calls
    regardless of the DB's row-return order."""
    payload = json.dumps(items, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _threshold_item(
    db: AsyncSession, tenant_id: uuid.UUID, source_type: str, source_id: str, threshold: int
) -> dict[str, Any]:
    """Old (`Asset.risk_score`) vs new (`Asset.risk_exposure_score`) match
    count for one stored threshold — read-only, tenant-scoped."""
    old_count = (
        await db.execute(
            select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id, Asset.risk_score >= threshold)
        )
    ).scalar_one()
    new_count = (
        await db.execute(
            select(func.count())
            .select_from(Asset)
            .where(Asset.tenant_id == tenant_id, Asset.risk_exposure_score >= threshold)
        )
    ).scalar_one()
    delta = new_count - old_count
    delta_pct = round((delta / old_count * 100), 2) if old_count else (100.0 if new_count else 0.0)
    return {
        "source_type": source_type,
        "source_id": source_id,
        "threshold": threshold,
        "old_match_count": old_count,
        "new_match_count": new_count,
        "delta": delta,
        "delta_pct": delta_pct,
    }


async def compute_threshold_diff(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Pre/post threshold diff report for every `TicketRule.conditions`
    and `SavedFilter.filters` `min_risk_score` this tenant has stored.

    GATE (Pitfall 3): if the tenant's `RiskExposureBackfillJob.status !=
    "completed"` (including no job at all), returns
    `{"ready": False, "reason": "backfill_incomplete"}` — never a misleading
    undercounted diff computed against a partially-migrated
    `Asset.risk_exposure_score` distribution.

    Read-only: does not modify any `TicketRule`/`SavedFilter` row.
    """
    status = await _backfill_status(db, tenant_id)
    if status != "completed":
        return {"ready": False, "reason": "backfill_incomplete"}

    items: list[dict[str, Any]] = []

    rules = (await db.execute(select(TicketRule).where(TicketRule.tenant_id == tenant_id))).scalars().all()
    for rule in rules:
        # Read-site mirrors rule_engine.py:65-67 exactly (>0 check, not truthy).
        threshold = (rule.conditions or {}).get("min_risk_score")
        if threshold is None or threshold <= 0:
            continue
        items.append(await _threshold_item(db, tenant_id, "rule", str(rule.id), threshold))

    saved_filters = (await db.execute(select(SavedFilter).where(SavedFilter.tenant_id == tenant_id))).scalars().all()
    for sf in saved_filters:
        # Read-site mirrors saved_filters.py:104-105 exactly (truthy check).
        threshold = (sf.filters or {}).get("min_risk_score")
        if not threshold:
            continue
        items.append(await _threshold_item(db, tenant_id, "filter", str(sf.id), threshold))

    # Deterministic ordering so diff_hash is stable independent of DB row order.
    items.sort(key=lambda i: (str(i["source_type"]), str(i["source_id"])))

    return {"ready": True, "items": items, "diff_hash": _diff_hash(items)}


async def record_threshold_ack(db: AsyncSession, user: CurrentUser) -> dict[str, Any]:
    """Recompute the current diff (must be ready) and stamp
    `Tenant.risk_cutover_threshold_ack_at` = now,
    `Tenant.risk_cutover_threshold_ack_diff_hash` = the current diff_hash.

    Raises 409 if the backfill isn't complete yet (nothing to ack).
    `audit()` is called BEFORE `db.commit()` (fail-closed, AUDIT-01).
    """
    diff = await compute_threshold_diff(db, user.tenant_id)
    if not diff["ready"]:
        raise HTTPException(status_code=409, detail="backfill_incomplete")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    now = datetime.now(UTC)
    tenant.risk_cutover_threshold_ack_at = now
    tenant.risk_cutover_threshold_ack_diff_hash = diff["diff_hash"]

    await audit(
        db,
        user,
        "risk_cutover.threshold_ack",
        "tenant",
        str(user.tenant_id),
        {"diff_hash": diff["diff_hash"]},
    )
    await db.commit()

    return {"acked_at": now.isoformat(), "diff_hash": diff["diff_hash"]}


async def enqueue_backfill(db: AsyncSession, user: CurrentUser) -> dict[str, Any]:
    """Admin-triggered production entry point for RISK-07's historical
    backfill machinery (34-VERIFICATION.md GAP 2 / Human Verification #2):
    `risk_backfill_service.enqueue_backfill_job` was fully correct and
    fixture-proven but had NO production call site — only tests invoked it,
    so a real tenant's backfill could never actually start on a live stack.

    Idempotent: `enqueue_backfill_job`'s `UniqueConstraint(tenant_id)` means
    calling this again while a job is already pending/in_progress/completed
    returns the EXISTING row unchanged (never a duplicate, never an error).
    Only a genuinely NEW enqueue (no job row existed before this call) is
    audited — a repeated call against an already-active/completed job is a
    harmless no-op, not a fresh mutation worth its own audit row.
    """
    from app.vulnerabilities.risk_backfill_service import enqueue_backfill_job

    existing_status = await _backfill_status(db, user.tenant_id)
    is_new = existing_status is None

    job = await enqueue_backfill_job(db, user.tenant_id)

    if is_new:
        await audit(
            db,
            user,
            "risk_cutover.backfill_enqueue",
            "tenant",
            str(user.tenant_id),
            {"job_id": str(job.id), "rows_total_estimate": job.rows_total_estimate},
        )
    await db.commit()

    return {
        "job_id": str(job.id),
        "status": job.status,
        "rows_total_estimate": job.rows_total_estimate,
        "rows_migrated": job.rows_migrated,
        "already_active": not is_new,
    }


async def enable_cutover(db: AsyncSession, user: CurrentUser) -> dict[str, Any]:
    """The ONLY path that can set `Tenant.cutover_risk_exposure_scoring =
    True`. Requires BOTH gates:

        (a) `RiskExposureBackfillJob.status == "completed"` — else 409
            `detail="backfill_incomplete"`.
        (b) `risk_cutover_threshold_ack_at` is set AND
            `risk_cutover_threshold_ack_diff_hash` matches the CURRENT
            diff_hash — else 409 `detail="threshold_ack_missing"` (no ack
            recorded yet) or `detail="threshold_ack_stale"` (a threshold
            changed after the ack, invalidating it — no silent
            reinterpretation, T-34-10).

    NOTE: never actually called against live tenant data in this
    environment (34-CONTEXT.md, locked) — fixture-tested only.
    """
    status = await _backfill_status(db, user.tenant_id)
    if status != "completed":
        raise HTTPException(status_code=409, detail="backfill_incomplete")

    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.risk_cutover_threshold_ack_at is None:
        raise HTTPException(status_code=409, detail="threshold_ack_missing")

    diff = await compute_threshold_diff(db, user.tenant_id)
    if not diff["ready"] or tenant.risk_cutover_threshold_ack_diff_hash != diff["diff_hash"]:
        raise HTTPException(status_code=409, detail="threshold_ack_stale")

    tenant.cutover_risk_exposure_scoring = True

    await audit(
        db,
        user,
        "risk_cutover.flag_enable",
        "tenant",
        str(user.tenant_id),
        {"diff_hash": diff["diff_hash"]},
    )
    await db.commit()

    return {"cutover_risk_exposure_scoring": True}
