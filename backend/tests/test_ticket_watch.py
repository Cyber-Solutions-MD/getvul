"""Phase 13 / Plan 03 — Task 3: watch routes + ticket detail + bulk-action blocked tests.

Tests (watch):
- POST /tickets/{id}/watch creates a watcher row, 200; re-POST is a no-op (still one row, 200)
- DELETE /tickets/{id}/watch removes it, 200; DELETE again is a no-op 200
- cross-tenant {id} → 404
- each writes audit ticket.watch / ticket.unwatch

Tests (detail):
- GET /tickets/{id} returns the resolved logical ticket {id, provider, external_ticket_url,
  external_status, blocked, blocked_reason, sla_due_at, assignee, reporter, title, linked_vulns,
  watchers} for the group; reporter is the ticket creator (or null); cross-tenant 404

Tests (bulk blocked):
- POST /tickets/bulk-action {action:"block", external_ticket_urls:[...], blocked_reason:"..."}
  sets blocked on all listed groups + audits each

Fixtures from conftest.py: db_session, tenant_a, tenant_b, analyst_user, analyst_user_b,
client, client_factory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.assets.models import Asset
from app.audit import AuditLog
from app.ticketing.models import Ticket, TicketWatcher
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


def _seed_ticket(tenant_id, *, vulnerability_id, external_ticket_url: str, created_by_user_id=None) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=external_ticket_url,
        external_status="open",
        ticket_created_at=datetime.now(UTC),
        created_by_user_id=created_by_user_id,
    )


async def _seed_group(db_session, tenant_id, *, user_id=None):
    """Seed: asset → vuln → ticket. Return (ticket, external_ticket_url)."""
    asset = _seed_asset(tenant_id)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_id, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    ticket = _seed_ticket(
        tenant_id,
        vulnerability_id=vuln.id,
        external_ticket_url=url,
        created_by_user_id=user_id,
    )
    db_session.add(ticket)
    await db_session.flush()

    return ticket, url


# ── Test: POST watch → 200 + idempotent ───────────────────────────────────────


@pytest.mark.asyncio
async def test_post_watch_creates_row_and_idempotent(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/watch creates a watcher row (200); re-POST is a no-op (still 200)."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    # First watch
    response = await client.post(f"/api/v1/tickets/{ticket.id}/watch")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("watching") is True, f"Expected watching=True, got {data!r}"

    # Re-watch — must still return 200 (idempotent, D-W-02)
    response2 = await client.post(f"/api/v1/tickets/{ticket.id}/watch")
    assert response2.status_code == 200, f"Expected 200 on re-watch, got {response2.status_code}"
    data2 = response2.json()
    assert data2.get("watching") is True

    # Only ONE watcher row must exist (PK constraint prevents duplicates)
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(TicketWatcher)
            .where(
                TicketWatcher.ticket_id == ticket.id,
                TicketWatcher.user_id == analyst_user.id,
            )
        )
    ).scalar_one()
    assert count == 1, f"Expected exactly 1 watcher row, got {count}"


# ── Test: DELETE watch → 200 + idempotent ─────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_watch_removes_row_and_idempotent(db_session, tenant_a, analyst_user, client):
    """DELETE /tickets/{id}/watch removes the watcher (200); re-DELETE is a no-op (200)."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    # First watch, then unwatch
    await client.post(f"/api/v1/tickets/{ticket.id}/watch")

    response = await client.delete(f"/api/v1/tickets/{ticket.id}/watch")
    assert response.status_code == 200, f"Expected 200 on unwatch, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("watching") is False, f"Expected watching=False, got {data!r}"

    # Re-delete is a no-op (D-W-02)
    response2 = await client.delete(f"/api/v1/tickets/{ticket.id}/watch")
    assert response2.status_code == 200, f"Expected 200 on re-delete, got {response2.status_code}"
    data2 = response2.json()
    assert data2.get("watching") is False


