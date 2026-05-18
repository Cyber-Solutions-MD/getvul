"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: POST /api/v1/vulnerabilities/{id}/snooze must:
  - require ANALYST role (V4 access control)
  - filter by user.tenant_id (IDOR — V4 / V8)
  - default `until` to now+1h when body is empty
  - bound `until` to ≤30 days from now (V11 business logic)
  - reject `until` in the past
  - emit a vuln.snooze audit event (AUDIT-01)
  - set vuln status to 'SUPPRESSED'

per D-B-04 / D-H-07 (REQ UX-02-01). Tests will fail until Task 3 lands
the route in backend/app/vulnerabilities/router.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.audit import AuditLog
from app.vulnerabilities.models import Vulnerability


def _seed_open_vuln(tenant_id) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-SN-{uuid.uuid4().hex[:4]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cvss_v3_score=9.8,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_snooze_requires_analyst(client_factory, db_session, viewer_user, analyst_user, tenant_a):
    """UX-02-01 / T-10-03 / ASVS V4: viewer POST returns 403; analyst returns 200."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    analyst_client = client_factory(analyst_user)

    viewer_resp = await viewer_client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    assert viewer_resp.status_code == 403, viewer_resp.text

    analyst_resp = await analyst_client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    assert analyst_resp.status_code == 200, analyst_resp.text


@pytest.mark.asyncio
async def test_snooze_default_1h(client, db_session, tenant_a):
    """UX-02-01 / D-H-07: empty body POST → server sets `until` ≈ now+1h."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    before = datetime.now(UTC)
    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    after = datetime.now(UTC)
    assert resp.status_code == 200, resp.text

    until_str = resp.json()["until"]
    until = datetime.fromisoformat(until_str)
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)

    expected_lo = before + timedelta(hours=1) - timedelta(seconds=5)
    expected_hi = after + timedelta(hours=1) + timedelta(seconds=5)
    assert expected_lo <= until <= expected_hi, (
        f"Default until={until} outside [now+1h-5s, now+1h+5s]"
    )


@pytest.mark.asyncio
async def test_snooze_sets_status_suppressed(client, db_session, tenant_a):
    """UX-02-01 / D-B-04: after snooze the vuln status flips to SUPPRESSED."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    assert resp.status_code == 200, resp.text

    # GET should now show SUPPRESSED
    get_resp = await client.get(f"/api/v1/vulnerabilities/{v.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "SUPPRESSED"


@pytest.mark.asyncio
async def test_snooze_bounded_30_days(client, db_session, tenant_a):
    """UX-02-01 / T-10-02 / ASVS V11: until > now+30d returns 400."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    far_future = (datetime.now(UTC) + timedelta(days=31)).isoformat()
    resp = await client.post(
        f"/api/v1/vulnerabilities/{v.id}/snooze", json={"until": far_future}
    )
    assert resp.status_code == 400, resp.text
    assert "30 days" in resp.text


@pytest.mark.asyncio
async def test_snooze_until_in_past_rejected(client, db_session, tenant_a):
    """UX-02-01 / T-10-02: until <= now returns 400 (avoid no-op snoozes)."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={"until": past})
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_snooze_idor_blocked(
    client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b
):
    """UX-02-01 / T-10-01 / ASVS V4/V8: analyst from tenant A POSTing against
    tenant B's vuln id receives 404 (NOT 403 — rows you can't see don't exist)."""
    # Create vuln owned by tenant B
    foreign_vuln = _seed_open_vuln(tenant_b)
    db_session.add(foreign_vuln)
    await db_session.commit()

    attacker = client_factory(analyst_user)
    resp = await attacker.post(f"/api/v1/vulnerabilities/{foreign_vuln.id}/snooze", json={})
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_snooze_emits_audit_event(client, db_session, analyst_user, tenant_a):
    """UX-02-01 / T-10-04 / AUDIT-01: snooze emits a vuln.snooze audit row
    with the analyst's id and the vuln id."""
    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    assert resp.status_code == 200

    row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "vuln.snooze",
                AuditLog.resource_id == str(v.id),
            )
        )
    ).scalar_one_or_none()
    assert row is not None, "Expected a vuln.snooze AuditLog row"
    assert row.user_id == analyst_user.id
    assert row.resource_type == "vulnerability"


@pytest.mark.asyncio
async def test_snooze_fails_closed_when_audit_write_fails(
    client, db_session, monkeypatch, tenant_a
):
    """BL-04 / AUDIT-01 fail-closed: if the audit row cannot be written, the
    snooze MUST NOT commit. The previous behaviour was silent-success — the
    snooze landed without an audit trail, which is a compliance hazard.

    Patch the audit() helper to raise; the route's `await db.commit()` will
    not be reached and SQLAlchemy will roll back the UPDATE on the next
    transaction. The vuln status must remain OPEN.
    """
    from app import audit as audit_module

    v = _seed_open_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    async def _fail_audit(*args, **kwargs):
        raise RuntimeError("simulated audit write failure")

    monkeypatch.setattr(audit_module, "audit", _fail_audit)

    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/snooze", json={})
    # The mutation must not return success when its audit row can't land.
    assert resp.status_code >= 400, resp.text

    # Vuln status must remain OPEN — the snooze update was rolled back.
    await db_session.refresh(v)
    assert v.status == "OPEN", "Snooze must not commit when audit write fails"
