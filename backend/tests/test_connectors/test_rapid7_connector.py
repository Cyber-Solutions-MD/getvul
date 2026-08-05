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


# ── ENRICH-03/04 (Phase 31 Plan 04): riskScore -> native_priority_score,
# source_signals missing-vs-negative (Pitfall 5: read from vuln_entry -- the
# per-asset AssetVulnerability association entry -- NEVER `detail`, the
# vendor-neutral vulnerability definition) ──────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_risk_score_from_vuln_entry_populates_native_priority_score(
    monkeypatch: pytest.MonkeyPatch,
):
    """A vuln_entry carrying riskScore -> native_priority_score == the raw
    number (0-1000 scale) on the emitted finding (D-06: no re-scale);
    native_priority_rating stays explicit None (Risk Score is numeric-only,
    no separate vendor categorical rating)."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/3/assets":
            return _json_response(200, {"resources": [ASSET_1], "page": {"totalPages": 1}})
        if path == "/api/3/assets/100/vulnerabilities":
            return _json_response(
                200,
                {"resources": [{"id": "ssl-poodle", "riskScore": 653.5}], "page": {"totalPages": 1}},
            )
        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, VULN_DETAIL_1)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        return _json_response(404, {"message": "not found"})

    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert len(results) == 1
    assert results[0].native_priority_score == 653.5
    assert results[0].native_priority_rating is None


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_risk_score_absent_stays_none_no_crash(monkeypatch: pytest.MonkeyPatch):
    """A vuln_entry WITHOUT riskScore -> native_priority_score stays None
    (soft-null, never a crash)."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/3/assets":
            return _json_response(200, {"resources": [ASSET_1], "page": {"totalPages": 1}})
        if path == "/api/3/assets/100/vulnerabilities":
            return _json_response(200, {"resources": [{"id": "ssl-poodle"}], "page": {"totalPages": 1}})
        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, VULN_DETAIL_1)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        return _json_response(404, {"message": "not found"})

    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert results[0].native_priority_score is None


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_risk_score_read_from_vuln_entry_not_detail(
    monkeypatch: pytest.MonkeyPatch,
):
    """Pitfall 5: a `detail` resource carrying a riskScore-shaped key must
    NOT leak into native_priority_score -- Risk Score lives on the per-asset
    AssetVulnerability association entry (vuln_entry), not the vendor-neutral
    vulnerability definition resource (identical for every asset sharing
    this CVE)."""
    detail_with_risk_score = {**VULN_DETAIL_1, "riskScore": 999.0}  # must be ignored

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/3/assets":
            return _json_response(200, {"resources": [ASSET_1], "page": {"totalPages": 1}})
        if path == "/api/3/assets/100/vulnerabilities":
            # vuln_entry itself carries no riskScore.
            return _json_response(200, {"resources": [{"id": "ssl-poodle"}], "page": {"totalPages": 1}})
        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, detail_with_risk_score)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        return _json_response(404, {"message": "not found"})

    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert results[0].native_priority_score is None  # NOT 999.0 -- must ignore `detail`


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_source_signals_missing_vs_negative_and_no_pii_or_promoted_keys(
    monkeypatch: pytest.MonkeyPatch,
):
    """source_signals captures a vendor field that IS present (`status`,
    even a weaker vulnerable-version match) while riskScore itself is not
    duplicated (already promoted to native_priority_score, D-08); no
    PII-adjacent or already-promoted keys ever leak in."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/3/assets":
            return _json_response(200, {"resources": [ASSET_1], "page": {"totalPages": 1}})
        if path == "/api/3/assets/100/vulnerabilities":
            return _json_response(
                200,
                {
                    "resources": [{"id": "ssl-poodle", "riskScore": 653.5, "status": "vulnerable-version"}],
                    "page": {"totalPages": 1},
                },
            )
        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, VULN_DETAIL_1)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        return _json_response(404, {"message": "not found"})

    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    signals = results[0].source_signals
    assert signals["status"] == "vulnerable-version"  # present
    assert signals["status_confirmed"] is False  # derived: not an exact/confirmed match
    assert "riskScore" not in signals  # promoted to native_priority_score, not duplicated (D-08)
    for forbidden in ("hostname", "ip_addresses", "cve_id", "cvss", "severity", "epss", "native_priority"):
        assert forbidden not in signals


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_status_confirmed_true_and_status_absent_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    """`status == "vulnerable"` -> derived status_confirmed True; when
    `status` is absent entirely from a different finding's vuln_entry, BOTH
    keys are omitted (missing, never a False sentinel) -- in the SAME
    fetch_vulnerabilities() run."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/3/assets":
            return _json_response(200, {"resources": [ASSET_1, ASSET_2], "page": {"totalPages": 1}})
        if path == "/api/3/assets/100/vulnerabilities":
            return _json_response(
                200, {"resources": [{"id": "ssl-poodle", "status": "vulnerable"}], "page": {"totalPages": 1}}
            )
        if path == "/api/3/assets/200/vulnerabilities":
            return _json_response(200, {"resources": [{"id": "openssh-cve"}], "page": {"totalPages": 1}})
        if path == "/api/3/vulnerabilities/ssl-poodle":
            return _json_response(200, VULN_DETAIL_1)
        if path == "/api/3/vulnerabilities/ssl-poodle/solutions":
            return _json_response(200, SOLUTIONS_1)
        if path == "/api/3/vulnerabilities/openssh-cve":
            return _json_response(200, VULN_DETAIL_2)
        if path == "/api/3/vulnerabilities/openssh-cve/solutions":
            return _json_response(200, SOLUTIONS_2)
        return _json_response(404, {"message": "not found"})

    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    by_cve = {r.cve_id: r for r in results}
    assert by_cve["CVE-2014-3566"].source_signals["status"] == "vulnerable"
    assert by_cve["CVE-2014-3566"].source_signals["status_confirmed"] is True

    # openssh-cve's vuln_entry has no `status` key at all -> both keys absent.
    assert "status" not in by_cve["CVE-2023-9999"].source_signals
    assert "status_confirmed" not in by_cve["CVE-2023-9999"].source_signals


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_native_priority_fields_always_set_even_without_risk_score(
    monkeypatch: pytest.MonkeyPatch,
):
    """ENRICH-06: even when riskScore/status are entirely absent (the
    module-level VULN_ENTRY_1/VULN_ENTRY_2 fixtures used elsewhere in this
    file), all 3 new fields are explicitly set (native_priority_score=None,
    native_priority_rating=None, source_signals={}) -- never omitted, never
    a crash."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = Rapid7Connector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert len(results) == 2
    for r in results:
        assert r.native_priority_score is None
        assert r.native_priority_rating is None
        assert r.source_signals == {}
