"""Tests for `app.connectors.enrichment_feeds` (ENRICH-01/02/05, Phase 31
Plan 02) -- EPSS/CISA KEV feed fetch+parse (via `httpx.MockTransport`, no
live network) and the D-09 atomic-swap-keeps-last-good refresh transaction,
plus the D-01/D-02 re-propagation UPDATE.

HTTP mocking convention (no respx/pytest-httpx anywhere in this repo):
monkeypatch `httpx.AsyncClient.__init__` to inject an
`httpx.MockTransport(handler)`, mirroring
`tests/test_connectors/test_defender_connector.py::_install_mock_transport`
verbatim.

DB-touching tests use the shared `db_session`/`tenant_a` fixtures and only
ever `flush()` (never `commit()`) their seed rows -- `refresh_enrichment_
reference_data`/`repropagate_enrichment` are called with that SAME session
object (never a separate one), so a flush is enough for the function under
test (and this test's own follow-up assertions) to see the seeded rows.
Nothing is ever committed, so the fixture's automatic rollback is sufficient
teardown -- no manual DELETE needed, and the shared dev Postgres's
`epss_scores`/`cisa_kev` tables (global, no tenant_id, NOT covered by
conftest.py's post-test TRUNCATE list) are never permanently mutated by this
file.

Seed `cve_id` values in this file deliberately use a pre-1999 year (e.g.
`CVE-1990-...`) -- the real CVE numbering scheme's floor is 1999, so this
range can NEVER collide with a real EPSS/KEV entry. This matters in
practice, not just in theory: `settings.environment` defaults to
"production" (no test-mode gate anywhere in this codebase, see 31-02's
deferred-items.md), so ANY test elsewhere in the suite that spins up the
real FastAPI app lifespan (the `client` fixture) also starts the real
in-process scheduler, whose `_dispatch_enrichment_refresh` eager/first-tick
call fetches the REAL feeds unconditionally on a cold gate -- this was
observed to populate this dev stack's `epss_scores` with ~355k real rows
mid-session, which collided with an earlier `CVE-2024-...`-ranged seed here.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`) + JWT_SECRET_KEY set,
per-file.
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.connectors import enrichment_feeds
from app.vulnerabilities.models import CisaKev, EpssScore, Vulnerability


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Force every httpx.AsyncClient constructed during the test to use a
    MockTransport (verbatim from test_defender_connector.py)."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


# ── EPSS fetch+parse ──────────────────────────────────────────────────────

_EPSS_CSV_BODY = (
    "#model_version:v2026.06.15,score_date:2026-08-04T12:00:14Z\n"
    "cve,epss,percentile\n"
    "CVE-2024-0001,0.03351,0.87494\n"
    "CVE-2024-0002,0.00021,0.15000\n"
)

_REDIRECT_TARGET = "https://epss.empiricalsecurity.com/epss_scores-2026-08-04.csv.gz"


def _epss_redirect_handler(body: bytes):
    """A 302 (empty body) for the "current" URL, then a 200 with `body` for
    the dated-snapshot redirect target -- mirrors the real feed's behavior
    (31-RESEARCH.md Pitfall 1, VERIFIED live)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == enrichment_feeds.EPSS_URL:
            return httpx.Response(302, headers={"location": _REDIRECT_TARGET})
        return httpx.Response(200, content=body)

    return handler


async def test_fetch_and_parse_epss_follows_redirect_and_parses_gzip_csv(monkeypatch):
    """Pitfall 1: the EPSS URL 302-redirects with an empty body; the client
    must be built with follow_redirects=True so the SECOND (dated-snapshot)
    response -- a gzip'd CSV with a leading `#model_version:...` comment
    line -- is the one actually decompressed and parsed."""
    gz_body = gzip.compress(_EPSS_CSV_BODY.encode())
    _install_mock_transport(monkeypatch, _epss_redirect_handler(gz_body))

    rows = await enrichment_feeds._fetch_and_parse_epss()

    assert len(rows) == 2
    by_cve = {r["cve_id"]: r for r in rows}
    assert by_cve["CVE-2024-0001"]["epss_score"] == Decimal("0.03351")
    assert by_cve["CVE-2024-0001"]["percentile"] == Decimal("0.87494")
    assert by_cve["CVE-2024-0002"]["epss_score"] == Decimal("0.00021")
    assert by_cve["CVE-2024-0002"]["percentile"] == Decimal("0.15000")


