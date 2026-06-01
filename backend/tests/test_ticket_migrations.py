"""Phase 13 / Plan 01 — Wave 0 migration verification tests.

Validates that migrations 026/027/028 created the correct schema and that the
ORM models wire up properly to the new tables/columns.

Test 1: Ticket.sla_due_at is wired to the column — a Ticket linked to a
  Vulnerability with a non-null sla_due_at can have its sla_due_at set to the
  vuln's value (validates 027 column + model wiring; the SQL backfill itself is
  exercised by `alembic upgrade head` in Task 1's verify).

Test 2: TicketComment can be inserted with ticket_id + user_id + body and read
  back; ordering by created_at ASC returns rows chronologically ascending
  (validates ix_ticket_comments_ticket_created semantics and column wiring).

Test 3: TicketWatcher composite PK rejects a duplicate (ticket_id, user_id)
  insert with an IntegrityError — proving PK constraint from 028 is in effect.

Fixtures from conftest.py: db_session, tenant_a, analyst_user (provides
user_id for comments/watchers). The `_reset_engine_pool` autouse fixture in
conftest.py handles the asyncpg pool-per-loop issue (WR-14).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.assets.models import Asset
from app.ticketing.models import Ticket, TicketComment, TicketWatcher
from app.vulnerabilities.models import Vulnerability


# ── Seed helpers ──────────────────────────────────────────────────────────────


def _seed_asset(tenant_id) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04 LTS",
    )


def _seed_vuln(tenant_id, *, asset_id, sla_due_at=None) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-2026-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status="OPEN",
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        sla_due_at=sla_due_at,
        first_detected_at=now,
        last_seen_at=now,
    )


def _seed_ticket(tenant_id, *, vulnerability_id) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=f"https://asana.test/{uuid.uuid4().hex}",
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )


# ── Test 1: Ticket.sla_due_at column wiring ───────────────────────────────────


@pytest.mark.asyncio
async def test_ticket_sla_due_at_set_from_vuln(db_session, tenant_a):
    """Migration 027 adds sla_due_at to tickets.

    A ticket row's sla_due_at can be set to its linked vulnerability's
    sla_due_at. This validates the column exists, the ORM mapping is correct,
    and the value round-trips through flush+select. The production backfill
    (UPDATE tickets t SET sla_due_at = v.sla_due_at FROM vulnerabilities v
    WHERE t.vulnerability_id = v.id) is exercised by `alembic upgrade head`.
    """
    due = datetime.now(UTC) + timedelta(days=30)

    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=due)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vulnerability_id=vuln.id)
    ticket.sla_due_at = vuln.sla_due_at  # mirror what the backfill SQL does
    db_session.add(ticket)
    await db_session.flush()

    result = await db_session.execute(
        select(Ticket).where(Ticket.id == ticket.id)
    )
    fetched = result.scalar_one()
    assert fetched.sla_due_at is not None, "sla_due_at should be set"
    # Compare at second precision — DB may truncate sub-second.
    assert abs((fetched.sla_due_at - due).total_seconds()) < 2, (
        f"sla_due_at mismatch: expected ~{due}, got {fetched.sla_due_at}"
    )


# ── Test 2: TicketComment insert + chronological ordering ─────────────────────


@pytest.mark.asyncio
async def test_ticket_comment_insert_and_chronological_order(
    db_session, tenant_a, analyst_user
):
    """Migration 026 adds ticket_comments table with ix_ticket_comments_ticket_created.

    Inserts two comments for the same ticket and verifies:
    - both rows are readable via ORM
    - ORDER BY created_at ASC returns first-inserted first (ascending order)
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vulnerability_id=vuln.id)
    db_session.add(ticket)
    await db_session.flush()

    # Insert two comments with explicit created_at so ordering is deterministic.
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
    await db_session.flush()

    result = await db_session.execute(
        select(TicketComment)
        .where(TicketComment.ticket_id == ticket.id)
        .order_by(TicketComment.created_at.asc())
    )
    comments = result.scalars().all()
    assert len(comments) == 2, f"expected 2 comments, got {len(comments)}"
    assert comments[0].body == "First comment", (
        f"Expected 'First comment' first, got {comments[0].body!r}"
    )
    assert comments[1].body == "Second comment", (
        f"Expected 'Second comment' second, got {comments[1].body!r}"
    )


# ── Test 3: TicketWatcher composite PK rejects duplicates ─────────────────────


@pytest.mark.asyncio
async def test_ticket_watcher_duplicate_rejected_by_pk(
    db_session, tenant_a, analyst_user
):
    """Migration 028 adds ticket_watchers with PK (ticket_id, user_id).

    A second INSERT of the same (ticket_id, user_id) pair must raise an
    IntegrityError, proving the PrimaryKeyConstraint is in effect (T-13-03).
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    ticket = _seed_ticket(tenant_a, vulnerability_id=vuln.id)
    db_session.add(ticket)
    await db_session.flush()

    w1 = TicketWatcher(ticket_id=ticket.id, user_id=analyst_user.id)
    db_session.add(w1)
    await db_session.flush()  # first insert must succeed

    w2 = TicketWatcher(ticket_id=ticket.id, user_id=analyst_user.id)
    db_session.add(w2)
    with pytest.raises(IntegrityError):
        await db_session.flush()  # duplicate must raise IntegrityError
