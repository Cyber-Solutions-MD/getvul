"""Phase 23 Plan 02 — Nessus connector coverage (REL-03, incl. D-21 verify_tls default).

Exercises the full simulated sync: authenticate (API-key headers, a
`/server/status` probe, False-on-failure convention, no raise) -> list
completed scans -> per-scan detail -> per-host detail -> fetch_vulnerabilities
-> NormalizedVulnerability mapping, via an httpx.MockTransport (no live
credentials). Also pins D-21: verify_tls resolves from config, default True.

NOTE (deviation from 23-CONTEXT.md's assumption): this connector's actual
fetch_vulnerabilities does NOT implement a scan-export request/poll/download
loop — the real code lists completed scans, then GETs /scans/{id} and
/scans/{id}/hosts/{id} directly (no export/poll endpoints exist anywhere in
nessus.py). The "multi-page pagination followed to completion" requirement
(D-05) is satisfied here as a multi-scan/multi-host iteration-to-completion
test instead — the real analog of pagination for this connector's shape —
rather than a poll-loop test, since the poll loop does not exist in the
current codebase. See 23-02-SUMMARY.md for this discovered plan/code mismatch.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.connectors.nessus import NessusConnector


def _install_fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch asyncio.sleep to be instant — fetch_vulnerabilities pauses 0.25s/0.5s
    between host/scan requests for rate-limiting; not relevant to test correctness."""

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)


CREDS = {
    "url": "https://nessus.example.com:8834",
    "access_key": "fake-access-key",
    "secret_key": "fake-secret-key",
}

SCANS_LIST = {
    "scans": [
        {"id": 1, "name": "Scan A", "status": "completed"},
        {"id": 2, "name": "Scan B", "status": "completed"},
        {"id": 3, "name": "Scan C", "status": "running"},  # must be filtered out
    ]
}

SCAN_1_DETAIL = {"hosts": [{"host_id": 10}]}
SCAN_2_DETAIL = {"hosts": [{"host_id": 20}]}

HOST_1_DETAIL = {
    "info": {
        "host-ip": "10.2.2.2",
        "host-fqdn": "nessus-host-a",
        "operating-system": "Ubuntu 22.04",
    },
    "vulnerabilities": [
        {
            "plugin_id": 12345,
            "plugin_name": "OpenSSL Heap Overflow",
            "severity": 4,
            "cvss3_base_score": 9.1,
            "solution": "Upgrade OpenSSL to 3.0.14",
            "cve": ["CVE-2024-3333"],
            "plugin_attributes": {"exploit_available": "true"},
        }
    ],
}

HOST_2_DETAIL = {
    "info": {
        "host-ip": "10.2.2.3",
        "host-fqdn": "nessus-host-b",
        "operating-system": "Debian 12",
    },
    "vulnerabilities": [
        {
            "plugin_id": 54321,
            "plugin_name": "Weak Cipher Suite",
            "severity": 2,
            "cve": [],
        }
    ],
}


def _json_response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )


def _install_capture_transport(monkeypatch: pytest.MonkeyPatch, handler, captured_kwargs: list) -> None:
    """Patch httpx.AsyncClient.__init__ to inject a MockTransport AND record the
    constructor kwargs (used to assert the `verify` kwarg — D-21)."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        captured_kwargs.append(dict(kwargs))
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _handler_factory(auth_status: int = 200):
    calls: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls[path] = calls.get(path, 0) + 1

        if path == "/server/status":
            if auth_status != 200:
                return _json_response(auth_status, {"error": "unauthorized"})
            return _json_response(200, {"status": "ready"})
        if path == "/scans":
            return _json_response(200, SCANS_LIST)
        if path == "/scans/1":
            return _json_response(200, SCAN_1_DETAIL)
        if path == "/scans/1/hosts/10":
            return _json_response(200, HOST_1_DETAIL)
        if path == "/scans/2":
            return _json_response(200, SCAN_2_DETAIL)
        if path == "/scans/2/hosts/20":
            return _json_response(200, HOST_2_DETAIL)

        return _json_response(404, {"error": f"unexpected path {path}"})

    return handler, calls


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    handler, _calls = _handler_factory()
    _install_capture_transport(monkeypatch, handler, [])

    connector = NessusConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_returns_false(monkeypatch: pytest.MonkeyPatch):
    """A 401 /server/status probe raises via resp.raise_for_status(), caught and
    converted to a clean False return (Nessus's own convention — no propagated
    exception)."""
    handler, _calls = _handler_factory(auth_status=401)
    _install_capture_transport(monkeypatch, handler, [])

    connector = NessusConnector()
    result = await connector.authenticate(CREDS, {})

    assert result is False


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_iterates_all_completed_scans_to_completion(
    monkeypatch: pytest.MonkeyPatch,
):
    """Both completed scans (1 and 2) are processed to completion — the running
    scan (3) is filtered out and never requested."""
    _install_fast_sleep(monkeypatch)
    handler, calls = _handler_factory()
    _install_capture_transport(monkeypatch, handler, [])

    connector = NessusConnector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert calls.get("/scans/1") == 1
    assert calls.get("/scans/1/hosts/10") == 1
    assert calls.get("/scans/2") == 1
    assert calls.get("/scans/2/hosts/20") == 1
    assert "/scans/3" not in calls  # status=running is filtered out
    assert len(results) == 2


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps a fixture response field-for-field into
    NormalizedVulnerability, across both hosts."""
    _install_fast_sleep(monkeypatch)
    handler, _calls = _handler_factory()
    _install_capture_transport(monkeypatch, handler, [])

    connector = NessusConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    by_cve = {r.cve_id: r for r in results}

    first = by_cve["CVE-2024-3333"]
    assert first.vulnerability_name == "OpenSSL Heap Overflow"
    assert first.cvss_v3_score == 9.1
    assert first.severity == "CRITICAL"
    assert first.source_vuln_id == "12345"
    assert first.hostname == "nessus-host-a"
    assert first.ip_addresses == ["10.2.2.2"]
    assert first.os_name == "Ubuntu"
    assert first.os_version == "22.04"
    assert first.remediation_info == "Upgrade OpenSSL to 3.0.14"
    assert first.exploit_available is True

    # No CVE on the second plugin -> falls back to a NESSUS-{plugin_id} synthetic id.
    second = by_cve["NESSUS-54321"]
    assert second.vulnerability_name == "Weak Cipher Suite"
    assert second.severity == "MEDIUM"  # severity_int=2 per SEVERITY_MAP
    assert second.hostname == "nessus-host-b"
    assert second.exploit_available is False


@pytest.mark.asyncio
async def test_verify_tls_defaults_true_and_config_can_disable(monkeypatch: pytest.MonkeyPatch):
    """D-21: verify_tls resolves to True by default; only explicit config
    verify_tls:false disables TLS validation."""
    handler, _calls = _handler_factory()
    captured: list = []
    _install_capture_transport(monkeypatch, handler, captured)

    connector = NessusConnector()
    await connector.authenticate(CREDS, {})
    await connector.close()
    assert captured[-1]["verify"] is True

    connector2 = NessusConnector()
    await connector2.authenticate(CREDS, {"verify_tls": False})
    await connector2.close()
    assert captured[-1]["verify"] is False
