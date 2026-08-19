"""Phase 39 Plan 02 (EXC-01 full scope model) -- ASSET/ASSET_GROUP scope
resolution, per-scope precondition reconciliation (D-03 x D-11 / Pitfall 8),
Pitfall-9 server-side target derivation (Task 1); D-14 hard expiry cap +
default windows + D-12 overlap OR-semantics + D-11 live membership
(Task 2, appended below).

Uses the project's canonical inline-seed + `client_factory` harness
(`test_campaigns.py` / `test_exceptions.py`) verbatim.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions_scope.py -x
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.assets.models import Asset, AssetGroup, AssetGroupMember
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04",
    )


def _seed_group(tenant_id: uuid.UUID) -> AssetGroup:
    return AssetGroup(tenant_id=tenant_id, name=f"group-{uuid.uuid4().hex[:6]}")


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None = None,
    status: str = "OPEN",
    cve_id: str | None = None,
    source: str = "MOCK",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id or f"CVE-SCOPE-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status=status,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now - timedelta(days=3),
        last_seen_at=now,
    )


def _grant_body(
    *,
    scope_type: str,
    approver_id: uuid.UUID,
    exc_type: str = "ACCEPTED_RISK",
    days: int = 30,
    vulnerability_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    asset_group_id: uuid.UUID | None = None,
    cve_id: str | None = None,
    expires_at: datetime | None = None,
) -> dict:
    body: dict = {
        "type": exc_type,
        "scope_type": scope_type,
        "justification": "Compensating control in place while vendor patch is scheduled",
        "approver_user_id": str(approver_id),
        "expires_at": (expires_at or (datetime.now(UTC) + timedelta(days=days))).isoformat(),
    }
    if vulnerability_id is not None:
        body["vulnerability_id"] = str(vulnerability_id)
    if asset_id is not None:
        body["asset_id"] = str(asset_id)
    if asset_group_id is not None:
        body["asset_group_id"] = str(asset_group_id)
    if cve_id is not None:
        body["cve_id"] = cve_id
    return body


# ── Task 1: all three scope types grant correctly (EXC-01 scope model) ──


@pytest.mark.asyncio
async def test_scope_finding_grant(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """FINDING scope: server derives cve_id/asset_id from the resolved
    Vulnerability row and persists vulnerability_id; asset_group_id stays
    NULL."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["scope_type"] == "FINDING"
    assert payload["cve_id"] == vuln.cve_id
    assert payload["vulnerability_id"] == str(vuln.id)
    assert payload["asset_id"] == str(asset.id)
    assert payload["asset_group_id"] is None


