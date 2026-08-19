"""Phase 39 Plan 05 (EXC-02 "dashboards", D-15) -- consumer-sweep coverage
for the asset list/detail badges (incl. sla_breach), owner-risk aggregate,
and /dashboard tiles/top-vuln/nav counts + get_dashboard_stats.

Task 1 (this section): assets/router.py, users/router.py, dashboard.py +
service.py::get_dashboard_stats.

Task 2 will append export.py, risk_exposure_service.py, and a Tier 3
non-regression guard (search.py) to this same file.

Every test hand-seeds an `ExceptionRecord` directly (bypassing
`grant_exception`), mirroring `test_exceptions_sla.py::_seed_exception` --
full control and no RBAC/precondition friction, matching this phase's
established test-authoring precedent.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions_dashboards.py -x
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.assets.models import Asset
from app.exceptions.models import ExceptionRecord
from app.tenants.models import User
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id: uuid.UUID, **overrides: Any) -> Asset:
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "hostname": f"host-{uuid.uuid4().hex[:8]}",
        "os_name": "Ubuntu 22.04",
    }
    defaults.update(overrides)
    return Asset(**defaults)


def _seed_vuln(tenant_id: uuid.UUID, **overrides: Any) -> Vulnerability:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "tenant_id": tenant_id,
        "asset_id": None,
        "cve_id": f"CVE-DASH-{uuid.uuid4().hex[:6]}",
        "severity": "CRITICAL",
        "status": "OPEN",
        "source": "MOCK",
        "source_vuln_id": str(uuid.uuid4()),
        "first_detected_at": now - timedelta(days=3),
        "last_seen_at": now,
    }
    defaults.update(overrides)
    return Vulnerability(**defaults)


def _seed_exception(
    tenant_id: uuid.UUID,
    *,
    vuln: Vulnerability,
    approver_user_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
    exc_type: str = "ACCEPTED_RISK",
) -> ExceptionRecord:
    """A currently-ACTIVE FINDING-scope exception targeting `vuln` --
    hand-seeded (bypassing `grant_exception`), mirroring
    `test_exceptions_sla.py::_seed_exception`. Every consumer under test
    here matches on `active_exception_subquery`'s FINDING branch
    (`ExceptionRecord.vulnerability_id == Vulnerability.id`) -- the
    underlying exclusion semantics were already proven for all 3 scope
    types by 39-01/39-02; this plan only proves each NEW consumer learned
    the shared join.
    """
    return ExceptionRecord(
        tenant_id=tenant_id,
        type=exc_type,
        scope_type="FINDING",
        cve_id=vuln.cve_id,
        vulnerability_id=vuln.id,
        asset_id=vuln.asset_id,
        justification="Seeded directly for dashboard/export exclusion test",
        approver_user_id=approver_user_id,
        granted_by_user_id=granted_by_user_id,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


# ── Task 1: asset / owner / dashboard / nav badge exclusion ────────────────


@pytest.mark.asyncio
async def test_excluded_from_asset_badges(client, db_session, tenant_a, admin_user, analyst_user):
    """Asset list AND detail vuln-count/critical/high/exploitable/kev
    badges (assets/router.py, Tier 2 #11) exclude an actively-excepted
    finding."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL", exploit_available=True, cisa_kev=True)
    db_session.add(vuln)
    await db_session.commit()

    list_before = (await client.get("/api/v1/assets")).json()
    item = next(i for i in list_before["items"] if i["id"] == str(asset.id))
    assert item["total_vulns"] == 1
    assert item["critical"] == 1
    assert item["exploitable"] == 1
    assert item["kev"] == 1

    detail_before = (await client.get(f"/api/v1/assets/{asset.id}")).json()
    assert detail_before["vuln_counts"]["total"] == 1
    assert detail_before["vuln_counts"]["critical"] == 1
    assert detail_before["vuln_counts"]["exploitable"] == 1
    assert detail_before["vuln_counts"]["kev"] == 1

    db_session.add(
        _seed_exception(tenant_a, vuln=vuln, approver_user_id=admin_user.id, granted_by_user_id=analyst_user.id)
    )
    await db_session.commit()

    list_after = (await client.get("/api/v1/assets")).json()
    item2 = next(i for i in list_after["items"] if i["id"] == str(asset.id))
    assert item2["total_vulns"] == 0
    assert item2["critical"] == 0
    assert item2["exploitable"] == 0
    assert item2["kev"] == 0

    detail_after = (await client.get(f"/api/v1/assets/{asset.id}")).json()
    assert detail_after["vuln_counts"]["total"] == 0
    assert detail_after["vuln_counts"]["critical"] == 0
    assert detail_after["vuln_counts"]["exploitable"] == 0
    assert detail_after["vuln_counts"]["kev"] == 0


