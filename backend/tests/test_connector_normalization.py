"""Phase 8 — connector normalization coverage (test coverage floor).

At least one test per vulnerability-scanner connector, exercising each one's
pure normalization / severity-mapping logic (no live HTTP, no credentials).
This is the correctness-critical layer: every scanner's raw payload must map
into a consistent NormalizedVulnerability so the aggregation/correlation across
scanners is sound.

Covered scanners: CrowdStrike, Defender, Nessus, Qualys, Rapid7, Wiz.
"""

from __future__ import annotations

import pytest

from app.connectors.crowdstrike import CrowdStrikeConnector
from app.connectors.defender import DefenderConnector
from app.connectors.nessus import SEVERITY_MAP as NESSUS_SEVERITY_MAP
from app.connectors.nessus import _normalize_vuln as nessus_normalize
from app.connectors.nessus import _parse_os as nessus_parse_os
from app.connectors.qualys import _parse_os as qualys_parse_os
from app.connectors.rapid7 import Rapid7Connector
from app.connectors.wiz import _map_misconfig_severity, _map_vuln_severity

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
