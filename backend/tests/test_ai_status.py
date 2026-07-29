"""Tests for GET /api/v1/ai/status -- the lightweight, non-admin-safe "is AI
configured" boolean signal that closes the 24-VERIFICATION.md truth #2 gap
(D-23 no-key role-gating, 24-10 gap-closure plan).

Mirrors test_ai_explain_host_remediation.py's route-test style: client_factory
+ per-role fixtures against a real Postgres via db_session. The seed helper
shape is copied from test_ai_explain_stream.py's `_seed_anthropic_connector`
(encrypt_value + ConnectorConfig(connector_type="ANTHROPIC")), but commits
(rather than flushes) the seeded row -- this file exercises the route over
HTTP via `client_factory`, which resolves `get_db` through the app's OWN,
independently-connected session (WR-13 contract; see conftest.py's
`db_session` docstring and test_ai_explain_host_remediation.py's `_seed_asset`).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir).
"""

from __future__ import annotations

import json
import uuid

from app.encryption import encrypt_value
from app.ticketing.models import ConnectorConfig

SEEDED_KEY = "sk-ant-test-key-abc123"


async def _seed_anthropic_connector(db_session, tenant_id: uuid.UUID, *, api_key: str = SEEDED_KEY) -> ConnectorConfig:
    connector = ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="ANTHROPIC",
        credentials_secret_arn=json.dumps({"api_key": encrypt_value(api_key)}),
        config={},
    )
    db_session.add(connector)
    await db_session.commit()  # visible to the app's OWN, independently-connected session
    return connector


async def test_status_viewer_unconfigured_returns_false(client_factory, db_session, tenant_a, viewer_user):
    """A Viewer in a tenant with NO ANTHROPIC ConnectorConfig row gets a real,
    non-error-coded 200 {"configured": false} -- never a 403 pass-through."""
    client = client_factory(viewer_user)
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": False}


async def test_status_analyst_configured_returns_true(client_factory, db_session, tenant_a, analyst_user):
    """An Analyst in a tenant WITH a seeded ANTHROPIC key gets 200
    {"configured": true} -- the same signal Admin/Owner would see."""
    await _seed_anthropic_connector(db_session, tenant_a)
    client = client_factory(analyst_user)
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": True}


async def test_status_admin_returns_200(client_factory, db_session, tenant_a, admin_user):
    """require_viewer is the floor -- every authed role, including Admin,
    can read this endpoint; the tenant is unconfigured so the boolean is
    explicitly asserted false (not just "200 with some body")."""
    client = client_factory(admin_user)
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": False}

    await _seed_anthropic_connector(db_session, tenant_a)
    resp_configured = await client.get("/api/v1/ai/status")
    assert resp_configured.status_code == 200, resp_configured.text
    assert resp_configured.json() == {"configured": True}


async def test_status_response_never_leaks_key_material(client_factory, db_session, tenant_a, analyst_user):
    """Response body has EXACTLY one key ("configured"); the seeded key
    string never appears anywhere in the response body (T-24-40)."""
    await _seed_anthropic_connector(db_session, tenant_a, api_key=SEEDED_KEY)
    client = client_factory(analyst_user)
    resp = await client.get("/api/v1/ai/status")
    assert resp.status_code == 200, resp.text
    assert set(resp.json().keys()) == {"configured"}
    assert SEEDED_KEY not in resp.text


async def test_status_is_tenant_scoped(client_factory, db_session, tenant_a, tenant_b, analyst_user_b):
    """A tenant_b user sees configured:false while only tenant_a has a key
    (T-24-41) -- the route is scoped by the caller's own tenant_id, no
    tenant/id path parameter to tamper with."""
    await _seed_anthropic_connector(db_session, tenant_a)
    client_b = client_factory(analyst_user_b)
    resp = await client_b.get("/api/v1/ai/status")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"configured": False}