@pytest.mark.asyncio
async def test_excluded_from_asset_sla_breach_badge(client, db_session, tenant_a, admin_user, analyst_user):
    """The sla_breach badge (assets/router.py, reads persisted sla_due_at
    directly -- Tier 2 #11) excludes an actively-excepted finding, proving
    read-time exclusion agrees with 39-03's persisted-mirror fix."""
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, sla_due_at=datetime.now(UTC) - timedelta(days=1))
    db_session.add(vuln)
    await db_session.commit()

    list_before = (await client.get("/api/v1/assets")).json()
    item = next(i for i in list_before["items"] if i["id"] == str(asset.id))
    assert item["sla_breach"] == 1

    detail_before = (await client.get(f"/api/v1/assets/{asset.id}")).json()
    assert detail_before["sla_breach"] == 1
    assert detail_before["vuln_counts"]["sla_breach"] == 1

    db_session.add(
        _seed_exception(tenant_a, vuln=vuln, approver_user_id=admin_user.id, granted_by_user_id=analyst_user.id)
    )
    await db_session.commit()

    list_after = (await client.get("/api/v1/assets")).json()
    item2 = next(i for i in list_after["items"] if i["id"] == str(asset.id))
    assert item2["sla_breach"] == 0

    detail_after = (await client.get(f"/api/v1/assets/{asset.id}")).json()
    assert detail_after["sla_breach"] == 0
    assert detail_after["vuln_counts"]["sla_breach"] == 0


@pytest.mark.asyncio
async def test_excluded_from_owner_aggregate(client, db_session, tenant_a, admin_user, analyst_user):
    """Both users/router.py owner-risk surfaces (Tier 2 #12) -- the root
    Humaans-merged `list_users` AND `/directory` -- exclude an
    actively-excepted finding."""
    email = f"owner-{uuid.uuid4().hex[:8]}@test.local"
    directory_user = User(
        tenant_id=tenant_a,
        email=email,
        display_name="Test Owner",
        role="VIEWER",
        idp_subject=f"test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(directory_user)
    asset = _seed_asset(
        tenant_a,
        assigned_user=email,
        mdm_details={"humaans_person_id": "hp-test", "humaans_email": email},
    )
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL")
    db_session.add(vuln)
    await db_session.commit()

    root_before = (await client.get("/api/v1/users")).json()
    root_item = next(i for i in root_before["items"] if i["user_key"] == email.lower())
    assert root_item["total_vulns"] == 1
    assert root_item["critical_vulns"] == 1

    dir_before = (await client.get("/api/v1/users/directory")).json()
    dir_item = next(i for i in dir_before["items"] if i["email"] == email)
    assert dir_item["total_vulns"] == 1
    assert dir_item["critical_vulns"] == 1

    db_session.add(
        _seed_exception(tenant_a, vuln=vuln, approver_user_id=admin_user.id, granted_by_user_id=analyst_user.id)
    )
    await db_session.commit()

    root_after = (await client.get("/api/v1/users")).json()
    root_item2 = next(i for i in root_after["items"] if i["user_key"] == email.lower())
    assert root_item2["total_vulns"] == 0
    assert root_item2["critical_vulns"] == 0

    dir_after = (await client.get("/api/v1/users/directory")).json()
    dir_item2 = next(i for i in dir_after["items"] if i["email"] == email)
    assert dir_item2["total_vulns"] == 0
    assert dir_item2["critical_vulns"] == 0


@pytest.mark.asyncio
async def test_excluded_from_dashboard_tiles_and_nav(client, db_session, tenant_a, admin_user, analyst_user):
    """/dashboard tiles (critical_open/sla_at_risk/kev), the top-vuln
    spotlight, the persistent nav vuln_open_count, AND
    get_dashboard_stats' open_vulnerabilities (Tier 2 #13) all exclude an
    actively-excepted finding."""
    # first_detected_at 10d ago (> the 7d critical SLA tier) so the seeded
    # row is GENUINELY breached, not merely flag-forced -- the app's live
    # background scheduler (started by the `client` fixture's app lifespan)
    # independently recomputes sla_breached on its own tick and would
    # otherwise race a hand-set flag back to False.
    vuln = _seed_vuln(
        tenant_a,
        severity="CRITICAL",
        cisa_kev=True,
        sla_breached=True,
        cvss_v3_score=9.8,
        status="OPEN",
        first_detected_at=datetime.now(UTC) - timedelta(days=10),
    )
    db_session.add(vuln)
    await db_session.commit()

    body = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body["dashboard_tiles"]["critical_open"]["value"] == 1
    assert body["dashboard_tiles"]["sla_at_risk"]["value"] == 1
    assert body["dashboard_tiles"]["kev"]["value"] == 1
    assert body["vuln_open_count"] == 1
    assert body["open_vulnerabilities"] == 1
    assert body["top_vuln"] is not None
    assert body["top_vuln"]["cve_id"] == vuln.cve_id

    db_session.add(
        _seed_exception(tenant_a, vuln=vuln, approver_user_id=admin_user.id, granted_by_user_id=analyst_user.id)
    )
    await db_session.commit()

    body2 = (await client.get("/api/v1/vulnerabilities/stats")).json()
    assert body2["dashboard_tiles"]["critical_open"]["value"] == 0
    assert body2["dashboard_tiles"]["sla_at_risk"]["value"] == 0
    assert body2["dashboard_tiles"]["kev"]["value"] == 0
    assert body2["vuln_open_count"] == 0
    assert body2["open_vulnerabilities"] == 0
    assert body2["top_vuln"] is None
