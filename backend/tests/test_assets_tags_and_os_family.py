"""Phase 12 — UX-04-01 / UX-04-02 backend tests for the assets list + detail schema delta.

Covers:
  - tags array roundtrips through list + detail endpoints
  - sla_breach aggregation counts only OPEN/IN_PROGRESS vulns past their sla_due_at
  - os_family query param maps to the hardcoded ILIKE prefix sets (T-12-01)
  - os_family="other" excludes linux/windows/macos rows

Uses the canonical inline-construction pattern from test_top_vuln.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.assets.models import Asset
from app.db.session import engine
from app.vulnerabilities.models import Vulnerability


# WORKAROUND for a pre-existing test-infra issue: pytest-asyncio uses a
# function-scoped event loop, but `app.db.session.engine` is a module-level
# async engine whose asyncpg connection pool is bound to whichever loop
# happened to make the first connection. After test #1's loop closes,
# subsequent tests find the cached pool full of "Event loop is closed"
# connections and `_db_reachable()` returns False (→ pytest.skip), or the
# next session.flush() trips a RuntimeError before any user code runs.
#
# Disposing the engine before each test gives this file a fresh pool bound
# to the current loop, which is enough for the suite to run end-to-end.
# Scoped to this test file so we don't churn the global conftest fixture.
@pytest_asyncio.fixture(autouse=True)
async def _reset_engine_pool():
    await engine.dispose()
    yield


def _seed_asset(tenant_id, hostname: str, *, tags=None, os_name="Ubuntu 22.04 LTS") -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        tags=tags or [],
        os_name=os_name,
    )


def _seed_vuln(
    tenant_id,
    *,
    asset_id,
    status: str = "OPEN",
    sla_due_at=None,
    cve_id: str | None = None,
    severity: str = "HIGH",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id or f"CVE-2026-{uuid.uuid4().hex[:6]}",
        severity=severity,
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        sla_due_at=sla_due_at,
        first_detected_at=now,
        last_seen_at=now,
    )


@pytest.mark.asyncio
async def test_list_assets_returns_tags_and_sla_breach(client, db_session, tenant_a):
    a = _seed_asset(tenant_a, "prod-db-01", tags=["pci", "tier-1"])
    db_session.add(a)
    await db_session.flush()
    # 2 vulns: one breached (sla_due_at in the past), one not.
    db_session.add(
        _seed_vuln(
            tenant_a,
            asset_id=a.id,
            status="OPEN",
            sla_due_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    db_session.add(
        _seed_vuln(
            tenant_a,
            asset_id=a.id,
            status="OPEN",
            sla_due_at=datetime.now(UTC) + timedelta(days=3),
        )
    )
    await db_session.commit()

    r = await client.get("/api/v1/assets")
    assert r.status_code == 200
    items = r.json()["items"]
    target = next(i for i in items if i["hostname"] == "prod-db-01")
    assert target["tags"] == ["pci", "tier-1"]
    assert target["sla_breach"] == 1


@pytest.mark.asyncio
async def test_detail_endpoint_returns_tags_and_sla_breach(client, db_session, tenant_a):
    a = _seed_asset(tenant_a, "prod-web-02", tags=["dmz"], os_name="Windows Server 2022")
    db_session.add(a)
    await db_session.flush()
    db_session.add(
        _seed_vuln(
            tenant_a,
            asset_id=a.id,
            status="OPEN",
            sla_due_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.commit()

    r = await client.get(f"/api/v1/assets/{a.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["tags"] == ["dmz"]
    assert body["vuln_counts"]["sla_breach"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "os_name,family,should_match",
    [
        ("Ubuntu 22.04 LTS", "linux", True),
        ("Debian 12", "linux", True),
        ("Windows 11", "windows", True),
        ("macOS Ventura", "macos", True),
        ("Mac OS X 10.15", "macos", True),
        ("Ubuntu 22.04 LTS", "windows", False),
        ("Windows 11", "linux", False),
    ],
)
async def test_os_family_filter_matches_prefix(
    client, db_session, tenant_a, os_name, family, should_match
):
    hostname = f"host-{family}-{uuid.uuid4().hex[:6]}"
    a = _seed_asset(tenant_a, hostname, os_name=os_name)
    db_session.add(a)
    await db_session.commit()
    r = await client.get(f"/api/v1/assets?os_family={family}")
    assert r.status_code == 200
    hostnames = [i["hostname"] for i in r.json()["items"]]
    if should_match:
        assert hostname in hostnames, f"{os_name} should match os_family={family}"
    else:
        assert hostname not in hostnames, f"{os_name} should NOT match os_family={family}"


@pytest.mark.asyncio
async def test_os_family_other_excludes_known_families(client, db_session, tenant_a):
    db_session.add(_seed_asset(tenant_a, "cisco-rtr-01", os_name="Cisco IOS XE"))
    db_session.add(_seed_asset(tenant_a, "ubuntu-01", os_name="Ubuntu 22.04 LTS"))
    await db_session.commit()
    r = await client.get("/api/v1/assets?os_family=other")
    assert r.status_code == 200
    hostnames = [i["hostname"] for i in r.json()["items"]]
    assert "cisco-rtr-01" in hostnames
    assert "ubuntu-01" not in hostnames
