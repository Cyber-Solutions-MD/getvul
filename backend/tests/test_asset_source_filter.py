"""Phase 35 Plan 03 — Assets OR/AND source filter + scanner/enrichment
partition + batched sources + query-count no-N+1 proof (SRC-02/03/04/06/08).

REGRESSION PROOF: `test_or_default_multi_scanner_returns_union` is the
regression test for the shipped bug at `assets/router.py:154-159` — the
chained `.where(Asset.seen_by_sources.contains([s]))` loop SQLAlchemy
silently ANDs, so a multi-scanner select today returns only assets seen by
ALL selected scanners (the opposite of the intended OR-default union). This
test FAILS against that code (it would return only the fully-corroborated
asset) and must pass once the fix lands (`or_(*contains)` OR-default, with
the true-AND behavior gated behind the explicit `source_mode=and` toggle).

Mirrors `test_vuln_source_filter.py`'s `_seed`/fixture idiom, adapted to
`Asset.seen_by_sources` (a JSONB list, not a per-row `source` column).
Reuses `tests/query_count.py` (Plan 01's `before_cursor_execute` harness) for
the SRC-08 page-size-invariance assertion, following Plan 01's own
documented table-filter discipline (its SUMMARY's key-decisions note) so the
assertion isolates `list_assets`'s OWN statement shape (the `assets` table)
from the pre-existing, out-of-scope per-row vuln-count query already in
`list_assets` (unrelated to the SRC-08 sources/sources_count data spine this
plan adds — that field is derived in-Python from the already-selected
`seen_by_sources` column, zero extra queries).
"""

from __future__ import annotations

import uuid

import pytest

from app.assets.models import Asset


def _seed_asset(tenant_id, hostname: str, seen_by_sources: list[str] | None = None) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        seen_by_sources=seen_by_sources if seen_by_sources is not None else [],
    )


@pytest.mark.asyncio
async def test_or_default_multi_scanner_returns_union(client, db_session, tenant_a):
    """THE BUG REGRESSION (SRC-03): no source_mode -> OR-default union.

    Today's chained-`.where()` loop ANDs, so this would wrongly return only
    asset-C (seen by both). The fix must return all three.
    """
    a = _seed_asset(tenant_a, "asset-a", ["CROWDSTRIKE"])
    b = _seed_asset(tenant_a, "asset-b", ["NESSUS"])
    c = _seed_asset(tenant_a, "asset-c", ["CROWDSTRIKE", "NESSUS"])
    db_session.add_all([a, b, c])
    await db_session.commit()

    resp = await client.get("/api/v1/assets?scanner=CROWDSTRIKE,NESSUS")
    assert resp.status_code == 200
    hostnames = {i["hostname"] for i in resp.json()["items"]}
    assert hostnames == {"asset-a", "asset-b", "asset-c"}, f"expected OR union of all 3, got {hostnames}"


@pytest.mark.asyncio
async def test_and_toggle_requires_all(client, db_session, tenant_a):
    """SRC-04: source_mode=and requires ALL selected scanners — true
    corroboration, gated behind the explicit toggle (not the default)."""
    a = _seed_asset(tenant_a, "asset-and-a", ["CROWDSTRIKE"])
    b = _seed_asset(tenant_a, "asset-and-b", ["NESSUS"])
    c = _seed_asset(tenant_a, "asset-and-c", ["CROWDSTRIKE", "NESSUS"])
    db_session.add_all([a, b, c])
    await db_session.commit()

    resp = await client.get("/api/v1/assets?scanner=CROWDSTRIKE,NESSUS&source_mode=and")
    assert resp.status_code == 200
    hostnames = {i["hostname"] for i in resp.json()["items"]}
    assert hostnames == {"asset-and-c"}, f"AND must match only the fully-corroborated asset, got {hostnames}"


@pytest.mark.asyncio
async def test_enrichment_does_not_leak_into_scanner_filter(client, db_session, tenant_a):
    """SRC-06: enrichment sources (JAMF/HUMAANS/INTUNE) are a distinct
    provenance class from scanners and must not leak into a `?scanner=`
    result, nor should a scanner filter's clamp fall through to "no
    filter" (that would silently show enrichment-only assets)."""
    j = _seed_asset(tenant_a, "asset-jamf", ["JAMF"])
    db_session.add(j)
    await db_session.commit()

    resp_scanner = await client.get("/api/v1/assets?scanner=JAMF")
    assert resp_scanner.status_code == 200
    assert resp_scanner.json()["items"] == [], "JAMF must be clamped out of a scanner filter (SRC-06)"

    resp_enrichment = await client.get("/api/v1/assets?enrichment_source=JAMF")
    assert resp_enrichment.status_code == 200
    hostnames = {i["hostname"] for i in resp_enrichment.json()["items"]}
    assert hostnames == {"asset-jamf"}, f"expected asset-jamf via the enrichment_source facet, got {hostnames}"


@pytest.mark.asyncio
async def test_asset_row_carries_sources(client, db_session, tenant_a):
    """SRC-01/08 data spine (assets side): each list row carries `sources`
    (== its seen_by_sources) and `sources_count` (== count of SCANNER_
    SOURCES present, excluding enrichment sources like JAMF)."""
    a = _seed_asset(tenant_a, "asset-sources", ["CROWDSTRIKE", "JAMF"])
    db_session.add(a)
    await db_session.commit()

    resp = await client.get("/api/v1/assets?search=asset-sources")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    row = items[0]
    assert set(row["sources"]) == {"CROWDSTRIKE", "JAMF"}, row
    assert row["sources_count"] == 1, f"only CROWDSTRIKE is a scanner source, got {row['sources_count']}"


@pytest.mark.asyncio
async def test_bad_source_mode_422(client, db_session, tenant_a):
    """SRC-02: source_mode outside {or, and} is rejected with 422, not
    silently defaulted."""
    resp = await client.get("/api/v1/assets?source_mode=bogus")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_assets_query_count_invariant(client, db_session, tenant_a):
    """SRC-08: list_assets issues the SAME number of `assets`-table
    statements for a 5-row page and a 50-row page — the new sources/
    sources_count fields are derived in-Python from the already-selected
    `seen_by_sources` column, so they must add ZERO extra queries.

    Filtered to statements referencing the `assets` table (not
    `vulnerabilities`) per Plan 01's documented table-filter discipline —
    the pre-existing per-row vuln-count query in `list_assets` is a
    separate, out-of-scope concern (unrelated to the SRC-08 sources data
    spine this plan adds) and would otherwise make ANY page-size comparison
    fail regardless of this plan's changes.
    """
    from tests.query_count import count_queries

    for n in range(60):
        db_session.add(_seed_asset(tenant_a, f"asset-qcount-{n:03d}-{uuid.uuid4().hex[:6]}"))
    await db_session.commit()

    def _assets_only(statements: list[str]) -> list[str]:
        return [s for s in statements if "assets" in s]

    with count_queries() as statements_small:
        resp_small = await client.get("/api/v1/assets?page_size=5")
    with count_queries() as statements_large:
        resp_large = await client.get("/api/v1/assets?page_size=50")

    assert resp_small.status_code == 200
    assert resp_large.status_code == 200

    statements_small = _assets_only(statements_small)
    statements_large = _assets_only(statements_large)

    assert len(statements_small) == len(statements_large), (
        f"assets-table statement count must be page-size-invariant: "
        f"page_size=5 issued {len(statements_small)}, page_size=50 issued {len(statements_large)}"
    )
    assert len(statements_small) <= 3, f"expected a small fixed statement count, got {len(statements_small)}"
