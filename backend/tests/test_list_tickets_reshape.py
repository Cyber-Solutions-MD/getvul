"""Phase 13 / Plan 03 — Task 1: list_tickets reshape + recompute_ticket_sla tests.

Tests:

Test 1: list_tickets result items each include keys `blocked` (bool), `blocked_reason`,
  `sla_due_at` (group MIN ISO string or null), `external_status`.

Test 2: a group with two rows where one vuln has earlier sla_due_at reports the MIN
  (soonest) as the group sla_due_at.

Test 3: recompute_ticket_sla(db, external_ticket_url, tenant_id) sets every row in
  the group to MIN(linked vuln.sla_due_at); null when no linked vuln has sla_due_at.

Fixtures from conftest.py: db_session, tenant_a, analyst_user.
The `_reset_engine_pool` autouse fixture in conftest.py handles asyncpg pool-per-loop (WR-14).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.ticketing.models import Ticket
from app.ticketing.service import list_tickets, recompute_ticket_sla
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


def _seed_ticket(tenant_id, *, vulnerability_id, external_ticket_url: str, sla_due_at=None) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=external_ticket_url,
        external_status="open",
        ticket_created_at=datetime.now(UTC),
        sla_due_at=sla_due_at,
    )


# ── Test 1: list_tickets items include blocked/blocked_reason/sla_due_at/external_status ──


@pytest.mark.asyncio
async def test_list_tickets_includes_new_fields(db_session, tenant_a):
    """list_tickets items include blocked, blocked_reason, sla_due_at, external_status.

    Each item in the result must have these keys. When the group has one ticket
    with blocked=False and no sla_due_at, blocked must be False and sla_due_at None.
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    ticket = _seed_ticket(tenant_a, vulnerability_id=vuln.id, external_ticket_url=url)
    db_session.add(ticket)
    await db_session.flush()

    result = await list_tickets(db_session, tenant_a)
    items = result["items"]
    assert len(items) >= 1, "Expected at least one item"

    # Find our ticket
    our_items = [i for i in items if i["external_ticket_url"] == url]
    assert len(our_items) == 1, f"Expected exactly one item for URL {url}"
    item = our_items[0]

    # All required keys must be present
    assert "blocked" in item, "item must have 'blocked' key"
    assert "blocked_reason" in item, "item must have 'blocked_reason' key"
    assert "sla_due_at" in item, "item must have 'sla_due_at' key"
    assert "external_status" in item, "item must have 'external_status' key"

    # Values for a non-blocked, no-SLA ticket
    assert item["blocked"] is False, f"expected blocked=False, got {item['blocked']!r}"
    assert item["blocked_reason"] is None, f"expected blocked_reason=None, got {item['blocked_reason']!r}"
    assert item["sla_due_at"] is None, f"expected sla_due_at=None, got {item['sla_due_at']!r}"
    assert item["external_status"] == "open", f"expected external_status='open', got {item['external_status']!r}"


# ── Test 2: group sla_due_at is MIN across rows ───────────────────────────────


