"""Phase 36 Plan 03 — escalation firing engine (SLA-03, D-05/D-06/D-07/D-08).

Covers `app/vulnerabilities/sla_tier_service.py`'s `detect_and_escalate` +
`_escalation_already_fired` (the transition-detection + exactly-once firing
loop that drives Plan 02's channel senders + escalation-event table), the
D-08 reconciliation of the legacy `alerts.py::_check_sla_breaches` to a
no-op, and the new tenant-scoped `GET /vulnerabilities/{id}/escalations`
history endpoint.

Direct-await convention (mirrors `test_scheduler_enrichment_refresh.py` /
`test_sla_tier_service.py`'s `run_sla_tier_pass` test): calls
`detect_and_escalate(db_session, tenant)` directly, no scheduler loop
involved. `dispatch_channel` is monkeypatched at the
`app.notifications.escalation_channels` module level -- `detect_and_
escalate`'s own `from app.notifications.escalation_channels import
dispatch_channel` is a LOCAL import inside the function body (same idiom
`escalation_channels.py`'s own docstring documents for its senders), so it
re-resolves the module attribute fresh on every call and honors whatever
`monkeypatch.setattr` most recently set.

Every test seeds `tenant.sla_config` directly via the ORM (not through the
`/settings` PATCH endpoint) but Fernet-encrypts channel secrets with the
SAME `app.encryption.encrypt_value` Plan 05's PATCH handler calls, so
`detect_and_escalate`'s own `decrypt_value` round-trips against a realistic
at-rest shape.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

import app.notifications.escalation_channels as ec
from app.audit import AuditLog
from app.encryption import encrypt_value
from app.notifications.alerts import _check_sla_breaches
from app.notifications.models import Notification
from app.tenants.models import Tenant
from app.vulnerabilities.models import SlaEscalationEvent, Vulnerability
from app.vulnerabilities.sla_tier_service import (
    DEFAULT_APPROACHING_PCT,
    DEFAULT_TIER_POLICY,
    detect_and_escalate,
    run_sla_tier_pass,
)

CRITICAL_DAYS = DEFAULT_TIER_POLICY["critical"]
MODERATE_DAYS = DEFAULT_TIER_POLICY["moderate"]


# ── Seed helpers ─────────────────────────────────────────────────────────


def _vuln(
    *,
    tenant_id: uuid.UUID,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    risk_exposure_score: int | None = None,
    first_detected_at: datetime,
) -> Vulnerability:
    """Bare Vulnerability row — mirrors test_sla_tier_service.py's `_vuln`."""
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="CROWDSTRIKE",
        status=status,
        risk_exposure_score=risk_exposure_score,
        first_detected_at=first_detected_at,
        last_seen_at=now,
    )


def _breached_first_detected(now: datetime, tier_days: int) -> datetime:
    """`now` is unambiguously past this tier's due date."""
    return now - timedelta(days=tier_days, hours=6)


def _approaching_first_detected(now: datetime, tier_days: int) -> datetime:
    """`now` sits inside the approaching window (past approaching_at, still
    before due_at) for ANY of the three default tiers — due in 1h puts
    approaching_at (tier_days * (1-pct) days before due) comfortably in the
    past regardless of tier_days."""
    due_at = now + timedelta(hours=1)
    return due_at - timedelta(days=tier_days)


def _sla_config(
    *,
    tier_floor: str | None = None,
    routing: dict[str, list[str]] | None = None,
    slack_url: str | None = "https://hooks.slack.com/services/T00/B00/FAKE",
    pagerduty_key: str | None = "R0FAKEROUTINGKEY",
) -> dict[str, Any]:
    """A `tenant.sla_config` dict mirroring Plan 05's persisted (Fernet-
    encrypted-at-rest) shape."""
    channels: dict[str, Any] = {}
    if slack_url:
        channels["slack"] = {"url": encrypt_value(slack_url), "enabled": True}
    if pagerduty_key:
        channels["pagerduty"] = {"routing_key": encrypt_value(pagerduty_key), "enabled": True}
    return {
        "tier_policy": dict(DEFAULT_TIER_POLICY),
        "approaching_pct": DEFAULT_APPROACHING_PCT,
        "tier_floor": tier_floor,
        "channels": channels,
        "routing": routing if routing is not None else {"approaching": [], "breached": []},
    }


