"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: GET /api/v1/vulnerabilities/stats must expose
top-level `dashboard_tiles` carrying four tiles (critical_open / sla_at_risk
/ kev / mttr_30d) each with value / delta / delta_direction, plus three
nav counts (vuln_open_count, asset_total_count, ticket_open_count) per
D-B-02 / D-S-01..04 (REQ UX-02-02).

Tests will fail until Task 2 lands the tile computation in
backend/app/vulnerabilities/dashboard.py (or service.py — whichever owns
get_dashboard_stats today).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.trends import DailySnapshot


def _seed_vuln(tenant_id, *, severity="CRITICAL", status="OPEN", cisa_kev=False):
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-2099-{uuid.uuid4().hex[:4]}",
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        cisa_kev=cisa_kev,
        cvss_v3_score=9.8,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_dashboard_tiles_shape(client, db_session, tenant_a):
    """UX-02-02 / D-B-02: response has dashboard_tiles with 4 sub-keys, each
    carrying value, delta, delta_direction."""
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities/stats")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "dashboard_tiles" in body, "Missing top-level dashboard_tiles"
    tiles = body["dashboard_tiles"]
    assert set(tiles.keys()) >= {"critical_open", "sla_at_risk", "kev", "mttr_30d"}

    for name in ("critical_open", "sla_at_risk", "kev", "mttr_30d"):
        tile = tiles[name]
        assert "value" in tile
        assert "delta" in tile
        assert "delta_direction" in tile
        if tile["delta_direction"] is not None:
            assert tile["delta_direction"] in {"up", "down", "flat"}


@pytest.mark.asyncio
async def test_dashboard_tiles_delta_computed_from_snapshot(client, db_session, tenant_a):
    """UX-02-02 / D-S-01: dashboard_tiles.critical_open.delta = today - 7d.

    Seed a DailySnapshot at today-7d with critical_open=10, then seed two
    critical OPEN vulns today, then assert delta = today_count - 10.
    """
    # Two CRITICAL OPEN vulns today
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    # DailySnapshot seven days ago saying critical_open was 10
    seven_days_ago = (datetime.now(UTC) - timedelta(days=7)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=seven_days_ago,
            metrics={"critical_open": 10, "sla_breached": 0, "kev_count": 0},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    critical = body["dashboard_tiles"]["critical_open"]

    assert critical["value"] >= 2  # today's count
    # delta = today (>=2) - 10 (prior) → negative
    assert critical["delta"] is not None
    assert critical["delta"] == critical["value"] - 10
    assert critical["delta_direction"] in {"up", "down", "flat"}
    if critical["delta"] < 0:
        assert critical["delta_direction"] == "down"
    elif critical["delta"] > 0:
        assert critical["delta_direction"] == "up"
    else:
        assert critical["delta_direction"] == "flat"


@pytest.mark.asyncio
async def test_dashboard_tiles_delta_null_when_no_snapshot(client, db_session, tenant_a):
    """UX-02-02 / Pitfall 8: when no snapshot exists at today-7d, delta and
    delta_direction must both be null so the UI renders 'Δ —'."""
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    await db_session.commit()
    # Deliberately do NOT create a DailySnapshot at -7d.

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    critical = body["dashboard_tiles"]["critical_open"]

    assert critical["delta"] is None
    assert critical["delta_direction"] is None


@pytest.mark.asyncio
async def test_dashboard_tiles_delta_handles_jsonb_null_metric(client, db_session, tenant_a):
    """BL-03 regression: a DailySnapshot at -7d may have a known metric key
    whose value is explicitly None (e.g. a metric was added after older
    snapshots were written, or a partial write left the key null). The tile
    computation must treat that as 0, not call int(None) and crash /stats
    with TypeError → 500.
    """
    db_session.add(_seed_vuln(tenant_a, severity="CRITICAL"))
    seven_days_ago = (datetime.now(UTC) - timedelta(days=7)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=seven_days_ago,
            # `kev_count` present-but-null exercises the
            # `prior_metrics.get(key, 0) is None` path that BL-03 fixed.
            metrics={"critical_open": 5, "sla_breached": None, "kev_count": None},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities/stats")
    assert resp.status_code == 200, resp.text  # would be 500 before BL-03 fix
    body = resp.json()
    sla = body["dashboard_tiles"]["sla_at_risk"]
    kev = body["dashboard_tiles"]["kev"]
    # The None value should be treated as 0 prior, so delta = today_value - 0.
    assert sla["delta"] is not None
    assert kev["delta"] is not None


@pytest.mark.asyncio
async def test_nav_counts_present(client, db_session, tenant_a):
    """UX-02-02 / D-B-02: response carries vuln_open_count, asset_total_count,
    ticket_open_count at the top level (used by the persistent sidebar)."""
    db_session.add(_seed_vuln(tenant_a, severity="HIGH"))
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert "vuln_open_count" in body
    assert "asset_total_count" in body
    assert "ticket_open_count" in body
    assert isinstance(body["vuln_open_count"], int)
    assert isinstance(body["asset_total_count"], int)
    assert isinstance(body["ticket_open_count"], int)
