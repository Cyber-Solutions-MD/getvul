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

import pytest

from app.assets.models import Asset
from app.auth.schemas import CurrentUser


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
    has_authoritative_inventory=false (D-11: never a misleading 0%/100%)."""
    scanner_only = _seed_asset(tenant_a, seen_by_sources=["QUALYS"])
    db_session.add(scanner_only)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["has_authoritative_inventory"] is False


# ── Quiet-win: inventory exists, fully covered ──


@pytest.mark.asyncio
async def test_blind_spot_all_covered(client_factory, db_session, tenant_a, viewer_user):
    """A tenant whose only authoritative asset is ALSO scanner-covered gets
    items=[] AND has_authoritative_inventory=true -- the "every device is
    covered" quiet-win state, distinguishable from the no-inventory case."""
    covered = _seed_asset(tenant_a, seen_by_sources=["JAMF", "QUALYS"])
    db_session.add(covered)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/coverage/blind-spots")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["has_authoritative_inventory"] is True


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
