"""Phase 8 — SLA service coverage.

Covers app/vulnerabilities/sla_service.py: SLA-day config resolution, due-date
backfill/recalculation, breach detection + cleanup, and compliance metrics.
These are pure DB-logic functions (no external APIs), seeded against getvul_test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.assets.models import Asset
from app.exceptions.models import ExceptionRecord
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
    asset_id: uuid.UUID | None = None,
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
        asset_id=asset_id,
    )


def _asset(tenant_id) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")


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


# ── Phase 43 Plan 01 (RPT-01/RPT-03) additive extension: severity +
# exclude_exceptions on get_sla_metrics (43-RESEARCH.md Pitfall 1/2) ──────────


def _finding_exception(
    tenant_id, vuln: Vulnerability, *, expires_at: datetime, revoked_at: datetime | None = None
) -> ExceptionRecord:
    """A minimal FINDING-scope ExceptionRecord, constructed directly (not
    via grant_exception) so the test controls expires_at/revoked_at
    precisely. Mirrors active_exception_subquery's FINDING-scope match:
    `ExceptionRecord.vulnerability_id == Vulnerability.id`."""
    return ExceptionRecord(
        tenant_id=tenant_id,
        type="ACCEPTED_RISK",
        scope_type="FINDING",
        cve_id=vuln.cve_id,
        vulnerability_id=vuln.id,
        asset_id=None,
        asset_group_id=None,
        justification="Compensating control in place.",
        approver_user_id=None,
        granted_by_user_id=None,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


@pytest.mark.asyncio
async def test_default_args_are_byte_identical_to_explicit_defaults(db_session, tenant_a):
    """Calling with no kwargs must match calling with severity=None,
    exclude_exceptions=False explicitly -- proves the additive params are
    genuinely opt-in, never a hidden default-behavior change for the
    existing dashboard.py/router.py/trends.py call sites."""
    now = datetime.now(UTC)
    breached = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    db_session.add(breached)
    await db_session.commit()

    m_default = await get_sla_metrics(db_session, tenant_a)
    m_explicit = await get_sla_metrics(db_session, tenant_a, severity=None, exclude_exceptions=False)
    assert m_default == m_explicit


@pytest.mark.asyncio
async def test_exclude_exceptions_drops_actively_excepted_finding_from_breached_and_at_risk(db_session, tenant_a):
    """43-RESEARCH.md Pitfall 2: a finding under an active accepted-risk
    exception is excluded from breached/at_risk when exclude_exceptions=
    True, and still counted when False (default, byte-compatible)."""
    now = datetime.now(UTC)
    excepted = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    at_risk_excepted = _vuln(tenant_a, status="OPEN", sla_due_at=now + timedelta(hours=24), sla_breached=False)
    plain_breached = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    db_session.add_all([excepted, at_risk_excepted, plain_breached])
    await db_session.flush()

    active_grant = _finding_exception(tenant_a, excepted, expires_at=now + timedelta(days=30))
    active_grant_2 = _finding_exception(tenant_a, at_risk_excepted, expires_at=now + timedelta(days=30))
    db_session.add_all([active_grant, active_grant_2])
    await db_session.commit()

    m_included = await get_sla_metrics(db_session, tenant_a)
    assert m_included["breached"] == 2  # excepted + plain_breached, exception not applied by default
    assert m_included["at_risk"] == 1

    m_excluded = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert m_excluded["breached"] == 1  # only plain_breached remains
    assert m_excluded["at_risk"] == 0


@pytest.mark.asyncio
async def test_exclude_exceptions_expired_or_revoked_grant_still_counts(db_session, tenant_a):
    """A LAPSED (expired or revoked) exception must NOT suppress the
    finding -- active_exception_subquery's strict `expires_at > now` and
    `revoked_at IS NULL` boundary, exercised through get_sla_metrics."""
    now = datetime.now(UTC)
    expired_grant_target = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    revoked_grant_target = _vuln(tenant_a, status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    db_session.add_all([expired_grant_target, revoked_grant_target])
    await db_session.flush()

    expired = _finding_exception(tenant_a, expired_grant_target, expires_at=now - timedelta(days=1))
    revoked = _finding_exception(
        tenant_a, revoked_grant_target, expires_at=now + timedelta(days=30), revoked_at=now - timedelta(hours=1)
    )
    db_session.add_all([expired, revoked])
    await db_session.commit()

    m = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert m["breached"] == 2  # both findings resurface -- neither exception is currently active


@pytest.mark.asyncio
async def test_severity_scopes_open_backlog_conditions(db_session, tenant_a):
    """severity="CRITICAL" scopes open_with_sla/breached/at_risk to
    CRITICAL only -- a HIGH-severity breach is excluded."""
    now = datetime.now(UTC)
    crit_breached = _vuln(tenant_a, severity="CRITICAL", status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    high_breached = _vuln(tenant_a, severity="HIGH", status="OPEN", sla_due_at=now - timedelta(days=1), sla_breached=True)
    db_session.add_all([crit_breached, high_breached])
    await db_session.commit()

    m_all = await get_sla_metrics(db_session, tenant_a)
    assert m_all["breached"] == 2

    m_critical_only = await get_sla_metrics(db_session, tenant_a, severity="CRITICAL")
    assert m_critical_only["breached"] == 1
    assert m_critical_only["open_with_sla"] == 1


@pytest.mark.asyncio
async def test_exclude_exceptions_applies_to_compliance_pct_source_queries(db_session, tenant_a):
    """43-RESEARCH.md Pitfall 2: exclude_exceptions must also reach
    remediated_total/remediated_within_sla (compliance_pct's source), not
    just breached/at_risk -- otherwise RPT-03's sla_compliance_pct control
    would pass exclude_exceptions=True with zero actual effect. An
    ASSET-scope exception (D-11 forward-looking, matches on (cve_id,
    asset_id) regardless of the row's current status) covering an
    already-REMEDIATED finding is excluded from the compliance_pct
    calculation when exclude_exceptions=True."""
    now = datetime.now(UTC)
    due = now - timedelta(days=1)
    asset = _asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    on_time = _vuln(tenant_a, status="REMEDIATED", sla_due_at=due, remediated_at=due - timedelta(days=1))
    late_but_excepted = _vuln(
        tenant_a, status="REMEDIATED", sla_due_at=due, remediated_at=due + timedelta(hours=1), asset_id=asset.id
    )
    db_session.add_all([on_time, late_but_excepted])
    await db_session.flush()

    asset_scope_grant = ExceptionRecord(
        tenant_id=tenant_a,
        type="ACCEPTED_RISK",
        scope_type="ASSET",
        cve_id=late_but_excepted.cve_id,
        vulnerability_id=None,
        asset_id=late_but_excepted.asset_id,
        asset_group_id=None,
        justification="Compensating control in place.",
        approver_user_id=None,
        granted_by_user_id=None,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(asset_scope_grant)
    await db_session.commit()

    m_included = await get_sla_metrics(db_session, tenant_a)
    assert m_included["remediated_total"] == 2
    assert m_included["compliance_pct"] == 50.0

    m_excluded = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert m_excluded["remediated_total"] == 1  # late_but_excepted dropped
    assert m_excluded["remediated_within_sla"] == 1
    assert m_excluded["compliance_pct"] == 100.0


@pytest.mark.asyncio
async def test_pitfall1_zero_remediated_is_fake_100_but_flagged_via_remediated_total(db_session, tenant_a):
    """Regression for 43-RESEARCH.md Pitfall 1 CONSUMPTION: a tenant with
    remediated_total==0 still gets the function's own documented
    compliance_pct==100.0 fallback (this function's existing behavior is
    intentionally untouched -- the fake-100 guard belongs at the CALL SITE,
    per the plan's D-01a "never re-derive"), but remediated_total==0 is
    present in the return dict so a caller (compliance/service.py) can
    detect "not measured" and never trust compliance_pct blindly."""
    m = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert m["remediated_total"] == 0
    assert m["compliance_pct"] == 100.0


# ── T-43 regression: pre-existing call sites are unchanged (grep-level,
# not runtime) -- see acceptance_criteria; verified by reading router.py/
# dashboard.py/trends.py source directly rather than re-asserting behavior
# already covered by the tests above.
