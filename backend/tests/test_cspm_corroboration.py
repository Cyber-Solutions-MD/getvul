"""Phase 35 Plan 04 — CSPM AND corroboration (no silent OR) + batched group
sources + query-count no-N+1 proof.

Covers SRC-05 (true multi-tool AND corroboration via a read-time
GROUP BY(tenant_id, rule_id, resource_id) over Misconfiguration rows — NEVER
a silent `Misconfiguration.source.in_()` fallback for AND), SRC-02 (cspm
half: `source_mode` bound as a real router Query param so `?source_mode=and`
reaches the grouping), and SRC-08 (list_misconfigurations issues a FIXED
statement count independent of page size).

Seeds Misconfiguration rows directly, sharing vs differing (rule_id,
resource_id) pairs, mirroring the `uq_misconfig_dedup(tenant_id, rule_id,
resource_id, source)` constraint at cspm/models.py:48. Reuses
`tests.query_count.count_queries` (Plan 01's harness) verbatim.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.cspm.models import Misconfiguration
from app.cspm.schemas import MisconfigFilter
from app.cspm.service import list_misconfigurations
from app.pagination import PaginationParams
from tests.query_count import count_queries


def _seed_misconfig(
    tenant_id: uuid.UUID,
    *,
    source: str,
    rule_id: str,
    resource_id: str,
    severity: str = "HIGH",
) -> Misconfiguration:
    now = datetime.now(UTC)
    return Misconfiguration(
        tenant_id=tenant_id,
        rule_id=rule_id,
        rule_name=f"Rule {rule_id}",
        category="NETWORK",
        severity=severity,
        resource_id=resource_id,
        resource_name=f"resource-{resource_id}",
        source=source,
        status="OPEN",
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_cspm_and_requires_same_group(client, db_session, tenant_a):
    """SRC-05 core: AND mode requires the SAME (rule_id, resource_id) group
    to be flagged by BOTH selected tools — not just present somewhere in the
    result set. WIZ+DEFENDER share (R1, X1); WIZ alone flags (R2, X2);
    DEFENDER alone flags (R3, X3). ?source=WIZ&source=DEFENDER&source_mode=and
    must return ONLY the (R1, X1) group's rows."""
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="R1", resource_id="X1"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="R1", resource_id="X1"))
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="R2", resource_id="X2"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="R3", resource_id="X3"))
    await db_session.commit()

    resp = await client.get("/api/v1/cspm?source=WIZ&source=DEFENDER&source_mode=and")
    assert resp.status_code == 200
    items = resp.json()["items"]
    keys = {(i["rule_id"], i["resource_id"]) for i in items}
    assert keys == {("R1", "X1")}, f"AND must gate on the (rule_id,resource_id) group, got {keys}"
    assert len(items) == 2, "both rows (WIZ + DEFENDER) of the (R1,X1) group should be present"


@pytest.mark.asyncio
async def test_cspm_or_default_unchanged(client, db_session, tenant_a):
    """OR stays correct: no source_mode (or source_mode=or) returns the union
    of all WIZ-or-DEFENDER rows, including the non-corroborated (R2,X2) and
    (R3,X3) singles."""
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="R1OR", resource_id="X1OR"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="R1OR", resource_id="X1OR"))
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="R2OR", resource_id="X2OR"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="R3OR", resource_id="X3OR"))
    db_session.add(_seed_misconfig(tenant_a, source="QUALYS", rule_id="R4OR", resource_id="X4OR"))
    await db_session.commit()

    resp = await client.get("/api/v1/cspm?source=WIZ&source=DEFENDER")
    assert resp.status_code == 200
    items = resp.json()["items"]
    keys = {(i["rule_id"], i["resource_id"]) for i in items}
    assert keys == {("R1OR", "X1OR"), ("R2OR", "X2OR"), ("R3OR", "X3OR")}, keys


