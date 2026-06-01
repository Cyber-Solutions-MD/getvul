"""Phase 12 / Plan 02 — UX-04-04 backend tests for POST /api/v1/assets/{id}/owner.

Covers:
  - happy path: assigned_user is updated AND an asset.owner_changed audit row
    lands in the same transaction (T-12-09 mitigation)
  - 404 on unknown asset id
  - 404 (NOT 403) on cross-tenant probe (T-12-20 — existence hidden)
  - 422 on missing/empty/whitespace-only email (T-12-11)
  - email is normalised to lowercase before persistence

Uses the project's canonical inline-seed pattern from
test_assets_tags_and_os_family.py — the plan's spec referenced fictional
``asset_factory``/``tenant_factory``/``auth_headers``/``current_user``
fixtures that do not exist in this repo. The fixture surface the project
actually provides (db_session, tenant_a, tenant_b, analyst_user_b,
client_factory) is enough to cover every assertion in the plan; only the
fixture names change.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog

# `_reset_engine_pool` (autouse) lives in conftest.py — WR-14 centralised it.


def _seed_asset(
    tenant_id,
    hostname: str,
    *,
    assigned_user: str | None = None,
    os_name: str = "Ubuntu 22.04 LTS",
) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        assigned_user=assigned_user,
        os_name=os_name,
    )


@pytest.mark.asyncio
async def test_reassign_updates_assigned_user_and_writes_audit(
    client, db_session, tenant_a
):
    """Happy path: PATCH-style POST updates the field AND writes an
    ``asset.owner_changed`` audit row (T-12-09 — mutation+audit are atomic).
    """
    a = _seed_asset(tenant_a, "prod-db-01", assigned_user="alice@example.com")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    r = await client.post(
        f"/api/v1/assets/{asset_id}/owner",
        json={"assigned_user_email": "bob@example.com"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assigned_user"] == "bob@example.com"
    assert body["hostname"] == "prod-db-01"
    assert body["id"] == str(asset_id)

    # Audit row written in the same transaction (T-12-09 mitigation).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "asset.owner_changed",
                    AuditLog.resource_id == str(asset_id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1, f"expected exactly one audit row, got {len(audit_rows)}"
    row = audit_rows[0]
    assert row.details["from"] == "alice@example.com"
    assert row.details["to"] == "bob@example.com"
    assert row.details["hostname"] == "prod-db-01"
    assert row.resource_type == "asset"


@pytest.mark.asyncio
async def test_reassign_404_on_nonexistent_asset(client):
    """Unknown asset id returns 404 even when payload is valid."""
    r = await client.post(
        "/api/v1/assets/00000000-0000-0000-0000-000000000000/owner",
        json={"assigned_user_email": "carol@example.com"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reassign_cross_tenant_returns_404_not_403(
    client, db_session, tenant_b
):
    """T-12-20 mitigation — cross-tenant probe must return 404, not 403.

    The caller is the default `client` fixture (analyst_user in tenant_a).
    The asset lives in tenant_b, so the WHERE clause finds nothing and the
    handler raises 404 — without leaking that the asset id exists in
    another tenant.
    """
    foreign_asset = _seed_asset(tenant_b, "tenant-b-host")
    db_session.add(foreign_asset)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/assets/{foreign_asset.id}/owner",
        json={"assigned_user_email": "carol@example.com"},
    )
    assert r.status_code == 404
    # And no audit row should have been written cross-tenant either.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "asset.owner_changed",
                    AuditLog.resource_id == str(foreign_asset.id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert audit_rows == []


@pytest.mark.asyncio
async def test_reassign_422_on_missing_email_field(client, db_session, tenant_a):
    """Pydantic raises 422 when the required ``assigned_user_email`` key is absent."""
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/assets/{a.id}/owner",
        json={},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reassign_422_on_whitespace_only_email(client, db_session, tenant_a):
    """T-12-11 — strip-and-empty-check rejects whitespace-only payloads with 422.

    Pydantic alone would accept ``"   "`` as a valid str; the handler's
    ``new_email = body.assigned_user_email.strip().lower()`` followed by
    ``if not new_email: raise 422`` is what catches this.
    """
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/assets/{a.id}/owner",
        json={"assigned_user_email": "   "},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reassign_normalizes_email_to_lowercase(client, db_session, tenant_a):
    """``BOB@Example.COM`` → ``bob@example.com`` before write — keeps the
    column case-uniform for downstream ``_get_directory_user`` matching.
    """
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}", assigned_user="alice@example.com")
    db_session.add(a)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/assets/{a.id}/owner",
        json={"assigned_user_email": "BOB@Example.COM"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assigned_user"] == "bob@example.com"
