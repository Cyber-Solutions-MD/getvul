"""Phase 10 / Plan 01 — Wave 0 RED.

Behaviour under test: POST /api/v1/vulnerabilities/{id}/unsnooze must:
  - require ANALYST role
  - filter by user.tenant_id (IDOR)
  - reset vuln status to 'OPEN'
  - be idempotent (re-running on an OPEN vuln returns 200)
  - emit a vuln.unsnooze audit event (distinct from vuln.snooze)

This route backs the D-H-08 Undo toast (REQ UX-02-01). Separate route from
snooze for audit-clarity: auditors can reconstruct the snooze/unsnooze
sequence from the action stream.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.audit import AuditLog
from app.vulnerabilities.models import Vulnerability


def _seed_suppressed_vuln(tenant_id) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-US-{uuid.uuid4().hex[:4]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="SUPPRESSED",
        cvss_v3_score=9.0,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_unsnooze_requires_analyst(client_factory, db_session, viewer_user, analyst_user, tenant_a):
    """UX-02-01 / ASVS V4: viewer 403; analyst 200."""
    v = _seed_suppressed_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    viewer = client_factory(viewer_user)
    analyst = client_factory(analyst_user)

    vr = await viewer.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    assert vr.status_code == 403, vr.text

    ar = await analyst.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    assert ar.status_code == 200, ar.text


@pytest.mark.asyncio
async def test_unsnooze_resets_status_to_open(client, db_session, tenant_a):
    """UX-02-01 / D-H-08: SUPPRESSED → OPEN after unsnooze."""
    v = _seed_suppressed_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    assert resp.status_code == 200, resp.text

    get_resp = await client.get(f"/api/v1/vulnerabilities/{v.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "OPEN"


@pytest.mark.asyncio
async def test_unsnooze_idor_blocked(client_factory, db_session, analyst_user, analyst_user_b, tenant_a, tenant_b):
    """UX-02-01 / T-10-04b / ASVS V4/V8: cross-tenant id returns 404."""
    foreign = _seed_suppressed_vuln(tenant_b)
    db_session.add(foreign)
    await db_session.commit()

    attacker = client_factory(analyst_user)
    resp = await attacker.post(f"/api/v1/vulnerabilities/{foreign.id}/unsnooze")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_unsnooze_no_op_when_already_open(client, db_session, tenant_a):
    """UX-02-01 / D-H-08: idempotent — re-firing on an already-OPEN vuln
    returns 200 (the 8s Undo toast may dispatch twice if user double-clicks)."""
    now = datetime.now(UTC)
    v = Vulnerability(
        tenant_id=tenant_a,
        cve_id="CVE-IDEMP",
        severity="HIGH",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )
    db_session.add(v)
    await db_session.commit()

    r1 = await client.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    r2 = await client.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_unsnooze_emits_audit_event(client, db_session, analyst_user, tenant_a):
    """UX-02-01 / T-10-04a / AUDIT-01: distinct event_type 'vuln.unsnooze'."""
    v = _seed_suppressed_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    resp = await client.post(f"/api/v1/vulnerabilities/{v.id}/unsnooze")
    assert resp.status_code == 200

    row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "vuln.unsnooze",
                AuditLog.resource_id == str(v.id),
            )
        )
    ).scalar_one_or_none()
    assert row is not None, "Expected a vuln.unsnooze AuditLog row"
    assert row.user_id == analyst_user.id
    assert row.resource_type == "vulnerability"
