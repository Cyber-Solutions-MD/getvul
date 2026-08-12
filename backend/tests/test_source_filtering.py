"""Phase 35 Plan 01 (LEAD TRACER) — Vulnerabilities OR/AND source filter +
sources/sources_count response fields + query-count no-N+1 proof.

Covers SRC-01 (data spine: every list row carries sources/sources_count,
single-source fallback never null), SRC-02 (source_mode filter param
accepted/validated), SRC-03 (OR default, reaching single-source findings via
the direct-source fallback), SRC-04 (AND toggle via the correlation ARRAY
`@>`, structurally excluding single-source findings), and SRC-08 (the new
`before_cursor_execute` query-count harness proves list_vulnerabilities is
page-size-invariant — exactly one extra batched correlation query per page,
never one-per-row).

Reuses `test_vuln_source_filter.py`'s `_seed` + `client`/`db_session`/
`tenant_a` fixture idiom and `test_risk_exposure_service.py`'s
`VulnerabilityCorrelation` direct-seed shape.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.assets.models import Asset
from app.pagination import PaginationParams
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation
from app.vulnerabilities.schemas import VulnerabilityFilter
from app.vulnerabilities.service import list_vulnerabilities
from tests.query_count import count_queries


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(tenant_id=tenant_id, hostname=f"host-{uuid.uuid4().hex[:8]}")


def _seed_vuln(tenant_id: uuid.UUID, asset_id: uuid.UUID | None, *, source: str, cve_id: str) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=cve_id,
        asset_id=asset_id,
        severity="HIGH",
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_or_default_returns_union(client, db_session, tenant_a):
    """SRC-03: OR default (no source_mode) reaches single-source findings
    that have NO correlation row at all — union across selected sources."""
    asset1 = _seed_asset(tenant_a)
    asset2 = _seed_asset(tenant_a)
    db_session.add_all([asset1, asset2])
    await db_session.flush()
    db_session.add(_seed_vuln(tenant_a, asset1.id, source="QUALYS", cve_id="CVE-OR-Q-001"))
    db_session.add(_seed_vuln(tenant_a, asset2.id, source="RAPID7", cve_id="CVE-OR-R-001"))
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS&source=RAPID7")
    assert resp.status_code == 200
    cve_ids = {i["cve_id"] for i in resp.json()["items"]}
    assert cve_ids == {"CVE-OR-Q-001", "CVE-OR-R-001"}, f"expected union of both, got {cve_ids}"


@pytest.mark.asyncio
async def test_and_toggle_requires_corroboration(client, db_session, tenant_a):
    """SRC-04: source_mode=and matches ONLY findings whose (cve_id,asset_id)
    has a VulnerabilityCorrelation containing BOTH selected sources — a
    single-source finding (no correlation row) is structurally excluded, even
    though it is one of the selected sources."""
    lone_asset = _seed_asset(tenant_a)
    corroborated_asset = _seed_asset(tenant_a)
    db_session.add_all([lone_asset, corroborated_asset])
    await db_session.flush()

    # Lone QUALYS-only finding — NO correlation row.
    db_session.add(_seed_vuln(tenant_a, lone_asset.id, source="QUALYS", cve_id="CVE-AND-L-001"))

    # Corroborated finding — two Vulnerability rows (one per source) sharing
    # the same (cve_id, asset_id), plus the VulnerabilityCorrelation row.
    db_session.add(_seed_vuln(tenant_a, corroborated_asset.id, source="QUALYS", cve_id="CVE-AND-C-001"))
    db_session.add(_seed_vuln(tenant_a, corroborated_asset.id, source="RAPID7", cve_id="CVE-AND-C-001"))
    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id="CVE-AND-C-001",
            asset_id=corroborated_asset.id,
            sources=["QUALYS", "RAPID7"],
            sources_count=2,
            confidence="HIGH",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?source=QUALYS&source=RAPID7&source_mode=and")
    assert resp.status_code == 200
    items = resp.json()["items"]
    cve_ids = {i["cve_id"] for i in items}
    assert cve_ids == {"CVE-AND-C-001"}, f"AND must exclude the lone QUALYS-only finding, got {cve_ids}"
    assert len(items) == 2, "both source rows of the corroborated finding should be present"


@pytest.mark.asyncio
async def test_and_with_single_source_is_or(client, db_session, tenant_a):
    """Pitfall 1 (documented no-op): AND with fewer than 2 selected sources
    behaves identically to OR — mathematically the two modes coincide at a
    single value, and this must not be left ambiguous."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    db_session.add(_seed_vuln(tenant_a, asset.id, source="QUALYS", cve_id="CVE-NOOP-001"))
    await db_session.commit()

    resp_and = await client.get("/api/v1/vulnerabilities?source=QUALYS&source_mode=and")
    resp_or = await client.get("/api/v1/vulnerabilities?source=QUALYS&source_mode=or")
    assert resp_and.status_code == 200
    assert resp_or.status_code == 200
    cve_ids_and = {i["cve_id"] for i in resp_and.json()["items"]}
    cve_ids_or = {i["cve_id"] for i in resp_or.json()["items"]}
    assert cve_ids_and == cve_ids_or == {"CVE-NOOP-001"}


