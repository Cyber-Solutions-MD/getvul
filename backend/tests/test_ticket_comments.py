"""Phase 13 / Plan 03 — Task 2: comment routes tests.

Tests (comment route):

- POST /tickets/{id}/comments with valid body → 201, writes audit ticket.comment_added, persists
- GET /tickets/{id}/comments returns comments ascending by created_at
- blank body → 422
- body >10000 chars → 422
- cross-tenant {id} → 404

Fixtures from conftest.py: db_session, tenant_a, tenant_b, analyst_user, analyst_user_b,
client, client_factory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.ticketing.models import Ticket, TicketComment
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


async def _seed_group(db_session, tenant_id):
    """Seed: asset → vuln → ticket. Return (ticket, external_ticket_url)."""
    asset = _seed_asset(tenant_id)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_id, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    ticket = _seed_ticket(tenant_id, vulnerability_id=vuln.id, external_ticket_url=url)
    db_session.add(ticket)
    await db_session.flush()

    return ticket, url


# ── Test: POST /tickets/{id}/comments — 201, persisted, audit written ─────────


@pytest.mark.asyncio
async def test_post_comment_201_and_audit(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/comments with valid body returns 201, creates comment, writes audit."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()  # commit seed so the FastAPI session can see the rows

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "This is a test comment"},
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    data = response.json()
    assert "id" in data, "response must have 'id'"
    assert data["body"] == "This is a test comment"

    # Comment must be persisted in DB
    comments = (
        (await db_session.execute(select(TicketComment).where(TicketComment.ticket_id == ticket.id))).scalars().all()
    )
    assert len(comments) == 1, f"Expected 1 comment in DB, found {len(comments)}"
    assert comments[0].body == "This is a test comment"

    # Audit row must be written for ticket.comment_added
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "ticket.comment_added",
                    AuditLog.tenant_id == tenant_a,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) >= 1, "Expected at least one ticket.comment_added audit row"


# ── Test: GET /tickets/{id}/comments — ascending order ────────────────────────


@pytest.mark.asyncio
async def test_get_comments_ascending_order(db_session, tenant_a, analyst_user, client):
    """GET /tickets/{id}/comments returns comments sorted ascending by created_at."""
    ticket, url = await _seed_group(db_session, tenant_a)

    # Seed two comments with explicit created_at to ensure ordering is deterministic
    now = datetime.now(UTC)
    c1 = TicketComment(
        ticket_id=ticket.id,
        user_id=analyst_user.id,
        body="First comment",
        created_at=now - timedelta(seconds=10),
    )
    c2 = TicketComment(
        ticket_id=ticket.id,
        user_id=analyst_user.id,
        body="Second comment",
        created_at=now,
    )
    db_session.add_all([c1, c2])
    await db_session.commit()

    response = await client.get(f"/api/v1/tickets/{ticket.id}/comments")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    items = response.json()
    assert isinstance(items, list), "Response must be a list"
    assert len(items) == 2, f"Expected 2 comments, got {len(items)}"
    assert items[0]["body"] == "First comment", f"Expected 'First comment' first, got {items[0]['body']!r}"
    assert items[1]["body"] == "Second comment", f"Expected 'Second comment' second, got {items[1]['body']!r}"


# ── Test: POST blank body → 422 ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_comment_blank_body_422(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/comments with blank body → 422 (validator rejects whitespace-only)."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "   "},
    )
    assert response.status_code == 422, f"Expected 422 for blank body, got {response.status_code}"


# ── Test: POST body >10000 → 422 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_comment_too_long_422(db_session, tenant_a, analyst_user, client):
    """POST /tickets/{id}/comments with body >10000 chars → 422."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    long_body = "x" * 10001
    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": long_body},
    )
    assert response.status_code == 422, f"Expected 422 for too-long body, got {response.status_code}"


# ── Test: extra field → 422 (T-13-09 mass-assignment guard) ──────────────────


@pytest.mark.asyncio
async def test_post_comment_extra_field_422(db_session, tenant_a, analyst_user, client):
    """POST with an undeclared field → 422 (CommentCreate extra='forbid', T-13-09)."""
    ticket, url = await _seed_group(db_session, tenant_a)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/tickets/{ticket.id}/comments",
        json={"body": "legit note", "is_admin": True},
    )
    assert response.status_code == 422, f"Expected 422 rejecting extra field, got {response.status_code}"


# ── Test: cross-tenant {id} → 404 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_comment_cross_tenant_404(
    db_session, tenant_a, tenant_b, analyst_user, analyst_user_b, client_factory
):
    """POST /tickets/{id}/comments with a ticket from another tenant → 404 (IDOR guard)."""
    # Seed a ticket in tenant_b
    ticket_b, url_b = await _seed_group(db_session, tenant_b)
    await db_session.commit()

    # Attack as tenant_a analyst
    client_a = client_factory(analyst_user)
    async with client_a:
        response = await client_a.post(
            f"/api/v1/tickets/{ticket_b.id}/comments",
            json={"body": "Cross-tenant attack"},
        )
    assert response.status_code == 404, f"Expected 404 for cross-tenant comment, got {response.status_code}"
