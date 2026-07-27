"""Phase 23 Plan 01 — Rapid7 connector coverage (REL-02, REL-03, D-21).

Exercises the full simulated sync: no-arg construction (the REL-02 regression —
today Rapid7Connector() raises TypeError since __init__ required a `config` arg
and `authenticate` was unimplemented) → authenticate (Basic auth over
InsightVM API v3) → REST page/totalPages pagination → fetch_vulnerabilities →
NormalizedVulnerability mapping, via an httpx.MockTransport (no live creds).
Also pins D-21: verify_tls resolves from config, default True.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.connectors.rapid7 import Rapid7Connector

CREDS = {
    "url": "https://insightvm.example.com:3780",
    "username": "api-user",
    "password": "fake-password",
}

ASSET_1 = {
    "id": 100,
    "hostName": "web-01.example.com",
    "ip": "10.1.1.10",
    "os": {"description": "Ubuntu Linux", "version": "22.04"},
}
ASSET_2 = {
    "id": 200,
    "hostName": "db-01.example.com",
    "ip": "10.1.1.20",
    "os": {"description": "CentOS Linux", "version": "8"},
}

VULN_ENTRY_1 = {"id": "ssl-poodle"}
VULN_ENTRY_2 = {"id": "openssh-cve"}

VULN_DETAIL_1 = {
    "id": "ssl-poodle",
    "title": "SSL POODLE vulnerability",
    "cvss": {"v3": {"score": 7.5}},
    "exploits": 2,
    "cves": ["CVE-2014-3566"],
}
VULN_DETAIL_2 = {
    "id": "openssh-cve",
    "title": "OpenSSH weak ciphers",
    "cvss": {"v3": {"score": 5.9}},
    "exploits": 0,
    "cves": ["CVE-2023-9999"],
}

SOLUTIONS_1 = {"resources": [{"summary": "Disable SSLv3"}]}
SOLUTIONS_2 = {"resources": [{"summary": "Disable weak ciphers"}]}


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a MockTransport,
    mirroring test_wiz_connector.py's idiom (Rapid7 constructs its client inside
    authenticate(), not __init__)."""
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


def _handler_factory(auth_probe_status: int = 200):
    """Route requests by path; assets/vulnerabilities pagination is 2 pages each
    (totalPages == 2), and the auth probe hits /api/3/assets?page=0&size=1."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        path = request.url.path
        params = dict(request.url.params)

        if path == "/api/3/assets":
            size = params.get("size")
            if size == "1":
                # The auth probe call.
                if auth_probe_status != 200:
                    return _json_response(auth_probe_status, {"message": "unauthorized"})
                return _json_response(
                    200, {"resources": [ASSET_1], "page": {"totalPages": 1}}
                )
            page = int(params.get("page", "0"))
            resources = [ASSET_1] if page == 0 else [ASSET_2]
            return _json_response(200, {"resources": resources, "page": {"totalPages": 2}})

        if path == "/api/3/assets/100/vulnerabilities":
            page = int(params.get("page", "0"))
            if page == 0:
                return _json_response(200, {"resources": [VULN_ENTRY_1], "page": {"totalPages": 2}})
            return _json_response(200, {"resources": [], "page": {"totalPages": 2}})

        if path == "/api/3/assets/200/vulnerabilities":
            page = int(params.get("page", "0"))
            if page == 0:
                return _json_response(200, {"resources": [VULN_ENTRY_2], "page": {"totalPages": 2}})
            return _json_response(200, {"resources": [], "page": {"totalPages": 2}})

        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, VULN_DETAIL_1)
        if path == "/api/3/vulnerabilities/openssh-cve":
            return _json_response(200, VULN_DETAIL_2)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        if path == "/api/3/vulnerabilities/openssh-cve/solutions":
            return _json_response(200, SOLUTIONS_2)

        return _json_response(404, {"message": "not found"})

    return handler, calls


def test_constructs_with_no_arguments():
    """REL-02 regression: Rapid7Connector() must construct without a config arg
    (previously TypeError: Can't instantiate abstract class ... 'authenticate')."""
    connector = Rapid7Connector()
    assert connector.source_name == "RAPID7"


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_returns_false(monkeypatch: pytest.MonkeyPatch):
    """A 401 on the auth probe returns False (consistent with the Nessus/Qualys
    sibling connector convention — no raised exception on auth failure)."""
    handler, _calls = _handler_factory(auth_probe_status=401)
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is False


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_paginates_to_completion(monkeypatch: pytest.MonkeyPatch):
    """REST page/totalPages pagination followed to completion (assets: totalPages=2)."""
    handler, calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    # Assets pagination alone requires 2 page calls (totalPages=2); assert the
    # handler was invoked well beyond a single page across the whole sync.
    assert calls["n"] >= 3
    assert len(results) == 2


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps a fixture response field-for-field into NormalizedVulnerability."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    by_cve = {r.cve_id: r for r in results}

    ssl_poodle = by_cve["CVE-2014-3566"]
    assert ssl_poodle.vulnerability_name == "SSL POODLE vulnerability"
    assert ssl_poodle.cvss_v3_score == 7.5
    assert ssl_poodle.severity == "HIGH"
    assert ssl_poodle.source_vuln_id == "ssl-poodle"
    assert ssl_poodle.hostname == "web-01.example.com"
    assert ssl_poodle.ip_addresses == ["10.1.1.10"]
    assert ssl_poodle.os_name == "Ubuntu Linux"
    assert ssl_poodle.os_version == "22.04"
    assert ssl_poodle.remediation_info == "Disable SSLv3"
    assert ssl_poodle.exploit_available is True

    openssh = by_cve["CVE-2023-9999"]
    assert openssh.vulnerability_name == "OpenSSH weak ciphers"
    assert openssh.cvss_v3_score == 5.9
    assert openssh.severity == "MEDIUM"
    assert openssh.exploit_available is False


@pytest.mark.asyncio
async def test_verify_tls_defaults_true_and_config_can_disable(monkeypatch: pytest.MonkeyPatch):
    """D-21: verify_tls resolves to True by default; only explicit config
    verify_tls:false disables TLS validation."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    assert connector._client is not None
    assert connector._client._transport is not None  # sanity: mock transport installed
    assert connector.verify_tls is True
    await connector.close()

    connector2 = Rapid7Connector()
    await connector2.authenticate(CREDS, {"verify_tls": False})
    assert connector2.verify_tls is False
    await connector2.close()
