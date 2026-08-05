"""Phase 8 — connector normalization coverage (test coverage floor).

At least one test per vulnerability-scanner connector, exercising each one's
pure normalization / severity-mapping logic (no live HTTP, no credentials).
This is the correctness-critical layer: every scanner's raw payload must map
into a consistent NormalizedVulnerability so the aggregation/correlation across
scanners is sound.

Covered scanners: CrowdStrike, Defender, Nessus, Qualys, Rapid7, Wiz.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.defender import DefenderConnector
from app.connectors.nessus import SEVERITY_MAP as NESSUS_SEVERITY_MAP
from app.connectors.nessus import _normalize_vuln as nessus_normalize
from app.connectors.nessus import _parse_os as nessus_parse_os
from app.connectors.qualys import _normalize_detection as qualys_normalize_detection
from app.connectors.qualys import _parse_os as qualys_parse_os
from app.connectors.rapid7 import Rapid7Connector
from app.connectors.wiz import WizConnector, _map_misconfig_severity, _map_vuln_severity

_VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


# ── Rapid7 — CVSS → severity thresholds ───────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "expected"),
    [(9.0, "CRITICAL"), (9.9, "CRITICAL"), (7.0, "HIGH"), (6.9, "MEDIUM"), (4.0, "MEDIUM"), (3.9, "LOW"), (0.0, "LOW")],
)
def test_rapid7_severity_from_cvss(score, expected):
    assert Rapid7Connector._severity_from_cvss(score) == expected


def test_rapid7_severity_none_defaults_low():
    assert Rapid7Connector._severity_from_cvss(None) == "LOW"


# ── Wiz — severity maps + safe fallbacks ──────────────────────────────────────


def test_wiz_vuln_severity_fallbacks():
    assert _map_vuln_severity(None) == "MEDIUM"  # missing → MEDIUM
    assert _map_vuln_severity("totally-unknown") == "MEDIUM"  # unmapped → MEDIUM
    assert _map_vuln_severity("critical") in _VALID_SEVERITIES  # case-insensitive, valid


def test_wiz_misconfig_severity_fallbacks():
    assert _map_misconfig_severity(None) == "LOW"  # missing → LOW
    assert _map_misconfig_severity("totally-unknown") == "LOW"
    assert _map_misconfig_severity("high") in _VALID_SEVERITIES


# ── Qualys — OS string parsing ────────────────────────────────────────────────


def test_qualys_parse_os_splits_trailing_version():
    assert qualys_parse_os("Red Hat Enterprise Linux 8.4") == ("Red Hat Enterprise Linux", "8.4")


def test_qualys_parse_os_no_version_and_empty():
    assert qualys_parse_os("Windows") == ("Windows", "")
    assert qualys_parse_os("") == ("", "")


# ── Nessus — OS parsing + numeric-severity normalization ──────────────────────


def test_nessus_parse_os():
    assert nessus_parse_os("Microsoft Windows 10 Pro 10.0.19041") == ("Microsoft Windows 10 Pro", "10.0.19041")
    assert nessus_parse_os("") == ("", "")


def test_nessus_severity_map_ordering():
    assert NESSUS_SEVERITY_MAP[4] == "CRITICAL"
    assert NESSUS_SEVERITY_MAP[0] == "INFO"


def test_nessus_normalize_vuln_maps_severity_and_cves():
    vuln = {
        "plugin_id": 12345,
        "plugin_name": "Some RCE",
        "severity": 4,  # → CRITICAL
        "cvss3_base_score": 9.8,
        "cve": ["CVE-2024-0001", "CVE-2024-0002"],
        "solution": "Patch it",
    }
    out = nessus_normalize(vuln, hostname="host-1", host_ip="10.0.0.1", os_name="Linux", os_version="5.4")
    assert {v.cve_id for v in out} == {"CVE-2024-0001", "CVE-2024-0002"}  # one per CVE
    assert all(v.severity == "CRITICAL" for v in out)
    assert all(v.hostname == "host-1" for v in out)


def test_nessus_normalize_vuln_synthesizes_id_when_no_cve():
    vuln = {"plugin_id": 999, "plugin_name": "Info finding", "severity": 1, "cve": []}
    out = nessus_normalize(vuln, hostname="h", host_ip="1.1.1.1", os_name="", os_version="")
    assert len(out) == 1
    assert out[0].cve_id == "NESSUS-999"  # synthetic id when no CVE
    assert out[0].severity == "LOW"


# ── Defender — record normalization ───────────────────────────────────────────


def test_defender_normalize_vuln_maps_fields():
    conn = DefenderConnector()
    conn._machine_cache = {"m1": {"computerDnsName": "win-box", "ipAddresses": [{"ipAddress": "10.0.0.5"}]}}
    rec = {"cveId": "CVE-2024-1234", "machineId": "m1", "severity": "High", "cvssV3": "7.5"}
    v = conn._normalize_vuln(rec)
    assert v is not None
    assert v.cve_id == "CVE-2024-1234"
    assert v.severity == "HIGH"  # "High" → uppercased
    assert v.cvss_v3_score == 7.5  # coerced to float
    assert v.hostname == "win-box"
    assert "10.0.0.5" in v.ip_addresses


def test_defender_normalize_vuln_skips_records_without_cve():
    conn = DefenderConnector()
    assert conn._normalize_vuln({"machineId": "m1", "severity": "High"}) is None


def test_defender_normalize_vuln_unknown_severity_defaults_medium():
    conn = DefenderConnector()
    conn._machine_cache = {}
    v = conn._normalize_vuln({"cveId": "CVE-2024-1", "machineId": "x", "severity": "bogus"})
    assert v is not None and v.severity == "MEDIUM"


# ── CrowdStrike — item normalization + severity passthrough ───────────────────


def test_crowdstrike_normalize_vuln_extracts_cve_and_severity():
    conn = CrowdStrikeConnector()
    item = {"vulnerability_id": "CVE-2024-9999", "aid": "a1", "apps": []}
    v = conn._normalize_vuln(item, "CRITICAL")
    assert v is not None
    assert v.cve_id == "CVE-2024-9999"
    assert v.severity == "CRITICAL"


def test_crowdstrike_normalize_vuln_reads_nested_cve_object():
    conn = CrowdStrikeConnector()
    item = {"cve": {"id": "CVE-2024-8888"}, "aid": "a2", "apps": []}
    v = conn._normalize_vuln(item, "HIGH")
    assert v is not None and v.cve_id == "CVE-2024-8888"


def test_crowdstrike_normalize_vuln_without_cve_has_null_cve_id():
    # CrowdStrike still normalizes an item with no CVE id (cve_id is None);
    # it does not drop the finding — documents current behavior.
    conn = CrowdStrikeConnector()
    v = conn._normalize_vuln({"aid": "a3", "apps": []}, "LOW")
    assert v is not None and v.cve_id is None


# ── ENRICH-06 (Phase 31 Plan 05): cross-6 native_priority_*/source_signals
# sweep — a representative call into EVERY connector's normalize path proves
# all 3 new dataclass fields are always explicitly SET (never
# AttributeError, never a silent omission): populated for the connector's
# own genuine signal, explicit None everywhere else (by design, not by
# crash/omission). ───────────────────────────────────────────────────────────


def _build_crowdstrike_findings(monkeypatch: pytest.MonkeyPatch):
    """CrowdStrike's own genuine native signal is the ExPRT.AI categorical
    RATING; native_priority_score stays None (no confirmed numeric ExPRT
    companion field — 31-RESEARCH.md Assumptions Log)."""
    conn = CrowdStrikeConnector()
    conn._vuln_metadata_cache["vuln-sweep"] = {"cve": {"exploit_status": 50, "exprt_rating": "HIGH"}}
    item = {"id": "vuln-sweep", "vulnerability_id": "CVE-2030-0001", "aid": "", "apps": []}
    v = conn._normalize_vuln(item, "CRITICAL")
    return [v] if v else []


def _build_nessus_findings(monkeypatch: pytest.MonkeyPatch):
    """Nessus VPR is numeric-only — native_priority_rating stays explicit
    None; native_priority_score populates via the vpr_score probe."""
    vuln = {
        "plugin_id": 555555,
        "plugin_name": "Sweep RCE",
        "severity": 3,
        "cve": ["CVE-2030-0002"],
        "plugin_attributes": {"vpr_score": "7.8"},
    }
    return nessus_normalize(vuln, hostname="sweep-host", host_ip="10.1.1.1", os_name="Linux", os_version="5.10")


def _build_defender_findings(monkeypatch: pytest.MonkeyPatch):
    """Defender has NO vendor-authored composite (Pitfall 6) — both
    native_priority_* stay explicit None regardless of input."""
    conn = DefenderConnector()
    conn._machine_cache = {"m-sweep": {"computerDnsName": "sweep-box", "ipAddresses": []}}
    rec = {
        "cveId": "CVE-2030-0003",
        "machineId": "m-sweep",
        "severity": "High",
        "cvssV3": 7.0,
        "exploitVerified": True,
    }
    v = conn._normalize_vuln(rec)
    return [v] if v else []


def _build_qualys_findings(monkeypatch: pytest.MonkeyPatch):
    """Qualys QDS is numeric-only — native_priority_rating stays explicit
    None; native_priority_score reads from the per-DETECTION dict (Pitfall
    4), never kb_cache."""
    detection = {"qid": 100234, "severity": 4, "QDS": "82"}
    host = {"ip": "10.1.1.2", "dns": "sweep-qualys", "os": "Ubuntu 22.04"}
    kb_cache = {
        100234: {
            "TITLE": "Sweep Qualys Vuln",
            "CVSS_V3": {"BASE": "8.5"},
            "CVE_LIST": {"CVE": [{"ID": "CVE-2030-0004"}]},
        }
    }
    return qualys_normalize_detection(detection, host, kb_cache)


async def _build_rapid7_findings(monkeypatch: pytest.MonkeyPatch):
    """Rapid7 has no extractable pure-normalize function
    (fetch_vulnerabilities is the only entry point) — reuses
    test_rapid7_connector.py's own MockTransport routing convention. Risk
    Score is numeric-only — native_priority_rating stays explicit None;
    native_priority_score reads from vuln_entry (Pitfall 5), never detail."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path == "/api/3/assets":
            if params.get("size") == "1":
                return httpx.Response(200, json={"resources": [{"id": 900}], "page": {"totalPages": 1}})
            return httpx.Response(
                200,
                json={
                    "resources": [
                        {
                            "id": 900,
                            "hostName": "sweep-r7-host",
                            "ip": "10.1.1.3",
                            "os": {"description": "Linux", "version": "5.10"},
                        }
                    ],
                    "page": {"totalPages": 1},
                },
            )
        if path == "/api/3/assets/900/vulnerabilities":
            return httpx.Response(
                200,
                json={"resources": [{"id": "sweep-vuln", "riskScore": 653.5}], "page": {"totalPages": 1}},
            )
        if path == "/api/3/vulnerabilities/sweep-vuln":
            return httpx.Response(
                200,
                json={
                    "id": "sweep-vuln",
                    "title": "Sweep Rapid7 Vuln",
                    "cvss": {"v3": {"score": 6.5}},
                    "exploits": 0,
                    "cves": ["CVE-2030-0005"],
                },
            )
        if path == "/api/3/vulnerabilities/sweep-vuln/solutions":
            return httpx.Response(200, json={"resources": []})
        return httpx.Response(404, json={"message": "not found"})

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    connector = Rapid7Connector()
    await connector.authenticate(
        {"url": "https://sweep.example.com:3780", "username": "sweep-user", "password": "sweep-pass"},
        {},
    )
    results = await connector.fetch_vulnerabilities()
    await connector.close()
    return results


