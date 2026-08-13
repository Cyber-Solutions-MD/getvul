"""Phase 36 Plan 01 (LEAD TRACER) — SLA tier engine unit tests.

Covers `app/vulnerabilities/sla_tier_service.py`: risk-tier boundary
resolution (D-12), the severity fallback map (D-03), the tier+elapsed-%
state formula (D-02), the custom-or-default tenant policy merge (mirrors
`sla_service.get_sla_days`), and end-to-end per-vuln state resolution
(scored / NULL-score fallback / below-floor not_tracked).

Almost every function under test is pure (no DB I/O) — unlike
test_sla_service.py's async DB-backed tests, none of these need
`db_session`/`tenant_a` fixtures: `get_tier_policy` takes a plain `Tenant`
(or None) with no query inside it, and `resolve_state_for_vuln` takes a
plain `Vulnerability` with no query inside it either. Frozen `now`
datetimes are always derived FROM the same tier_days/approaching_pct
constants used by the formula under test (never hardcoded calendar dates)
so boundary assertions stay exact regardless of when the suite runs.

The lone exception is `run_sla_tier_pass` (the scheduler-tick entrypoint,
added in Task 3) — it DOES perform DB I/O (queries + writes + a ticket-SLA
resync), so its test at the bottom of this file uses `db_session`/`tenant_a`
like test_sla_service.py's DB-backed tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.sla_tier_service import (
    DEFAULT_APPROACHING_PCT,
    DEFAULT_TIER_POLICY,
    compute_sla_state,
    get_tier_policy,
    resolve_state_for_vuln,
    run_sla_tier_pass,
    severity_to_tier,
    tier_for_score,
)


def _vuln(
    *,
    tenant_id: uuid.UUID | None = None,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    risk_exposure_score: int | None = None,
    first_detected_at: datetime | None = None,
) -> Vulnerability:
    """Bare Vulnerability — pure attribute access, no DB by default.

    `tenant_id` defaults to a fresh random UUID for the pure-function tests
    above (which never persist this object); pass a real tenant fixture's
    UUID to seed a row for the DB-backed `run_sla_tier_pass` test below.
    """
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id or uuid.uuid4(),
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        status=status,
        risk_exposure_score=risk_exposure_score,
        first_detected_at=first_detected_at or now,
        last_seen_at=now,
    )


def _policy(tier_days: dict[str, int] | None = None, approaching_pct: float = DEFAULT_APPROACHING_PCT) -> dict:
    return {
        "tier_days": dict(tier_days or DEFAULT_TIER_POLICY),
        "approaching_pct": approaching_pct,
    }


# ── tier_for_score boundaries (D-12: None below RISK_SCORE_TIER_MEDIUM) ──────


def test_tier_for_score_critical_at_80():
    assert tier_for_score(80) == "critical"


def test_tier_for_score_high_just_below_critical_at_79():
    assert tier_for_score(79) == "high"


def test_tier_for_score_high_at_50():
    assert tier_for_score(50) == "high"


def test_tier_for_score_moderate_just_below_high_at_49():
    assert tier_for_score(49) == "moderate"


def test_tier_for_score_moderate_at_20():
    assert tier_for_score(20) == "moderate"


def test_tier_for_score_none_just_below_moderate_at_19():
    """D-12: below RISK_SCORE_TIER_MEDIUM (20) — no named tier, no 4th 'low' tier."""
    assert tier_for_score(19) is None


def test_tier_for_score_none_score_returns_none():
    assert tier_for_score(None) is None


# ── severity_to_tier fallback map (D-03 / D-12) ──────────────────────────────


def test_severity_to_tier_critical():
    assert severity_to_tier("CRITICAL") == "critical"


def test_severity_to_tier_high():
    assert severity_to_tier("HIGH") == "high"


def test_severity_to_tier_medium_is_moderate():
    assert severity_to_tier("MEDIUM") == "moderate"


def test_severity_to_tier_low_is_moderate():
    assert severity_to_tier("LOW") == "moderate"


def test_severity_to_tier_info_is_moderate():
    assert severity_to_tier("INFO") == "moderate"


# ── get_tier_policy (custom-or-default merge, mirrors sla_service.get_sla_days) ─


def test_get_tier_policy_defaults_when_no_tenant():
    policy = get_tier_policy(None)
    assert policy["tier_days"] == DEFAULT_TIER_POLICY
    assert policy["approaching_pct"] == DEFAULT_APPROACHING_PCT


def test_get_tier_policy_defaults_when_tenant_has_no_sla_config():
    tenant = Tenant(name="T", slug="t", sla_config=None)
    policy = get_tier_policy(tenant)
    assert policy["tier_days"] == DEFAULT_TIER_POLICY
    assert policy["approaching_pct"] == DEFAULT_APPROACHING_PCT


def test_get_tier_policy_custom_overrides_partial():
    tenant = Tenant(name="T", slug="t", sla_config={"tier_policy": {"critical": 3}})
    policy = get_tier_policy(tenant)
    assert policy["tier_days"]["critical"] == 3  # overridden
    assert policy["tier_days"]["high"] == DEFAULT_TIER_POLICY["high"]  # falls back to default
    assert policy["tier_days"]["moderate"] == DEFAULT_TIER_POLICY["moderate"]  # falls back to default


def test_get_tier_policy_custom_approaching_pct():
    tenant = Tenant(name="T", slug="t", sla_config={"approaching_pct": 0.5})
    policy = get_tier_policy(tenant)
    assert policy["approaching_pct"] == 0.5
    assert policy["tier_days"] == DEFAULT_TIER_POLICY  # untouched when only approaching_pct is custom


def test_get_tier_policy_ignores_empty_config():
    tenant = Tenant(name="T", slug="t2", sla_config={})
    policy = get_tier_policy(tenant)
    assert policy["tier_days"] == DEFAULT_TIER_POLICY
    assert policy["approaching_pct"] == DEFAULT_APPROACHING_PCT


# ── compute_sla_state boundaries (D-02: approaching % scales per tier) ───────


def test_compute_sla_state_on_track_before_approaching_boundary_critical():
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["critical"]  # 7
    approaching_pct = DEFAULT_APPROACHING_PCT  # 0.8
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))

    due, state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=approaching_at - timedelta(seconds=1),
    )
    assert state == "on_track"
    assert due == sla_due_at


def test_compute_sla_state_approaching_at_exact_boundary_critical():
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["critical"]
    approaching_pct = DEFAULT_APPROACHING_PCT
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))

    due, state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=approaching_at,
    )
    assert state == "approaching"
    assert due == sla_due_at


def test_compute_sla_state_breached_at_exact_due_date_critical():
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["critical"]
    approaching_pct = DEFAULT_APPROACHING_PCT
    sla_due_at = first_detected_at + timedelta(days=tier_days)

    due, state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=sla_due_at,
    )
    assert state == "breached"
    assert due == sla_due_at


def test_compute_sla_state_approaching_window_scales_per_tier_moderate():
    """D-02: 80% of a 90d moderate window is a proportionately wider lead
    time (18d) than 80% of a 7d critical window (1.4d) — same % of a
    different-length window, not a fixed lead time."""
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["moderate"]  # 90
    approaching_pct = DEFAULT_APPROACHING_PCT  # 0.8
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    assert sla_due_at - approaching_at == timedelta(days=18)  # 90 * 0.2

    due, state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=approaching_at,
    )
    assert state == "approaching"
    assert due == sla_due_at

    on_track_due, on_track_state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=approaching_at - timedelta(days=1),
    )
    assert on_track_state == "on_track"
    assert on_track_due == sla_due_at


def test_compute_sla_state_breached_at_exact_due_date_moderate():
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["moderate"]
    approaching_pct = DEFAULT_APPROACHING_PCT
    sla_due_at = first_detected_at + timedelta(days=tier_days)

    due, state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=sla_due_at,
    )
    assert state == "breached"
    assert due == sla_due_at


# ── resolve_state_for_vuln (D-03 fallback, D-12 not_tracked floor) ──────────


def test_resolve_state_for_vuln_null_score_uses_severity_fallback_critical():
    """NULL score + CRITICAL severity resolves via the critical (7d) tier —
    proven by an elapsed time (10d) that is breached under critical but would
    be on_track under the moderate (90d) default, so the assertion actually
    distinguishes which tier the fallback chose."""
    now = datetime(2026, 1, 15, tzinfo=UTC)
    vuln = _vuln(
        severity="CRITICAL",
        risk_exposure_score=None,
        first_detected_at=now - timedelta(days=10),
    )
    due, state = resolve_state_for_vuln(vuln, _policy(), now)
    assert state == "breached"
    assert due == vuln.first_detected_at + timedelta(days=DEFAULT_TIER_POLICY["critical"])


def test_resolve_state_for_vuln_null_score_uses_severity_fallback_low_is_moderate():
    """NULL score + LOW severity resolves via the moderate (90d) tier — same
    10d elapsed time as the CRITICAL case above, but here it must be
    on_track, proving LOW maps to moderate (D-12), not critical."""
    now = datetime(2026, 1, 15, tzinfo=UTC)
    vuln = _vuln(
        severity="LOW",
        risk_exposure_score=None,
        first_detected_at=now - timedelta(days=10),
    )
    due, state = resolve_state_for_vuln(vuln, _policy(), now)
    assert state == "on_track"
    assert due == vuln.first_detected_at + timedelta(days=DEFAULT_TIER_POLICY["moderate"])


def test_resolve_state_for_vuln_score_below_floor_is_not_tracked():
    """D-12: a SCORED finding below RISK_SCORE_TIER_MEDIUM (20) is always
    not_tracked with no due date — severity is irrelevant once scored, and
    it never breaches no matter how old the finding is."""
    now = datetime(2026, 1, 15, tzinfo=UTC)
    vuln = _vuln(
        severity="CRITICAL",
        risk_exposure_score=19,
        first_detected_at=now - timedelta(days=1000),
    )
    due, state = resolve_state_for_vuln(vuln, _policy(), now)
    assert due is None
    assert state == "not_tracked"


def test_resolve_state_for_vuln_scored_uses_tier_based_state_not_severity():
    """A scored finding uses tier_for_score, ignoring severity entirely —
    LOW severity but score=85 (critical tier) must breach at 8d elapsed."""
    now = datetime(2026, 1, 15, tzinfo=UTC)
    vuln = _vuln(
        severity="LOW",
        risk_exposure_score=85,
        first_detected_at=now - timedelta(days=8),
    )
    due, state = resolve_state_for_vuln(vuln, _policy(), now)
    assert state == "breached"
    assert due == vuln.first_detected_at + timedelta(days=DEFAULT_TIER_POLICY["critical"])


def test_resolve_state_for_vuln_scored_on_track_moderate():
    now = datetime(2026, 1, 15, tzinfo=UTC)
    vuln = _vuln(
        severity="CRITICAL",  # irrelevant once scored
        risk_exposure_score=25,  # -> "moderate" tier (90d)
        first_detected_at=now - timedelta(days=1),
    )
    due, state = resolve_state_for_vuln(vuln, _policy(), now)
    assert state == "on_track"
    assert due == vuln.first_detected_at + timedelta(days=DEFAULT_TIER_POLICY["moderate"])


# ── run_sla_tier_pass (scheduler-tick entrypoint, D-01/D-02/D-08) ──────────
#
# The only DB-backed test in this file — everything above is a pure
# function. This proves the scheduler-tick WRITE path itself (queries the
# tenant's OPEN/IN_PROGRESS vulns, writes tier-based sla_due_at + the
# sla_breached derived mirror) actually persists correctly, since the live
# GET /vulnerabilities integration tests in test_vuln_sort.py exercise the
# INDEPENDENT read-time resolution path in service.py, not this function.


@pytest.mark.asyncio
async def test_run_sla_tier_pass_writes_due_date_and_breached_mirror(db_session, tenant_a):
    """A CRITICAL-severity, NULL-score OPEN vuln detected 10 days ago (>
    critical's 7d fallback window, D-03) must come out of run_sla_tier_pass
    with sla_due_at = first_detected_at + 7d AND sla_breached=True (D-08
    derived mirror) — proving the write path, not just the pure formula."""
    from sqlalchemy import select

    from app.tenants.models import Tenant

    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        status="OPEN",
        first_detected_at=now - timedelta(days=10),
    )
    db_session.add(vuln)
    await db_session.commit()

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    result = await run_sla_tier_pass(db_session, tenant)
    await db_session.commit()

    await db_session.refresh(vuln)
    assert vuln.sla_due_at == vuln.first_detected_at + timedelta(days=DEFAULT_TIER_POLICY["critical"])
    assert vuln.sla_breached is True
    assert result["updated"] == 1


@pytest.mark.asyncio
async def test_run_sla_tier_pass_ignores_remediated_vulns(db_session, tenant_a):
    """Only OPEN/IN_PROGRESS vulns are touched — a REMEDIATED vuln's
    sla_due_at must stay untouched (None), never backfilled retroactively."""
    from sqlalchemy import select

    from app.tenants.models import Tenant

    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        status="REMEDIATED",
        first_detected_at=now - timedelta(days=10),
    )
    db_session.add(vuln)
    await db_session.commit()

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    result = await run_sla_tier_pass(db_session, tenant)
    await db_session.commit()

    await db_session.refresh(vuln)
    assert vuln.sla_due_at is None
    assert result["updated"] == 0
