"""Phase 32 Plan 04 — per-connector real internet_facing detection (EXPO-02).

Proves, per connector, whether a real vendor-supplied internet-facing /
public-exposure signal is mapped into `NormalizedVulnerability.internet_facing`
or whether the connector legitimately has no such signal today (documented
FALLBACK — `internet_facing` stays the dataclass default of `None`, so
`infer_exposure_context`'s external_ip/tag proxy applies downstream).

This session's inspection of all 6 connectors' actual raw payload/GraphQL
response shape (crowdstrike.py, wiz.py, qualys.py, nessus.py, rapid7.py,
defender.py) found ZERO connectors that currently extract a distinct
internet-facing/public-exposure signal — see `app/assets/exposure.py`'s
module docstring for the full honest per-connector coverage table (re-
confirms 32-PATTERNS.md's "No Analog Found" finding; no field name here is
guessed, per CONTEXT.md's explicit instruction). This cross-6 sweep proves
that honestly, the same way test_connector_normalization.py's
ENRICH-06 sweep proves native_priority_*/source_signals population — every
connector's normalize path is exercised with a representative payload and
`internet_facing` is asserted `None` (never a crash, never a fabricated
value) in every case.

If a future session confirms a real vendor field (e.g. a live Wiz schema
introspection turns up a genuine public-exposure field), that connector
moves from this file's FALLBACK assertion to a REAL-signal assertion, and
the coverage table in exposure.py's docstring is updated to match — the
rest of the wiring (dataclass field, Asset column, sync passthrough,
inference precedence) needs zero changes (Plan 04's schema spine already
lands ahead of any confirmed per-connector mapping).
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.defender import DefenderConnector
from app.connectors.nessus import _normalize_vuln as nessus_normalize
from app.connectors.qualys import _normalize_detection as qualys_normalize_detection
from app.connectors.rapid7 import Rapid7Connector
from app.connectors.wiz import WizConnector


def _build_crowdstrike_findings():
    """CrowdStrike's device dict (`/devices/entities/devices/v2`) exposes
    `external_ip` (already the v1 proxy's own signal) but no distinct
    public-exposure/security-group field — FALLBACK."""
    conn = CrowdStrikeConnector()
    conn._device_cache["a1"] = {"hostname": "cs-host", "external_ip": "203.0.113.9"}
    item = {"vulnerability_id": "CVE-2031-0001", "aid": "a1", "apps": []}
    v = conn._normalize_vuln(item, "CRITICAL")
    return [v] if v else []


def _build_nessus_findings():
    """Nessus scan/host detail surfaces hostname/ip/os plus plugin output —
    no exposure/network-zone field — FALLBACK."""
    vuln = {
        "plugin_id": 700001,
        "plugin_name": "IF-sweep RCE",
        "severity": 3,
        "cve": ["CVE-2031-0002"],
    }
    return nessus_normalize(vuln, hostname="if-sweep-nessus", host_ip="10.3.1.1", os_name="Linux", os_version="5.10")


def _build_defender_findings():
    """Defender's machine dict surfaces hostname/ip/health/exploit fields —
    `exposureScore` (a per-tenant risk metric, not a per-machine public-
    exposure boolean) is not queried by this connector — FALLBACK."""
    conn = DefenderConnector()
    conn._machine_cache = {"m-if": {"computerDnsName": "if-sweep-defender", "ipAddresses": []}}
    rec = {"cveId": "CVE-2031-0003", "machineId": "m-if", "severity": "High", "cvssV3": 7.0}
    v = conn._normalize_vuln(rec)
    return [v] if v else []


def _build_qualys_findings():
    """Qualys host list (`/api/2.0/fo/asset/host/`) feeds only ip/dns/os into
    `_normalize_detection` — no TRACKING_METHOD/network-zone/public-IP flag
    is extracted — FALLBACK."""
    detection = {"qid": 700004, "severity": 3}
    host = {"ip": "10.3.1.2", "dns": "if-sweep-qualys", "os": "Ubuntu 22.04"}
    kb_cache = {700004: {"TITLE": "IF-sweep Qualys Vuln", "CVE_LIST": {"CVE": [{"ID": "CVE-2031-0004"}]}}}
    return qualys_normalize_detection(detection, host, kb_cache)


async def _build_rapid7_findings(monkeypatch: pytest.MonkeyPatch):
    """InsightVM `/api/3/assets` resource dict surfaces hostName/ip/os — no
    `exposures`/tag-based internet-facing field is currently queried by this
    connector — FALLBACK."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path == "/api/3/assets":
            if params.get("size") == "1":
                return httpx.Response(200, json={"resources": [{"id": 901}], "page": {"totalPages": 1}})
            return httpx.Response(
                200,
                json={
                    "resources": [
                        {
                            "id": 901,
                            "hostName": "if-sweep-r7-host",
                            "ip": "10.3.1.3",
                            "os": {"description": "Linux", "version": "5.10"},
                        }
                    ],
                    "page": {"totalPages": 1},
                },
            )
        if path == "/api/3/assets/901/vulnerabilities":
            return httpx.Response(
                200,
                json={"resources": [{"id": "if-sweep-vuln", "riskScore": 500.0}], "page": {"totalPages": 1}},
            )
        if path == "/api/3/vulnerabilities/if-sweep-vuln":
            return httpx.Response(
                200,
                json={
                    "id": "if-sweep-vuln",
                    "title": "IF-sweep Rapid7 Vuln",
                    "cvss": {"v3": {"score": 6.0}},
                    "exploits": 0,
                    "cves": ["CVE-2031-0005"],
                },
            )
        if path == "/api/3/vulnerabilities/if-sweep-vuln/solutions":
            return httpx.Response(200, json={"resources": []})
        return httpx.Response(404, json={"message": "not found"})

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    connector = Rapid7Connector()
    await connector.authenticate(
        {"url": "https://if-sweep.example.com:3780", "username": "if-sweep-user", "password": "if-sweep-pass"},
        {},
    )
    results = await connector.fetch_vulnerabilities()
    await connector.close()
    return results


async def _build_wiz_findings(monkeypatch: pytest.MonkeyPatch):
    """Wiz's `vulnerableAsset` sub-object (both VULNERABILITY_QUERY and the
    EPSS-enriched VULNERABILITY_QUERY_ENRICHED) exposes cloudPlatform/
    region/ipAddresses/operatingSystem — no publicExposure/isInternetFacing
    field is queried — FALLBACK (T-32-12: not guessed without live schema
    confirmation)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "if-sweep-token", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "data": {
                    "vulnerabilityFindings": {
                        "nodes": [
                            {
                                "id": "finding-if-sweep-1",
                                "name": "CVE-2031-0006",
                                "detailedName": "IF-sweep Wiz finding",
                                "severity": "HIGH",
                                "score": 7.0,
                                "exploitAvailable": False,
                                "hasExploit": False,
                                "hasCisaKevExploit": False,
                                "status": "OPEN",
                                "vulnerableAsset": {
                                    "id": "asset-if-sweep-1",
                                    "name": "if-sweep-wiz-host",
                                    "operatingSystem": "Amazon Linux 2",
                                    "ipAddresses": ["10.4.4.4"],
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            },
        )

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    connector = WizConnector()
    await connector.authenticate(
        {
            "client_id": "if-sweep-id",
            "client_secret": "if-sweep-secret",
            "api_url": "https://api.if-sweep.wiz.io",
            "auth_url": "https://auth.if-sweep.wiz.io",
        },
        {},
    )
    results = await connector.fetch_vulnerabilities()
    await connector.close()
    return results


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connector_name", "build_findings"),
    [
        ("crowdstrike", _build_crowdstrike_findings),
        ("nessus", _build_nessus_findings),
        ("defender", _build_defender_findings),
        ("qualys", _build_qualys_findings),
        ("rapid7", _build_rapid7_findings),
        ("wiz", _build_wiz_findings),
    ],
)
async def test_all_6_connectors_internet_facing_is_documented_fallback(connector_name, build_findings, monkeypatch):
    """Cross-6 sweep (mirrors test_connector_normalization.py's ENRICH-06
    shape): every connector's normalize path always explicitly SETS
    `internet_facing` (never AttributeError) and it is `None` for all 6 —
    the honest, inspected-not-guessed conclusion for this session (see
    exposure.py's module docstring coverage table). `infer_exposure_context`
    falls through to the v1 external_ip/tag proxy for every one of them in
    production today."""
    if connector_name in ("rapid7", "wiz"):
        findings = await _maybe_await(build_findings(monkeypatch))
    else:
        findings = build_findings()

    assert findings, f"{connector_name}: sweep fixture produced no findings"

    for finding in findings:
        assert hasattr(finding, "internet_facing")
        assert finding.internet_facing is None, (
            f"{connector_name}: internet_facing must be None (documented FALLBACK) — "
            "no confirmed vendor signal is mapped for this connector"
        )