async def test_fetch_and_parse_epss_aborts_on_empty_redirect_body(monkeypatch):
    """A 302-then-empty-body response must raise, never silently return an
    empty (0-row) result the caller could mistake for "feed had zero CVEs
    today" (31-RESEARCH.md Pitfall 1)."""
    _install_mock_transport(monkeypatch, _epss_redirect_handler(b""))

    with pytest.raises(Exception):  # noqa: B017 -- deliberately broad: any parse/fetch failure must abort
        await enrichment_feeds._fetch_and_parse_epss()


async def test_fetch_and_parse_epss_tolerates_small_fraction_of_malformed_rows(monkeypatch):
    """V5: a single stray malformed row (e.g. a corrupted/misaligned line)
    must NOT abort an otherwise-legitimate refresh -- only a broadly
    corrupt feed (>1% bad rows) aborts (D-09)."""
    lines = ["#model_version:v2026.06.15,score_date:2026-08-04T12:00:14Z", "cve,epss,percentile"]
    for i in range(200):
        lines.append(f"CVE-2024-{i:04d},0.01000,0.10000")
    lines.append("garbage-not-csv-shaped")  # 1 malformed row out of 201 (~0.5%) -- under the 1% cap
    gz_body = gzip.compress(("\n".join(lines) + "\n").encode())
    _install_mock_transport(monkeypatch, _epss_redirect_handler(gz_body))

    rows = await enrichment_feeds._fetch_and_parse_epss()

    assert len(rows) == 200


async def test_fetch_and_parse_epss_aborts_on_broadly_corrupt_feed(monkeypatch):
    """>1% malformed rows must abort the WHOLE refresh, not just skip the
    bad ones -- a broadly corrupt feed signals something seriously wrong
    upstream, not a data-quality nit (D-09/T-31-01)."""
    lines = ["#model_version:v2026.06.15,score_date:2026-08-04T12:00:14Z", "cve,epss,percentile"]
    for i in range(10):
        lines.append(f"CVE-2024-{i:04d},0.01000,0.10000")
    for _ in range(5):
        lines.append("garbage-not-csv-shaped")  # 5/15 = 33% malformed -- well over the 1% cap
    gz_body = gzip.compress(("\n".join(lines) + "\n").encode())
    _install_mock_transport(monkeypatch, _epss_redirect_handler(gz_body))

    with pytest.raises(Exception):  # noqa: B017
        await enrichment_feeds._fetch_and_parse_epss()


# ── CISA KEV fetch+parse ──────────────────────────────────────────────────

_KEV_JSON_BODY = {
    "title": "CISA Catalog of Known Exploited Vulnerabilities",
    "catalogVersion": "2026.08.04",
    "dateReleased": "2026-08-04T16:45:52.0783Z",
    "count": 2,
    "vulnerabilities": [
        {
            "cveID": "CVE-2024-0001",
            "vendorProject": "Acme",
            "product": "Widget",
            "vulnerabilityName": "Acme Widget RCE",
            "dateAdded": "2024-01-15",
            "dueDate": "2024-02-05",
            "knownRansomwareCampaignUse": "Known",
        },
        {
            "cveID": "CVE-2024-0002",
            "vendorProject": "Acme",
            "product": "Gadget",
            "vulnerabilityName": "Acme Gadget Overflow",
            "dateAdded": "2024-02-01",
            "dueDate": "2024-02-22",
            "knownRansomwareCampaignUse": "Unknown",
        },
    ],
}