@pytest.mark.asyncio
async def test_list_tickets_sla_due_at_is_group_min(db_session, tenant_a):
    """A group with two ticket rows shows the soonest (MIN) sla_due_at.

    Two vulns link to the same external_ticket_url. Vuln A has sla_due_at = 30 days
    from now; Vuln B has sla_due_at = 10 days from now (sooner). The group's
    sla_due_at reported by list_tickets must be vuln B's value (the MIN).
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    now = datetime.now(UTC)
    later = now + timedelta(days=30)
    sooner = now + timedelta(days=10)

    vuln_a = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=later)
    vuln_b = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=sooner)
    db_session.add_all([vuln_a, vuln_b])
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    t_a = _seed_ticket(tenant_a, vulnerability_id=vuln_a.id, external_ticket_url=url, sla_due_at=later)
    t_b = _seed_ticket(tenant_a, vulnerability_id=vuln_b.id, external_ticket_url=url, sla_due_at=sooner)
    db_session.add_all([t_a, t_b])
    await db_session.flush()

    result = await list_tickets(db_session, tenant_a)
    items = result["items"]

    our_items = [i for i in items if i["external_ticket_url"] == url]
    assert len(our_items) == 1, f"Expected exactly one group for URL {url}"
    item = our_items[0]

    assert item["sla_due_at"] is not None, "sla_due_at must not be None for a group with SLA"
    # Parse the ISO string and compare with sooner (the MIN)
    from datetime import timezone
    group_sla = datetime.fromisoformat(item["sla_due_at"].replace("Z", "+00:00"))
    # Confirm it matches sooner (within 2s precision)
    assert abs((group_sla - sooner).total_seconds()) < 2, (
        f"Expected group sla_due_at ≈ sooner ({sooner}), got {group_sla}"
    )
    assert (group_sla - later).total_seconds() < 0, (
        "group sla_due_at should be BEFORE the later value"
    )


# ── Test 3: recompute_ticket_sla sets group rows to MIN(vuln.sla_due_at) ─────


@pytest.mark.asyncio
async def test_recompute_ticket_sla_sets_group_min(db_session, tenant_a):
    """recompute_ticket_sla sets every row in the group to MIN(linked vuln.sla_due_at).

    Two ticket rows share an external_ticket_url. Vuln A has sla_due_at = 60d,
    Vuln B has sla_due_at = 20d (soonest). After recompute_ticket_sla, BOTH rows
    must have sla_due_at = Vuln B's value (the group MIN). If no linked vuln has
    sla_due_at, all rows are set to NULL.
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    now = datetime.now(UTC)
    far = now + timedelta(days=60)
    near = now + timedelta(days=20)

    vuln_a = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=far)
    vuln_b = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=near)
    db_session.add_all([vuln_a, vuln_b])
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    t_a = _seed_ticket(tenant_a, vulnerability_id=vuln_a.id, external_ticket_url=url, sla_due_at=far)
    t_b = _seed_ticket(tenant_a, vulnerability_id=vuln_b.id, external_ticket_url=url, sla_due_at=near)
    db_session.add_all([t_a, t_b])
    await db_session.flush()

    # Call recompute_ticket_sla — should set BOTH rows to near (MIN)
    await recompute_ticket_sla(db_session, url, tenant_a)
    await db_session.flush()

    rows = (
        await db_session.execute(
            select(Ticket).where(
                Ticket.external_ticket_url == url,
                Ticket.tenant_id == tenant_a,
            )
        )
    ).scalars().all()

    assert len(rows) == 2, f"Expected 2 ticket rows, got {len(rows)}"
    for row in rows:
        assert row.sla_due_at is not None, f"Row {row.id} sla_due_at should not be None after recompute"
        assert abs((row.sla_due_at - near).total_seconds()) < 2, (
            f"Row {row.id}: expected sla_due_at ≈ near ({near}), got {row.sla_due_at}"
        )


@pytest.mark.asyncio
async def test_recompute_ticket_sla_null_when_no_vuln_sla(db_session, tenant_a):
    """recompute_ticket_sla sets rows to NULL when no linked vuln has sla_due_at."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=None)
    db_session.add(vuln)
    await db_session.flush()

    url = f"https://asana.test/{uuid.uuid4().hex}"
    # Pre-seed with a non-None sla_due_at to ensure recompute actually clears it
    ticket = _seed_ticket(
        tenant_a,
        vulnerability_id=vuln.id,
        external_ticket_url=url,
        sla_due_at=datetime.now(UTC) + timedelta(days=5),
    )
    db_session.add(ticket)
    await db_session.flush()

    await recompute_ticket_sla(db_session, url, tenant_a)
    await db_session.flush()

    row = (
        await db_session.execute(
            select(Ticket).where(Ticket.id == ticket.id)
        )
    ).scalar_one()

    assert row.sla_due_at is None, (
        f"Expected sla_due_at=None after recompute with no-SLA vuln, got {row.sla_due_at}"
    )
