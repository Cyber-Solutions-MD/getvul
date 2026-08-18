"""Phase 38 Plans 01-02 (CAMP-01/CAMP-02/CAMP-04) -- campaign persistence
tracer slice + per-owner bulk ticketing.

TRACER SLICE (Plan 01): migration + model + race-safe get-or-create (D-11) +
list/detail read with compute-on-read progress (D-07/D-18) + audit (D-15) +
RBAC (D-16).

PLAN 02: per-owner bulk-create/assign tickets (CAMP-02) -- re-carves
`create_remediation_ticket()`'s single-ticket-for-the-whole-group shape into
one ticket PER OWNER, reusing owner routing verbatim (D-05), adopting
already-ticketed findings instead of duplicating (D-06), landing owner-less
findings in an unassigned bucket (D-08), and setting campaign tickets'
`created_by_rule` to the bare `remediation_id` so a later `per_remediation`
automation rule's own dedup check sees them (D-20 / Pitfall 1). Full
progress/MTTR + lifecycle (CAMP-03, Plan 03) is still out of scope here.

Task 2: DB-level partial-unique-index proof for D-11 (exactly one ACTIVE
campaign per (tenant_id, remediation_id); a CLOSED campaign's remediation_id
accepts a fresh active campaign).

Task 3: get-or-create endpoint (audit-once, D-11 reopen semantics), the
corrected compute-on-read progress filter (Pitfall 2 regression guard),
the zero-member zero-guard (Pitfall 5), RBAC (D-16), and tenant scoping
(T-38-01 IDOR defense).

Uses the project's canonical inline-seed + client_factory pattern
(test_asset_groups.py / test_asset_owner_reassign.py) -- an ad hoc
`CurrentUser` (not persisted to the `users` table) stands in for "a tenant_b
analyst" since `client_factory`'s dependency override bypasses
`get_current_user` entirely.

The bulk-assign tests reuse `test_ticketing_dispatch.py`'s `FakeTicketingClient`
shape (records `.create()` calls, returns a provider-shaped fake URL per call
so `_extract_ref`'s "last path segment" parsing is exercised for real) --
scoped locally here since campaigns is a new caller, not a new provider.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.assets.models import Asset
from app.audit import AuditLog
from app.auth.schemas import CurrentUser
from app.campaigns.models import Campaign
from app.campaigns.service import bulk_create_campaign_tickets
from app.ticketing.models import Ticket
from app.vulnerabilities.models import Vulnerability

_FAKE_URL_BASE = "https://acme.atlassian.net/browse"


class FakeTicketingClient:
    """Records every `.create()` call; returns a distinct provider-shaped
    fake URL per call (mirrors `test_ticketing_dispatch.py::FakeTicketingClient`)."""

    def __init__(self) -> None:
        self.created: list[tuple[str, str, dict]] = []
        self._seq = 0

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        self._seq += 1
        self.created.append((title, body, kwargs))
        return f"{_FAKE_URL_BASE}/ref-{self._seq}"


def _make_campaign(tenant_id: uuid.UUID, remediation_id: str, **overrides: Any) -> Campaign:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "remediation_id": remediation_id,
    }
    defaults.update(overrides)
    return Campaign(**defaults)


def _seed_vuln(
    tenant_id: uuid.UUID,
    remediation_id: str,
    *,
    status: str = "OPEN",
    asset_id: uuid.UUID | None = None,
    severity: str = "HIGH",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-CAMP-{uuid.uuid4().hex[:6]}",
        severity=severity,
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        remediation_id=remediation_id,
        first_detected_at=now - timedelta(days=3),
        last_seen_at=now,
    )


def _seed_asset(tenant_id: uuid.UUID, *, humaans_email: str | None = None) -> Asset:
    """A minimal asset -- `mdm_details.humaans_email` is the SAME field
    `ticketing/service.py:614` reads for owner derivation (D-05)."""
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04",
        mdm_details={"humaans_email": humaans_email} if humaans_email else None,
    )


def _analyst_user_for(tenant_id: uuid.UUID) -> CurrentUser:
    """An ad hoc ANALYST `CurrentUser` scoped to `tenant_id` -- no DB row
    needed since `client_factory`'s dependency override bypasses
    `get_current_user` entirely (mirrors test_asset_groups.py's
    `_admin_user_for`)."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"analyst-{uuid.uuid4().hex[:8]}@test.local",
        role="ANALYST",
    )


# ── Task 2: D-11 partial unique index (DB-constraint proof) ─────────────────