async def test_fetch_and_parse_kev_parses_envelope(monkeypatch):
    """The KEV feed's `{catalogVersion, count, vulnerabilities:[...]}`
    envelope -- parser yields one row per entry, keyed by `cveID`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps(_KEV_JSON_BODY).encode())

    _install_mock_transport(monkeypatch, handler)

    rows = await enrichment_feeds._fetch_and_parse_kev()

    assert {r["cve_id"] for r in rows} == {"CVE-2024-0001", "CVE-2024-0002"}
    by_cve = {r["cve_id"]: r for r in rows}
    assert by_cve["CVE-2024-0001"]["known_ransomware_campaign_use"] == "Known"
    assert by_cve["CVE-2024-0002"]["vendor_project"] == "Acme"
    assert by_cve["CVE-2024-0002"]["known_ransomware_campaign_use"] == "Unknown"


async def test_fetch_and_parse_kev_aborts_on_empty_body(monkeypatch):
    """A 200-with-empty-body KEV response must raise, mirroring the EPSS
    empty-body guard -- never silently treated as "zero KEV entries"."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    _install_mock_transport(monkeypatch, handler)

    with pytest.raises(Exception):  # noqa: B017
        await enrichment_feeds._fetch_and_parse_kev()


# ── Atomic swap (D-09) ─────────────────────────────────────────────────────


async def test_refresh_atomic_swap_keeps_last_good_on_parse_failure(db_session, monkeypatch):
    """D-09: seed a prior-good epss_scores row, force `_fetch_and_parse_epss`
    to raise mid-parse, then assert `refresh_enrichment_reference_data`
    returns a failed status WITHOUT deleting the prior row -- the atomic
    swap only touches the DB after BOTH feeds are fetched+parsed fully in
    memory, so a failure here must leave the ref table byte-for-byte
    unchanged."""
    seed = EpssScore(cve_id="CVE-1990-0001", epss_score=Decimal("0.50000"), percentile=Decimal("0.90000"))
    db_session.add(seed)
    await db_session.flush()

    async def _raise() -> list[dict]:
        raise ValueError("truncated upstream response")

    monkeypatch.setattr(enrichment_feeds, "_fetch_and_parse_epss", _raise)

    result = await enrichment_feeds.refresh_enrichment_reference_data(db_session)

    assert result["status"] == "failed"

    still_there = (
        await db_session.execute(select(EpssScore).where(EpssScore.cve_id == "CVE-1990-0001"))
    ).scalar_one_or_none()
    assert still_there is not None
    assert still_there.epss_score == Decimal("0.50000")


async def test_refresh_swaps_in_new_data_on_full_success(db_session, monkeypatch):
    """Full-success path: both fetchers succeed -> the prior row is gone
    (TRUNCATE-equivalent delete) and the freshly-fetched rows are present."""
    seed = EpssScore(cve_id="CVE-1990-0002", epss_score=Decimal("0.10000"), percentile=Decimal("0.20000"))
    db_session.add(seed)
    await db_session.flush()

    async def _fake_epss() -> list[dict]:
        return [
            {
                "cve_id": "CVE-2024-9999",
                "epss_score": Decimal("0.42000"),
                "percentile": Decimal("0.77000"),
                "model_version": "v2026.06.15",
                "score_date": None,
            }
        ]

    async def _fake_kev() -> list[dict]:
        return [
            {
                "cve_id": "CVE-2024-9999",
                "date_added": None,
                "vendor_project": "Acme",
                "product": "Widget",
                "vulnerability_name": "Acme Widget RCE",
                "due_date": None,
                "known_ransomware_campaign_use": "Known",
                "catalog_version": "2026.08.04",
            }
        ]

    monkeypatch.setattr(enrichment_feeds, "_fetch_and_parse_epss", _fake_epss)
    monkeypatch.setattr(enrichment_feeds, "_fetch_and_parse_kev", _fake_kev)

    result = await enrichment_feeds.refresh_enrichment_reference_data(db_session)

    assert result == {"status": "ok", "epss_rows": 1, "kev_rows": 1}

    old_row = (
        await db_session.execute(select(EpssScore).where(EpssScore.cve_id == "CVE-1990-0002"))
    ).scalar_one_or_none()
    assert old_row is None  # TRUNCATE-equivalent delete wiped the prior row

    new_row = (
        await db_session.execute(select(EpssScore).where(EpssScore.cve_id == "CVE-2024-9999"))
    ).scalar_one_or_none()
    assert new_row is not None
    assert new_row.epss_score == Decimal("0.42000")

    new_kev = (await db_session.execute(select(CisaKev).where(CisaKev.cve_id == "CVE-2024-9999"))).scalar_one_or_none()
    assert new_kev is not None
    assert new_kev.vendor_project == "Acme"


