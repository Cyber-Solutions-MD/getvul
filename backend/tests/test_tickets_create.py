"""Phase 11 / Plan 01 — Wave 0 verification of existing POST /api/v1/tickets.

Behaviour under test (D-P-04): the ticket-create endpoint must be reachable,
role-guarded, and validate request body via Pydantic. The endpoint is
already implemented at backend/app/ticketing/router.py::create_new_tickets.

These tests SHOULD PASS now — they verify existing behaviour. If any fail,
the existing endpoint has regressed and the failure must be surfaced before
Wave 1 frontend work proceeds (Phase 11 D-P-04 sets the contract the
frontend mutation depends on).

The "no Asana connector" 400 path proves the endpoint is wired without
needing a fake Asana mock; it lets the test suite verify the routing chain
(require_analyst → tenant scope → schema validation → _get_asana_client)
without external HTTP dependencies.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.vulnerabilities.models import Vulnerability


def _seed_vuln(tenant_id) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-TKT-{uuid.uuid4().hex[:4]}",
        severity="CRITICAL",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        cvss_v3_score=9.8,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest_asyncio.fixture
async def unauth_client(redis_test_url, db_session):
    """An httpx client whose requests are NOT authed.

    `client` / `client_factory` override `get_current_user` to short-circuit
    JWT validation. For the 401 negative test we need the real dependency
    chain so HTTPBearer raises HTTP_401_UNAUTHORIZED.
    """
    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            yield ac


@pytest.mark.asyncio
async def test_post_tickets_endpoint_exists_returns_400_without_connector(
    client, db_session, tenant_a
):
    """D-P-04: POST /api/v1/tickets with a valid body but no ASANA connector
    configured returns 400 (not 404, not 500). This proves the endpoint is
    wired through require_analyst → body validation → _get_asana_client.

    The 400 detail message is set by _get_asana_client at
    backend/app/ticketing/router.py:66 — re-using it here as the canonical
    'endpoint is reachable' signal.
    """
    v = _seed_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/tickets",
        json={
            "vulnerability_ids": [str(v.id)],
            "provider": "ASANA",
            "project_key": "1199999999",
        },
    )
    # The request reaches the create handler, validates the body, and only
    # then fails because no connector exists for this tenant.
    assert resp.status_code == 400, resp.text
    detail = resp.json().get("detail", "")
    assert "asana" in detail.lower() or "connector" in detail.lower(), (
        f"expected detail to mention asana/connector, got: {detail}"
    )


@pytest.mark.asyncio
async def test_post_tickets_rejects_viewer_role_403(
    client_factory, db_session, viewer_user, tenant_a
):
    """T-11-06: require_analyst rejects VIEWER → 403 before any body work.

    The seed vuln is a placeholder so the body passes schema validation; the
    request must die at the RBAC dependency.
    """
    v = _seed_vuln(tenant_a)
    db_session.add(v)
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    resp = await viewer_client.post(
        "/api/v1/tickets",
        json={
            "vulnerability_ids": [str(v.id)],
            "provider": "ASANA",
            "project_key": "1199999999",
        },
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_post_tickets_rejects_unauthenticated_401(unauth_client):
    """T-11-07: unauthenticated POST → 401 (no JWT in headers).

    The HTTPBearer scheme raises HTTP_401_UNAUTHORIZED at
    backend/app/auth/dependencies.py:29 before require_analyst even runs.
    Body validation is intentionally NOT bypassed by an empty body — Pydantic
    still surfaces 422 if reached, so the test must also confirm the response
    is exactly 401 (auth wins over body shape).
    """
    resp = await unauth_client.post(
        "/api/v1/tickets",
        json={
            "vulnerability_ids": [str(uuid.uuid4())],
            "provider": "ASANA",
            "project_key": "1199999999",
        },
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_post_tickets_validates_request_body_422(client):
    """T-11-05 / Pydantic: missing required `vulnerability_ids` → 422."""
    resp = await client.post(
        "/api/v1/tickets",
        json={
            "provider": "ASANA",
            "project_key": "1199999999",
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_post_tickets_validates_provider_literal(client):
    """T-11-05 / Pydantic: provider='JENKINS' is not in {ASANA, JIRA, GITHUB} → 422.

    Mitigates the surface where a malicious analyst sends an arbitrary
    provider string hoping to confuse downstream routing.
    """
    resp = await client.post(
        "/api/v1/tickets",
        json={
            "vulnerability_ids": [str(uuid.uuid4())],
            "provider": "JENKINS",
            "project_key": "1199999999",
        },
    )
    assert resp.status_code == 422, resp.text