@pytest.mark.asyncio
async def test_cspm_row_carries_group_sources(client, db_session, tenant_a):
    """Each row carries `sources` (the array_agg of tools on its own
    (rule_id, resource_id) group) and `sources_count`. A corroborated group's
    rows show both tools + count 2; a single-tool row shows [its source] / 1."""
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="RGRP", resource_id="XGRP"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="RGRP", resource_id="XGRP"))
    db_session.add(_seed_misconfig(tenant_a, source="QUALYS", rule_id="RSOLO", resource_id="XSOLO"))
    await db_session.commit()

    resp = await client.get("/api/v1/cspm?resource_type=")
    assert resp.status_code == 200
    items = resp.json()["items"]
    by_key = {(i["rule_id"], i["resource_id"], i["source"]): i for i in items}

    grp_wiz = by_key[("RGRP", "XGRP", "WIZ")]
    grp_def = by_key[("RGRP", "XGRP", "DEFENDER")]
    assert set(grp_wiz["sources"]) == {"WIZ", "DEFENDER"}
    assert grp_wiz["sources_count"] == 2
    assert set(grp_def["sources"]) == {"WIZ", "DEFENDER"}
    assert grp_def["sources_count"] == 2

    solo = by_key[("RSOLO", "XSOLO", "QUALYS")]
    assert solo["sources"] == ["QUALYS"], f"single-tool fallback must never be null/unknown: {solo}"
    assert solo["sources_count"] == 1


@pytest.mark.asyncio
async def test_cspm_query_count_invariant(db_session, tenant_a):
    """SRC-08: list_misconfigurations issues a FIXED statement count
    independent of page size — one grouped batched query for the page's
    (rule_id, resource_id) keys, never per-row."""
    for n in range(60):
        db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id=f"RQC{n:03d}", resource_id=f"XQC{n:03d}"))
    await db_session.commit()

    filters = MisconfigFilter()
    _relevant_tables = ("misconfigurations", "tenants")

    def _relevant(statements: list[str]) -> list[str]:
        return [s for s in statements if any(t in s for t in _relevant_tables)]

    with count_queries() as statements_small:
        await list_misconfigurations(db_session, tenant_a, filters, PaginationParams(page=1, page_size=5))
    with count_queries() as statements_large:
        await list_misconfigurations(db_session, tenant_a, filters, PaginationParams(page=1, page_size=50))

    statements_small = _relevant(statements_small)
    statements_large = _relevant(statements_large)

    assert len(statements_small) == len(statements_large), (
        f"statement count must be page-size-invariant: "
        f"page_size=5 issued {len(statements_small)}, page_size=50 issued {len(statements_large)}"
    )
    assert len(statements_small) <= 4, f"expected a small fixed statement count, got {len(statements_small)}"


@pytest.mark.asyncio
async def test_cspm_and_reaches_service_via_http(client, db_session, tenant_a):
    """SRC-04/02 binding: ?source_mode=and over HTTP must reach the same
    corroboration-only result as calling list_misconfigurations directly —
    proving source_mode is bound at the router (not silently dropped by
    FastAPI param parsing)."""
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="RHTTP", resource_id="XHTTP"))
    db_session.add(_seed_misconfig(tenant_a, source="DEFENDER", rule_id="RHTTP", resource_id="XHTTP"))
    db_session.add(_seed_misconfig(tenant_a, source="WIZ", rule_id="RHTTP2", resource_id="XHTTP2"))
    await db_session.commit()

    filters = MisconfigFilter(source=["WIZ", "DEFENDER"], source_mode="and")
    direct = await list_misconfigurations(db_session, tenant_a, filters, PaginationParams(page=1, page_size=50))
    direct_keys = {(i.rule_id, i.resource_id) for i in direct.items}

    resp = await client.get("/api/v1/cspm?source=WIZ&source=DEFENDER&source_mode=and")
    assert resp.status_code == 200
    http_keys = {(i["rule_id"], i["resource_id"]) for i in resp.json()["items"]}

    assert http_keys == direct_keys == {("RHTTP", "XHTTP")}
