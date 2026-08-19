"""Phase 39 Plan 03 (EXC-02/EXC-04, D-15/D-16) -- wiring the exception
exclusion join into the Phase 36 SLA engine + the D-16 SLA-clock
subtraction on resurface.

Task 1 (this section): pure-function unit tests for `_merge_intervals`
(Pitfall 4 / T-39-12 -- overlapping lapsed-exception windows must be
interval-merged before summing, never naively added) and
`compute_sla_state`'s new `excepted_seconds` parameter (D-16). Neither
needs `db_session`/`tenant_a` -- both are pure, no DB I/O, mirroring
`test_sla_tier_service.py`'s documented pure-vs-DB-backed split.

Task 2 (appended below): DB-backed integration tests proving the full
D-15/D-16 wiring end-to-end -- `list_vulnerabilities`/`get_vulnerability`
read-time subtraction, `run_sla_tier_pass`'s persisted-mirror agreement
(Pitfall 1), and `detect_and_escalate`'s exclusion (T-39-11) + its own
subtraction (so a just-resurfaced finding doesn't fire an instant-breach
escalation storm -- the plan's own stated objective).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions_sla.py -x
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

import app.notifications.escalation_channels as ec
from app.assets.models import Asset
from app.encryption import encrypt_value
from app.exceptions.models import ExceptionRecord
from app.exceptions.service import _merge_intervals
from app.notifications.models import Notification
from app.tenants.models import Tenant
from app.vulnerabilities.models import SlaEscalationEvent, Vulnerability
from app.vulnerabilities.service import get_vulnerability
from app.vulnerabilities.sla_tier_service import (
    DEFAULT_APPROACHING_PCT,
    DEFAULT_TIER_POLICY,
    compute_sla_state,
    detect_and_escalate,
    run_sla_tier_pass,
)

# ── _merge_intervals (Pitfall 4 / T-39-12: overlap counted once) ───────────


def test_merge_intervals_empty():
    assert _merge_intervals([]) == 0


def test_merge_intervals_single():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=3)
    assert _merge_intervals([(start, end)]) == int(timedelta(days=3).total_seconds())


def test_merge_intervals_disjoint():
    """Two non-overlapping windows sum plainly -- no merge needed."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=1))
    window_b = (start + timedelta(days=5), start + timedelta(days=6))
    expected = int(timedelta(days=1).total_seconds()) * 2
    assert _merge_intervals([window_a, window_b]) == expected
    # Order-independent -- sorted internally.
    assert _merge_intervals([window_b, window_a]) == expected


def test_merge_intervals_overlap_union_not_sum():
    """Two overlapping windows must count the union once, NOT the naive
    sum of each window's own duration (T-39-12 -- prevents an
    over-credited SLA clock when D-12 permits simultaneous overlapping
    exceptions)."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=3))  # [0, 3]
    window_b = (start + timedelta(days=1), start + timedelta(days=4))  # [1, 4]
    naive_sum = int(timedelta(days=3).total_seconds()) + int(timedelta(days=3).total_seconds())
    union_seconds = int(timedelta(days=4).total_seconds())  # [0, 4] merged
    result = _merge_intervals([window_a, window_b])
    assert result == union_seconds
    assert result != naive_sum


def test_merge_intervals_touching_adjacent_merged():
    """Windows that exactly touch (one's end == the other's start) merge
    into a single continuous run."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    window_a = (start, start + timedelta(days=2))
    window_b = (start + timedelta(days=2), start + timedelta(days=5))
    assert _merge_intervals([window_a, window_b]) == int(timedelta(days=5).total_seconds())


# ── compute_sla_state's excepted_seconds param (D-16) ───────────────────────


def test_excepted_seconds_subtraction():
    """excepted_seconds shifts the effective start (and therefore the due
    date) later by exactly that many seconds -- the classification
    thresholds (tier_days/approaching_pct) themselves are unchanged."""
    first_detected_at = datetime(2026, 1, 1, tzinfo=UTC)
    tier_days = DEFAULT_TIER_POLICY["critical"]  # 7
    approaching_pct = DEFAULT_APPROACHING_PCT
    excepted_seconds = int(timedelta(days=10).total_seconds())

    baseline_due, _ = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=first_detected_at,
    )
    shifted_due, shifted_state = compute_sla_state(
        first_detected_at=first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=first_detected_at,
        excepted_seconds=excepted_seconds,
    )

    assert shifted_due == baseline_due + timedelta(seconds=excepted_seconds)
    # 10 days of excepted time pushed the due date well into the future
    # relative to `now` (still first_detected_at) -- on_track, not
    # breached, proving the shift actually moves the classification too.
    assert shifted_state == "on_track"