@pytest.mark.asyncio
async def test_summary_carries_sources(client, db_session, tenant_a):
    """SRC-01 data spine: a corroborated finding's list row carries BOTH
    scanners in `sources` and `sources_count == 2`; a single-source finding's
    row defaults to `sources == [its source]` and `sources_count == 1` —
    never null/unknown, even though no correlation row exists for it."""
    lone_asset = _seed_asset(tenant_a)
    corroborated_asset = _seed_asset(tenant_a)
    db_session.add_all([lone_asset, corroborated_asset])
    await db_session.flush()

    db_session.add(_seed_vuln(tenant_a, lone_asset.id, source="QUALYS", cve_id="CVE-SRC01-L-001"))
    db_session.add(_seed_vuln(tenant_a, corroborated_asset.id, source="QUALYS", cve_id="CVE-SRC01-C-001"))
    db_session.add(_seed_vuln(tenant_a, corroborated_asset.id, source="RAPID7", cve_id="CVE-SRC01-C-001"))
    db_session.add(
        VulnerabilityCorrelation(
            tenant_id=tenant_a,
            cve_id="CVE-SRC01-C-001",
            asset_id=corroborated_asset.id,
            sources=["QUALYS", "RAPID7"],
            sources_count=2,
            confidence="HIGH",
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities?cve_id=CVE-SRC01")
    assert resp.status_code == 200
    items = {i["cve_id"] + ":" + i["source"]: i for i in resp.json()["items"]}

    lone_row = items["CVE-SRC01-L-001:QUALYS"]
    assert lone_row["sources"] == ["QUALYS"], f"single-source fallback must never be null/unknown: {lone_row}"
    assert lone_row["sources_count"] == 1

    for key in ("CVE-SRC01-C-001:QUALYS", "CVE-SRC01-C-001:RAPID7"):
        row = items[key]
        assert set(row["sources"]) == {"QUALYS", "RAPID7"}
        assert row["sources_count"] == 2


@pytest.mark.asyncio
async def test_bad_source_mode_422(client, db_session, tenant_a):
    """SRC-02: source_mode is a Pydantic Literal["or","and"] — anything else
    surfaces as 422, not a silently-ignored/defaulted value."""
    resp = await client.get("/api/v1/vulnerabilities?source_mode=nonsense")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_query_count_is_page_size_invariant(db_session, tenant_a):
    """SRC-08: list_vulnerabilities issues a FIXED, small number of SQL
    statements independent of page size — a 5-row page and a 50-row page
    emit the IDENTICAL statement count. Proves exactly one batched
    page-scoped correlation query, never one-per-row.

    Calls the service function directly (not via HTTP) so the count isolates
    list_vulnerabilities' own query shape from auth/session middleware noise.
    """
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()

    for n in range(60):
        db_session.add(_seed_vuln(tenant_a, asset.id, source="QUALYS", cve_id=f"CVE-QCOUNT-{n:03d}"))
    await db_session.commit()

    filters = VulnerabilityFilter()

    with count_queries() as statements_small:
        await list_vulnerabilities(db_session, tenant_a, filters, PaginationParams(page=1, page_size=5))
    with count_queries() as statements_large:
        await list_vulnerabilities(db_session, tenant_a, filters, PaginationParams(page=1, page_size=50))

    assert len(statements_small) == len(statements_large), (
        f"statement count must be page-size-invariant: "
        f"page_size=5 issued {len(statements_small)}, page_size=50 issued {len(statements_large)}"
    )
    # Sanity: it must be a small, fixed number (count + tenant + data +
    # batched-correlation), never one-per-row (which would scale with 5/50).
    assert len(statements_small) <= 6, f"expected a small fixed statement count, got {len(statements_small)}"