@pytest.mark.asyncio
async def test_campaign_unique_active_index(db_session, tenant_a):
    """A second ACTIVE (closed_at IS NULL) campaign on the same
    (tenant_id, remediation_id) raises IntegrityError -- the D-11 partial
    unique index (`uq_campaign_active_remediation`, migration 049) is
    enforced at the DB level, not just in application code."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    c1 = _make_campaign(tenant_a, remediation_id)
    db_session.add(c1)
    await db_session.flush()  # first insert must succeed

    c2 = _make_campaign(tenant_a, remediation_id)
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        await db_session.flush()  # duplicate ACTIVE row must raise


@pytest.mark.asyncio
async def test_new_campaign_after_close(db_session, tenant_a):
    """A CLOSED campaign's remediation_id can get a fresh active campaign --
    the partial index only guards rows WHERE closed_at IS NULL (D-13
    auto-complete / D-17 manual-close-is-sticky both require this
    remediation_id to stay re-launchable after a prior campaign closes)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    closed = _make_campaign(
        tenant_a,
        remediation_id,
        closed_at=datetime.now(UTC) - timedelta(days=1),
        close_trigger="manual",
    )
    db_session.add(closed)
    await db_session.flush()

    reopened = _make_campaign(tenant_a, remediation_id)
    db_session.add(reopened)
    await db_session.flush()  # must NOT raise -- the closed row doesn't block a new active one

    assert reopened.closed_at is None
    assert reopened.id != closed.id


# ── Task 3: get-or-create endpoint + audit (D-11/D-15) ───────────────────────


@pytest.mark.asyncio
async def test_create_campaign_new(client_factory, db_session, tenant_a, analyst_user):
    """POST with a fresh remediation_id -> 200, persists a row,
    already_existed=false, and writes exactly one campaign.create audit row."""
    await db_session.commit()  # tenant_a + analyst_user must be visible to the app's own session (FK)
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["remediation_id"] == remediation_id
    assert body["already_existed"] is False
    campaign_id = body["id"]

    r = await analyst_client.get("/api/v1/campaigns")
    assert r.status_code == 200, r.text
    assert any(c["id"] == campaign_id for c in r.json())

    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_a,
                    AuditLog.action == "campaign.create",
                    AuditLog.resource_id == campaign_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1, f"expected exactly 1 campaign.create audit row, got {len(audit_rows)}"


@pytest.mark.asyncio
async def test_create_campaign_reopens_existing(client_factory, db_session, tenant_a, analyst_user):
    """POST again on the same active remediation_id -> 200,
    already_existed=true, NO new row, NO second audit row (D-11)."""
    await db_session.commit()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    analyst_client = client_factory(analyst_user)
    r1 = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r1.status_code == 200, r1.text
    campaign_id = r1.json()["id"]
    assert r1.json()["already_existed"] is False

    r2 = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r2.status_code == 200, r2.text
    assert r2.json()["already_existed"] is True
    assert r2.json()["id"] == campaign_id

    row_count = (
        await db_session.execute(
            select(func.count())
            .select_from(Campaign)
            .where(Campaign.tenant_id == tenant_a, Campaign.remediation_id == remediation_id)
        )
    ).scalar_one()
    assert row_count == 1, f"expected exactly 1 campaigns row, got {row_count}"

    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_a,
                    AuditLog.action == "campaign.create",
                    AuditLog.resource_id == campaign_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1, f"expected exactly 1 campaign.create audit row (no second), got {len(audit_rows)}"


# ── Task 3: compute-on-read progress (D-07/D-18, Pitfall 2/5 regression) ────


