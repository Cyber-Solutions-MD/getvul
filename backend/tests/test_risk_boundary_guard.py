"""Phase 34 Plan 04 (RISK-10) — version-boundary guard fixture suite.

Bug being fixed: `_check_risk_score_changes` (app/notifications/alerts.py:189-255)
reads `snapshot.metrics.get("asset_risk_scores", {})` — a key `capture_daily_snapshot`
(app/vulnerabilities/trends.py:218-329) has NEVER written. Every DailySnapshot row in
every tenant's history has this key missing, so the check has returned 0 alerts for
every tenant, every day, since it was written — it is dead code today.

This suite proves three things, in this order (Pitfall 2 — boundary-guarding a check
that has never fired proves nothing):
  1. capture_daily_snapshot now dual-writes asset_risk_scores (OLD, the dead-code fix),
     asset_risk_exposure_scores (NEW), avg_risk_exposure_score, and
     risk_model_version_snapshot into every DailySnapshot — UNCONDITIONALLY, regardless
     of the tenant's cutover_risk_exposure_scoring flag.
  2. _check_risk_score_changes ACTUALLY FIRES now, for a genuine same-version spike —
     both on the OLD-model branch (flag OFF) and the NEW-model branch (flag ON). These
     are non-zero controls: a green "0 alerts" boundary test is meaningless without them.
  3. A fixture spanning the version-boundary (yesterday has both old+new dicts at real
     values; the flag flips OFF->ON; today's live scores reflect a small genuine
     same-version drift) produces ZERO storm alerts, because the diff is same-version-only
     (new-vs-new), never cross-version (new-vs-old). The trend chart's new series is
     likewise continuous (no cliff) across the same boundary.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.notifications import alerts as alerts_module
from app.tenants.models import Tenant
from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION
from app.vulnerabilities.trends import DailySnapshot, capture_daily_snapshot, get_risk_score_trend


def _seed_asset(tenant_id: uuid.UUID, *, risk_score: int | None, risk_exposure_score: int | None) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:8]}",
        risk_score=risk_score,
        risk_exposure_score=risk_exposure_score,
    )


async def _get_tenant(db_session, tenant_id: uuid.UUID) -> Tenant:
    return (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()


async def _set_cutover_flag(db_session, tenant_id: uuid.UUID, enabled: bool) -> Tenant:
    tenant = await _get_tenant(db_session, tenant_id)
    tenant.cutover_risk_exposure_scoring = enabled
    await db_session.commit()
    return await _get_tenant(db_session, tenant_id)


@pytest.mark.asyncio
async def test_snapshot_populates_asset_risk_dicts(db_session, tenant_a):
    """capture_daily_snapshot dual-writes both per-asset dicts + the scalar
    avg_risk_exposure_score + risk_model_version_snapshot, unconditionally."""
    a1 = _seed_asset(tenant_a, risk_score=30, risk_exposure_score=25)
    a2 = _seed_asset(tenant_a, risk_score=50, risk_exposure_score=45)
    db_session.add_all([a1, a2])
    await db_session.commit()

    result = await capture_daily_snapshot(db_session, tenant_a)
    await db_session.commit()
    assert result["captured"] is True

    snapshot = (
        await db_session.execute(
            select(DailySnapshot).where(
                DailySnapshot.tenant_id == tenant_a,
                DailySnapshot.snapshot_date == datetime.now(UTC).date(),
            )
        )
    ).scalar_one()

    metrics = snapshot.metrics
    assert "asset_risk_scores" in metrics, "dead-code fix: asset_risk_scores must now be populated"
    assert "asset_risk_exposure_scores" in metrics
    assert metrics["asset_risk_scores"], "asset_risk_scores must be non-empty"
    assert metrics["asset_risk_exposure_scores"], "asset_risk_exposure_scores must be non-empty"
    assert metrics["asset_risk_scores"].get(str(a1.id)) == 30
    assert metrics["asset_risk_scores"].get(str(a2.id)) == 50
    assert metrics["asset_risk_exposure_scores"].get(str(a1.id)) == 25
    assert metrics["asset_risk_exposure_scores"].get(str(a2.id)) == 45
    assert isinstance(metrics["avg_risk_exposure_score"], (int, float))
    assert metrics["risk_model_version_snapshot"] == RISK_MODEL_VERSION


@pytest.mark.asyncio
async def test_genuine_spike_still_alerts(db_session, tenant_a):
    """Pitfall-2 control (OFF branch): a real +30 same-version delta on the
    OLD score must fire >=1 alert now that asset_risk_scores is populated —
    proving the check is no longer dead code."""
    asset = _seed_asset(tenant_a, risk_score=40, risk_exposure_score=None)
    db_session.add(asset)
    await db_session.flush()

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=yesterday,
            metrics={"asset_risk_scores": {str(asset.id): 10}},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    tenant = await _set_cutover_flag(db_session, tenant_a, False)
    alerts_created = await alerts_module._check_risk_score_changes(db_session, tenant)
    await db_session.commit()

    assert alerts_created >= 1, "genuine same-version spike (OFF/old) must alert — check must actually fire"


@pytest.mark.asyncio
async def test_genuine_spike_new_version_alerts(db_session, tenant_a):
    """Pitfall-2 control (ON branch): a real +30 same-version delta on the
    NEW score must fire >=1 alert when the flag is ON."""
    asset = _seed_asset(tenant_a, risk_score=None, risk_exposure_score=40)
    db_session.add(asset)
    await db_session.flush()

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=yesterday,
            metrics={"asset_risk_exposure_scores": {str(asset.id): 10}},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    tenant = await _set_cutover_flag(db_session, tenant_a, True)
    alerts_created = await alerts_module._check_risk_score_changes(db_session, tenant)
    await db_session.commit()

    assert alerts_created >= 1, "genuine same-version spike (ON/new) must alert"


@pytest.mark.asyncio
async def test_cutover_boundary_no_storm_no_cliff(db_session, tenant_a):
    """The core RISK-10 fixture: yesterday's snapshot carries BOTH dicts at
    genuine pre-cutover values; the flag flips OFF->ON between yesterday and
    today; today's live scores reflect only a small genuine NEW-model drift
    (+2), not a cross-version jump (new 24 vs old 70 would be +/-46 and would
    falsely storm). Same-version-only diffing must yield ZERO alerts."""
    asset = _seed_asset(tenant_a, risk_score=72, risk_exposure_score=24)
    db_session.add(asset)
    await db_session.flush()

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=yesterday,
            metrics={
                "asset_risk_scores": {str(asset.id): 70},
                "asset_risk_exposure_scores": {str(asset.id): 22},
            },
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    # Boundary: flag flips OFF -> ON "today".
    tenant = await _set_cutover_flag(db_session, tenant_a, True)
    alerts_created = await alerts_module._check_risk_score_changes(db_session, tenant)
    await db_session.commit()

    assert alerts_created == 0, (
        "cross-version diff (new 24 vs old 70) would have falsely stormed; "
        "same-version diff (new 24 vs new 22, delta=2) must NOT alert"
    )


@pytest.mark.asyncio
async def test_trend_no_cliff(db_session, tenant_a):
    """get_risk_score_trend's new (avg_risk_exposure) series stays continuous
    across a boundary day where avg_risk_score (old series) jumps sharply."""
    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day1,
            metrics={"avg_risk_score": 20, "avg_risk_exposure_score": 21},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day2,
            # Old-model scale jumps sharply (simulating a naive cutover cliff);
            # new-model value drifts only slightly — proving continuity.
            metrics={"avg_risk_score": 85, "avg_risk_exposure_score": 23},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    rows = await get_risk_score_trend(db_session, tenant_a)
    by_date = {r["date"]: r for r in rows}

    r1 = by_date[day1.isoformat()]
    r2 = by_date[day2.isoformat()]

    assert "avg_risk_exposure" in r1
    assert "avg_risk_exposure" in r2
    # existing wire-contract field stays byte-identical (still reads avg_risk_score)
    assert r1["avg_risk"] == 20
    assert r2["avg_risk"] == 85
    # the OLD series has a cliff (65-point jump); the NEW series must not.
    assert abs(r2["avg_risk"] - r1["avg_risk"]) >= 60
    assert abs(r2["avg_risk_exposure"] - r1["avg_risk_exposure"]) <= 5
