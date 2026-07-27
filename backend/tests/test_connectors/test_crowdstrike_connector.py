"""Phase 23 Plan 02 — CrowdStrike connector coverage (REL-03).

Exercises the full simulated sync: authenticate (OAuth2 client_credentials,
CrowdStrike's own 201-on-success / False-on-failure convention) -> Spotlight
combined-vulnerabilities `after`-cursor pagination -> device/remediation/
vuln-metadata batch enrichment -> fetch_vulnerabilities -> NormalizedVulnerability
mapping, via an httpx.MockTransport (no live credentials).

Also pins D-22's documented main-loop-vs-enrichment-batch 429 inconsistency:
the main vulnerability-pagination loop retries 429 unboundedly (`sleep(5); continue`),
while the enrichment-batch helpers (_resolve_devices_batch etc.) only `sleep(3)`
on 429 with no actual retry — the batch's data is silently dropped. Both halves
are pinned here as CURRENT behavior (not fixed) per 23-RESEARCH Open Question 10.

NOTE on pagination fixture size: CrowdStrike's _fetch_vulns_by_filter only follows
the `after` cursor when `after` is truthy AND len(resources) >= 400 (see
crowdstrike.py's `if not after or len(resources) < 400: break`) — genuinely
exercising >=2 pages therefore requires a first page of >=400 resources, which
this file builds programmatically rather than pasting 400 literal fixtures.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.connectors.crowdstrike import CrowdStrikeConnector

CREDS = {
    "client_id": "fake-client-id",
    "client_secret": "fake-client-secret",
    "base_url": "https://api.crowdstrike.com",
}

TOKEN_OK = {"access_token": "fake-cs-token"}


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a MockTransport.

    CrowdStrike constructs its own httpx.AsyncClient inside authenticate(), so we
    patch the class __init__ to inject a MockTransport transparently, mirroring
    test_wiz_connector.py's idiom.
    """
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _install_fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch asyncio.sleep to be instant so 429-retry pinned-behavior tests
    don't actually wait the real sleep(3)/sleep(5) durations."""

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)


def _json_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


# ── Main pagination + field-mapping fixture ──

MAIN_RESOURCE = {
    "id": "vuln-main",
    "vulnerability_id": "CVE-2024-7777",
    "aid": "aid-1",
    "apps": [
        {
            "product_name_version": "OpenSSL 1.1.1",
            "vendor_normalized": "openssl",
            "remediation": {"ids": ["rem-1"]},
        }
    ],
}


def _filler_resource(i: int) -> dict:
    return {"id": f"filler-{i}", "aid": "", "apps": []}


# >=400 resources on page 1 so the `after`-cursor loop actually continues
# (see module docstring — CrowdStrike's own len(resources) < 400 threshold).
PAGE_1_RESOURCES = [MAIN_RESOURCE] + [_filler_resource(i) for i in range(399)]
PAGE_2_RESOURCES = [{"id": "vuln-page2", "vulnerability_id": "CVE-2024-8888", "aid": "", "apps": []}]

DEVICE_AID_1 = {
    "device_id": "aid-1",
    "hostname": "CS-PROD-01",
    "local_ip": "10.9.9.9",
    "os_version": "22.04",
    "platform_name": "Ubuntu",
    "product_type_desc": "Server",
    "serial_number": "SN123",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "external_ip": "1.2.3.4",
    "last_login_user": "admin",
    "last_login_timestamp": "2026-01-01T00:00:00Z",
    "last_seen": "2026-01-02T00:00:00Z",
    "status": "normal",
    "containment_status": "normal",
    "system_manufacturer": "Dell",
    "system_product_name": "PowerEdge",
}

REMEDIATION_1 = {"id": "rem-1", "action": "Upgrade to OpenSSL 1.1.1w"}

# exploit_status 40 = "Used in Malware" -> exploit_available True (>=20), cisa_kev False (<50)
VULN_METADATA_MAIN = {"id": "vuln-main", "cve": {"exploit_status": 40, "cisa_kev": False}}


