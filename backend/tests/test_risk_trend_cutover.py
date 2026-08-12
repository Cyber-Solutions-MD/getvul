"""Phase 34 Plan 05 (RISK-08 gap closure) — trend-chart cutover fixture suite.

34-VERIFICATION.md's GAP 1: `get_risk_score_trend` (app/vulnerabilities/
trends.py) was the third named real cutover consumer (alongside
`list_vulnerabilities(sort="triage")` and `get_top_findings_for_ai_batch`,
both already flag-gated in service.py per 34-02) but had NO branch on
`Tenant.cutover_risk_exposure_scoring` at all — it unconditionally returned
BOTH `avg_risk` (old) and `avg_risk_exposure` (new) as additional keys on
every row, regardless of the flag.

This suite proves the corrected behavior mirrors the 34-02 pattern exactly:
  1. OFF (default): `avg_risk` reads the OLD `avg_risk_score` — byte-identical
     to pre-Phase-34 (no `avg_risk_exposure` key at all, matching the shape
     before RISK-10's dual-write additive key was introduced).
  2. ON: `avg_risk` reads the NEW `avg_risk_exposure_score` instead — the
     PRIMARY series swaps, exactly like service.py's primary-order-key swap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.tenants.models import Tenant
from app.vulnerabilities.trends import DailySnapshot, get_risk_score_trend


async def _set_cutover_flag(db_session, tenant_id, *, enabled: bool) -> None:
    await db_session.execute(update(Tenant).where(Tenant.id == tenant_id).values(cutover_risk_exposure_scoring=enabled))
    await db_session.commit()


async def _seed_snapshot(db_session, tenant_id, *, day, avg_risk_score, avg_risk_exposure_score) -> None:
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_id,
            snapshot_date=day,
            metrics={
                "avg_risk_score": avg_risk_score,
                "avg_risk_exposure_score": avg_risk_exposure_score,
                "open_vulns": 3,
                "critical_open": 1,
                "sla_breached": 0,
                "compliance_pct": 90,
            },
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_trend_flag_off_is_byte_identical(db_session, tenant_a):
    """Flag OFF (default): avg_risk reads avg_risk_score only; NO
    avg_risk_exposure key is present anywhere in the response — the OFF path
    must not add extra keys (mirrors 34-02's OFF-byte-identical guarantee)."""
    day = (datetime.now(UTC) - timedelta(days=1)).date()
    await _seed_snapshot(db_session, tenant_a, day=day, avg_risk_score=42, avg_risk_exposure_score=99)

    rows = await get_risk_score_trend(db_session, tenant_a)
    by_date = {r["date"]: r for r in rows}
    row = by_date[day.isoformat()]

    assert row["avg_risk"] == 42
    assert "avg_risk_exposure" not in row
    assert set(row.keys()) == {
        "date",
        "avg_risk",
        "open_vulns",
        "critical",
        "sla_breached",
        "compliance_pct",
    }


@pytest.mark.asyncio
async def test_trend_flag_on_surfaces_new_series(db_session, tenant_a):
    """Flag ON: avg_risk swaps to read avg_risk_exposure_score instead of
    avg_risk_score — the tenant's trend chart genuinely shows the new score
    once cut over."""
    day = (datetime.now(UTC) - timedelta(days=1)).date()
    await _seed_snapshot(db_session, tenant_a, day=day, avg_risk_score=42, avg_risk_exposure_score=99)

    await _set_cutover_flag(db_session, tenant_a, enabled=True)

    rows = await get_risk_score_trend(db_session, tenant_a)
    by_date = {r["date"]: r for r in rows}
    row = by_date[day.isoformat()]

    assert row["avg_risk"] == 99
    assert "avg_risk_exposure" not in row


@pytest.mark.asyncio
async def test_trend_flag_off_missing_new_score_defaults_zero(db_session, tenant_a):
    """OFF path is fully insulated from the new field: even if
    avg_risk_exposure_score is absent from an old snapshot row, avg_risk
    (sourced from avg_risk_score) is unaffected."""
    day = (datetime.now(UTC) - timedelta(days=2)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day,
            metrics={"avg_risk_score": 55, "open_vulns": 1},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    rows = await get_risk_score_trend(db_session, tenant_a)
    by_date = {r["date"]: r for r in rows}
    row = by_date[day.isoformat()]

    assert row["avg_risk"] == 55
