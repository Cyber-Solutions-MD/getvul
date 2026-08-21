"""Phase 41 Plan 01 (COV-01) -- coverage & blind-spot-detection tracer
slice: GET /api/v1/coverage/blind-spots reconciles the authoritative
(MDM/HR) inventory against scanner-seen assets and returns exactly the
devices no scanner has ever touched (D-01/D-02), proven end-to-end before
any COV-02/COV-03 expansion.

Uses the project's canonical inline-seed + `client_factory` harness
(`test_exceptions.py` / `test_campaigns.py`) verbatim -- an ad hoc
`CurrentUser` (not persisted to the `users` table) stands in for "a
tenant_b viewer" since `client_factory`'s dependency override bypasses
`get_current_user` entirely.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret python -m pytest tests/test_coverage.py -x -q
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.auth.schemas import CurrentUser
from app.ticketing.models import ConnectorConfig


def _seed_asset(
    tenant_id: uuid.UUID,
    *,
    hostname: str | None = None,
    seen_by_sources: list[str] | None = None,
    is_ignored: bool = False,
) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname or f"host-{uuid.uuid4().hex[:8]}",
        os_name="Ubuntu 22.04",
        device_category="WORKSTATION",
        seen_by_sources=seen_by_sources if seen_by_sources is not None else [],
        is_ignored=is_ignored,
    )


def _seed_connector(
    tenant_id: uuid.UUID,
    connector_type: str,
    *,
    is_enabled: bool = True,
    last_sync_at: datetime | None = None,
    last_sync_status: str | None = None,
) -> ConnectorConfig:
    """A minimal enabled scanner connector -- no credentials needed since
    GET /coverage/summary never decrypts anything (mirrors
    test_campaigns.py::_seed_connector's shape, without the credentials
    payload this endpoint doesn't touch)."""
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type=connector_type,
        is_enabled=is_enabled,
        last_sync_at=last_sync_at,
        last_sync_status=last_sync_status,
    )


def _viewer_user_for(tenant_id: uuid.UUID) -> CurrentUser:
    """An ad hoc VIEWER `CurrentUser` scoped to `tenant_id` -- no DB row
    needed since `client_factory`'s dependency override bypasses
    `get_current_user` entirely (mirrors test_exceptions.py's
    `_analyst_user_for`)."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
        role="VIEWER",
    )


def _analyst_user_for(tenant_id: uuid.UUID) -> CurrentUser:
    """An ad hoc ANALYST `CurrentUser` scoped to `tenant_id` (mirrors
    test_exceptions.py's `_analyst_user_for`)."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"analyst-{uuid.uuid4().hex[:8]}@test.local",
        role="ANALYST",
    )


async def _audit_rows(db_session, tenant_id: uuid.UUID, action: str, resource_id: str) -> list[AuditLog]:
    """Mirrors test_exceptions.py's `_audit_rows` helper."""
    return list(
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action == action,
                    AuditLog.resource_id == resource_id,
                )
            )
        )
        .scalars()
        .all()
    )


# ── COV-01/D-01/D-02: authoritative AND never-scanned, ignored excluded ──


@pytest.mark.asyncio
async def test_blind_spot_list(client_factory, db_session, tenant_a, viewer_user):
    """A JAMF-only asset appears; JAMF+QUALYS does NOT (scanner-touched);
    QUALYS-only does NOT (not authoritative); an is_ignored=true JAMF asset
    does NOT (mirrors the /assets list default)."""
    blind = _seed_asset(tenant_a, hostname="host-blind", seen_by_sources=["JAMF"])
    covered = _seed_asset(tenant_a, hostname="host-covered", seen_by_sources=["JAMF", "QUALYS"])
    scanner_only = _seed_asset(tenant_a, hostname="host-scanner-only", seen_by_sources=["QUALYS"])
    ignored_blind = _seed_asset(tenant_a, hostname="host-ignored", seen_by_sources=["JAMF"], is_ignored=True)
    db_session.add_all([blind, covered, scanner_only, ignored_blind])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert str(blind.id) in ids, ids
    assert str(covered.id) not in ids, ids
    assert str(scanner_only.id) not in ids, ids
    assert str(ignored_blind.id) not in ids, ids


# ── D-11: zero authoritative inventory -> honest empty signal, no fallback ──