# ── Re-propagation (D-01/D-02) ─────────────────────────────────────────────


async def test_repropagate_enrichment_updates_existing_findings_by_cve_id(db_session, tenant_a):
    """D-01/D-02: keyed on cve_id (not "ingested this run") -- a purely
    historical finding (ingested long before EPSS/KEV had an opinion on its
    CVE) gets backfilled for free by the SAME unconditional UPDATE that
    also keeps freshly-ingested findings in sync with the feed's daily
    drift. The CISA KEV catalog recompute is authoritative in BOTH
    directions -- a finding not in the catalog must flip back to False."""
    vuln = Vulnerability(
        tenant_id=tenant_a,
        cve_id="CVE-2030-1234",
        severity="HIGH",
        source="DEFENDER",
        status="OPEN",
        cisa_kev=True,  # stale True -- must flip to False since NOT in the seeded cisa_kev catalog below
        first_detected_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(vuln)

    epss_row = EpssScore(cve_id="CVE-2030-1234", epss_score=Decimal("0.65000"), percentile=Decimal("0.95000"))
    db_session.add(epss_row)
    await db_session.flush()

    result = await enrichment_feeds.repropagate_enrichment(db_session)

    await db_session.refresh(vuln)
    assert vuln.epss_score == Decimal("0.65000")
    assert vuln.epss_percentile == Decimal("0.95000")
    assert vuln.cisa_kev is False  # not in the (empty) cisa_kev catalog -- authoritative recompute
    assert result["repropagated"] >= 1


async def test_repropagate_enrichment_sets_cisa_kev_true_for_catalog_member(db_session, tenant_a):
    """The flip side of the above: a finding whose cve_id IS present in the
    cisa_kev catalog must become True, even if the connector never guessed
    KEV for it at ingest (D-04's authoritative-catalog-wins contract)."""
    vuln = Vulnerability(
        tenant_id=tenant_a,
        cve_id="CVE-2030-5678",
        severity="CRITICAL",
        source="DEFENDER",
        status="OPEN",
        cisa_kev=False,  # Defender's own hardcode/guess -- must flip True from the catalog
        first_detected_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(vuln)

    kev_row = CisaKev(cve_id="CVE-2030-5678", vendor_project="Acme")
    db_session.add(kev_row)
    await db_session.flush()

    await enrichment_feeds.repropagate_enrichment(db_session)

    await db_session.refresh(vuln)
    assert vuln.cisa_kev is True


async def test_repropagate_enrichment_preserves_cisa_kev_for_null_cve_id_row(db_session, tenant_a):
    """CR-01 regression: `NULL IN (<non-empty subquery>)` is SQL NULL, not
    FALSE, per three-valued logic -- without the `WHERE cve_id IS NOT NULL`
    guard, the KEV UPDATE would silently overwrite this row's `cisa_kev`
    with NULL, which then fails Pydantic validation on read-back
    (`VulnerabilityResponse.cisa_kev`/`VulnerabilitySummary.cisa_kev` are
    both non-Optional `bool`). CrowdStrike's `_normalize_vuln`/Wiz's
    `cve_id=node.get("name")` both lack a fallback-exhausted guard, so a
    NULL-`cve_id` row is a reachable state, not a hypothetical.

    The `cisa_kev` catalog table must be non-empty for the bug to manifest:
    `x IN (<empty subquery>)` is FALSE regardless of x, so an empty catalog
    would mask the missing guard even without the fix."""
    vuln = Vulnerability(
        tenant_id=tenant_a,
        cve_id=None,  # e.g. a CrowdStrike Spotlight item with no vulnerability_id/cve.id
        severity="HIGH",
        source="CROWDSTRIKE",
        status="OPEN",
        cisa_kev=True,  # pre-existing value -- must survive re-propagation untouched, never NULL
        first_detected_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add(vuln)

    # Non-empty catalog -- required for the bug to manifest (see docstring).
    kev_row = CisaKev(cve_id="CVE-2030-9999", vendor_project="Acme")
    db_session.add(kev_row)
    await db_session.flush()

    await enrichment_feeds.repropagate_enrichment(db_session)

    await db_session.refresh(vuln)
    assert vuln.cisa_kev is True  # untouched -- not NULL, not flipped
