"""Phase 42 Plan 01 (TREND-01/03 tracer slice) -- analytics module tests.

Proves, in this order (mirrors test_risk_boundary_guard.py's own ordering
discipline -- prove the flag-decoupling and range-bounding first, then the
never-before-exercised version-boundary axis, then tenant isolation):

  1. get_scoped_trend_series ALWAYS reads avg_risk_exposure_score,
     regardless of Tenant.cutover_risk_exposure_scoring (D-12) -- the
     opposite of get_risk_score_trend's existing flag-branch.
  2. get_scoped_trend_series is bounded by a real date range, not the
     legacy 90-row LIMIT (D-13).
  3. detect_version_boundaries returns [] for a single-version series
     (today's real-world case for every tenant -- RISK_MODEL_VERSION has
     never been bumped past "v1").
  4. detect_version_boundaries DOES detect a boundary on a SYNTHETIC
     multi-version fixture (the never-before-varied risk_model_version_
     snapshot axis -- 42-RESEARCH.md Pitfall 1 -- there is no real data to
     test this against).
  5. get_analytics_overview is tenant-scoped -- tenant_b's data never
     leaks into tenant_a's overview (T-42-01).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.analytics.service import (
    detect_version_boundaries,
    get_analytics_overview,
    get_scoped_trend_series,
)
from app.tenants.models import Tenant
from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION
from app.vulnerabilities.trends import DailySnapshot


async def _set_cutover_flag(db_session, tenant_id, enabled: bool) -> None:
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    tenant.cutover_risk_exposure_scoring = enabled
    await db_session.commit()


@pytest.mark.asyncio
async def test_tenant_trend_ignores_cutover_flag(db_session, tenant_a):
    """D-12: get_scoped_trend_series always reads avg_risk_exposure_score --
    identical result whether the tenant's cutover flag is True or False."""
    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day1,
            metrics={"avg_risk_exposure_score": 21.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day2,
            # Old-model key present too -- proves the new series never reads it.
            metrics={
                "avg_risk_score": 999.0,
                "avg_risk_exposure_score": 23.0,
                "risk_model_version_snapshot": RISK_MODEL_VERSION,
            },
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await _set_cutover_flag(db_session, tenant_a, False)
    off_rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)

    await _set_cutover_flag(db_session, tenant_a, True)
    on_rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)

    assert off_rows == on_rows, "series must be identical regardless of the cutover flag"
    # Ascending by date.
    assert [r["date"] for r in off_rows] == [day1.isoformat(), day2.isoformat()]
    assert off_rows[0]["avg_risk_exposure_score"] == 21.0
    assert off_rows[1]["avg_risk_exposure_score"] == 23.0
    # Never the old-model key/value (999.0 must not leak through).
    assert all(r["avg_risk_exposure_score"] != 999.0 for r in off_rows)


@pytest.mark.asyncio
async def test_tenant_trend_respects_date_range(db_session, tenant_a):
    """D-13: only in-window rows are returned -- no reliance on a 90-row
    LIMIT. A snapshot far outside the requested window must not appear even
    though it would easily fit inside a 90-row cap."""
    in_window = (datetime.now(UTC) - timedelta(days=5)).date()
    out_of_window = (datetime.now(UTC) - timedelta(days=200)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=in_window,
            metrics={"avg_risk_exposure_score": 10.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=out_of_window,
            metrics={"avg_risk_exposure_score": 999.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    start = (datetime.now(UTC) - timedelta(days=30)).date()
    end = datetime.now(UTC).date()
    rows = await get_scoped_trend_series(db_session, tenant_a, start=start, end=end)

    dates = [r["date"] for r in rows]
    assert in_window.isoformat() in dates
    assert out_of_window.isoformat() not in dates
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_no_boundary_when_single_version(db_session, tenant_a):
    """A single-version series (every real tenant today) yields zero
    boundaries and stays one continuous segment."""
    base = datetime.now(UTC) - timedelta(days=3)
    for i in range(3):
        db_session.add(
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=(base + timedelta(days=i)).date(),
                metrics={"avg_risk_exposure_score": float(10 + i), "risk_model_version_snapshot": "v1"},
                created_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    start = (base).date()
    end = datetime.now(UTC).date()
    rows = await get_scoped_trend_series(db_session, tenant_a, start=start, end=end)
    boundaries = detect_version_boundaries(rows)

    assert boundaries == []


@pytest.mark.asyncio
async def test_version_boundary_detected_and_segmented(db_session, tenant_a):
    """SYNTHETIC fixture (42-RESEARCH.md Pitfall 1 -- no real tenant has
    ever varied risk_model_version_snapshot): seeding "v1" then "v2" must
    emit exactly one boundary dict {date, old_version, new_version}."""
    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day1,
            metrics={"avg_risk_exposure_score": 20.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day2,
            metrics={"avg_risk_exposure_score": 22.0, "risk_model_version_snapshot": "v2"},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)
    boundaries = detect_version_boundaries(rows)

    assert boundaries == [{"date": day2.isoformat(), "old_version": "v1", "new_version": "v2"}]


@pytest.mark.asyncio
async def test_overview_is_tenant_scoped(db_session, tenant_a, tenant_b):
    """T-42-01: get_analytics_overview(db, tenant_a) never returns
    tenant_b's data, even when both tenants have a snapshot on the exact
    same date."""
    today = datetime.now(UTC).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=today,
            metrics={"avg_risk_exposure_score": 24.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_b,
            snapshot_date=today,
            metrics={"avg_risk_exposure_score": 99.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    overview = await get_analytics_overview(db_session, tenant_a, days=30)

    assert overview["trend"], "tenant_a must see its own snapshot"
    assert all(r["avg_risk_exposure_score"] != 99.0 for r in overview["trend"]), (
        "tenant_b's score must never leak into tenant_a's overview"
    )
    assert overview["trend"][-1]["avg_risk_exposure_score"] == 24.0