# ── Test: watch/unwatch audit rows ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_watch_writes_audit(db_session, tenant_a, analyst_user, client):
    """POST /watch and DELETE /watch each write audit ticket.watch / ticket.unwatch."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    await client.post(f"/api/v1/tickets/{ticket.id}/watch")
    await client.delete(f"/api/v1/tickets/{ticket.id}/watch")

    watch_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ticket.watch",
                    AuditLog.tenant_id == tenant_a,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(watch_audits) >= 1, "Expected at least one ticket.watch audit row"

    unwatch_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ticket.unwatch",
                    AuditLog.tenant_id == tenant_a,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(unwatch_audits) >= 1, "Expected at least one ticket.unwatch audit row"


# ── Test: cross-tenant → 404 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_watch_cross_tenant_404(
    db_session, tenant_a, tenant_b, analyst_user, analyst_user_b, client_factory
):
    """POST /tickets/{id}/watch with a ticket from another tenant → 404 (IDOR guard)."""
    ticket_b, url_b = await _seed_group(db_session, tenant_b)
    await db_session.commit()

    client_a = client_factory(analyst_user)
    async with client_a:
        response = await client_a.post(f"/api/v1/tickets/{ticket_b.id}/watch")
    assert response.status_code == 404, f"Expected 404 for cross-tenant watch, got {response.status_code}"


# ── Test: GET /tickets/{id} detail ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ticket_detail_returns_required_fields(db_session, tenant_a, analyst_user, client):
    """GET /tickets/{id} returns logical ticket with required fields."""
    ticket, url = await _seed_group(db_session, tenant_a, user_id=analyst_user.id)
    await db_session.commit()

    response = await client.get(f"/api/v1/tickets/{ticket.id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    # Required fields per plan spec (UX-05-04)
    required_keys = [
        "id",
        "provider",
        "external_ticket_url",
        "external_status",
        "blocked",
        "blocked_reason",
        "sla_due_at",
        "assignee",
        "reporter",
        "linked_vulns",
        "watchers",
    ]
    for key in required_keys:
        assert key in data, f"Detail response missing key: {key!r}"

    assert data["external_ticket_url"] == url
    # CR-06: provider emitted lowercased at the API boundary (stored uppercase).
    assert data["provider"] == "asana"
    assert data["blocked"] is False
    assert isinstance(data["linked_vulns"], list), "linked_vulns must be a list"
    assert isinstance(data["watchers"], list), "watchers must be a list"

    # Each watcher must carry role: "watcher" (D-W-04 seam)
    for w in data["watchers"]:
        assert "role" in w, f"Watcher {w!r} missing 'role' key"
        assert w["role"] == "watcher"


@pytest.mark.asyncio
async def test_get_ticket_detail_cross_tenant_404(
    db_session, tenant_a, tenant_b, analyst_user, analyst_user_b, client_factory
):
    """GET /tickets/{id} with a ticket from another tenant → 404."""
    ticket_b, url_b = await _seed_group(db_session, tenant_b)
    await db_session.commit()

    client_a = client_factory(analyst_user)
    async with client_a:
        response = await client_a.get(f"/api/v1/tickets/{ticket_b.id}")
    assert response.status_code == 404, f"Expected 404 for cross-tenant detail, got {response.status_code}"


# ── Test: bulk-action block ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_action_block_sets_group_blocked(db_session, tenant_a, analyst_user, client):
    """POST /tickets/bulk-action {action:'block', ...} sets blocked on all listed groups."""
    ticket1, url1 = await _seed_group(db_session, tenant_a)
    ticket2, url2 = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    response = await client.post(
        "/api/v1/tickets/bulk-action",
        json={
            "action": "block",
            "ticket_urls": [url1, url2],
            "blocked_reason": "bulk block test",
        },
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify audit rows were created for both groups
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ticket.blocked",
                    AuditLog.tenant_id == tenant_a,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) >= 2, f"Expected >= 2 ticket.blocked audit rows for 2 groups, got {len(audit_rows)}"
