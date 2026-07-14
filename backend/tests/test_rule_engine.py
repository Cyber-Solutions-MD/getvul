"""Phase 8 — ticket rule-engine coverage.

Covers app/ticketing/rule_engine.py::find_matching_assets — the pure
condition-matching core (device category, risk score, scanner, and per-asset
vulnerability conditions). run_rule/run_all_due_rules are not exercised here
because they require a live Asana client; the matching logic is the testable,
security/automation-relevant heart of the engine.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.ticketing.rule_engine import find_matching_assets
from app.vulnerabilities.models import Vulnerability


async def _asset(
    db,
    tenant_id,
    *,
    hostname: str,
    device_category: str = "SERVER",
    risk_score: int = 50,
    seen_by_sources: list[str] | None = None,
    is_ignored: bool = False,
    mdm_details: dict | None = None,
) -> Asset:
    a = Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        device_category=device_category,
        risk_score=risk_score,
        seen_by_sources=seen_by_sources or [],
        is_ignored=is_ignored,
        mdm_details=mdm_details or {},
    )
    db.add(a)
    await db.flush()  # assign a.id for linking vulns
    return a


def _vuln(
    tenant_id,
    asset_id,
    *,
    severity: str = "HIGH",
    exploit_available: bool = False,
    cisa_kev: bool = False,
    status: str = "OPEN",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        exploit_available=exploit_available,
        cisa_kev=cisa_kev,
        first_detected_at=now,
        last_seen_at=now,
    )


def _names(assets) -> set[str]:
    return {a.hostname for a in assets}


@pytest.mark.asyncio
async def test_no_conditions_returns_all_non_ignored(db_session, tenant_a):
    await _asset(db_session, tenant_a, hostname="keep-1")
    await _asset(db_session, tenant_a, hostname="keep-2")
    await _asset(db_session, tenant_a, hostname="ignored-1", is_ignored=True)
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {})
    assert _names(matched) == {"keep-1", "keep-2"}  # is_ignored excluded


@pytest.mark.asyncio
async def test_device_category_filter(db_session, tenant_a):
    await _asset(db_session, tenant_a, hostname="srv", device_category="SERVER")
    await _asset(db_session, tenant_a, hostname="wks", device_category="WORKSTATION")
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"device_category": ["SERVER"]})
    assert _names(matched) == {"srv"}


@pytest.mark.asyncio
async def test_min_risk_score_filter(db_session, tenant_a):
    await _asset(db_session, tenant_a, hostname="low", risk_score=10)
    await _asset(db_session, tenant_a, hostname="high", risk_score=90)
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"min_risk_score": 50})
    assert _names(matched) == {"high"}


@pytest.mark.asyncio
async def test_scanner_filter_matches_seen_by_sources(db_session, tenant_a):
    await _asset(db_session, tenant_a, hostname="wiz-host", seen_by_sources=["WIZ", "NESSUS"])
    await _asset(db_session, tenant_a, hostname="cs-host", seen_by_sources=["CROWDSTRIKE"])
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"scanner": ["WIZ"]})
    assert _names(matched) == {"wiz-host"}


@pytest.mark.asyncio
async def test_severity_condition_requires_matching_vuln(db_session, tenant_a):
    crit = await _asset(db_session, tenant_a, hostname="has-crit")
    high = await _asset(db_session, tenant_a, hostname="has-high")
    await _asset(db_session, tenant_a, hostname="no-vulns")
    db_session.add(_vuln(tenant_a, crit.id, severity="CRITICAL"))
    db_session.add(_vuln(tenant_a, high.id, severity="HIGH"))
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"severity": ["CRITICAL"]})
    assert _names(matched) == {"has-crit"}  # only the asset with a CRITICAL vuln


@pytest.mark.asyncio
async def test_exploit_available_condition(db_session, tenant_a):
    exp = await _asset(db_session, tenant_a, hostname="exploitable")
    plain = await _asset(db_session, tenant_a, hostname="not-exploitable")
    db_session.add(_vuln(tenant_a, exp.id, exploit_available=True))
    db_session.add(_vuln(tenant_a, plain.id, exploit_available=False))
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"exploit_available": True})
    assert _names(matched) == {"exploitable"}


@pytest.mark.asyncio
async def test_cisa_kev_condition(db_session, tenant_a):
    kev = await _asset(db_session, tenant_a, hostname="kev-host")
    non = await _asset(db_session, tenant_a, hostname="non-kev")
    db_session.add(_vuln(tenant_a, kev.id, cisa_kev=True))
    db_session.add(_vuln(tenant_a, non.id, cisa_kev=False))
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"cisa_kev": True})
    assert _names(matched) == {"kev-host"}


@pytest.mark.asyncio
async def test_min_critical_vulns_threshold(db_session, tenant_a):
    two = await _asset(db_session, tenant_a, hostname="two-crit")
    one = await _asset(db_session, tenant_a, hostname="one-crit")
    for _ in range(2):
        db_session.add(_vuln(tenant_a, two.id, severity="CRITICAL"))
    db_session.add(_vuln(tenant_a, one.id, severity="CRITICAL"))
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {"min_critical_vulns": 2})
    assert _names(matched) == {"two-crit"}


@pytest.mark.asyncio
async def test_conditions_are_tenant_scoped(db_session, tenant_a, tenant_b):
    await _asset(db_session, tenant_a, hostname="a-host")
    await _asset(db_session, tenant_b, hostname="b-host")
    await db_session.commit()

    matched = await find_matching_assets(db_session, tenant_a, {})
    assert _names(matched) == {"a-host"}  # tenant B's asset never leaks