@pytest.mark.asyncio
async def test_progress_counts_include_remediated(client_factory, db_session, tenant_a, analyst_user):
    """A REMEDIATED member IS counted in `done` (Pitfall 2 regression guard
    -- naively reusing remediation_service.py's _base_open_vulns() would
    exclude REMEDIATED entirely and permanently read 0% done).
    SUPPRESSED/FALSE_POSITIVE members are excluded from the denominator
    entirely (D-18)."""
    await db_session.commit()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    db_session.add_all(
        [
            _seed_vuln(tenant_a, remediation_id, status="OPEN"),
            _seed_vuln(tenant_a, remediation_id, status="IN_PROGRESS"),
            _seed_vuln(tenant_a, remediation_id, status="REMEDIATED"),
            _seed_vuln(tenant_a, remediation_id, status="REMEDIATED"),
            _seed_vuln(tenant_a, remediation_id, status="SUPPRESSED"),
            _seed_vuln(tenant_a, remediation_id, status="FALSE_POSITIVE"),
        ]
    )
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    r = await analyst_client.get(f"/api/v1/campaigns/{campaign_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    # total = OPEN + IN_PROGRESS + 2x REMEDIATED = 4 (SUPPRESSED/FALSE_POSITIVE excluded, D-18)
    assert body["total"] == 4, body
    assert body["done"] == 2, body
    assert body["in_progress"] == 1, body
    assert body["open"] == 1, body
    assert body["pct_remediated"] == 50, body
    assert body["status"] == "ACTIVE", body  # not 100% -- still active


@pytest.mark.asyncio
async def test_progress_zero_member_no_crash(client_factory, db_session, tenant_a, analyst_user):
    """A zero-member remediation_id renders pct_remediated=0 with HTTP 200
    -- never a 500 from ZeroDivisionError (Pitfall 5), and never
    misreported as COMPLETE (0/0 is not 100%)."""
    await db_session.commit()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    r = await analyst_client.get(f"/api/v1/campaigns/{campaign_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["open"] == 0
    assert body["in_progress"] == 0
    assert body["done"] == 0
    assert body["pct_remediated"] == 0
    assert body["status"] == "ACTIVE"


# ── Task 3: RBAC (D-16) + tenant isolation (T-38-01 IDOR) ────────────────────


@pytest.mark.asyncio
async def test_campaign_rbac(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """A viewer gets 403 on POST; a viewer CAN GET (list + detail)."""
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": f"remediation-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.post("/api/v1/campaigns", json={"remediation_id": f"remediation-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 403, r.text

    r = await viewer_client.get("/api/v1/campaigns")
    assert r.status_code == 200, r.text

    r = await viewer_client.get(f"/api/v1/campaigns/{campaign_id}")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_campaign_cross_tenant_isolation(client_factory, db_session, tenant_a, tenant_b, analyst_user):
    """A campaign from tenant A is invisible to tenant B -- 404 on detail
    (not a fetch-then-403; existence stays private, T-38-01) and absent
    from tenant B's list."""
    await db_session.commit()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={"remediation_id": remediation_id})
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    tenant_b_analyst = client_factory(_analyst_user_for(tenant_b))
    r = await tenant_b_analyst.get(f"/api/v1/campaigns/{campaign_id}")
    assert r.status_code == 404, r.text

    r = await tenant_b_analyst.get("/api/v1/campaigns")
    assert r.status_code == 200, r.text
    assert all(c["id"] != campaign_id for c in r.json())


# ── Plan 02 Task 1: bulk_create_campaign_tickets (per-owner carve-up) ───────


@pytest.mark.asyncio
async def test_bulk_assign_one_ticket_per_owner(db_session, tenant_a):
    """3 findings across 2 distinct owners -> exactly 2 external_ticket_urls;
    each owner's findings share their own url (D-04)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    owner_a = "alice@acme.test"
    owner_b = "bob@acme.test"

    asset_a1 = _seed_asset(tenant_a, humaans_email=owner_a)
    asset_a2 = _seed_asset(tenant_a, humaans_email=owner_a)
    asset_b1 = _seed_asset(tenant_a, humaans_email=owner_b)
    db_session.add_all([asset_a1, asset_a2, asset_b1])
    await db_session.flush()

    v1 = _seed_vuln(tenant_a, remediation_id, asset_id=asset_a1.id)
    v2 = _seed_vuln(tenant_a, remediation_id, asset_id=asset_a2.id)
    v3 = _seed_vuln(tenant_a, remediation_id, asset_id=asset_b1.id)
    db_session.add_all([v1, v2, v3])
    campaign = _make_campaign(tenant_a, remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    fake = FakeTicketingClient()
    result = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert result["owners"] == 2, result
    assert result["created_tickets"] == 2, result
    assert result["tickets_linked"] == 3, result
    assert result["adopted"] == 0, result
    assert result["failed_owners"] == [], result
    assert len(fake.created) == 2

    rows = (
        (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id.in_([v1.id, v2.id, v3.id]))))
        .scalars()
        .all()
    )
    assert len(rows) == 3
    urls_by_vuln = {r.vulnerability_id: r.external_ticket_url for r in rows}
    assert urls_by_vuln[v1.id] == urls_by_vuln[v2.id], "owner_a's two findings must share one url"
    assert urls_by_vuln[v1.id] != urls_by_vuln[v3.id], "distinct owners must get distinct urls"
    assignees_by_vuln = {r.vulnerability_id: r.assignee for r in rows}
    assert assignees_by_vuln[v1.id] == owner_a
    assert assignees_by_vuln[v3.id] == owner_b
    # D-20 / Pitfall 1: bare remediation_id, never a "campaign:{id}" prefix.
    assert all(r.created_by_rule == remediation_id for r in rows)


@pytest.mark.asyncio
async def test_bulk_assign_unassigned_bucket(db_session, tenant_a):
    """An owner-less finding (no humaans_email) -> one ticket in the
    None/unassigned bucket, assignee NULL -- never silently dropped (D-08)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    asset = _seed_asset(tenant_a, humaans_email=None)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, remediation_id, asset_id=asset.id)
    db_session.add(vuln)
    campaign = _make_campaign(tenant_a, remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    fake = FakeTicketingClient()
    result = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert result["owners"] == 1, result
    assert result["created_tickets"] == 1, result
    assert len(fake.created) == 1

    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    assert row.assignee is None
    assert row.project_key == "PROJ"
    assert row.created_by_rule == remediation_id


@pytest.mark.asyncio
async def test_bulk_assign_adopts_existing_ticket(db_session, tenant_a):
    """A finding already linked to an unresolved Ticket is adopted (counted
    in `adopted`, no new ticket created) (D-06)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    owner = "alice@acme.test"
    asset = _seed_asset(tenant_a, humaans_email=owner)
    db_session.add(asset)
    await db_session.flush()

    already_ticketed = _seed_vuln(tenant_a, remediation_id, asset_id=asset.id)
    fresh = _seed_vuln(tenant_a, remediation_id, asset_id=asset.id)
    db_session.add_all([already_ticketed, fresh])
    await db_session.flush()

    db_session.add(
        Ticket(
            tenant_id=tenant_a,
            vulnerability_id=already_ticketed.id,
            provider="JIRA",
            external_ticket_id="PRIOR-1",
            external_ticket_url="https://acme.atlassian.net/browse/PRIOR-1",
            external_status="open",
            project_key="PROJ",
            created_by_rule="some-other-rule",
        )
    )
    campaign = _make_campaign(tenant_a, remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    fake = FakeTicketingClient()
    result = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert result["adopted"] == 1, result
    assert result["tickets_linked"] == 1, result
    assert len(fake.created) == 1, "only the newcomer should get a new ticket"

    rows = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == fresh.id))).scalars().all()
    assert len(rows) == 1
    # The already-ticketed vuln must NOT gain a second Ticket row.
    prior_rows = (
        (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == already_ticketed.id))).scalars().all()
    )
    assert len(prior_rows) == 1


@pytest.mark.asyncio
async def test_bulk_assign_idempotent_rerun(db_session, tenant_a):
    """Re-running bulk-assign after some members were ticketed only tickets
    the newcomers (D-06/D-10) -- no duplicate tickets for already-adopted
    members."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    owner = "alice@acme.test"
    asset1 = _seed_asset(tenant_a, humaans_email=owner)
    asset2 = _seed_asset(tenant_a, humaans_email=owner)
    db_session.add_all([asset1, asset2])
    await db_session.flush()

    v1 = _seed_vuln(tenant_a, remediation_id, asset_id=asset1.id)
    db_session.add(v1)
    campaign = _make_campaign(tenant_a, remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    fake = FakeTicketingClient()
    first = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()
    assert first["created_tickets"] == 1
    assert first["adopted"] == 0

    # A newcomer arrives for the same remediation_id, same owner.
    v2 = _seed_vuln(tenant_a, remediation_id, asset_id=asset2.id)
    db_session.add(v2)
    await db_session.commit()

    second = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert second["adopted"] == 1, second  # v1 adopted, not re-ticketed
    assert second["tickets_linked"] == 1, second  # only v2 newly linked
    assert second["created_tickets"] == 1, second
    assert len(fake.created) == 2, "one create() from each run, not duplicated for v1"

    v1_rows = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == v1.id))).scalars().all()
    assert len(v1_rows) == 1, "v1 must not gain a second Ticket row on rerun"


@pytest.mark.asyncio
async def test_owner_derivation_matches_ticketing_service(db_session, tenant_a):
    """Campaign owner derivation equals ticketing/service.py's for the same
    asset fixture -- byte-identical `(mdm or {}).get('humaans_email')`
    lookup, never a new resolver (D-05)."""
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    owner = "carol@acme.test"
    asset = _seed_asset(tenant_a, humaans_email=owner)
    db_session.add(asset)
    await db_session.flush()

    vuln = _seed_vuln(tenant_a, remediation_id, asset_id=asset.id)
    db_session.add(vuln)
    campaign = _make_campaign(tenant_a, remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    fake = FakeTicketingClient()
    await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    row = (await db_session.execute(select(Ticket).where(Ticket.vulnerability_id == vuln.id))).scalar_one()
    # Same derivation ticketing/service.py:614 uses for the identical asset shape.
    expected_owner = (asset.mdm_details or {}).get("humaans_email")
    assert row.assignee == expected_owner == owner
