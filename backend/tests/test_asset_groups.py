"""Phase 32 Plan 03 — tests for the real AssetGroup entity: tenant-scoped
CRUD, membership add/remove, and admin-gating/tenant-isolation (EXPO-04).

Group-scope precedence (override-applies-to-members, asset-beats-group,
multi-group tiebreak, group-override audit row, add-member-reapplies)
lives in test_asset_exposure.py per 32-03-PLAN.md's task split — this file
covers the AssetGroup entity itself: CRUD, membership CRUD, RBAC, tenant
isolation.

Uses the project's canonical inline-seed + client_factory pattern
(test_asset_owner_reassign.py / test_ai_status.py). An ad hoc `CurrentUser`
(not persisted to the `users` table) stands in for "a tenant_b admin" —
`get_current_user` is fully overridden by `client_factory`'s dependency
override, so no real User row is required for RBAC/tenant-isolation checks.
"""

from __future__ import annotations

import uuid

import pytest

from app.assets.models import Asset
from app.auth.schemas import CurrentUser

# `_reset_engine_pool` (autouse) lives in conftest.py.


def _seed_asset(tenant_id, hostname: str, os_name: str = "Ubuntu 22.04 LTS") -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, os_name=os_name)


def _admin_user_for(tenant_id) -> CurrentUser:
    """An ad hoc ADMIN `CurrentUser` scoped to `tenant_id` — no DB row
    needed since `client_factory`'s dependency override bypasses
    `get_current_user` entirely."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"admin-{uuid.uuid4().hex[:8]}@test.local",
        role="ADMIN",
    )


@pytest.mark.asyncio
async def test_asset_group_crud_tenant_isolation(client_factory, db_session, tenant_a, tenant_b, admin_user):
    """Admin creates a group; it appears in the list; a tenant_b admin
    cannot see/patch/delete it (404, not 403 — cross-tenant existence
    stays private, same convention as the per-asset override endpoint)."""
    # `tenant_a`/`tenant_b` fixtures only flush (not commit); AssetGroup has
    # a real FK to `tenants` (unlike Asset, which has none), so the row must
    # be committed before the app's separate session can satisfy the FK
    # check on INSERT.
    await db_session.commit()

    admin_client = client_factory(admin_user)
    r = await admin_client.post("/api/v1/asset-groups", json={"name": "Prod DB Tier", "description": "prod dbs"})
    assert r.status_code == 201, r.text
    group_id = r.json()["id"]

    r = await admin_client.get("/api/v1/asset-groups")
    assert r.status_code == 200, r.text
    assert any(g["id"] == group_id for g in r.json())

    tenant_b_admin = client_factory(_admin_user_for(tenant_b))

    r = await tenant_b_admin.get("/api/v1/asset-groups")
    assert r.status_code == 200, r.text
    assert all(g["id"] != group_id for g in r.json())

    r = await tenant_b_admin.get(f"/api/v1/asset-groups/{group_id}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset group not found"

    r = await tenant_b_admin.patch(f"/api/v1/asset-groups/{group_id}", json={"name": "Hijacked"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset group not found"

    r = await tenant_b_admin.delete(f"/api/v1/asset-groups/{group_id}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset group not found"


@pytest.mark.asyncio
async def test_group_endpoints_require_admin(
    client_factory, db_session, tenant_a, admin_user, analyst_user, viewer_user
):
    """Non-admin roles are rejected (403) on every mutating group endpoint:
    create, add member, group-scope exposure override."""
    await db_session.commit()  # tenant_a must be committed — AssetGroup FKs to tenants.

    admin_client = client_factory(admin_user)
    r = await admin_client.post("/api/v1/asset-groups", json={"name": "RBAC Test Group"})
    assert r.status_code == 201, r.text
    group_id = r.json()["id"]

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    for user in (analyst_user, viewer_user):
        c = client_factory(user)

        r = await c.post("/api/v1/asset-groups", json={"name": "Should Not Exist"})
        assert r.status_code == 403, r.text

        r = await c.post(f"/api/v1/asset-groups/{group_id}/members/{asset_id}")
        assert r.status_code == 403, r.text

        r = await c.patch(
            f"/api/v1/asset-groups/{group_id}/exposure-context",
            json={"field": "business_criticality", "value": "CRITICAL"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_group_member_add_and_remove(client_factory, db_session, tenant_a, admin_user):
    """Admin can add and remove a member; both are idempotent (TicketWatcher
    composite-PK pattern) and 404 on an unknown group/asset id."""
    await db_session.commit()  # tenant_a must be committed — AssetGroup FKs to tenants.

    admin_client = client_factory(admin_user)
    r = await admin_client.post("/api/v1/asset-groups", json={"name": "Membership Test Group"})
    assert r.status_code == 201, r.text
    group_id = r.json()["id"]

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    r = await admin_client.post(f"/api/v1/asset-groups/{group_id}/members/{asset_id}")
    assert r.status_code == 201, r.text

    # Idempotent — adding the same member twice does not error.
    r = await admin_client.post(f"/api/v1/asset-groups/{group_id}/members/{asset_id}")
    assert r.status_code == 201, r.text

    r = await admin_client.delete(f"/api/v1/asset-groups/{group_id}/members/{asset_id}")
    assert r.status_code == 200, r.text

    # Removing a non-member is a 404.
    r = await admin_client.delete(f"/api/v1/asset-groups/{group_id}/members/{asset_id}")
    assert r.status_code == 404

    # Unknown group id on add is a 404.
    r = await admin_client.post(f"/api/v1/asset-groups/{uuid.uuid4()}/members/{asset_id}")
    assert r.status_code == 404
