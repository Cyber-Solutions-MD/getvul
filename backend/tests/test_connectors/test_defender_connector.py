"""Phase 23 Plan 02 — Microsoft Defender for Endpoint connector coverage (REL-03).

Exercises the full simulated sync: authenticate (Azure AD OAuth2 client_credentials,
200-success / False-failure convention, no raise) -> machines + recommendations
fetched in parallel -> `@odata.nextLink` pagination on the vulnerabilities endpoint
followed to completion -> fetch_vulnerabilities -> NormalizedVulnerability mapping,
via an httpx.MockTransport (no live credentials).

Also pins D-22: the MAX_RETRIES=3 429-retry loop in `_request_with_retry` —
retried up to the bound then gives up cleanly (returns None, no exception).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.connectors.defender import DefenderConnector

CREDS = {
    "tenant_id": "fake-tenant-id",
    "client_id": "fake-client-id",
    "client_secret": "fake-client-secret",
}

TOKEN_OK = {"access_token": "fake-defender-token"}


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a MockTransport,
    mirroring test_crowdstrike_connector.py's idiom (Defender builds its client
    inside authenticate(), not __init__)."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _install_fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch asyncio.sleep to be instant so 429-retry pinned-behavior tests
    don't actually wait the real Retry-After/RETRY_BACKOFF durations."""

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)


def _json_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


MACHINES_PAGE = {
    "value": [
        {
            "id": "machine-1",
            "computerDnsName": "defender-host-1",
            "ipAddresses": [{"ipAddress": "10.4.4.4"}],
            "osPlatform": "Windows10",
            "osVersion": "20H2",
            "lastSeen": "2026-01-01T00:00:00Z",
            "healthStatus": "Active",
        },
        {
            "id": "machine-2",
            "computerDnsName": "defender-host-2",
            "ipAddresses": [{"ipAddress": "10.4.4.5"}],
            "osPlatform": "Windows11",
            "osVersion": "22H2",
        },
    ]
}

RECOMMENDATIONS_PAGE = {
    "value": [
        {
            "relatedCves": ["CVE-2024-1234"],
            "remediationType": "Update",
            "recommendedVersion": "1.1.1w",
            "productName": "OpenSSL",
        }
    ]
}

VULNS_PAGE_1 = {
    "value": [
        {
            "id": "finding-1",
            "cveId": "CVE-2024-1234",
            "machineId": "machine-1",
            "severity": "High",
            "cvssV3": 8.5,
            "productName": "OpenSSL",
            "productVendor": "OpenSSL",
            "productVersion": "1.1.1",
            "exploitVerified": True,
        }
    ],
    "@odata.nextLink": "https://api.securitycenter.microsoft.com/api/vulnerabilities/machinesVulnerabilities?page=2",
}

VULNS_PAGE_2 = {
    "value": [
        {
            "id": "finding-2",
            "cveId": "CVE-2024-5678",
            "machineId": "machine-2",
        }
    ]
}


