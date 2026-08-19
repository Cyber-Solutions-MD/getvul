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

from app.assets.models import Asset, AssetGroup
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
