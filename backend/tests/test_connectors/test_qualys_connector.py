"""Phase 23 Plan 02 — Qualys VMDR connector coverage (REL-03).

Exercises the full simulated sync: authenticate (Basic auth, a hosts-list
connectivity probe, False-on-failure convention, no raise) -> XML host-list
pagination -> XML VM-detection pagination -> knowledge-base batch enrichment
-> fetch_vulnerabilities -> NormalizedVulnerability mapping, via an
httpx.MockTransport (no live credentials).

Also pins D-22: `_request_with_rate_limit` retries on HTTP 409 (Qualys's own
rate-limit status code, not 429) and proactively throttles when
`X-RateLimit-Remaining <= 2`.

NOTE on pagination fixture size: both `_fetch_all_hosts` and
`_fetch_all_detections` only continue past page 1 when the page returned
>= 1000 records (`if len(host_list) < 1000: break` / `if len(host_records) < 1000: break`)
— genuinely exercising 2-page XML pagination therefore requires building a
1000-element first page programmatically rather than pasting a literal fixture.

NOTE (discovered, out of scope for this test-authoring plan per D-22/threat
model — no production code changes): three sites read a LOWERCASE-ONLY key
with no uppercase fallback, unlike `_normalize_detection`'s dual-case-checked
QID/SEVERITY/IP/DNS/OS fields:
  - `_fetch_all_hosts`/`_fetch_all_detections`: `h.get("id")` / `host_rec.get("id")`
    (the id_min pagination cursor + host_id association)
  - `fetch_vulnerabilities`'s KB-prefetch step: `det.get("qid")` (which QIDs get
    knowledge-base-enriched)
  - `_fetch_kb_entries`: `v.get("qid")` (which KB response rows get cached)
Real Qualys XML conventionally uses uppercase `<ID>`/`<QID>` tags, which would
silently break pagination cursoring, host-to-detection association, AND all
knowledge-base enrichment (title/CVSS/CVE/solution/exploit) against a live API
— `_normalize_detection`'s own qid/severity extraction works fine either way,
but the KB cache it reads from would stay permanently empty. This fixture uses
lowercase `id`/`qid` tags at exactly these sites to pin the connector's CURRENT
(as implemented) *working* behavior — logged to deferred-items.md as a real
production bug candidate, not fixed here per this plan's no-code-changes scope.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.connectors.qualys import QualysConnector, _normalize_detection

CREDS = {
    "url": "https://qualysapi.qualys.com",
    "username": "fake-user",
    "password": "fake-password",
}

REAL_HOST_ID = 1
REAL_QID = 100234
FILLER_QID = 9999


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def _install_fast_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)


def _xml_response(status: int, body: bytes, headers: dict | None = None) -> httpx.Response:
    all_headers = {"content-type": "text/xml"}
    if headers:
        all_headers.update(headers)
    return httpx.Response(status_code=status, content=body, headers=all_headers)


# ── XML fixture builders (see module docstring on the >=1000-record threshold) ──


def _build_hosts_page_1() -> bytes:
    parts = []
    for hid in range(1, 1001):
        if hid == REAL_HOST_ID:
            parts.append(f"<HOST><id>{hid}</id><IP>10.3.3.3</IP><DNS>qualys-host-1</DNS><OS>Ubuntu 20.04</OS></HOST>")
        else:
            parts.append(f"<HOST><id>{hid}</id><IP></IP><DNS></DNS><OS></OS></HOST>")
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<HOST_LIST_OUTPUT><RESPONSE><HOST_LIST>" + "".join(parts) + "</HOST_LIST></RESPONSE></HOST_LIST_OUTPUT>"
    ).encode()


def _build_hosts_page_2() -> bytes:
    return (
        b"<?xml version='1.0' encoding='UTF-8'?>"
        b"<HOST_LIST_OUTPUT><RESPONSE><HOST_LIST>"
        b"<HOST><id>1001</id><IP></IP><DNS></DNS><OS></OS></HOST>"
        b"</HOST_LIST></RESPONSE></HOST_LIST_OUTPUT>"
    )


def _build_detections_page_1() -> bytes:
    parts = []
    for hid in range(1, 1001):
        qid = REAL_QID if hid == REAL_HOST_ID else FILLER_QID
        sev = 5 if hid == REAL_HOST_ID else 1
        parts.append(
            f"<HOST><id>{hid}</id><DETECTION_LIST>"
            f"<DETECTION><qid>{qid}</qid><SEVERITY>{sev}</SEVERITY></DETECTION>"
            "</DETECTION_LIST></HOST>"
        )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<HOST_VM_DETECTION_LIST_OUTPUT><RESPONSE><HOST_LIST>"
        + "".join(parts)
        + "</HOST_LIST></RESPONSE></HOST_VM_DETECTION_LIST_OUTPUT>"
    ).encode()


def _build_detections_page_2() -> bytes:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<HOST_VM_DETECTION_LIST_OUTPUT><RESPONSE><HOST_LIST>"
        "<HOST><id>1001</id><DETECTION_LIST>"
        f"<DETECTION><qid>{FILLER_QID}</qid><SEVERITY>1</SEVERITY></DETECTION>"
        "</DETECTION_LIST></HOST>"
        "</HOST_LIST></RESPONSE></HOST_VM_DETECTION_LIST_OUTPUT>"
    ).encode()


def _build_kb_page() -> bytes:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<KNOWLEDGE_BASE_VULN_LIST_OUTPUT><RESPONSE><VULN_LIST><VULN>"
        f"<qid>{REAL_QID}</qid><TITLE>OpenSSL Remote Code Execution</TITLE>"
        "<CVSS_V3><BASE>9.4</BASE></CVSS_V3>"
        "<CVE_LIST><CVE><ID>CVE-2024-9999</ID></CVE></CVE_LIST>"
        "<SOLUTION>Upgrade to OpenSSL 3.2.1</SOLUTION>"
        "<EXPLOIT_LIST><EXPLOIT><REF>EDB-99999</REF></EXPLOIT></EXPLOIT_LIST>"
        "</VULN></VULN_LIST></RESPONSE></KNOWLEDGE_BASE_VULN_LIST_OUTPUT>"
    ).encode()


HOSTS_PAGE_1 = _build_hosts_page_1()
HOSTS_PAGE_2 = _build_hosts_page_2()
DETECTIONS_PAGE_1 = _build_detections_page_1()
DETECTIONS_PAGE_2 = _build_detections_page_2()
KB_PAGE = _build_kb_page()


def _handler_factory(auth_status: int = 200):
    calls = {"hosts": 0, "detections": 0, "kb": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)

        if path == "/api/2.0/fo/asset/host/":
            if params.get("truncation_limit") == "1":
                # The authenticate() connectivity probe.
                if auth_status != 200:
                    return _xml_response(auth_status, b"<error/>")
                return _xml_response(200, b"<HOST_LIST_OUTPUT><RESPONSE/></HOST_LIST_OUTPUT>")
            calls["hosts"] += 1
            if "id_min" not in params:
                return _xml_response(200, HOSTS_PAGE_1)
            return _xml_response(200, HOSTS_PAGE_2)

        if path == "/api/2.0/fo/asset/host/vm/detection/":
            calls["detections"] += 1
            if "id_min" not in params:
                return _xml_response(200, DETECTIONS_PAGE_1)
            return _xml_response(200, DETECTIONS_PAGE_2)

        if path == "/api/2.0/fo/knowledge_base/vuln/":
            calls["kb"] += 1
            return _xml_response(200, KB_PAGE)

        return _xml_response(404, b"<error/>")

    return handler, calls


@pytest.mark.asyncio
async def test_authenticate_success_returns_true(monkeypatch: pytest.MonkeyPatch):
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = QualysConnector()
    result = await connector.authenticate(CREDS, {})
    await connector.close()

    assert result is True


@pytest.mark.asyncio
async def test_authenticate_failure_returns_false(monkeypatch: pytest.MonkeyPatch):
    """A 401 connectivity probe raises via resp.raise_for_status(), caught and
    converted to a clean False return (Qualys's own convention — no propagated
    exception)."""
    handler, _calls = _handler_factory(auth_status=401)
    _install_mock_transport(monkeypatch, handler)

    connector = QualysConnector()
    result = await connector.authenticate(CREDS, {})

    assert result is False


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_paginates_xml_to_completion(monkeypatch: pytest.MonkeyPatch):
    _install_fast_sleep(monkeypatch)
    handler, calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = QualysConnector()
    authed = await connector.authenticate(CREDS, {})
    assert authed is True

    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert calls["hosts"] == 2  # id_min cursor followed to a 2nd (terminal) page
    assert calls["detections"] == 2
    assert len(results) == 1001  # 1000 (page 1) + 1 (page 2) detections


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_field_mapping(monkeypatch: pytest.MonkeyPatch):
    """fetch_vulnerabilities maps a fixture response field-for-field into
    NormalizedVulnerability, including host + knowledge-base enrichment."""
    _install_fast_sleep(monkeypatch)
    handler, _calls = _handler_factory()
    _install_mock_transport(monkeypatch, handler)

    connector = QualysConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    real = next(r for r in results if r.cve_id == "CVE-2024-9999")

    assert real.vulnerability_name == "OpenSSL Remote Code Execution"
    assert real.cvss_v3_score == 9.4
    assert real.severity == "CRITICAL"
    assert real.source_vuln_id == str(REAL_QID)
    assert real.hostname == "qualys-host-1"
    assert real.ip_addresses == ["10.3.3.3"]
    assert real.os_name == "Ubuntu"
    assert real.os_version == "20.04"
    assert real.remediation_info == "Upgrade to OpenSSL 3.2.1"
    assert real.exploit_available is True

    # Filler detections have no KB entry -> fall back to a QID-{qid} synthetic id.
    filler = next(r for r in results if r.cve_id == f"QID-{FILLER_QID}")
    assert filler.vulnerability_name == f"QID {FILLER_QID}"
    assert filler.exploit_available is False


@pytest.mark.asyncio
async def test_409_retry_pinned(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — Qualys retries on HTTP 409 (its own rate-limit status code,
    # not 429), up to `_retries` attempts.
    _install_fast_sleep(monkeypatch)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _xml_response(409, b"<error/>", headers={"X-RateLimit-ToWait-Sec": "0"})
        return _xml_response(200, b"<ok/>")

    connector = QualysConnector()
    connector._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")

    resp = await connector._request_with_rate_limit("GET", "/some/path")
    await connector.close()

    assert resp.status_code == 200
    assert calls["n"] == 2  # 409 then success — retried, not abandoned


@pytest.mark.asyncio
async def test_proactive_throttle_on_low_rate_limit_remaining(monkeypatch: pytest.MonkeyPatch):
    # D-22: pinned — proactively sleeps X-RateLimit-ToWait-Sec whenever
    # X-RateLimit-Remaining <= 2, even on an otherwise-successful response.
    sleep_calls: list = []

    async def _spy_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _spy_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return _xml_response(200, b"<ok/>", headers={"X-RateLimit-Remaining": "2", "X-RateLimit-ToWait-Sec": "7"})

    connector = QualysConnector()
    connector._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://mock")

    resp = await connector._request_with_rate_limit("GET", "/some/path")
    await connector.close()

    assert resp.status_code == 200
    assert 7 in sleep_calls


# ── ENRICH-03/04 (Phase 31 Plan 04): QDS -> native_priority_score,
# source_signals missing-vs-negative (Pitfall 4: read from the detection
# dict, NEVER kb_cache -- QDS is computed at detection time, not a QID-level
# knowledge-base constant) ──────────────────────────────────────────────────


def test_normalize_detection_qds_populates_native_priority_score():
    """A detection dict carrying a QDS value -> native_priority_score == the
    raw QDS number (1-100) on EVERY per-CVE fanout finding (D-06: no
    re-scale); native_priority_rating stays explicit None (QDS is
    numeric-only, no separate vendor categorical rating)."""
    detection = {"qid": REAL_QID, "severity": 5, "QDS": "82"}
    host = {"ip": "10.3.3.3", "dns": "qualys-host-1", "os": "Ubuntu 20.04"}
    kb_cache = {
        REAL_QID: {
            "TITLE": "OpenSSL Remote Code Execution",
            "CVSS_V3": {"BASE": "9.4"},
            "CVE_LIST": {"CVE": [{"ID": "CVE-2024-9999"}, {"ID": "CVE-2024-8888"}]},
        }
    }

    results = _normalize_detection(detection, host, kb_cache)

    assert len(results) == 2
    for r in results:
        assert r.native_priority_score == 82.0
        assert r.native_priority_rating is None


def test_normalize_detection_qds_absent_stays_none_no_crash():
    """A detection WITHOUT a QDS key -> native_priority_score stays None on
    every emitted finding (soft-null, never a crash)."""
    detection = {"qid": REAL_QID, "severity": 3}
    host: dict = {}
    kb_cache = {REAL_QID: {"CVE_LIST": {"CVE": [{"ID": "CVE-2024-7777"}]}}}

    results = _normalize_detection(detection, host, kb_cache)

    assert len(results) == 1
    assert results[0].native_priority_score is None


def test_normalize_detection_qds_read_from_detection_not_kb_cache():
    """Pitfall 4: a kb_cache entry that happens to carry a QDS-shaped key
    must NOT leak into native_priority_score -- QDS is a per-DETECTION field,
    not a QID-level knowledge-base constant."""
    detection = {"qid": REAL_QID, "severity": 3}  # no QDS on the detection itself
    host: dict = {}
    kb_cache = {
        REAL_QID: {
            "QDS": "99",  # a KB entry that happens to carry a QDS-shaped key
            "CVE_LIST": {"CVE": [{"ID": "CVE-2024-6666"}]},
        }
    }

    results = _normalize_detection(detection, host, kb_cache)

    assert results[0].native_priority_score is None  # NOT 99.0 -- must ignore kb_cache


def test_normalize_detection_source_signals_missing_vs_negative_and_no_pii_or_promoted_keys():
    """source_signals captures a vendor field that IS present (TYPE) while a
    genuinely-absent one (QDS_FACTORS) stays omitted in the SAME finding; no
    PII-adjacent or already-promoted keys leak in; QDS itself is not
    duplicated (already promoted to native_priority_score, D-08)."""
    detection = {
        "qid": REAL_QID,
        "severity": 5,
        "QDS": "82",
        "TYPE": "Confirmed",
        # QDS_FACTORS intentionally absent -- Qualys did not return a
        # threat-intel breakdown for this detection (the "missing" half).
    }
    host = {"ip": "10.3.3.3", "dns": "qualys-host-1", "os": "Ubuntu 20.04"}
    kb_cache = {REAL_QID: {"CVE_LIST": {"CVE": [{"ID": "CVE-2024-5555"}]}}}

    results = _normalize_detection(detection, host, kb_cache)

    signals = results[0].source_signals
    assert signals["TYPE"] == "Confirmed"  # present
    assert "QDS_FACTORS" not in signals  # genuinely never returned -- missing
    assert "QDS" not in signals  # promoted to native_priority_score, not duplicated (D-08)
    for forbidden in ("hostname", "ip_addresses", "cve_id", "cvss", "severity", "epss", "native_priority"):
        assert forbidden not in signals


def test_normalize_detection_qds_factors_present_but_empty_is_negative_not_missing():
    """A detection where Qualys DID return the QDS_FACTORS breakdown, even if
    it's empty (no elevated risk factors currently active), is present
    (negative) -- distinguishable from the genuinely-absent case above."""
    detection = {"qid": REAL_QID, "severity": 5, "QDS": "40", "QDS_FACTORS": {}}
    host: dict = {}
    kb_cache = {REAL_QID: {"CVE_LIST": {"CVE": [{"ID": "CVE-2024-4444"}]}}}

    results = _normalize_detection(detection, host, kb_cache)

    assert "QDS_FACTORS" in results[0].source_signals
    assert results[0].source_signals["QDS_FACTORS"] == {}


def test_normalize_detection_native_priority_fields_always_set_even_without_qds():
    """ENRICH-06: even when QDS/QDS_FACTORS/TYPE are entirely absent, all 3
    new fields are explicitly set (native_priority_score=None,
    native_priority_rating=None, source_signals={}) -- never omitted, never
    a crash."""
    detection = {"qid": FILLER_QID, "severity": 1}
    host: dict = {}
    kb_cache: dict = {}

    results = _normalize_detection(detection, host, kb_cache)

    assert results[0].native_priority_score is None
    assert results[0].native_priority_rating is None
    assert results[0].source_signals == {}


def test_normalize_detection_source_signals_dual_case_lowercase_json_path():
    """WR-03 regression: `_parse_response`'s JSON-response branch commonly
    yields lowercase keys -- the source_signals allowlist must check both
    casings (mirrors this file's own qid/severity/dns/QDS dual-case
    convention), never silently capturing nothing just because a response
    happened to arrive JSON-shaped. Always normalized to the canonical
    uppercase key in source_signals regardless of which casing was read."""
    detection = {
        "qid": REAL_QID,
        "severity": 5,
        "qds": "82",
        "type": "Confirmed",
        "qds_factors": {"exploit_maturity": "high"},
    }
    host = {"ip": "10.3.3.3", "dns": "qualys-host-1", "os": "Ubuntu 20.04"}
    kb_cache = {REAL_QID: {"CVE_LIST": {"CVE": [{"ID": "CVE-2024-3333"}]}}}

    results = _normalize_detection(detection, host, kb_cache)

    signals = results[0].source_signals
    assert signals["TYPE"] == "Confirmed"
    assert signals["QDS_FACTORS"] == {"exploit_maturity": "high"}
    assert results[0].native_priority_score == 82.0  # _get_qds's own dual-case path, unaffected


def test_normalize_detection_source_signals_uppercase_preferred_when_both_cases_present():
    """If a (malformed/mixed) response somehow carries both casings for the
    same field, the uppercase value wins -- matching the allowlist's
    upper-then-lower probe order."""
    detection = {"qid": REAL_QID, "severity": 5, "TYPE": "Confirmed", "type": "Potential"}
    host: dict = {}
    kb_cache = {REAL_QID: {"CVE_LIST": {"CVE": [{"ID": "CVE-2024-2222"}]}}}

    results = _normalize_detection(detection, host, kb_cache)

    assert results[0].source_signals["TYPE"] == "Confirmed"
