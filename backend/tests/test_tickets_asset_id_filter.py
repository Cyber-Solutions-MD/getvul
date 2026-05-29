"""Phase 12 / Plan 02 — UX-04-02 backend tests for GET /api/v1/tickets?asset_id=<uuid>.

Covers:
  - asset_id narrows the result set to tickets whose vuln is on that asset
  - omitting asset_id returns the full tenant ticket list (no regression)
  - asset_id with an unknown uuid returns an empty page (no 500, no leak)

Uses the project canonical inline-seed pattern (db_session, tenant_a,
client). The plan's spec referenced fictional factory fixtures that do not
exist; the project uses inline _seed_* helpers instead — adaptation
documented in SUMMARY.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.assets.models import Asset
from app.db.session import engine
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability


@pytest_asyncio.fixture(autouse=True)
async def _reset_engine_pool():
    # See test_assets_tags_and_os_family.py for the rationale.
    await engine.dispose()
    yield


def _seed_asset(tenant_id, hostname: str) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, os_name="Ubuntu 22.04 LTS")


def _seed_vuln(tenant_id, *, asset_id, cve_id: str | None = None) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id or f"CVE-2026-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status="OPEN",
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
    )


def _seed_ticket(tenant_id, *, vulnerability_id, external_ticket_url: str) -> Ticket:
    # external_ticket_id must be unique per (tenant, provider) — use a uuid.
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=external_ticket_url,
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_tickets_filter_by_asset_id_returns_matching_only(
    client, db_session, tenant_a
):
    """asset_id narrows the response to tickets whose vuln is on that asset."""
    a1 = _seed_asset(tenant_a, "host-a")
    a2 = _seed_asset(tenant_a, "host-b")
    db_session.add_all([a1, a2])
    await db_session.flush()

    v1 = _seed_vuln(tenant_a, asset_id=a1.id, cve_id="CVE-2026-A001")
    v2 = _seed_vuln(tenant_a, asset_id=a2.id, cve_id="CVE-2026-A002")
    db_session.add_all([v1, v2])
    await db_session.flush()

    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v1.id, external_ticket_url="https://jira/A-1"))
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v2.id, external_ticket_url="https://jira/A-2"))
    await db_session.commit()

    r = await client.get(f"/api/v1/tickets?asset_id={a1.id}")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    urls = {i["external_ticket_url"] for i in items}
    assert urls == {"https://jira/A-1"}, f"expected only A-1, got {urls}"


@pytest.mark.asyncio
async def test_tickets_no_asset_id_returns_all_tenant_tickets(
    client, db_session, tenant_a
):
    """No asset_id → the full tenant list (regression guard for existing behaviour)."""
    a = _seed_asset(tenant_a, "host-x")
    db_session.add(a)
    await db_session.flush()

    v = _seed_vuln(tenant_a, asset_id=a.id, cve_id="CVE-2026-B001")
    db_session.add(v)
    await db_session.flush()

    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v.id, external_ticket_url="https://jira/B-1"))
    await db_session.commit()

    r = await client.get("/api/v1/tickets")
    assert r.status_code == 200
    urls = {i["external_ticket_url"] for i in r.json()["items"]}
    assert "https://jira/B-1" in urls


@pytest.mark.asyncio
async def test_tickets_asset_id_unknown_returns_empty(client):
    """Unknown asset_id → empty page (no 500, no row leak)."""
    r = await client.get(
        "/api/v1/tickets?asset_id=00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_tickets_asset_id_excludes_other_assets_in_same_tenant(
    client, db_session, tenant_a
):
    """Sanity check: tickets on sibling assets in the SAME tenant are excluded
    when asset_id is set. Guards against the subquery accidentally widening
    via a missing AND.
    """
    a1 = _seed_asset(tenant_a, "host-sibling-1")
    a2 = _seed_asset(tenant_a, "host-sibling-2")
    db_session.add_all([a1, a2])
    await db_session.flush()

    v1 = _seed_vuln(tenant_a, asset_id=a1.id, cve_id="CVE-2026-C001")
    v2 = _seed_vuln(tenant_a, asset_id=a2.id, cve_id="CVE-2026-C002")
    db_session.add_all([v1, v2])
    await db_session.flush()

    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v1.id, external_ticket_url="https://jira/C-1"))
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v2.id, external_ticket_url="https://jira/C-2"))
    await db_session.commit()

    r = await client.get(f"/api/v1/tickets?asset_id={a2.id}")
    assert r.status_code == 200
    urls = {i["external_ticket_url"] for i in r.json()["items"]}
    assert urls == {"https://jira/C-2"}, f"expected only C-2, got {urls}"