def _handler_factory(token_status: int = 200):
    """Route requests: OAuth token, machines (single page), recommendations
    (single page), vulnerabilities (2 pages via @odata.nextLink)."""
    calls = {"token": 0, "machines": 0, "recommendations": 0, "vulns": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path.endswith("/oauth2/v2.0/token"):
            calls["token"] += 1
            if token_status != 200:
                return _json_response(token_status, {"error": "invalid_client"})
            return _json_response(200, TOKEN_OK)

        if path == "/api/machines":
            calls["machines"] += 1
            return _json_response(200, MACHINES_PAGE)

        if path == "/api/recommendations":
            calls["recommendations"] += 1
            return _json_response(200, RECOMMENDATIONS_PAGE)

        if path == "/api/vulnerabilities/machinesVulnerabilities":
            calls["vulns"] += 1
            if calls["vulns"] == 1:
                return _json_response(200, VULNS_PAGE_1)
            return _json_response(200, VULNS_PAGE_2)

        return _json_response(404, {"error": "not found"})

    return handler, calls


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_returns_false(monkeypatch: pytest.MonkeyPatch):
    """A 401 token response returns False (Defender's own convention — checks
    status_code == 200, no raise_for_status call in authenticate())."""
    handler, _calls = _handler_factory(token_status=401)
    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is False


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_paginates_nextlink_to_completion(monkeypatch: pytest.MonkeyPatch):
    """The vulnerabilities @odata.nextLink cursor is followed across >=2 pages."""
    handler, calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert calls["vulns"] >= 2
    assert len(results) == 2


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps a fixture response field-for-field into
    NormalizedVulnerability, including machine + recommendation enrichment."""
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    by_cve = {r.cve_id: r for r in results}

    first = by_cve["CVE-2024-1234"]
    assert first.vulnerability_name is None  # Defender's endpoint never supplies a name
    assert first.severity == "HIGH"  # uppercased from "High"
    assert first.cvss_v3_score == 8.5
    assert first.source_vuln_id == "finding-1"
    assert first.hostname == "defender-host-1"
    assert first.ip_addresses == ["10.4.4.4"]
    assert first.os_name == "Windows10"
    assert first.os_version == "20H2"
    assert first.affected_product == "OpenSSL"
    assert first.affected_version == "1.1.1"
    assert first.fixed_version == "1.1.1w"  # falls back to the recommendation cache
    assert first.remediation_info == "Update — product: OpenSSL — recommended version: 1.1.1w"
    assert first.exploit_available is True

    second = by_cve["CVE-2024-5678"]
    assert second.severity == "MEDIUM"  # default fallback when the API omits severity
    assert second.hostname == "defender-host-2"
    assert second.exploit_available is False


@pytest.mark.asyncio
async def test_429_retried_up_to_max_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — MAX_RETRIES=3 loop on 429 before giving up.
    _install_fast_sleep(monkeypatch)
    retry_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            return _json_response(200, TOKEN_OK)
        retry_calls["n"] += 1
        if retry_calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return _json_response(200, {"value": []})

    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    await connector.authenticate(CREDS, {})
    resp = await connector._request_with_retry("/api/machines")
    await connector.close()

    assert resp is not None
    assert resp.status_code == 200
    assert retry_calls["n"] == 3  # 2x 429 + 1 success, within MAX_RETRIES=3


@pytest.mark.asyncio
async def test_429_exhausts_max_retries_returns_none(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — exhausting MAX_RETRIES=3 gives up cleanly (returns None, no exception).
    _install_fast_sleep(monkeypatch)
    retry_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            return _json_response(200, TOKEN_OK)
        retry_calls["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "0"})

    _install_mock_transport(monkeypatch, handler)

    connector = DefenderConnector()
    await connector.authenticate(CREDS, {})
    resp = await connector._request_with_retry("/api/machines")
    await connector.close()

    assert resp is None
    assert retry_calls["n"] == 3  # MAX_RETRIES=3, all exhausted


# ── Phase 31 Plan 01 — source_signals missing-vs-negative (ENRICH-04/SC#4) ────


def test_defender_normalize_vuln_source_signals_missing_vs_negative():
    """RED until Task 3: NormalizedVulnerability has no source_signals /
    native_priority_score / native_priority_rating fields yet -- this raises
    AttributeError on `v.source_signals`.

    Once GREEN (Task 3), this pins ENRICH-04/D-07/D-08/SC#4: source_signals
    distinguishes a vendor field that came back False (negative, key present)
    from a vendor field Defender's API never returned at all (missing, key
    absent) -- in the SAME returned finding. Defender has no VPR-equivalent
    field at all, making 'vpr' a structurally-guaranteed-absent key: the
    cleanest connector to anchor this fixture on (31-RESEARCH.md's own
    recommendation, mirrored in 31-PATTERNS.md's Tests section).

    Also pins D-06/Pitfall 6: Defender has no vendor-authored composite
    priority rating (only granular booleans/sub-scores) -- native_priority_*
    must be explicitly None, never a synthesized/invented composite.

    And pins D-08/V8: PII-adjacent fields (hostname, ip_addresses,
    last_login_user, serial_number) and already-promoted columns never
    duplicate into source_signals.
    """
    conn = DefenderConnector()
    conn._machine_cache = {
        "m1": {
            "computerDnsName": "should-not-leak-into-signals",
            "ipAddresses": [{"ipAddress": "10.0.0.99"}],
        }
    }
    rec = {
        "cveId": "CVE-2024-9001",
        "machineId": "m1",
        "severity": "High",
        "cvssV3": 7.5,
        "exploitVerified": False,
        "publicExploit": False,
        # exploitInKit / exploitTypes / exploitUris / EPSS intentionally
        # absent -- Defender's API simply did not return them for this
        # finding (the "missing" half of the fixture).
    }

    v = conn._normalize_vuln(rec)

    assert v is not None
    assert v.source_signals is not None

    # Negative: vendor returned False explicitly -- the key IS present.
    assert v.source_signals["exploitVerified"] is False
    assert v.source_signals["publicExploit"] is False

    # Missing: vendor never returned these -- keys are absent entirely,
    # never written as an explicit None/False sentinel (D-07).
    assert "exploitInKit" not in v.source_signals
    assert "exploitTypes" not in v.source_signals
    assert "exploitUris" not in v.source_signals
    assert "EPSS" not in v.source_signals
    assert "vpr" not in v.source_signals  # no VPR-equivalent field exists for Defender

    # D-06/Pitfall 6: no vendor composite for Defender -- explicit null,
    # never an invented/synthesized cross-boolean composite.
    assert v.native_priority_score is None
    assert v.native_priority_rating is None

    # D-08/V8: PII-adjacent fields and already-promoted columns never
    # duplicate into source_signals.
    for pii_key in ("hostname", "ip_addresses", "last_login_user", "serial_number"):
        assert pii_key not in v.source_signals
