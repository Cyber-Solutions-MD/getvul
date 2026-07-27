"""Phase 23 Plan 01 — Wiz connector coverage (REL-01, REL-03).

Exercises the full simulated sync: authenticate (OAuth2 client_credentials) →
GraphQL cursor pagination → fetch_vulnerabilities → NormalizedVulnerability
mapping, via an httpx.MockTransport (no live Wiz credentials). Also pins the
REL-01 regression: authenticate() must return True (not None) on success so
the sync harness's `if not authed:` truthiness check proceeds correctly.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.connectors.wiz import WizConnector

CREDS = {
    "client_id": "fake-client-id",
    "client_secret": "fake-client-secret",
    "api_url": "https://api.us1.app.wiz.io",
    "auth_url": "https://auth.app.wiz.io",
}


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a MockTransport.

    Wiz's authenticate() constructs its own httpx.AsyncClient internally, so we
    patch the class __init__ to inject a MockTransport transparently — mirroring
    the `_patch_transport` idiom in test_provider_stubs.py, but applied *before*
    client construction since Wiz builds its client inside authenticate(), not
    in __init__.
    """
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _json_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


TOKEN_OK = {"access_token": "fake-token-123", "expires_in": 3600}

VULN_PAGE_1 = {
    "data": {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    "id": "finding-1",
                    "name": "CVE-2024-1111",
                    "detailedName": "OpenSSL heap overflow",
                    "severity": "CRITICAL",
                    "score": 9.8,
                    "exploitAvailable": True,
                    "hasExploit": True,
                    "hasCisaKevExploit": True,
                    "status": "OPEN",
                    "remediation": "Upgrade to 3.0.14",
                    "version": "3.0.1",
                    "fixedVersion": "3.0.14",
                    "vulnerableAsset": {
                        "id": "asset-1",
                        "name": "prod-web-01",
                        "type": "VIRTUAL_MACHINE",
                        "operatingSystem": "Ubuntu 22.04",
                        "ipAddresses": ["10.0.0.5"],
                    },
                }
            ],
            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-page-2"},
        }
    }
}

VULN_PAGE_2 = {
    "data": {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    "id": "finding-2",
                    "name": "CVE-2024-2222",
                    "detailedName": "libcurl info leak",
                    "severity": "MEDIUM",
                    "score": 5.3,
                    "exploitAvailable": False,
                    "hasExploit": False,
                    "hasCisaKevExploit": False,
                    "status": "OPEN",
                    "remediation": None,
                    "version": "7.68.0",
                    "fixedVersion": None,
                    "vulnerableAsset": {
                        "id": "asset-2",
                        "name": "prod-db-02",
                        "type": "VIRTUAL_MACHINE",
                        "operatingSystem": "Debian 12",
                        "ipAddresses": ["10.0.0.6"],
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
}


def _handler_factory(token_status: int = 200):
    """Build a request handler dispatching between the OAuth token endpoint and
    the GraphQL endpoint, paginating the latter across VULN_PAGE_1/2."""
    calls = {"n": 0}
    graphql_pages = [VULN_PAGE_1, VULN_PAGE_2]

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path.endswith("/oauth/token"):
            if token_status != 200:
                return _json_response(token_status, {"error": "invalid_client"})
            return _json_response(200, TOKEN_OK)

        # GraphQL endpoint — page through the fixture responses.
        page_idx = min(calls["n"] - 2, len(graphql_pages) - 1)
        page_idx = max(page_idx, 0)
        return _json_response(200, graphql_pages[page_idx])

    return handler, calls


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    """REL-01 regression: authenticate() must return True (not None) on success."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = WizConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_raises(monkeypatch: pytest.MonkeyPatch):
    """A 401 token response raises via resp.raise_for_status() — the harness's
    outer except Exception handles this path, not a falsy return."""
    handler, _calls = _handler_factory(token_status=401)
    _install_mock_transport(monkeypatch, handler)

    connector = WizConnector()
    with pytest.raises(httpx.HTTPStatusError):
        await connector.authenticate(CREDS, {})
    await connector.close()


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_paginates_to_completion(monkeypatch: pytest.MonkeyPatch):
    """_paginate/fetch_vulnerabilities follows endCursor/hasNextPage across >=2 pages."""
    handler, calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = WizConnector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    # 1 auth call + 2 graphql page calls == 3 total handler invocations.
    assert calls["n"] >= 3
    assert len(results) == 2


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps a fixture response field-for-field into NormalizedVulnerability."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = WizConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    first = results[0]
    assert first.cve_id == "CVE-2024-1111"
    assert first.vulnerability_name == "OpenSSL heap overflow"
    assert first.severity == "CRITICAL"
    assert first.cvss_v3_score == 9.8
    assert first.source_vuln_id == "finding-1"
    assert first.hostname == "prod-web-01"
    assert first.ip_addresses == ["10.0.0.5"]
    assert first.os_name == "Ubuntu 22.04"
    assert first.affected_version == "3.0.1"
    assert first.fixed_version == "3.0.14"
    assert first.remediation_info == "Upgrade to 3.0.14"
    assert first.exploit_available is True
    assert first.cisa_kev is True

    second = results[1]
    assert second.cve_id == "CVE-2024-2222"
    assert second.severity == "MEDIUM"
    assert second.exploit_available is False
    assert second.cisa_kev is False