@pytest.mark.asyncio
async def test_blind_spot_empty_inventory(client_factory, db_session, tenant_a, viewer_user):
    """A tenant with zero authoritative (MDM/HR) assets -- only a
    scanner-only asset exists -- gets items=[] AND
    has_authoritative_inventory=false (D-11: never a misleading 0%/100%),
    with total_authoritative_assets=0 backing that signal with a real count."""
    scanner_only = _seed_asset(tenant_a, seen_by_sources=["QUALYS"])
    db_session.add(scanner_only)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["has_authoritative_inventory"] is False
    assert body["total_authoritative_assets"] == 0


# ── Quiet-win: inventory exists, fully covered ──


@pytest.mark.asyncio
async def test_blind_spot_all_covered(client_factory, db_session, tenant_a, viewer_user):
    """A tenant whose only authoritative asset is ALSO scanner-covered gets
    items=[] AND has_authoritative_inventory=true -- the "every device is
    covered" quiet-win state, distinguishable from the no-inventory case --
    with total_authoritative_assets=1 supplying the quiet-win copy's real
    device count."""
    covered = _seed_asset(tenant_a, seen_by_sources=["JAMF", "QUALYS"])
    db_session.add(covered)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["has_authoritative_inventory"] is True
    assert body["total_authoritative_assets"] == 1


# ── Deterministic ordering: hostname asc, id asc tiebreak ──


@pytest.mark.asyncio
async def test_blind_spot_ordering(client_factory, db_session, tenant_a, viewer_user):
    """Results are ordered by hostname ASC (id ASC tiebreak) -- stable
    across two identical requests, so pagination is repeatable."""
    hosts = [_seed_asset(tenant_a, hostname=h, seen_by_sources=["HUMAANS"]) for h in ("zeta", "alpha", "mike")]
    db_session.add_all(hosts)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r1 = await viewer_client.get("/api/v1/coverage/blind-spots")
    r2 = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    hostnames_1 = [item["hostname"] for item in r1.json()["items"]]
    hostnames_2 = [item["hostname"] for item in r2.json()["items"]]
    assert hostnames_1 == ["alpha", "mike", "zeta"], hostnames_1
    assert hostnames_1 == hostnames_2


# ── T-41-01: cross-tenant isolation (IDOR) ──


@pytest.mark.asyncio
async def test_blind_spot_cross_tenant_isolation(client_factory, db_session, tenant_a, tenant_b, viewer_user):
    """Tenant B's viewer never sees tenant A's blind-spot assets --
    every WHERE clause (list + count + has_authoritative_inventory) is
    tenant-scoped, never fetch-then-filter."""
    asset_a = _seed_asset(tenant_a, seen_by_sources=["JAMF"])
    db_session.add(asset_a)
    await db_session.commit()

    tenant_b_client = client_factory(_viewer_user_for(tenant_b))
    r = await tenant_b_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert str(asset_a.id) not in ids, ids
    assert body["has_authoritative_inventory"] is False
    assert body["total_authoritative_assets"] == 0


# ── COV-02 (Phase 41 Plan 03): GET /coverage/summary -- per-connector
# coverage % (D-05) + staleness (D-06) + normalized sync status ──


@pytest.mark.asyncio
async def test_coverage_percentage(client_factory, db_session, tenant_a, viewer_user):
    """4 authoritative assets, 3 of them also touched by QUALYS -> the
    QUALYS card's coverage_pct == 75."""
    covered = [
        _seed_asset(tenant_a, seen_by_sources=["JAMF", "QUALYS"]),
        _seed_asset(tenant_a, seen_by_sources=["JAMF", "QUALYS"]),
        _seed_asset(tenant_a, seen_by_sources=["HUMAANS", "QUALYS"]),
    ]
    uncovered = _seed_asset(tenant_a, seen_by_sources=["JAMF"])
    connector = _seed_connector(tenant_a, "QUALYS")
    db_session.add_all([*covered, uncovered, connector])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_authoritative_assets"] == 4
    qualys_card = next(c for c in body["cards"] if c["connector_type"] == "QUALYS")
    assert qualys_card["coverage_pct"] == 75, qualys_card


@pytest.mark.asyncio
async def test_coverage_zero_denominator(client_factory, db_session, tenant_a, viewer_user):
    """A tenant with zero authoritative assets -> every card's
    coverage_pct is None (never 0/100), no ZeroDivisionError."""
    connector = _seed_connector(tenant_a, "NESSUS")
    db_session.add(connector)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_authoritative_assets"] == 0
    assert len(body["cards"]) == 1
    assert body["cards"][0]["coverage_pct"] is None