def _handler_factory(token_status: int = 201):
    """Route requests: OAuth token, Spotlight combined-vulnerabilities (paginated
    for the CRITICAL filter only, empty for HIGH/MEDIUM/LOW), devices, remediations,
    and vuln-metadata batch-enrichment endpoints."""
    calls = {"n": 0}
    critical_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        path = request.url.path

        if path == "/oauth2/token":
            if token_status != 201:
                return _json_response(token_status, {"errors": [{"message": "invalid_client"}]})
            return _json_response(201, TOKEN_OK)

        if path == "/spotlight/combined/vulnerabilities/v1":
            params = dict(request.url.params)
            if "CRITICAL" not in params.get("filter", ""):
                return _json_response(200, {"resources": []})
            critical_calls["n"] += 1
            after = params.get("after")
            if after == "cursor-2":
                return _json_response(200, {"resources": PAGE_2_RESOURCES, "meta": {"pagination": {"after": None}}})
            return _json_response(200, {"resources": PAGE_1_RESOURCES, "meta": {"pagination": {"after": "cursor-2"}}})

        if path == "/devices/entities/devices/v2":
            return _json_response(200, {"resources": [DEVICE_AID_1]})

        if path == "/spotlight/entities/remediations/v2":
            return _json_response(200, {"resources": [REMEDIATION_1]})

        if path == "/spotlight/entities/vulnerabilities/v2":
            ids = request.url.params.get_list("ids")
            if "vuln-main" in ids:
                return _json_response(200, {"resources": [VULN_METADATA_MAIN]})
            return _json_response(200, {"resources": []})

        return _json_response(404, {"error": "not found"})

    return handler, calls, critical_calls


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    handler, _calls, _crit = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_returns_false(monkeypatch: pytest.MonkeyPatch):
    """A 401 token response returns False (CrowdStrike's own convention —
    checks status_code == 201, no raise_for_status call in authenticate())."""
    handler, _calls, _crit = _handler_factory(token_status=401)
    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is False


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_paginates_after_cursor_to_completion(monkeypatch: pytest.MonkeyPatch):
    """_fetch_vulns_by_filter follows the `after` cursor across >=2 pages for the
    CRITICAL severity filter (the only one with >=400 first-page resources)."""
    handler, _calls, critical_calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert critical_calls["n"] >= 2
    assert len(results) == len(PAGE_1_RESOURCES) + len(PAGE_2_RESOURCES)
    assert any(v.source_vuln_id == "vuln-page2" for v in results)


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps the fixture response field-for-field into
    NormalizedVulnerability, including device + remediation + exploit/KEV enrichment."""
    handler, _calls, _crit = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    main = next(v for v in results if v.source_vuln_id == "vuln-main")

    assert main.cve_id == "CVE-2024-7777"
    assert main.severity == "CRITICAL"
    assert main.hostname == "cs-prod-01"  # lower()'d per _normalize_vuln
    assert main.ip_addresses == ["10.9.9.9"]
    assert main.affected_product == "OpenSSL 1.1.1"
    assert main.remediation_info == "Upgrade to OpenSSL 1.1.1w"
    assert main.exploit_available is True
    assert main.cisa_kev is False
    assert main.os_name == "Ubuntu"
    assert main.os_version == "22.04"
    # CrowdStrike's Spotlight combined-vulnerabilities endpoint never supplies these —
    # pinned as None, not a mapping omission.
    assert main.vulnerability_name is None
    assert main.cvss_v3_score is None


@pytest.mark.asyncio
async def test_main_loop_retries_429_unbounded(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — main loop retries 429 unbounded; enrichment batches drop on 429
    # (see 23-RESEARCH Open Question 10). This test pins the main-loop half.
    _install_fast_sleep(monkeypatch)
    critical_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/oauth2/token":
            return _json_response(201, TOKEN_OK)
        if path == "/spotlight/combined/vulnerabilities/v1":
            params = dict(request.url.params)
            if "CRITICAL" not in params.get("filter", ""):
                return _json_response(200, {"resources": []})
            critical_calls["n"] += 1
            if critical_calls["n"] == 1:
                return httpx.Response(429, headers={})
            return _json_response(
                200,
                {"resources": [{"id": "v1", "vulnerability_id": "CVE-9999-0001", "aid": "", "apps": []}]},
            )
        return _json_response(200, {"resources": []})

    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert critical_calls["n"] == 2  # 429 then success — retried, not abandoned
    assert any(v.cve_id == "CVE-9999-0001" for v in results)


@pytest.mark.asyncio
async def test_enrichment_batch_drops_on_429_no_retry(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — this is the enrichment-batch half of the same inconsistency:
    # _resolve_devices_batch (and its remediation/vuln-metadata/eval-logic siblings)
    # sleep(3) on 429 but do NOT retry — the batch's data is silently dropped.
    _install_fast_sleep(monkeypatch)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, headers={})

    _install_mock_transport(monkeypatch, handler)

    connector = CrowdStrikeConnector()
    connector.client = httpx.AsyncClient(base_url="https://mock")
    connector.access_token = "tok"

    await connector._resolve_devices_batch(["aid-x"])

    assert calls["n"] == 1  # no retry attempted
    assert connector._device_cache == {}  # batch silently dropped
