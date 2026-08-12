"""Phase 35 Plan 04 — Ticket transitive union provenance + real OR-default
source FILTER + query-count no-N+1 proof.

Covers SRC-07 (ticket provenance resolves TRANSITIVELY through the linked
vuln's VulnerabilityCorrelation — union of all linked vulns' sources for a
grouped ticket-task row, per CONTEXT.md [RESOLVED A4], never `func.min`
which is a representative pick not a union), SRC-02 (Tickets half: a real
server-side OR-default `?source=` filter joined through the linked vuln —
not display-only), and SRC-08 (list_tickets issues a FIXED statement count
independent of page size).

Reuses the `_seed_asset`/`_seed_vuln`/`_seed_ticket` idiom from
`test_tickets_asset_id_filter.py` and seeds `VulnerabilityCorrelation`
directly, mirroring `test_risk_exposure_service.py`'s multi-source fixture
shape. Imports `count_queries` from Plan 01's harness verbatim.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.ticketing.models import Ticket
from app.ticketing.service import list_tickets
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation
from tests.query_count import count_queries


def _seed_asset(tenant_id: uuid.UUID, hostname: str) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=hostname, os_name="Ubuntu 22.04 LTS")


def _seed_vuln(tenant_id: uuid.UUID, *, asset_id, cve_id: str, source: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id,
        severity="HIGH",
        status="OPEN",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now,
        last_seen_at=now,
    )


def _seed_ticket(tenant_id: uuid.UUID, *, vulnerability_id, external_ticket_url: str) -> Ticket:
    return Ticket(
        tenant_id=tenant_id,
        vulnerability_id=vulnerability_id,
        provider="ASANA",
        external_ticket_id=uuid.uuid4().hex,
        external_ticket_url=external_ticket_url,
        external_status="open",
        ticket_created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_ticket_transitive_provenance(client, db_session, tenant_a):
    """SRC-07: a ticket linked to a QUALYS vuln whose (cve_id, asset_id) is
    ALSO RAPID7-correlated shows sources=[QUALYS,RAPID7] — resolved
    transitively through the linked vuln's VulnerabilityCorrelation, not just
    the one Vulnerability row that triggered ticket creation."""
    asset = _seed_asset(tenant_a, "host-transitive")
    db_session.add(asset)
    await db_session.flush()

    v = _seed_vuln(tenant_a, asset_id=asset.id, cve_id="CVE-TRANS-001", source="QUALYS")
    db_session.add(v)
    await db_session.flush()

    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id="CVE-TRANS-001",
            asset_id=asset.id,
            sources=["QUALYS", "RAPID7"],
            sources_count=2,
            confidence="HIGH",
        )
    )
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v.id, external_ticket_url="https://jira/TRANS-1"))
    await db_session.commit()

    resp = await client.get("/api/v1/tickets")
    assert resp.status_code == 200
    items = {i["external_ticket_url"]: i for i in resp.json()["items"]}
    row = items["https://jira/TRANS-1"]
    assert set(row["sources"]) == {"QUALYS", "RAPID7"}, row
    assert row["sources_count"] == 2


@pytest.mark.asyncio
async def test_ticket_grouped_union(client, db_session, tenant_a):
    """CONTEXT A4: a grouped ticket-task spanning 2 linked vulns (one
    QUALYS-only-no-correlation, one QUALYS+RAPID7-correlated) unions to
    {QUALYS, RAPID7} and is multi-source (sources_count == 2) — proving the
    union spans ALL linked vulns in the group, not a representative pick."""
    asset1 = _seed_asset(tenant_a, "host-union-1")
    asset2 = _seed_asset(tenant_a, "host-union-2")
    db_session.add_all([asset1, asset2])
    await db_session.flush()

    v1 = _seed_vuln(tenant_a, asset_id=asset1.id, cve_id="CVE-UNION-001", source="QUALYS")
    v2 = _seed_vuln(tenant_a, asset_id=asset2.id, cve_id="CVE-UNION-002", source="QUALYS")
    db_session.add_all([v1, v2])
    await db_session.flush()

    # v2 is corroborated; v1 is NOT (no correlation row at all).
    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id="CVE-UNION-002",
            asset_id=asset2.id,
            sources=["QUALYS", "RAPID7"],
            sources_count=2,
            confidence="HIGH",
        )
    )

    # Both tickets share the SAME external_ticket_url -> one grouped row.
    shared_url = "https://jira/UNION-GROUP-1"
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v1.id, external_ticket_url=shared_url))
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v2.id, external_ticket_url=shared_url))
    await db_session.commit()

    resp = await client.get("/api/v1/tickets")
    assert resp.status_code == 200
    items = {i["external_ticket_url"]: i for i in resp.json()["items"]}
    row = items[shared_url]
    assert set(row["sources"]) == {"QUALYS", "RAPID7"}, row
    assert row["sources_count"] == 2, "grouped row must be multi-source since ANY linked vuln is corroborated"


@pytest.mark.asyncio
async def test_ticket_single_source_no_correlation(client, db_session, tenant_a):
    """A ticket linked to a vuln with NO correlation row falls back to
    sources=[vuln.source], sources_count=1 — never null/unknown."""
    asset = _seed_asset(tenant_a, "host-lone")
    db_session.add(asset)
    await db_session.flush()

    v = _seed_vuln(tenant_a, asset_id=asset.id, cve_id="CVE-LONE-001", source="RAPID7")
    db_session.add(v)
    await db_session.flush()
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=v.id, external_ticket_url="https://jira/LONE-1"))
    await db_session.commit()

    resp = await client.get("/api/v1/tickets")
    assert resp.status_code == 200
    items = {i["external_ticket_url"]: i for i in resp.json()["items"]}
    row = items["https://jira/LONE-1"]
    assert row["sources"] == ["RAPID7"], row
    assert row["sources_count"] == 1


@pytest.mark.asyncio
async def test_ticket_list_filter_by_source(client, db_session, tenant_a):
    """SRC-02 (Tickets half): ?source= is a REAL server-side OR-default
    filter joined through the linked Vulnerability.source — not
    display-only. A single selected source returns only that ticket; two
    selected sources return the union."""
    asset1 = _seed_asset(tenant_a, "host-filt-1")
    asset2 = _seed_asset(tenant_a, "host-filt-2")
    db_session.add_all([asset1, asset2])
    await db_session.flush()

    vq = _seed_vuln(tenant_a, asset_id=asset1.id, cve_id="CVE-FILT-Q001", source="QUALYS")
    vr = _seed_vuln(tenant_a, asset_id=asset2.id, cve_id="CVE-FILT-R001", source="RAPID7")
    db_session.add_all([vq, vr])
    await db_session.flush()

    db_session.add(_seed_ticket(tenant_a, vulnerability_id=vq.id, external_ticket_url="https://jira/FILT-Q"))
    db_session.add(_seed_ticket(tenant_a, vulnerability_id=vr.id, external_ticket_url="https://jira/FILT-R"))
    await db_session.commit()

    resp_q = await client.get("/api/v1/tickets?source=QUALYS")
    assert resp_q.status_code == 200
    urls_q = {i["external_ticket_url"] for i in resp_q.json()["items"]}
    assert urls_q == {"https://jira/FILT-Q"}, f"expected only the QUALYS-linked ticket, got {urls_q}"

    resp_both = await client.get("/api/v1/tickets?source=QUALYS&source=RAPID7")
    assert resp_both.status_code == 200
    urls_both = {i["external_ticket_url"] for i in resp_both.json()["items"]}
    assert urls_both == {"https://jira/FILT-Q", "https://jira/FILT-R"}, urls_both


@pytest.mark.asyncio
async def test_list_tickets_query_count_invariant(db_session, tenant_a):
    """SRC-08: list_tickets issues a FIXED statement count independent of
    page size — the transitive provenance resolution adds a bounded number
    of batched queries (grouped_q + details_q + ONE correlation query),
    never one-per-row."""
    asset = _seed_asset(tenant_a, "host-qcount")
    db_session.add(asset)
    await db_session.flush()

    for n in range(60):
        v = _seed_vuln(tenant_a, asset_id=asset.id, cve_id=f"CVE-TQC-{n:03d}", source="QUALYS")
        db_session.add(v)
        await db_session.flush()
        db_session.add(_seed_ticket(tenant_a, vulnerability_id=v.id, external_ticket_url=f"https://jira/TQC-{n:03d}"))
    await db_session.commit()

    _relevant_tables = ("tickets", "vulnerabilities", "vulnerability_correlations", "assets")

    def _relevant(statements: list[str]) -> list[str]:
        return [s for s in statements if any(t in s for t in _relevant_tables)]

    with count_queries() as statements_small:
        await list_tickets(db_session, tenant_a, page=1, page_size=5)
    with count_queries() as statements_large:
        await list_tickets(db_session, tenant_a, page=1, page_size=50)

    statements_small = _relevant(statements_small)
    statements_large = _relevant(statements_large)

    assert len(statements_small) == len(statements_large), (
        f"statement count must be page-size-invariant: "
        f"page_size=5 issued {len(statements_small)}, page_size=50 issued {len(statements_large)}"
    )