@pytest.mark.asyncio
async def test_stale_threshold_boundary(client_factory, db_session, tenant_a, viewer_user):
    """last_sync_at just under 7 days ago -> is_stale False (strict `>`);
    just over 7 days ago -> is_stale True. A one-minute margin on both sides
    of the literal 7-day boundary absorbs the seed-time vs. service-read-time
    clock gap without weakening the strict-`>` assertion itself."""
    now = datetime.now(timezone.utc)
    exactly_seven = _seed_connector(
        tenant_a, "CROWDSTRIKE", last_sync_at=now - timedelta(days=7, minutes=-1), last_sync_status="SUCCESS"
    )
    just_past_seven = _seed_connector(
        tenant_a, "DEFENDER", last_sync_at=now - timedelta(days=7, minutes=1), last_sync_status="SUCCESS"
    )
    db_session.add_all([exactly_seven, just_past_seven])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    by_type = {c["connector_type"]: c for c in body["cards"]}
    assert by_type["CROWDSTRIKE"]["is_stale"] is False, by_type["CROWDSTRIKE"]
    assert by_type["DEFENDER"]["is_stale"] is True, by_type["DEFENDER"]
    assert by_type["DEFENDER"]["stale_days"] == 7, by_type["DEFENDER"]


@pytest.mark.asyncio
async def test_status_normalized(client_factory, db_session, tenant_a, viewer_user):
    """A connector with last_sync_status="SUCCESS" surfaces as "ok" in the
    card payload; a connector with last_sync_status=None stays None."""
    synced = _seed_connector(tenant_a, "WIZ", last_sync_status="SUCCESS")
    never_synced = _seed_connector(tenant_a, "RAPID7", last_sync_status=None)
    db_session.add_all([synced, never_synced])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    by_type = {c["connector_type"]: c for c in body["cards"]}
    assert by_type["WIZ"]["last_sync_status"] == "ok", by_type["WIZ"]
    assert by_type["RAPID7"]["last_sync_status"] is None, by_type["RAPID7"]


@pytest.mark.asyncio
async def test_summary_flags(client_factory, db_session, tenant_a, viewer_user):
    """has_scanner_connector reflects whether >=1 enabled scanner connector
    exists; disabled connectors are excluded from cards entirely."""
    enabled = _seed_connector(tenant_a, "QUALYS", is_enabled=True)
    disabled = _seed_connector(tenant_a, "NESSUS", is_enabled=False)
    db_session.add_all([enabled, disabled])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_scanner_connector"] is True
    connector_types = {c["connector_type"] for c in body["cards"]}
    assert connector_types == {"QUALYS"}, connector_types


@pytest.mark.asyncio
async def test_summary_no_scanner_connector(client_factory, db_session, tenant_a, viewer_user):
    """A tenant with zero enabled scanner connectors at all ->
    has_scanner_connector False, cards empty."""
    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_scanner_connector"] is False
    assert body["cards"] == []


# ── COV-03 (Phase 41 Plan 04): POST /assets/{asset_id}/route-to-owner --
# resolve-then-notify-with-fallback (D-07/D-09), audited (D-08), analyst-
# gated, notify-only ──


@pytest.mark.asyncio
async def test_route_to_owner_resolved(client_factory, db_session, monkeypatch, tenant_a, analyst_user, viewer_user):
    """An asset whose assigned_user matches a real tenant User -> that
    user's email is notified directly (_send_notification_email), exactly
    one coverage.route_to_owner audit row is written with routed_to == the
    owner's display name, and the response mirrors it."""
    import app.notifications.service as notif_service
    from app.tenants.models import User

    sent: list[tuple[str, str, str, str]] = []

    async def fake_send(db, tenant_id, user_email, title, message, category):
        sent.append((user_email, title, message, category))

    monkeypatch.setattr(notif_service, "_send_notification_email", fake_send)

    owner_row = (await db_session.execute(select(User).where(User.id == viewer_user.id))).scalar_one()
    owner_display_name = owner_row.display_name

    asset = _seed_asset(tenant_a, hostname="host-shadow", seen_by_sources=["JAMF"])
    asset.assigned_user = viewer_user.email
    db_session.add(asset)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(f"/api/v1/coverage/assets/{asset.id}/route-to-owner")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hostname"] == "host-shadow"
    assert body["routed_to"] == owner_display_name

    assert len(sent) == 1, sent
    assert sent[0][0] == viewer_user.email
    assert sent[0][3] == "coverage_route_to_owner"

    rows = await _audit_rows(db_session, tenant_a, "coverage.route_to_owner", str(asset.id))
    assert len(rows) == 1, rows
    assert rows[0].details["routed_to"] == owner_display_name
    assert rows[0].details["hostname"] == "host-shadow"


