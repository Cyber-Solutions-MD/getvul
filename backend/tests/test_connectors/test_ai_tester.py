"""Phase 24 Plan 01 — test_anthropic() connector-test coverage (AI-01/D-04).

Mirrors backend/tests/test_okta_sync.py's httpx.MockTransport idiom: the
`anthropic` SDK is httpx-based internally, so patching `httpx.AsyncClient.__init__`
(same technique as test_crowdstrike_connector.py's `_install_mock_transport`)
transparently intercepts the SDK's own internal client construction — no live
Anthropic key, no inference billed, no network call leaves the test process.
"""

from __future__ import annotations

import httpx
import pytest

from app.connectors.schemas import CONNECTOR_TYPES

# Aliased on import: pytest collects ANY `test_*`-named callable at module
# scope, imported or not. A bare `test_anthropic` import would make pytest try
# to run the connector-tester function itself as a test case and fail at
# fixture-resolution for its `credentials`/`config` params.
from app.connectors.tester import TESTERS
from app.connectors.tester import test_anthropic as anthropic_tester


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test (including the
    one the anthropic SDK builds internally) to use a MockTransport."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


@pytest.mark.asyncio
async def test_anthropic_missing_api_key_short_circuits():
    result = await anthropic_tester({}, {})
    assert result.success is False
    assert "API key" in result.message


@pytest.mark.asyncio
async def test_anthropic_valid_key_succeeds(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages/count_tokens"
        return httpx.Response(200, json={"input_tokens": 12})

    _install_mock_transport(monkeypatch, handler)

    result = await anthropic_tester(
        {"api_key": "sk-ant-fake-valid-key"},
        {"model": "claude-sonnet-5"},
    )
    assert result.success is True
    assert "claude-sonnet-5" in result.message
    # NOTE: ConnectorTestResponse (schemas.py) has no `details` field — passing
    # details={...} to the constructor is a silent no-op, matching every other
    # existing tester (test_crowdstrike, test_jamf, etc.) that does the same;
    # not a new gap introduced here, so not fixed as part of this task (scope
    # boundary — see 24-01-SUMMARY.md deferred items).


@pytest.mark.asyncio
async def test_anthropic_invalid_key_returns_generic_message_no_key_material(
    monkeypatch: pytest.MonkeyPatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}},
        )

    _install_mock_transport(monkeypatch, handler)

    result = await anthropic_tester({"api_key": "sk-ant-totally-wrong"}, {})
    assert result.success is False
    # T-24-02: never echo key material in the tester's response message.
    assert result.message == "Invalid API key"
    assert "sk-ant-totally-wrong" not in result.message


@pytest.mark.asyncio
async def test_anthropic_uses_selected_model_not_hardcoded_default(monkeypatch: pytest.MonkeyPatch):
    """D-01: the tenant's chosen model (from config, never credentials) must
    actually reach count_tokens — a stale hardcoded default would silently
    validate the wrong model."""
    seen_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"input_tokens": 5})

    _install_mock_transport(monkeypatch, handler)

    result = await anthropic_tester({"api_key": "sk-ant-fake"}, {"model": "claude-haiku-4-5"})
    assert result.success is True
    assert "claude-haiku-4-5" in result.message
    assert seen_bodies[0]["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_anthropic_connection_error_is_caught():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    try:
        _install_mock_transport(mp, handler)
        result = await anthropic_tester({"api_key": "sk-ant-fake"}, {})
        assert result.success is False
        assert "Connection error" in result.message
    finally:
        mp.undo()


def test_anthropic_registered_in_testers_dispatch():
    """test_connector()'s TESTERS dispatch needs no change (generic over
    TESTERS.get()) — this only pins that the new entry exists and resolves to
    the right function."""
    assert TESTERS["ANTHROPIC"] is anthropic_tester


def test_anthropic_connector_type_registered():
    info = CONNECTOR_TYPES["ANTHROPIC"]
    assert info.id == "ANTHROPIC"
    field_names = {f["name"] for f in info.fields}
    assert field_names == {"api_key", "model", "monthly_budget_usd"}

    model_field = next(f for f in info.fields if f["name"] == "model")
    assert model_field["type"] == "select"
    assert model_field["required"] is True
    assert model_field["config"] is True
    option_values = [o["value"] for o in model_field["options"]]
    # Fixed, stable order (AI-01 must-have) — Sonnet 5 first == the D-01 default.
    assert option_values == ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"]

    budget_field = next(f for f in info.fields if f["name"] == "monthly_budget_usd")
    assert budget_field["required"] is False
    assert budget_field["config"] is True

    api_key_field = next(f for f in info.fields if f["name"] == "api_key")
    assert api_key_field["type"] == "password"
    assert api_key_field["required"] is True
    assert "config" not in api_key_field  # never routed to plaintext config


@pytest.mark.asyncio
async def test_anthropic_monthly_budget_round_trips_via_config(db_session, tenant_a):
    """AI-01 must-have: an admin-set monthly_budget_usd round-trips into
    ConnectorConfig.config.monthly_budget_usd (D-06) — plaintext, not the
    encrypted credentials_secret_arn. API-level per the plan's acceptance
    criteria ("asserted in the wizard/connector test or an API test")."""
    from app.connectors.schemas import ConnectorCreate
    from app.connectors.service import create_connector, list_connectors

    body = ConnectorCreate(
        connector_type="ANTHROPIC",
        credentials={"api_key": "sk-ant-fake-for-round-trip-test"},
        config={"model": "claude-sonnet-5", "monthly_budget_usd": 50},
    )
    created = await create_connector(db_session, tenant_a, body)
    assert created.config["monthly_budget_usd"] == 50
    assert created.config["model"] == "claude-sonnet-5"
    # The API key must never appear in the plaintext config or the response.
    assert "api_key" not in created.config
    assert created.has_credentials is True

    listed = await list_connectors(db_session, tenant_a)
    match = next(c for c in listed if c.connector_type == "ANTHROPIC")
    assert match.config["monthly_budget_usd"] == 50
