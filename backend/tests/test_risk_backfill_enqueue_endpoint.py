"""Phase 34 Plan 05 (RISK-07 gap closure) — admin-triggered backfill enqueue endpoint.

34-VERIFICATION.md's GAP 2 / Human Verification #2: `enqueue_backfill_job`
(app/vulnerabilities/risk_backfill_service.py:73) is fully correct and
fixture-proven, but was never called from any production code path, router,
or script — only from tests. The scheduler-wired chunk dispatcher
(`dispatch_backfill_chunks`) is fully functional once a job row exists, but
nothing shipped in the codebase creates that row for a real tenant, so the
backfill machinery was inert on a live stack.

This suite proves the new admin-only endpoint (mirrors the existing
risk-cutover router's `require_role("admin")` + audit()-then-commit shape,
and `POST /assets/recompute-risk-scores`'s admin-gated operational-trigger
precedent):
  - RBAC: 403 for analyst/viewer.
  - Enqueues a real `RiskExposureBackfillJob` row for the caller's tenant.
  - Idempotent: a second call while a job is already active (or completed)
    returns the EXISTING job's status rather than creating a duplicate row
    or erroring, and does not add a second audit row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.audit import AuditLog
from app.vulnerabilities.models import RiskExposureBackfillJob

ENQUEUE_URL = "/api/v1/risk-cutover/backfill/enqueue"


@pytest.mark.asyncio
async def test_admin_gate_rejects_non_admin(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    await db_session.commit()  # WR-13: make tenant_a/analyst_user/viewer_user visible cross-connection

    for user in (analyst_user, viewer_user):
        c = client_factory(user)
        r = await c.post(ENQUEUE_URL)
        assert r.status_code == 403, r.text

    jobs = (
        (await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a)))
        .scalars()
        .all()
    )
    assert jobs == [], "a rejected (403) request must never create a job row"


@pytest.mark.asyncio
async def test_enqueue_creates_job_and_audit_row(client_factory, db_session, tenant_a, admin_user):
    # WR-13: the client hits the endpoint via a SEPARATE session
    # (app.db.session.async_session_factory) from this test's own db_session
    # — the tenant_a/admin_user fixtures only flush (uncommitted), so an
    # explicit commit is required before the fixture rows are visible
    # cross-connection (mirrors test_risk_cutover_ack.py's seeding pattern).
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.post(ENQUEUE_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_active"] is False
    assert body["status"] == "pending"
    assert "job_id" in body and body["job_id"]

    job = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one()
    assert str(job.id) == body["job_id"]
    assert job.status == "pending"

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "risk_cutover.backfill_enqueue",
                    AuditLog.resource_id == str(tenant_a),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected exactly one audit row, got {len(rows)}"
    assert rows[0].user_email == admin_user.email
    assert rows[0].resource_type == "tenant"


@pytest.mark.asyncio
async def test_enqueue_idempotent_when_already_active(client_factory, db_session, tenant_a, admin_user):
    await db_session.commit()  # WR-13: make tenant_a/admin_user visible cross-connection

    c = client_factory(admin_user)
    r1 = await c.post(ENQUEUE_URL)
    assert r1.status_code == 200, r1.text
    first_job_id = r1.json()["job_id"]

    r2 = await c.post(ENQUEUE_URL)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["job_id"] == first_job_id, "a second call must return the SAME job, never a duplicate"
    assert body2["already_active"] is True

    jobs = (
        (await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1, "no duplicate RiskExposureBackfillJob row must be created"

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "risk_cutover.backfill_enqueue",
                    AuditLog.resource_id == str(tenant_a),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "a no-op repeat call must not add a second audit row"


@pytest.mark.asyncio
async def test_enqueue_idempotent_when_completed(client_factory, db_session, tenant_a, admin_user):
    """A tenant whose backfill already finished must not be re-enqueued into
    a fresh 'pending' job -- the existing completed row is returned as-is."""
    job = RiskExposureBackfillJob(tenant_id=tenant_a, status="completed", rows_migrated=42)
    db_session.add(job)
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.post(ENQUEUE_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_active"] is True
    assert body["status"] == "completed"
    assert body["job_id"] == str(job.id)

    jobs = (
        (await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1