@pytest.mark.asyncio
async def test_route_to_owner_fallback(client_factory, db_session, monkeypatch, tenant_a, analyst_user):
    """An asset with no resolvable owner -> _email_owners_and_admins fires,
    the coverage_unmanaged_asset channel dispatch is attempted (D-09), and
    the audit row's routed_to == "your admins"."""
    import app.notifications.alerts as alerts_module
    import app.notifications.escalation_channels as ec
    from app.tenants.models import Tenant

    admin_categories: list[str] = []

    async def fake_email_owners_and_admins(db, tenant, title, message, category):
        admin_categories.append(category)

    dispatched_channels: list[str] = []

    async def fake_dispatch_channel(channel, config, payload):
        dispatched_channels.append(channel)
        return {"ok": True}

    monkeypatch.setattr(alerts_module, "_email_owners_and_admins", fake_email_owners_and_admins)
    monkeypatch.setattr(ec, "dispatch_channel", fake_dispatch_channel)

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    tenant.alerting_config = {"routing": {"coverage_unmanaged_asset": ["slack"]}}
    await db_session.commit()

    asset = _seed_asset(tenant_a, hostname="host-unowned", seen_by_sources=["JAMF"])
    db_session.add(asset)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(f"/api/v1/coverage/assets/{asset.id}/route-to-owner")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routed_to"] == "your admins"
    assert admin_categories == ["coverage_route_to_owner"]
    assert dispatched_channels == ["slack"]

    rows = await _audit_rows(db_session, tenant_a, "coverage.route_to_owner", str(asset.id))
    assert len(rows) == 1, rows
    assert rows[0].details["routed_to"] == "your admins"


@pytest.mark.asyncio
async def test_route_to_owner_channel_failure_isolated(client_factory, db_session, monkeypatch, tenant_a, analyst_user):
    """A dispatch_channel exception must NOT prevent the admin email or the
    audit row -- the action still returns 200 with the audit present
    (channel leg fail-isolated, mirrors _fire_kev_epss_alert's pattern)."""
    import app.notifications.alerts as alerts_module
    import app.notifications.escalation_channels as ec
    from app.tenants.models import Tenant

    admin_categories: list[str] = []

    async def fake_email_owners_and_admins(db, tenant, title, message, category):
        admin_categories.append(category)

    async def failing_dispatch_channel(channel, config, payload):
        raise RuntimeError("channel dispatch exploded")

    monkeypatch.setattr(alerts_module, "_email_owners_and_admins", fake_email_owners_and_admins)
    monkeypatch.setattr(ec, "dispatch_channel", failing_dispatch_channel)

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    tenant.alerting_config = {"routing": {"coverage_unmanaged_asset": ["slack"]}}
    await db_session.commit()

    asset = _seed_asset(tenant_a, hostname="host-unowned-2", seen_by_sources=["JAMF"])
    db_session.add(asset)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(f"/api/v1/coverage/assets/{asset.id}/route-to-owner")
    assert r.status_code == 200, r.text
    assert admin_categories == ["coverage_route_to_owner"], "channel failure must not block the admin email"

    rows = await _audit_rows(db_session, tenant_a, "coverage.route_to_owner", str(asset.id))
    assert len(rows) == 1, "channel failure must not block the audit row"


@pytest.mark.asyncio
async def test_route_to_owner_rbac(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """A viewer gets 403 on the POST but can still GET /summary and
    /blind-spots (D-08 asymmetric RBAC); an analyst gets 200 on the POST."""
    asset = _seed_asset(tenant_a, hostname="host-rbac", seen_by_sources=["JAMF"])
    db_session.add(asset)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.post(f"/api/v1/coverage/assets/{asset.id}/route-to-owner")
    assert r.status_code == 403, r.text

    r = await viewer_client.get("/api/v1/coverage/summary")
    assert r.status_code == 200, r.text

    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(f"/api/v1/coverage/assets/{asset.id}/route-to-owner")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_route_to_owner_cross_tenant_404(client_factory, db_session, tenant_a, tenant_b, analyst_user):
    """A cross-tenant asset_id on route-to-owner returns 404, never
    403/500 (T-41-11 IDOR) -- tenant B's analyst cannot route tenant A's
    asset."""
    asset_a = _seed_asset(tenant_a, hostname="host-cross-tenant", seen_by_sources=["JAMF"])
    db_session.add(asset_a)
    await db_session.commit()

    tenant_b_analyst = client_factory(_analyst_user_for(tenant_b))
    r = await tenant_b_analyst.post(f"/api/v1/coverage/assets/{asset_a.id}/route-to-owner")
    assert r.status_code == 404, r.text
