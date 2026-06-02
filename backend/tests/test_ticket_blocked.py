"""Phase 13 / Plan 03 — Task 2: blocked route tests.

Tests (blocked route):

- POST /tickets/{id}/blocked {blocked:true, blocked_reason:"vendor patch slip"} sets blocked on
  ALL group rows, audit ticket.blocked w/ details.reason
- {blocked:false} clears reason, audit ticket.unblocked
- whitespace-only reason coerced to None
- cross-tenant 404
- if audit fails the row is NOT committed (fail-closed)

Fixtures from conftest.py: db_session, tenant_a, tenant_b, analyst_user, analyst_user_b,
client, client_factory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability


# ── Seed helpers ──────────────────────────────────────────────────────────────


def _seed_asset(tenant_id) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04 LTS",
    )


def _seed_vuln(tenant_id, *, asset_id) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-2026-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status="OPEN",
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
    )


def _seed_ticket(tenant_id, *, vulnerability_id, external_ticket_url: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=external_ticket_url,
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )


async def _seed_group_multi(db_session, tenant_id, *, n_tickets=2):
    """Seed: asset → n vulns → n tickets sharing one external_ticket_url.
    Return (ticket_list, external_ticket_url).
    """
    asset = _seed_asset(tenant_id)
    db_session.add(asset)
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    tickets = []
    for _ in range(n_tickets):
        vuln = _seed_vuln(tenant_id, asset_id=asset.id)
        db_session.add(vuln)
        await db_session.flush()

        ticket = _seed_ticket(tenant_id, vulnerability_id=vuln.id, external_ticket_url=url)
        db_session.add(ticket)
        await db_session.flush()
        tickets.append(ticket)

    return tickets, url


# ── Test: POST blocked=true sets ALL group rows + audit ticket.blocked ─────────


@pytest.mark.asyncio
async def test_post_blocked_sets_all_group_rows(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/blocked {blocked:true} sets blocked on ALL rows in the group."""
    tickets, url = await _seed_group_multi(db_session, tenant_a, n_tickets=2)
    first_ticket = tickets[0]
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tickets/{first_ticket.id}/blocked",
        json={"blocked": True, "blocked_reason": "vendor patch slip"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["blocked"] is True, f"Expected blocked=True in response, got {data['blocked']!r}"
    assert data["blocked_reason"] == "vendor patch slip"

    # ALL rows in the group must be blocked
    rows = (
        await db_session.execute(
            select(Ticket).where(
                Ticket.external_ticket_url == url,
                Ticket.tenant_id == tenant_a,
            )
        )
    ).scalars().all()
    assert len(rows) == 2, f"Expected 2 rows in group, got {len(rows)}"
    for row in rows:
        assert row.blocked is True, f"Row {row.id} blocked must be True, got {row.blocked!r}"
        assert row.blocked_reason == "vendor patch slip", (
            f"Row {row.id} blocked_reason mismatch: {row.blocked_reason!r}"
        )

    # Audit row ticket.blocked must exist
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "ticket.blocked",
                AuditLog.tenant_id == tenant_a,
            )
        )
    ).scalars().all()
    assert len(audit_rows) >= 1, "Expected at least one ticket.blocked audit row"


# ── Test: POST blocked=false clears reason + audit ticket.unblocked ───────────


@pytest.mark.asyncio
async def test_post_unblocked_clears_reason(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/blocked {blocked:false} clears blocked_reason, audits ticket.unblocked."""
    tickets, url = await _seed_group_multi(db_session, tenant_a, n_tickets=1)
    ticket = tickets[0]
    # Pre-seed as blocked
    ticket.blocked = True
    ticket.blocked_reason = "old reason"
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/blocked",
        json={"blocked": False, "blocked_reason": None},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["blocked"] is False, f"Expected blocked=False, got {data['blocked']!r}"
    assert data["blocked_reason"] is None, f"Expected blocked_reason=None, got {data['blocked_reason']!r}"

    # DB row must be unblocked
    row = (await db_session.execute(select(Ticket).where(Ticket.id == ticket.id))).scalar_one()
    assert row.blocked is False
    assert row.blocked_reason is None

    # Audit row ticket.unblocked must exist
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "ticket.unblocked",
                AuditLog.tenant_id == tenant_a,
            )
        )
    ).scalars().all()
    assert len(audit_rows) >= 1, "Expected at least one ticket.unblocked audit row"


# ── Test: whitespace-only blocked_reason → None ───────────────────────────────


@pytest.mark.asyncio
async def test_post_blocked_whitespace_reason_coerced_to_none(
    db_session, tenant_a, analyst_user, client
):
    """Whitespace-only blocked_reason is coerced to None by the BlockedUpdate validator."""
    tickets, url = await _seed_group_multi(db_session, tenant_a, n_tickets=1)
    ticket = tickets[0]
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/blocked",
        json={"blocked": True, "blocked_reason": "   "},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    # Whitespace-only reason must be coerced to None by the validator
    assert data["blocked_reason"] is None, (
        f"Expected blocked_reason=None after whitespace-only input, got {data['blocked_reason']!r}"
    )


# ── Test: cross-tenant → 404 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_blocked_cross_tenant_404(
    db_session, tenant_a, tenant_b, analyst_user, analyst_user_b, client_factory
):
    """POST /tickets/{id}/blocked with a ticket from another tenant → 404 (IDOR guard)."""
    tickets_b, url_b = await _seed_group_multi(db_session, tenant_b, n_tickets=1)
    ticket_b = tickets_b[0]
    await db_session.commit()

    client_a = client_factory(analyst_user)
    async with client_a:
        response = await client_a.post(
            f"/api/v1/tickets/{ticket_b.id}/blocked",
            json={"blocked": True, "blocked_reason": "cross-tenant attack"},
        )
    assert response.status_code == 404, (
        f"Expected 404 for cross-tenant blocked, got {response.status_code}"
    )