async def _get_tenant(db_session: Any, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    await db_session.refresh(tenant)
    return tenant


async def _escalation_rows(db_session: Any, vuln_id: uuid.UUID) -> list[SlaEscalationEvent]:
    result = await db_session.execute(
        select(SlaEscalationEvent).where(SlaEscalationEvent.vulnerability_id == vuln_id)
    )
    return list(result.scalars().all())


async def _notification_count(db_session: Any, tenant_id: uuid.UUID, category: str, resource_id: str) -> int:
    result = await db_session.execute(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.category == category,
            Notification.resource_id == resource_id,
        )
    )
    return result.scalar_one()


def _recording_dispatch(calls: list[tuple[str, dict, dict]], ok: bool = True, error: str | None = None):
    async def _fake(channel: str, config: dict, context: dict) -> dict:
        calls.append((channel, config, context))
        return {"ok": ok, "error": error}

    return _fake


# ── 1. Exactly-once across double invocation ────────────────────────────


async def test_double_invocation_fires_exactly_once_per_channel(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_breached_first_detected(now, CRITICAL_DAYS),
    )
    db_session.add(vuln)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": [], "breached": ["slack", "pagerduty"]})
    await db_session.commit()

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch(calls))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    rows = await _escalation_rows(db_session, vuln.id)
    assert len(rows) == 2
    assert {r.channel for r in rows} == {"slack", "pagerduty"}
    assert all(r.to_state == "breached" for r in rows)
    assert len(calls) == 2
    notified_once = await _notification_count(db_session, tenant_a, "sla_escalation", vuln.cve_id)
    assert notified_once == 1

    # Second tick — re-running the tick logic must not re-fire or re-notify.
    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    rows_after = await _escalation_rows(db_session, vuln.id)
    assert len(rows_after) == 2, "no duplicate escalation-event rows on the second tick"
    assert len(calls) == 2, "dispatch_channel must not be called again on the second tick"
    notified_twice = await _notification_count(db_session, tenant_a, "sla_escalation", vuln.cve_id)
    assert notified_twice == 1, "the in-app twin must not be duplicated on the second tick"


# ── 2. Below tier_floor tracks state but never escalates ───────────────


async def test_below_tier_floor_produces_zero_escalations_but_tracked_state(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    # Scored MODERATE-tier finding (risk_exposure_score=25), breached past
    # its 90d window — tracked and breached, but tier_floor="critical"
    # excludes moderate from ever escalating (D-06).
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="LOW",
        risk_exposure_score=25,
        first_detected_at=_breached_first_detected(now, MODERATE_DAYS),
    )
    db_session.add(vuln)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(tier_floor="critical", routing={"approaching": [], "breached": ["slack"]})
    await db_session.commit()

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch(calls))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    await db_session.refresh(vuln)
    assert vuln.sla_breached is True, "still a valid tracked+breached state, not not_tracked"
    assert vuln.sla_due_at is not None

    rows = await _escalation_rows(db_session, vuln.id)
    assert rows == []
    assert calls == []


# ── 3. Per-transition-type routing is exclusive ─────────────────────────


async def test_routing_is_scoped_per_transition_type(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    approaching_vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_approaching_first_detected(now, CRITICAL_DAYS),
    )
    breached_vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_breached_first_detected(now, CRITICAL_DAYS),
    )
    db_session.add_all([approaching_vuln, breached_vuln])

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": ["slack"], "breached": ["pagerduty"]})
    await db_session.commit()

    calls: list[tuple[str, dict, dict]] = []
    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch(calls))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    approaching_rows = await _escalation_rows(db_session, approaching_vuln.id)
    breached_rows = await _escalation_rows(db_session, breached_vuln.id)

    assert [r.channel for r in approaching_rows] == ["slack"]
    assert [r.to_state for r in approaching_rows] == ["approaching"]
    assert [r.channel for r in breached_rows] == ["pagerduty"]
    assert [r.to_state for r in breached_rows] == ["breached"]

    fired_channels_by_vuln = {(c[2]["vuln_id"], c[0]) for c in calls}
    assert (str(approaching_vuln.id), "slack") in fired_channels_by_vuln
    assert (str(approaching_vuln.id), "pagerduty") not in fired_channels_by_vuln
    assert (str(breached_vuln.id), "pagerduty") in fired_channels_by_vuln
    assert (str(breached_vuln.id), "slack") not in fired_channels_by_vuln


