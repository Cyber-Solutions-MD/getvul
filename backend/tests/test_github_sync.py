"""Phase 23 Plan 05 Task 1 — GitHub ticketing connector registration (D-11/D-13).

Proves GITHUB is registered as a creatable connector type in all four
backend registration points: schemas.py CONNECTOR_TYPES, connectors/router.py
CONNECTOR_CATEGORIES, tester.py's dispatch table, and sync.py
SPECIAL_CONNECTORS + no-data-sync short-circuit.

(Task 2 extends this file with the daily_sync GitHub branch's inbound-state
+ outbound-auto-close behavior tests.)
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.connectors.schemas import CONNECTOR_TYPES
from app.connectors.sync import SPECIAL_CONNECTORS, run_sync
from app.encryption import encrypt_value
from app.ticketing.github_client import GitHubClient
from app.ticketing.models import ConnectorConfig


def _seed_github_connector(tenant_id: uuid.UUID, *, enabled: bool = True) -> ConnectorConfig:
    """Seed a GITHUB ConnectorConfig with the established token(credentials)/
    owner+repo(config) split (matches test_ticketing_dispatch.py's
    _seed_connector fixture pattern)."""
    creds = {"token": "fake-gh-token"}
    return ConnectorConfig(
        tenant_id=tenant_id,
        connector_type="GITHUB",
        is_enabled=enabled,
        credentials_secret_arn=json.dumps({k: encrypt_value(v) for k, v in creds.items()}),
        config={"owner": "acme", "repo": "widgets"},
    )


def test_special_connectors_includes_github():
    assert "GITHUB" in SPECIAL_CONNECTORS


def test_connector_types_includes_github_with_token_as_credential_owner_repo_as_config():
    assert "GITHUB" in CONNECTOR_TYPES
    info = CONNECTOR_TYPES["GITHUB"]
    fields_by_name = {f["name"]: f for f in info.fields}
    assert fields_by_name["token"]["type"] == "password"
    assert fields_by_name["owner"]["type"] == "text"
    assert fields_by_name["repo"]["type"] == "text"


def test_connector_categories_includes_github_as_ticketing():
    from app.connectors.router import CONNECTOR_CATEGORIES

    assert CONNECTOR_CATEGORIES["GITHUB"] == "ticketing"


@pytest.mark.asyncio
async def test_tester_dispatch_resolves_github(monkeypatch):
    from app.connectors.tester import test_connector

    async def fake_test_connection(self):
        return {"success": True, "message": "Successfully connected to acme/widgets"}

    async def fake_close(self):
        return None

    monkeypatch.setattr(GitHubClient, "test_connection", fake_test_connection)
    monkeypatch.setattr(GitHubClient, "close", fake_close)

    result = await test_connector("GITHUB", {"token": "t"}, {"owner": "acme", "repo": "widgets"})
    assert result.success is True
    assert "acme/widgets" in result.message


@pytest.mark.asyncio
async def test_run_sync_github_short_circuits_to_success_with_no_vuln_fetch(db_session, tenant_a):
    """A GITHUB connector logs SUCCESS immediately — no data-sync attempted
    (mirrors the ASANA/JIRA no-data-sync short-circuit)."""
    connector = _seed_github_connector(tenant_a)
    db_session.add(connector)
    await db_session.commit()

    log = await run_sync(db_session, connector)

    assert log.status == "SUCCESS"
    assert "GitHub" in log.details["message"]