async def _build_wiz_findings(monkeypatch: pytest.MonkeyPatch):
    """Wiz has no pure extractable normalize function (fetch_vulnerabilities
    builds NormalizedVulnerability inline per GraphQL node) — reuses
    test_wiz_connector.py's own MockTransport convention. Wiz has NO
    vendor-authored composite (Pitfall 6) — both native_priority_* stay
    explicit None regardless of input."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "sweep-token", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "data": {
                    "vulnerabilityFindings": {
                        "nodes": [
                            {
                                "id": "finding-sweep-1",
                                "name": "CVE-2030-0006",
                                "detailedName": "Sweep Wiz finding",
                                "severity": "HIGH",
                                "score": 7.9,
                                "exploitAvailable": False,
                                "hasExploit": False,
                                "hasCisaKevExploit": False,
                                "status": "OPEN",
                                "vulnerableAsset": {
                                    "id": "asset-sweep-1",
                                    "name": "sweep-wiz-host",
                                    "operatingSystem": "Amazon Linux 2",
                                    "ipAddresses": ["10.2.2.2"],
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
            "client_id": "sweep-id",
            "client_secret": "sweep-secret",
            "api_url": "https://api.sweep.wiz.io",
            "auth_url": "https://auth.sweep.wiz.io",
        },
        {},
    )
    results = await connector.fetch_vulnerabilities()
    await connector.close()
    return results


async def _maybe_await(value):
    """Uniformly resolve either a plain return value (the 4 connectors with
    a pure, synchronous normalize function) or a coroutine (Wiz/Rapid7,
    which have no extractable pure-function and must be exercised through
    their async fetch_vulnerabilities() with a mocked HTTP/GraphQL
    transport)."""
    if asyncio.iscoroutine(value):
        return await value
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connector_name", "build_findings", "expect_score_populated", "expect_rating_populated"),
    [
        ("crowdstrike", _build_crowdstrike_findings, False, True),
        ("nessus", _build_nessus_findings, True, False),
        ("defender", _build_defender_findings, False, False),
        ("wiz", _build_wiz_findings, False, False),
        ("qualys", _build_qualys_findings, True, False),
        ("rapid7", _build_rapid7_findings, True, False),
    ],
)
async def test_all_6_connectors_set_native_priority_and_source_signals(
    connector_name, build_findings, expect_score_populated, expect_rating_populated, monkeypatch
):
    """ENRICH-06 cross-6 sweep: a representative call into EVERY connector's
    normalize path returns finding(s) where native_priority_score,
    native_priority_rating, and source_signals are all SET dataclass
    attributes (never AttributeError) — populated for the connector's own
    genuine signal (CrowdStrike: rating; Nessus/Qualys/Rapid7: score), and
    explicitly None (by design, not by omission/crash) for Defender/Wiz
    (Pitfall 6: no vendor-authored composite) and for the *_rating half on
    every numeric-only connector."""
    findings = await _maybe_await(build_findings(monkeypatch))

    assert findings, f"{connector_name}: sweep fixture produced no findings"

    for finding in findings:
        # ENRICH-06: all 3 fields are always explicitly SET attributes --
        # never a missing attribute (AttributeError), regardless of source.
        assert hasattr(finding, "native_priority_score")
        assert hasattr(finding, "native_priority_rating")
        assert hasattr(finding, "source_signals")
        assert finding.source_signals is None or isinstance(finding.source_signals, dict)

        # D-08: no PII-adjacent or already-promoted column name ever leaks
        # into source_signals, across all 6 connectors.
        if finding.source_signals:
            for forbidden in (
                "hostname",
                "ip_addresses",
                "cve_id",
                "cvss",
                "severity",
                "epss",
                "native_priority",
                "last_login_user",
                "serial_number",
            ):
                assert forbidden not in finding.source_signals, (
                    f"{connector_name}: forbidden key {forbidden!r} leaked into source_signals"
                )

    representative = findings[0]

    if expect_score_populated:
        assert representative.native_priority_score is not None, (
            f"{connector_name}: expected a populated native_priority_score for this fixture"
        )
    else:
        assert representative.native_priority_score is None, (
            f"{connector_name}: native_priority_score must be explicit None (by design), not populated"
        )

    if expect_rating_populated:
        assert representative.native_priority_rating is not None, (
            f"{connector_name}: expected a populated native_priority_rating for this fixture"
        )
    else:
        assert representative.native_priority_rating is None, (
            f"{connector_name}: native_priority_rating must be explicit None (by design), not populated"
        )