# ── 4. Every fire is audited ─────────────────────────────────────────────


async def test_every_fire_produces_exactly_one_audit_row(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_breached_first_detected(now, CRITICAL_DAYS),
    )
    db_session.add(vuln)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": [], "breached": ["slack"]})
    await db_session.commit()

    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch([]))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a,
            AuditLog.action == "sla.escalation_fire",
            AuditLog.resource_id == str(vuln.id),
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].details["channel"] == "slack"
    assert rows[0].details["to_state"] == "breached"


# ── 5. D-08 reconciliation — one breach, one in-app signal ──────────────


async def test_d08_single_breach_yields_one_notification_no_legacy_double_fire(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_breached_first_detected(now, CRITICAL_DAYS),
    )
    db_session.add(vuln)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": [], "breached": ["slack"]})
    await db_session.commit()

    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch([]))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)

    # The legacy flat 24h-lookahead breach check — reconciled to a no-op
    # (D-08) so it never independently creates a second in-app signal.
    legacy_alerts_created = await _check_sla_breaches(db_session, tenant)
    await db_session.commit()

    assert legacy_alerts_created == 0

    resource_id = vuln.cve_id
    sla_escalation_count = await _notification_count(db_session, tenant_a, "sla_escalation", resource_id)
    sla_breach_count = await _notification_count(db_session, tenant_a, "sla_breach", resource_id)
    assert sla_escalation_count == 1
    assert sla_breach_count == 0


# ── 6. Failed channel POST still records + audits, never raises ─────────


async def test_failed_dispatch_records_failed_status_and_audits_without_raising(monkeypatch, db_session, tenant_a):
    now = datetime.now(UTC)
    vuln = _vuln(
        tenant_id=tenant_a,
        severity="CRITICAL",
        first_detected_at=_breached_first_detected(now, CRITICAL_DAYS),
    )
    db_session.add(vuln)

    tenant = await _get_tenant(db_session, tenant_a)
    tenant.sla_config = _sla_config(routing={"approaching": [], "breached": ["slack"]})
    await db_session.commit()

    monkeypatch.setattr(ec, "dispatch_channel", _recording_dispatch([], ok=False, error="webhook unreachable"))

    await run_sla_tier_pass(db_session, tenant)
    await detect_and_escalate(db_session, tenant)  # must not raise
    await db_session.commit()

    rows = await _escalation_rows(db_session, vuln.id)
    assert len(rows) == 1
    assert rows[0].delivery_status == "failed"
    assert rows[0].error_message == "webhook unreachable"

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.tenant_id == tenant_a,
            AuditLog.action == "sla.escalation_fire",
            AuditLog.resource_id == str(vuln.id),
        )
    )
    audit_rows = result.scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].details["delivery_status"] == "failed"


# ── 7. GET /vulnerabilities/{id}/escalations is tenant-scoped ───────────


async def test_get_escalations_endpoint_is_tenant_scoped(
    client, client_factory, db_session, tenant_a, tenant_b, analyst_user_b
):
    now = datetime.now(UTC)
    vuln_a = _vuln(tenant_id=tenant_a, first_detected_at=now - timedelta(days=1))
    vuln_b = _vuln(tenant_id=tenant_b, first_detected_at=now - timedelta(days=1))
    db_session.add_all([vuln_a, vuln_b])
    await db_session.flush()

    event_a = SlaEscalationEvent(
        tenant_id=tenant_a,
        vulnerability_id=vuln_a.id,
        from_state="approaching",
        to_state="breached",
        channel="slack",
        fired_at=now,
        delivery_status="sent",
    )
    db_session.add(event_a)
    await db_session.commit()

    resp = await client.get(f"/api/v1/vulnerabilities/{vuln_a.id}/escalations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["channel"] == "slack"
    assert body[0]["to_state"] == "breached"
    assert body[0]["from_state"] == "approaching"
    assert body[0]["delivery_status"] == "sent"
    assert "fired_at" in body[0]

    # IDOR — tenant_b's analyst may not read tenant_a's vuln id.
    other_client = client_factory(analyst_user_b)
    cross_resp = await other_client.get(f"/api/v1/vulnerabilities/{vuln_a.id}/escalations")
    assert cross_resp.status_code == 404
