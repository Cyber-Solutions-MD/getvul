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


# ── ENRICH-03/04 (Phase 31 Plan 05): guarded EPSS/exploitability sub-scores
# -> source_signals, native_priority_* explicit None (Pitfall 6: Wiz has NO
# vendor-authored composite priority rating). A4: GraphQL fails the ENTIRE
# query on an unrecognized field name -- fetch_vulnerabilities() must fall
# back to the current/base field set on a schema error instead of breaking
# the whole Wiz sync. ─────────────────────────────────────────────────────

VULN_PAGE_ENRICHED_SUCCESS = {
    "data": {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    "id": "finding-enriched-1",
                    "name": "CVE-2024-5555",
                    "detailedName": "Enriched EPSS finding",
                    "severity": "HIGH",
                    "score": 8.1,
                    "exploitAvailable": True,
                    "hasExploit": True,
                    "hasCisaKevExploit": False,
                    "epssSeverity": "HIGH",
                    "epssPercentile": 0.91234,
                    "epssProbability": 0.045,
                    "exploitabilityScore": 3.9,
                    "impactScore": 5.9,
                    "status": "OPEN",
                    "remediation": "Upgrade the package",
                    "version": "1.2.3",
                    "fixedVersion": "1.2.4",
                    "vulnerableAsset": {
                        "id": "asset-enriched-1",
                        "name": "prod-app-01",
                        "type": "VIRTUAL_MACHINE",
                        "operatingSystem": "Amazon Linux 2",
                        "ipAddresses": ["10.0.1.5"],
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
}

# A single-page, base-field-set-only response used as the fallback target --
# deliberately hasNextPage=False so a test that reaches this branch cannot
# loop forever (unlike VULN_PAGE_1/2 above, which chain to a second page).
VULN_PAGE_BASE_FALLBACK_SUCCESS = {
    "data": {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    "id": "finding-fallback-1",
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
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
}

VULN_PAGE_MISSING_VS_NEGATIVE = {
    "data": {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    "id": "finding-mvn-1",
                    "name": "CVE-2024-6666",
                    "detailedName": "Missing-vs-negative fixture",
                    "severity": "MEDIUM",
                    "score": 5.0,
                    "exploitAvailable": False,
                    "hasExploit": False,
                    "hasCisaKevExploit": False,
                    "epssPercentile": 0.0,
                    # epssSeverity / epssProbability / exploitabilityScore /
                    # impactScore intentionally absent -- Wiz's response
                    # simply did not include them for this finding (the
                    # "missing" half of the fixture).
                    "status": "OPEN",
                    "remediation": None,
                    "version": "0.1",
                    "fixedVersion": None,
                    "vulnerableAsset": {
                        "id": "asset-mvn-1",
                        "name": "should-not-leak-into-signals",
                        "type": "VIRTUAL_MACHINE",
                        "operatingSystem": "Windows Server 2022",
                        "ipAddresses": ["10.9.9.9"],
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }
}


def _handler_enriched_success(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/oauth/token"):
        return _json_response(200, TOKEN_OK)
    return _json_response(200, VULN_PAGE_ENRICHED_SUCCESS)


def _handler_schema_error_fallback(request: httpx.Request) -> httpx.Response:
    """The enriched query (detected by the `epssSeverity` field name it
    alone carries) gets a GraphQL `errors` response; the base/current query
    (the fallback) succeeds normally."""
    if request.url.path.endswith("/oauth/token"):
        return _json_response(200, TOKEN_OK)
    body = json.loads(request.content)
    query = body.get("query", "")
    if "epssSeverity" in query:
        return _json_response(
            200,
            {"errors": [{"message": 'Cannot query field "epssSeverity" on type "VulnerabilityFinding".'}]},
        )
    return _json_response(200, VULN_PAGE_BASE_FALLBACK_SUCCESS)


def _handler_missing_vs_negative(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/oauth/token"):
        return _json_response(200, TOKEN_OK)
    return _json_response(200, VULN_PAGE_MISSING_VS_NEGATIVE)


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_enriched_query_populates_source_signals(monkeypatch: pytest.MonkeyPatch):
    """A successful enriched-query response maps the 5 new EPSS/exploitability
    sub-scores + hasCisaKevExploit (raw, PROVENANCE ONLY) into source_signals;
    native_priority_score/native_priority_rating stay explicit None (Wiz has
    no vendor-authored composite priority rating -- Pitfall 6)."""
    _install_mock_transport(monkeypatch, _handler_enriched_success)

    connector = WizConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert len(results) == 1
    v = results[0]
    assert v.cve_id == "CVE-2024-5555"
    assert v.native_priority_score is None
    assert v.native_priority_rating is None
    assert v.source_signals == {
        "hasCisaKevExploit": False,
        "epssSeverity": "HIGH",
        "epssPercentile": 0.91234,
        "epssProbability": 0.045,
        "exploitabilityScore": 3.9,
        "impactScore": 5.9,
    }


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_schema_error_on_enriched_query_falls_back_to_base_query(
    monkeypatch: pytest.MonkeyPatch,
):
    """A4 (the phase's hardest-failure risk): a GraphQL schema error on the
    enriched query (e.g., an unrecognized field name) must NOT break the
    entire Wiz sync -- fetch_vulnerabilities() catches WizGraphQLSchemaError
    and retries with the current/base VULNERABILITY_QUERY, still returning
    findings rather than raising or dropping everything."""
    _install_mock_transport(monkeypatch, _handler_schema_error_fallback)

    connector = WizConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert len(results) == 1
    assert results[0].cve_id == "CVE-2024-1111"
    # The base-query fallback never requested the 5 enriched fields -- Wiz
    # genuinely never returned them this sync, correctly modeled as missing.
    assert results[0].native_priority_score is None
    assert results[0].native_priority_rating is None
    assert "epssSeverity" not in results[0].source_signals
    # hasCisaKevExploit is on BOTH queries (unchanged base field) -- present.
    assert results[0].source_signals["hasCisaKevExploit"] is True


@pytest.mark.asyncio
async def test_fetch_vulnerabilities_source_signals_missing_vs_negative_and_no_pii_or_promoted_keys(
    monkeypatch: pytest.MonkeyPatch,
):
    """hasCisaKevExploit=False and epssPercentile=0.0 (both present-but-falsy)
    land in source_signals as NEGATIVE, while epssSeverity/epssProbability/
    exploitabilityScore/impactScore (genuinely never returned) stay MISSING
    (omitted) in the SAME finding (D-07). No PII-adjacent (asset name/ip/os)
    or already-promoted (cve/cvss/severity/native_priority) key ever leaks
    into source_signals (D-08)."""
    _install_mock_transport(monkeypatch, _handler_missing_vs_negative)

    connector = WizConnector()
    await connector.authenticate(CREDS, {})
    results = await connector.fetch_vulnerabilities()
    await connector.close()

    assert len(results) == 1
    signals = results[0].source_signals

    # Negative: vendor returned a falsy value explicitly -- the key IS present.
    assert signals["hasCisaKevExploit"] is False
    assert signals["epssPercentile"] == 0.0

    # Missing: vendor never returned these -- keys are absent entirely, never
    # written as an explicit None/False sentinel (D-07).
    assert "epssSeverity" not in signals
    assert "epssProbability" not in signals
    assert "exploitabilityScore" not in signals
    assert "impactScore" not in signals

    # No PII-adjacent or already-promoted keys leak into source_signals.
    for forbidden in ("hostname", "ip_addresses", "cve_id", "cvss", "severity", "epss", "native_priority", "asset"):
        assert forbidden not in signals