# ── Task 2: DB-backed wiring (D-15 exclusion + D-16 subtraction) ───────────
#
# Direct-await convention (mirrors test_sla_tier_service.py's
# run_sla_tier_pass test / test_escalation_engine.py): calls
# run_sla_tier_pass/detect_and_escalate/get_vulnerability directly against
# `db_session`, no scheduler loop or HTTP client involved. Exception rows
# are hand-seeded (bypassing grant_exception) so `created_at`/`expires_at`
# can be pinned to exact values for deterministic duration assertions.


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04",
    )


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None = None,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    first_detected_at: datetime | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-SLA-{uuid.uuid4().hex[:6]}",
        severity=severity,
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=first_detected_at or (now - timedelta(days=3)),
        last_seen_at=now,
    )


def _seed_exception(
    tenant_id: uuid.UUID,
    *,
    cve_id: str,
    approver_user_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
    expires_at: datetime,
    scope_type: str = "FINDING",
    vulnerability_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    asset_group_id: uuid.UUID | None = None,
    exc_type: str = "ACCEPTED_RISK",
    revoked_at: datetime | None = None,
    created_at: datetime | None = None,
) -> ExceptionRecord:
    """Directly-inserted exception row, bypassing `grant_exception` --
    mirrors `test_exceptions.py::_seed_exception` but ALWAYS accepts/sets
    `asset_id` explicitly. `lapsed_exception_seconds` (D-16) matches
    FINDING/ASSET scope via `(cve_id, asset_id)` equality (mirroring
    `grant_exception`'s real behavior of deriving FINDING's `asset_id`
    from the resolved `Vulnerability` row) -- a hand-seeded FINDING-scope
    row needs its `asset_id` populated to be found by it, unlike
    `test_exceptions.py`'s helper which only ever needs to prove
    `active_exception_subquery`'s FINDING branch (matched purely by
    `vulnerability_id`).

    `created_at` is explicitly overridable (bypassing the table's
    `server_default=func.now()`) so interval-merge duration assertions can
    be exact.
    """
    record = ExceptionRecord(
        tenant_id=tenant_id,
        type=exc_type,
        scope_type=scope_type,
        cve_id=cve_id,
        vulnerability_id=vulnerability_id,
        asset_id=asset_id,
        asset_group_id=asset_group_id,
        justification="Seeded directly for SLA-subtraction test",
        approver_user_id=approver_user_id,
        granted_by_user_id=granted_by_user_id,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    if created_at is not None:
        record.created_at = created_at
    return record


def _sla_config(*, routing: dict[str, list[str]]) -> dict:
    """Minimal tenant.sla_config with one Fernet-encrypted-at-rest slack
    channel -- mirrors test_escalation_engine.py's `_sla_config` shape."""
    return {
        "tier_policy": dict(DEFAULT_TIER_POLICY),
        "approaching_pct": DEFAULT_APPROACHING_PCT,
        "tier_floor": None,
        "channels": {"slack": {"url": encrypt_value("https://hooks.slack.com/services/T00/B00/FAKE")}},
        "routing": routing,
    }


def _recording_dispatch(calls: list[tuple[str, dict, dict]]):
    async def _fake(channel: str, config: dict, context: dict) -> dict:
        calls.append((channel, config, context))
        return {"ok": True, "error": None}

    return _fake


async def _get_tenant(db_session, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    await db_session.refresh(tenant)
    return tenant


# ── list_vulnerabilities/get_vulnerability read-time subtraction (D-16) ────


@pytest.mark.asyncio
async def test_sla_subtraction_on_resurface(db_session, tenant_a, admin_user, analyst_user):
    """A resurfaced finding's read-time sla_state is on_track (not
    breached) once its lapsed-exception time is subtracted -- and the
    exact due date proves two OVERLAPPING lapsed exceptions (D-12) were
    interval-MERGED (Pitfall 4 / T-39-12), not naively summed: a naive sum
    would land the due date 4 days later than the correct union.

    Numbers: first_detected_at = now-8d. Exception A (FINDING) covers
    [now-8d, now-1d] (7d). Exception B (ASSET, same cve+asset) covers
    [now-5d, now-1d] (4d), fully inside A's window. Union = 7d (A alone);
    naive sum would be 11d. Effective_start = (now-8d)+7d = now-1d. Due =
    effective_start+7d(critical tier) = now+6d -- on_track. A naive-sum
    bug would instead compute now-8d+11d+7d = now+10d, still on_track but
    a DIFFERENT due date, which the exact assertion below would catch.
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    now = datetime.now(UTC)
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL", first_detected_at=now - timedelta(days=8))
    db_session.add(vuln)
    await db_session.flush()

    exc_a = _seed_exception(
        tenant_a,
        scope_type="FINDING",
        vulnerability_id=vuln.id,
        asset_id=asset.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        created_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )
    exc_b = _seed_exception(
        tenant_a,
        scope_type="ASSET",
        asset_id=asset.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        created_at=now - timedelta(days=5),
        expires_at=now - timedelta(days=1),
    )
    db_session.add_all([exc_a, exc_b])
    await db_session.commit()

    result = await get_vulnerability(db_session, tenant_a, vuln.id)
    assert result is not None
    assert result.sla_state == "on_track", "the merged (not naively summed) subtraction must not read as breached"
    assert result.sla_due_at == vuln.first_detected_at + timedelta(days=14)  # 7d merged-excepted + 7d critical tier


# ── run_sla_tier_pass persisted-mirror agreement (Pitfall 1) ────────────────


@pytest.mark.asyncio
async def test_persisted_mirror_matches_live(db_session, tenant_a, admin_user, analyst_user):
    """After a scheduler tick, the PERSISTED sla_due_at/sla_breached mirror
    must agree with the independently-computed LIVE read-time value for a
    just-resurfaced finding -- Pitfall 1's two-parallel-representations
    failure mode, closed by applying the identical D-16 subtraction inside
    run_sla_tier_pass, not only the read-time callers."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    now = datetime.now(UTC)
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL", first_detected_at=now - timedelta(days=8))
    db_session.add(vuln)
    await db_session.flush()

    lapsed_exc = _seed_exception(
        tenant_a,
        vulnerability_id=vuln.id,
        asset_id=asset.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        created_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(lapsed_exc)
    await db_session.commit()

    tenant = await _get_tenant(db_session, tenant_a)
    await run_sla_tier_pass(db_session, tenant)
    await db_session.commit()
    await db_session.refresh(vuln)

    live = await get_vulnerability(db_session, tenant_a, vuln.id)
    assert live is not None
    assert live.sla_due_at == vuln.sla_due_at, "persisted mirror disagrees with the live read-time due date"
    assert vuln.sla_breached is False
    assert live.sla_state in ("on_track", "approaching")


# ── detect_and_escalate exclusion (T-39-11) + its own subtraction ──────────


@pytest.mark.asyncio
async def test_excluded_from_escalation(monkeypatch, db_session, tenant_a, admin_user, analyst_user):
    """detect_and_escalate must skip an ACTIVELY-excepted breaching
    finding entirely (T-39-11, governance-critical): an accepted-risk
    finding never fires a breach alert while covered -- and the persisted
    mirror stays untouched too (D-15 excludes it from run_sla_tier_pass's
    WHERE, same as a REMEDIATED vuln)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    now = datetime.now(UTC)
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL", first_detected_at=now - timedelta(days=30))
    db_session.add(vuln)
    await db_session.flush()

    active_exc = _seed_exception(
        tenant_a,
        vulnerability_id=vuln.id,
        asset_id=asset.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        expires_at=now + timedelta(days=30),  # still active -- not lapsed
    )
    db_session.add(active_exc)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": [], "breached": ["slack"]})
    await db_session.commit()

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch(calls))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    rows = (
        (await db_session.execute(select(SlaEscalationEvent).where(SlaEscalationEvent.vulnerability_id == vuln.id)))
        .scalars()
        .all()
    )
    assert rows == []
    assert calls == []

    notif_count = (
        await db_session.execute(
            select(func.count(Notification.id)).where(
                Notification.tenant_id == tenant_a,
                Notification.category == "sla_escalation",
                Notification.resource_id == vuln.cve_id,
            )
        )
    ).scalar_one()
    assert notif_count == 0

    await db_session.refresh(vuln)
    assert vuln.sla_due_at is None
    assert vuln.sla_breached is False


@pytest.mark.asyncio
async def test_escalation_not_fired_on_resurface(monkeypatch, db_session, tenant_a, admin_user, analyst_user):
    """Rule 2 (missing-critical, self-review addendum): detect_and_escalate
    must apply the SAME D-16 subtraction run_sla_tier_pass/read-time
    callers use. Without it, a just-resurfaced finding's un-subtracted due
    date (here, 1 day into breached territory) resolves 'breached'
    independently inside detect_and_escalate even though the persisted
    mirror/read-time state correctly shows on_track -- firing exactly the
    instant-breach escalation storm this plan's own objective names as
    what D-16 exists to prevent (Pitfall 1's failure mode, manifesting in
    the escalation-firing surface, not just the persisted mirror)."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    now = datetime.now(UTC)
    # Un-subtracted: first_detected_at+7d(critical) = now-1d -- 1 day breached.
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL", first_detected_at=now - timedelta(days=8))
    db_session.add(vuln)
    await db_session.flush()

    lapsed_exc = _seed_exception(
        tenant_a,
        vulnerability_id=vuln.id,
        asset_id=asset.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        created_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),  # lapsed 1 day ago, covered 7d
    )
    db_session.add(lapsed_exc)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": ["slack"], "breached": ["slack"]})
    await db_session.commit()

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch(calls))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    rows = (
        (await db_session.execute(select(SlaEscalationEvent).where(SlaEscalationEvent.vulnerability_id == vuln.id)))
        .scalars()
        .all()
    )
    assert rows == [], "un-subtracted clock would have fired an escalation immediately on resurface"
    assert calls == []

    await db_session.refresh(vuln)
    assert vuln.sla_breached is False