@pytest.mark.asyncio
async def test_scope_asset_grant(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """ASSET scope: requires asset_id + a client-supplied cve_id; persists
    (cve_id, asset_id) with no vulnerability_id -- succeeds even though no
    Vulnerability row for this CVE exists on the asset yet (D-11
    forward-looking)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    cve_id = "CVE-2024-30103"
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="ASSET", approver_id=admin_user.id, asset_id=asset.id, cve_id=cve_id),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["scope_type"] == "ASSET"
    assert payload["cve_id"] == cve_id
    assert payload["asset_id"] == str(asset.id)
    assert payload["vulnerability_id"] is None
    assert payload["asset_group_id"] is None


@pytest.mark.asyncio
async def test_scope_asset_group_grant(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """ASSET_GROUP scope: requires asset_group_id + a client-supplied
    cve_id; persists (cve_id, asset_group_id) with no vulnerability_id/
    asset_id -- live membership resolution happens at READ time
    (active_exception_subquery), not here."""
    await db_session.commit()
    group = _seed_group(tenant_a)
    db_session.add(group)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    cve_id = "CVE-2024-30104"
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(
            scope_type="ASSET_GROUP", approver_id=admin_user.id, asset_group_id=group.id, cve_id=cve_id
        ),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["scope_type"] == "ASSET_GROUP"
    assert payload["cve_id"] == cve_id
    assert payload["asset_group_id"] == str(group.id)
    assert payload["vulnerability_id"] is None
    assert payload["asset_id"] is None


# ── Task 1: D-03 precondition reconciliation (Pattern 2 / Pitfall 8) ──


@pytest.mark.asyncio
async def test_precondition_rejects_remediated(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """FINDING scope against a REMEDIATED (non-actionable) finding is
    rejected with the exact D-03 copy."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, status="REMEDIATED")
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "This finding is already remediated — nothing to except."


@pytest.mark.asyncio
async def test_precondition_skipped_for_asset_scope(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """ASSET scope does NOT apply the OPEN/IN_PROGRESS precondition
    (Pitfall 8): even with a matching REMEDIATED finding already on file
    for this exact (cve_id, asset_id) -- the precise shape that 400s under
    FINDING scope above -- the ASSET-scope grant still succeeds, because it
    only validates the asset exists/belongs to the tenant."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    cve_id = "CVE-2024-30105"
    remediated_vuln = _seed_vuln(tenant_a, asset_id=asset.id, status="REMEDIATED", cve_id=cve_id)
    db_session.add(remediated_vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="ASSET", approver_id=admin_user.id, asset_id=asset.id, cve_id=cve_id),
    )
    assert r.status_code == 200, r.text
    assert r.json()["cve_id"] == cve_id


# ── Task 1: Pitfall 9 -- FINDING scope derives cve_id/asset_id server-side ──


@pytest.mark.asyncio
async def test_derive_finding_target_server_side(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """A client-supplied cve_id sent alongside a FINDING-scope grant is
    silently discarded -- the server always derives cve_id (and asset_id)
    from the resolved Vulnerability row, never trusting the client's own
    field independently (T-39-08)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    body = _grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id)
    body["cve_id"] = "CVE-9999-99999"  # bogus, must be ignored
    r = await analyst_client.post("/api/v1/exceptions", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["cve_id"] == vuln.cve_id
    assert payload["cve_id"] != "CVE-9999-99999"
    assert payload["asset_id"] == str(asset.id)


# ── Task 2: D-14 hard expiry cap (past + over-cap) ──


@pytest.mark.asyncio
async def test_expiry_past_rejected(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """D-14: a past-or-present expiry is rejected server-side, regardless
    of scope type."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    past = datetime.now(UTC) - timedelta(days=1)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(
            scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id, expires_at=past
        ),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Pick a date between tomorrow and the maximum allowed date."


@pytest.mark.asyncio
async def test_expiry_over_cap_rejected(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """D-14: a date beyond MAX_EXPIRY_DAYS (365) is rejected server-side --
    a 2099 date quietly defeating "never permanently silenced" is exactly
    the threat T-39-09 mitigates, regardless of what a client sends."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    far_future = datetime(2099, 1, 1, tzinfo=UTC)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(
            scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id, expires_at=far_future
        ),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"].startswith("Pick a date between tomorrow and")


def test_default_windows_exposed():
    """DEFAULT_EXPIRY_DAYS is exposed for the (deferred, /gsd-ui-phase-owned)
    frontend's pre-fill UX -- `validate_expiry`'s cap/future checks stay
    authoritative server-side regardless of what this pre-fills to."""
    from app.exceptions.service import DEFAULT_EXPIRY_DAYS

    assert DEFAULT_EXPIRY_DAYS == {"FALSE_POSITIVE": 180, "ACCEPTED_RISK": 90}


# ── Task 2: D-12 overlap OR-semantics -- excluded while ANY active, resurfaces on last lapse ──


@pytest.mark.asyncio
async def test_overlap_or_semantics(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """Two active exceptions covering the SAME finding through DIFFERENT
    scope branches (FINDING + ASSET) -- excluded while ANY is active;
    revoking one while the other still covers it keeps it excluded;
    revoking the last covering exception resurfaces it (D-12 OR
    semantics, no partial-unique index)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)

    r1 = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id, days=5),
    )
    assert r1.status_code == 200, r1.text
    exc1_id = r1.json()["id"]

    r2 = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(
            scope_type="ASSET", approver_id=admin_user.id, asset_id=asset.id, cve_id=vuln.cve_id, days=20
        ),
    )
    assert r2.status_code == 200, r2.text
    exc2_id = r2.json()["id"]

    # Both active -> excluded.
    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) not in ids, ids

    # Revoke the FINDING-scope one -- the ASSET-scope one still covers it.
    r = await analyst_client.post(f"/api/v1/exceptions/{exc1_id}/revoke")
    assert r.status_code == 200, r.text
    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) not in ids, "still covered by the ASSET-scope exception"

    # Revoke the last covering exception too -- now it resurfaces.
    r = await analyst_client.post(f"/api/v1/exceptions/{exc2_id}/revoke")
    assert r.status_code == 200, r.text
    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) in ids, "should resurface once the last covering exception is gone"


# ── Task 2: D-11 live membership -- member and new-source additions post-grant, no re-grant ──


@pytest.mark.asyncio
async def test_live_group_membership(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An ASSET_GROUP exception covers a member added AFTER the grant with
    no re-grant, and a second SOURCE re-detecting the same CVE on that
    asset is excluded immediately too -- both resolved live via
    AssetGroupMember / (cve_id, asset_id), never a frozen snapshot (D-11)."""
    await db_session.commit()
    group = _seed_group(tenant_a)
    db_session.add(group)
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    cve_id = "CVE-2024-30199"
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, cve_id=cve_id, source="MOCK")
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(
            scope_type="ASSET_GROUP", approver_id=admin_user.id, asset_group_id=group.id, cve_id=cve_id
        ),
    )
    assert r.status_code == 200, r.text

    # Not yet a group member -- the finding is still active.
    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) in ids, "not a group member yet, must not be excluded"

    # Add the asset to the group AFTER the grant -- no re-grant.
    db_session.add(AssetGroupMember(group_id=group.id, asset_id=asset.id))
    await db_session.commit()

    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) not in ids, "live membership join should exclude it with no re-grant"

    # A second source re-detecting the same CVE on the same asset (a
    # distinct row per uq_vuln_dedup) is excluded immediately too.
    new_source_vuln = _seed_vuln(tenant_a, asset_id=asset.id, cve_id=cve_id, source="NESSUS")
    db_session.add(new_source_vuln)
    await db_session.commit()

    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(new_source_vuln.id) not in ids, "new source on the same (cve_id, asset_id) must also be covered"
