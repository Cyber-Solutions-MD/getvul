"""Phase 34 Plan 03 (RISK-09) — pre/post threshold diff report + per-tenant
re-tuning acknowledgment that GATES the (deferred, human) cutover flip.

This is a diff+ack ARTIFACT only — nothing in this plan retargets a live
threshold. `rule_engine.py` and `saved_filters.py` keep reading
`Asset.risk_score` unconditionally; the flag flip
(`Tenant.cutover_risk_exposure_scoring = True`) is never actually invoked
against live data in this environment (34-CONTEXT.md, locked). This suite
proves the machinery is falsifiable: the diff computation, the
backfill-completion gate (Pitfall 3 — never a misleading undercount), the
ack stamp+hash, stale-ack invalidation after a threshold changes, the
both-gates-enforced flag flip, RBAC (admin-only), and the audit rows.

Covers:
  - GET /api/v1/risk-cutover/threshold-diff
  - POST /api/v1/risk-cutover/threshold-ack
  - POST /api/v1/risk-cutover/enable

Fixture idioms reused:
  - admin-RBAC 403 loop + audit-row assertion — test_asset_exposure.py:354-425
  - min_risk_score fixture seeding — test_rule_engine.py:98-103
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.tenants.models import Tenant
from app.ticketing.models import TicketRule
from app.vulnerabilities.models import RiskExposureBackfillJob
from app.vulnerabilities.saved_filters import SavedFilter

# `_reset_engine_pool` (autouse) lives in conftest.py.

DIFF_URL = "/api/v1/risk-cutover/threshold-diff"
ACK_URL = "/api/v1/risk-cutover/threshold-ack"
ENABLE_URL = "/api/v1/risk-cutover/enable"

_DEFAULT_RULE_ACTION = {"provider": "ASANA", "project_key": "", "auto_assign": False, "due_days": None}


async def _seed_backfill_job(db_session, tenant_id, status: str = "completed") -> RiskExposureBackfillJob:
    job = RiskExposureBackfillJob(tenant_id=tenant_id, status=status)
    db_session.add(job)
    await db_session.flush()
    return job


async def _seed_asset(db_session, tenant_id, hostname: str, *, risk_score: int, risk_exposure_score: int) -> Asset:
    a = Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        risk_score=risk_score,
        risk_exposure_score=risk_exposure_score,
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _seed_rule(db_session, tenant_id, *, min_risk_score: int) -> TicketRule:
    rule = TicketRule(
        tenant_id=tenant_id,
        name=f"rule-{uuid.uuid4().hex[:6]}",
        conditions={"min_risk_score": min_risk_score},
        action=_DEFAULT_RULE_ACTION,
    )
    db_session.add(rule)
    await db_session.flush()
    return rule


async def _seed_saved_filter(db_session, tenant_id, *, min_risk_score: int) -> SavedFilter:
    sf = SavedFilter(
        tenant_id=tenant_id,
        name=f"filter-{uuid.uuid4().hex[:6]}",
        filter_type="vulnerability",
        filters={"min_risk_score": min_risk_score},
    )
    db_session.add(sf)
    await db_session.flush()
    return sf


# ── Diff computation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_threshold_diff_computation(client_factory, db_session, tenant_a, admin_user):
    """A completed backfill + one TicketRule (min_risk_score=80) + one
    SavedFilter (min_risk_score=50), plus known Asset.risk_score /
    Asset.risk_exposure_score values, produce hand-computable old/new match
    counts and a stable diff_hash."""
    await _seed_backfill_job(db_session, tenant_a, status="completed")
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await _seed_saved_filter(db_session, tenant_a, min_risk_score=50)

    # OLD (risk_score): 1 asset >= 80, 2 assets >= 50.
    # NEW (risk_exposure_score): 2 assets >= 80, 3 assets >= 50.
    await _seed_asset(db_session, tenant_a, "a1", risk_score=90, risk_exposure_score=95)
    await _seed_asset(db_session, tenant_a, "a2", risk_score=60, risk_exposure_score=85)
    await _seed_asset(db_session, tenant_a, "a3", risk_score=55, risk_exposure_score=55)
    await _seed_asset(db_session, tenant_a, "a4", risk_score=10, risk_exposure_score=10)
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.get(DIFF_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert "diff_hash" in body and body["diff_hash"]
    items = {(i["source_type"], i["threshold"]): i for i in body["items"]}

    rule_item = items[("rule", 80)]
    assert rule_item["old_match_count"] == 1
    assert rule_item["new_match_count"] == 2
    assert rule_item["delta"] == 1

    filter_item = items[("filter", 50)]
    assert filter_item["old_match_count"] == 2
    assert filter_item["new_match_count"] == 3
    assert filter_item["delta"] == 1

    # Stable across repeated calls.
    r2 = await c.get(DIFF_URL)
    assert r2.json()["diff_hash"] == body["diff_hash"]


@pytest.mark.asyncio
async def test_diff_refused_when_backfill_incomplete(client_factory, db_session, tenant_a, admin_user):
    """Pitfall 3 — an in-progress (or missing) backfill job must never
    produce a misleadingly-precise-but-wrong diff; it must refuse."""
    await _seed_backfill_job(db_session, tenant_a, status="in_progress")
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.get(DIFF_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is False
    assert body["reason"] == "backfill_incomplete"
    assert "items" not in body or not body["items"]


@pytest.mark.asyncio
async def test_diff_refused_when_no_backfill_job(client_factory, db_session, tenant_a, admin_user):
    """No RiskExposureBackfillJob row at all is also 'not ready' (Pitfall 3)."""
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.get(DIFF_URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is False
    assert body["reason"] == "backfill_incomplete"


# ── Ack stamp + hash ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_threshold_ack_stamps_and_hashes(client_factory, db_session, tenant_a, admin_user):
    await _seed_backfill_job(db_session, tenant_a, status="completed")
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await _seed_asset(db_session, tenant_a, "a1", risk_score=90, risk_exposure_score=95)
    await db_session.commit()

    c = client_factory(admin_user)
    diff_resp = await c.get(DIFF_URL)
    current_hash = diff_resp.json()["diff_hash"]

    r = await c.post(ACK_URL)
    assert r.status_code == 200, r.text

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    await db_session.refresh(tenant)
    assert tenant.risk_cutover_threshold_ack_at is not None
    assert tenant.risk_cutover_threshold_ack_diff_hash == current_hash

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "risk_cutover.threshold_ack",
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
async def test_ack_refused_when_backfill_incomplete(client_factory, db_session, tenant_a, admin_user):
    await _seed_backfill_job(db_session, tenant_a, status="in_progress")
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await db_session.commit()

    c = client_factory(admin_user)
    r = await c.post(ACK_URL)
    assert r.status_code == 409, r.text


# ── Stale ack + both-gates flip ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_ack_after_threshold_change(client_factory, db_session, tenant_a, admin_user):
    await _seed_backfill_job(db_session, tenant_a, status="completed")
    rule = await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await _seed_asset(db_session, tenant_a, "a1", risk_score=90, risk_exposure_score=95)
    await db_session.commit()

    c = client_factory(admin_user)
    ack_resp = await c.post(ACK_URL)
    assert ack_resp.status_code == 200, ack_resp.text

    # Change the rule's threshold after acking — the diff_hash now differs.
    from sqlalchemy.orm.attributes import flag_modified

    rule.conditions = {"min_risk_score": 81}
    flag_modified(rule, "conditions")
    await db_session.commit()

    r = await c.post(ENABLE_URL)
    assert r.status_code == 409, r.text

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    await db_session.refresh(tenant)
    assert tenant.cutover_risk_exposure_scoring is False


@pytest.mark.asyncio
async def test_flag_flip_requires_both_gates(client_factory, db_session, tenant_a, admin_user):
    await _seed_rule(db_session, tenant_a, min_risk_score=80)
    await _seed_asset(db_session, tenant_a, "a1", risk_score=90, risk_exposure_score=95)
    await db_session.commit()

    c = client_factory(admin_user)

    # (a) backfill incomplete + no ack at all -> 409.
    r = await c.post(ENABLE_URL)
    assert r.status_code == 409, r.text
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    assert tenant.cutover_risk_exposure_scoring is False

    # (b) backfill complete + no ack -> 409.
    job = (
        await db_session.execute(select(RiskExposureBackfillJob).where(RiskExposureBackfillJob.tenant_id == tenant_a))
    ).scalar_one_or_none()
    if job is None:
        job = await _seed_backfill_job(db_session, tenant_a, status="completed")
    else:
        job.status = "completed"
    await db_session.commit()

    r = await c.post(ENABLE_URL)
    assert r.status_code == 409, r.text
    await db_session.refresh(tenant)
    assert tenant.cutover_risk_exposure_scoring is False

    # (c) backfill complete + fresh matching ack -> 200, flag flips, audit row lands.
    ack_resp = await c.post(ACK_URL)
    assert ack_resp.status_code == 200, ack_resp.text

    r = await c.post(ENABLE_URL)
    assert r.status_code == 200, r.text

    await db_session.refresh(tenant)
    assert tenant.cutover_risk_exposure_scoring is True

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "risk_cutover.flag_enable",
                    AuditLog.resource_id == str(tenant_a),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected exactly one audit row, got {len(rows)}"


# ── RBAC ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_gates(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """Non-admin roles (analyst, viewer) are rejected with 403 on all three endpoints."""
    await _seed_backfill_job(db_session, tenant_a, status="completed")
    await db_session.commit()

    for user in (analyst_user, viewer_user):
        c = client_factory(user)
        r_diff = await c.get(DIFF_URL)
        assert r_diff.status_code == 403, r_diff.text
        r_ack = await c.post(ACK_URL)
        assert r_ack.status_code == 403, r_ack.text
        r_enable = await c.post(ENABLE_URL)
        assert r_enable.status_code == 403, r_enable.text
