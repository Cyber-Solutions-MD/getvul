"""Phase 8 — SLA service coverage.

Covers app/vulnerabilities/sla_service.py: SLA-day config resolution, due-date
backfill/recalculation, breach detection + cleanup, and compliance metrics.
These are pure DB-logic functions (no external APIs), seeded against getvul_test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.sla_service import (
    DEFAULT_SLA_DAYS,
    backfill_sla_due_dates,
    check_sla_breaches,
    get_sla_days,
    get_sla_metrics,
    recalculate_sla_due_dates,
)


def _vuln(
    tenant_id,
    *,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    first_detected_at: datetime | None = None,
    sla_due_at: datetime | None = None,
    sla_breached: bool = False,
    remediated_at: datetime | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        first_detected_at=first_detected_at or now,
        last_seen_at=now,
        sla_due_at=sla_due_at,
        sla_breached=sla_breached,
        remediated_at=remediated_at,
    )


# ── get_sla_days (pure config resolution, no DB) ──────────────────────────────


def test_get_sla_days_defaults_when_no_tenant():
    assert get_sla_days(None) == DEFAULT_SLA_DAYS
    # Returns a copy — mutating the result must not corrupt the module default.
    got = get_sla_days(None)
    got["CRITICAL"] = 1
    assert DEFAULT_SLA_DAYS["CRITICAL"] == 7


def test_get_sla_days_custom_overrides_partial():
    tenant = Tenant(name="T", slug="t", sla_config={"days": {"CRITICAL": 3, "HIGH": 14}})
    days = get_sla_days(tenant)
    assert days["CRITICAL"] == 3  # overridden
    assert days["HIGH"] == 14  # overridden
    assert days["MEDIUM"] == DEFAULT_SLA_DAYS["MEDIUM"]  # falls back to default
    assert days["LOW"] == DEFAULT_SLA_DAYS["LOW"]


def test_get_sla_days_ignores_empty_config():
    tenant = Tenant(name="T", slug="t", sla_config=None)
    assert get_sla_days(tenant) == DEFAULT_SLA_DAYS
    tenant2 = Tenant(name="T", slug="t2", sla_config={})
    assert get_sla_days(tenant2) == DEFAULT_SLA_DAYS


# ── backfill / recalculate due dates ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_backfill_sets_due_dates_by_severity(db_session, tenant_a):
    detected = datetime.now(UTC) - timedelta(days=1)
    crit = _vuln(tenant_a, severity="CRITICAL", first_detected_at=detected)
    high = _vuln(tenant_a, severity="HIGH", first_detected_at=detected)
    db_session.add_all([crit, high])
    await db_session.commit()

    result = await backfill_sla_due_dates(db_session, tenant_a)
    assert result["backfilled"] == 2

    await db_session.refresh(crit)
    await db_session.refresh(high)
    # CRITICAL = detected + 7d, HIGH = detected + 30d (DEFAULT_SLA_DAYS).
    assert crit.sla_due_at == detected + timedelta(days=DEFAULT_SLA_DAYS["CRITICAL"])
    assert high.sla_due_at == detected + timedelta(days=DEFAULT_SLA_DAYS["HIGH"])


@pytest.mark.asyncio
async def test_backfill_skips_vulns_that_already_have_due_date(db_session, tenant_a):
    existing_due = datetime.now(UTC) + timedelta(days=99)
    v = _vuln(tenant_a, severity="CRITICAL", sla_due_at=existing_due)
    db_session.add(v)
    await db_session.commit()

    result = await backfill_sla_due_dates(db_session, tenant_a)
    assert result["backfilled"] == 0  # already had a due date
    await db_session.refresh(v)
    assert v.sla_due_at == existing_due  # untouched


@pytest.mark.asyncio
async def test_recalculate_overwrites_existing_due_dates(db_session, tenant_a):
    detected = datetime.now(UTC) - timedelta(days=2)
    v = _vuln(tenant_a, severity="CRITICAL", first_detected_at=detected, sla_due_at=detected)
    db_session.add(v)
    await db_session.commit()

    result = await recalculate_sla_due_dates(db_session, tenant_a)
    assert result["recalculated"] == 1
    await db_session.refresh(v)
    assert v.sla_due_at == detected + timedelta(days=DEFAULT_SLA_DAYS["CRITICAL"])


# ── breach detection + cleanup ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_breaches_marks_past_due_open_vulns(db_session, tenant_a):
    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=10)
    overdue = _vuln(tenant_a, status="OPEN", sla_due_at=past, sla_breached=False)
    on_time = _vuln(tenant_a, status="OPEN", sla_due_at=future, sla_breached=False)
    db_session.add_all([overdue, on_time])
    await db_session.commit()

    result = await check_sla_breaches(db_session, tenant_a)
    assert result["newly_breached"] == 1

    await db_session.refresh(overdue)
    await db_session.refresh(on_time)
    assert overdue.sla_breached is True
    assert on_time.sla_breached is False


@pytest.mark.asyncio
async def test_check_breaches_cleans_up_resolved_vulns(db_session, tenant_a):
    past = datetime.now(UTC) - timedelta(days=1)
    # Was breached, but has since been remediated → should be un-breached.
    remediated = _vuln(tenant_a, status="REMEDIATED", sla_due_at=past, sla_breached=True)
    db_session.add(remediated)
    await db_session.commit()

    result = await check_sla_breaches(db_session, tenant_a)
    assert result["cleaned_up"] == 1
    await db_session.refresh(remediated)
    assert remediated.sla_breached is False


# ── metrics ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sla_metrics_partitions_open_vulns(db_session, tenant_a):
    now = datetime.now(UTC)
    breached = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    at_risk = _vuln(tenant_a, status="OPEN", sla_due_at=now + timedelta(hours=24), sla_breached=False)
    within = _vuln(tenant_a, status="OPEN", sla_due_at=now + timedelta(days=30), sla_breached=False)
    db_session.add_all([breached, at_risk, within])
    await db_session.commit()

    m = await get_sla_metrics(db_session, tenant_a)
    assert m["open_with_sla"] == 3
    assert m["breached"] == 1
    assert m["at_risk"] == 1  # due within 72h, not breached
    assert m["within_sla"] == 1
    assert m["breach_by_severity"].get("CRITICAL") == 1
    assert m["sla_config"] == DEFAULT_SLA_DAYS


@pytest.mark.asyncio
async def test_sla_metrics_compliance_pct(db_session, tenant_a):
    now = datetime.now(UTC)
    due = now - timedelta(days=1)
    # Remediated BEFORE due → within SLA; remediated AFTER due → breached SLA.
    on_time = _vuln(tenant_a, status="REMEDIATED", sla_due_at=due, remediated_at=due - timedelta(days=1))
    late = _vuln(tenant_a, status="REMEDIATED", sla_due_at=due, remediated_at=due + timedelta(hours=1))
    db_session.add_all([on_time, late])
    await db_session.commit()

    m = await get_sla_metrics(db_session, tenant_a)
    assert m["remediated_total"] == 2
    assert m["remediated_within_sla"] == 1
    assert m["compliance_pct"] == 50.0


@pytest.mark.asyncio
async def test_sla_metrics_empty_tenant_is_fully_compliant(db_session, tenant_a):
    m = await get_sla_metrics(db_session, tenant_a)
    assert m["open_with_sla"] == 0
    assert m["breached"] == 0
    assert m["compliance_pct"] == 100.0  # no remediations → default 100%
