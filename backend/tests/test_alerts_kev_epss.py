"""Phase 40 Plan 01 (ALERT-01) -- Wave 0 RED scaffold for KEV/EPSS
transition-detection alerting.

Asserts against `app.notifications.alerts._check_new_kev_epss`, which does
not exist until Plan 02. The module `app.notifications.alerts` itself
already exists (importing it at module level below is safe); the specific
function is looked up as an attribute *inside* each test body so
`pytest --collect-only` stays green (Wave 0 requirement) while every test
still documents -- and fails meaningfully against -- the intended ALERT-01
behavior until Plan 02 lands. `xfail(strict=False)` means once Plan 02
implements the function, these tests flip to XPASS (visible, non-fatal)
rather than needing this file edited to "unlock" them.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).

Test names match the Phase Requirements -> Test Map (40-RESEARCH.md:448-470).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from app.notifications import alerts

pytestmark = pytest.mark.xfail(
    strict=False, reason="_check_new_kev_epss ships in Phase 40 Plan 02 (ALERT-01) -- Wave 0 RED scaffold"
)


async def _make_kev_vuln(db_session: Any, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> Any:
    """A second KEV-qualifying finding, distinct from the `kev_epss_finding`
    fixture's own vuln -- simulates a finding arriving AFTER a tenant's
    cold-start pass has already seeded the baseline (D-06)."""
    from app.vulnerabilities.models import Vulnerability

    now = datetime.now(UTC)
    vuln = Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-2026-{uuid.uuid4().hex[:5]}",
        vulnerability_name="Second KEV-qualifying finding",
        severity="CRITICAL",
        cisa_kev=True,
        epss_score=Decimal("0.91"),
        asset_id=asset_id,
        source="NESSUS",
        first_detected_at=now,
        last_seen_at=now,
    )
    db_session.add(vuln)
    await db_session.flush()
    return vuln


async def test_first_pass_seeds_silently(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """D-06: a tenant's very first alerting pass records every currently-
    qualifying (cve, asset) pair into the guard table WITHOUT firing --
    otherwise day one would alert-storm the entire existing backlog."""
    from app.notifications.models import AlertingGuard
    from app.tenants.models import Tenant

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()

    fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert fired == 0, "cold-start pass must not fire any alerts"

    guard_rows = (
        (await db_session.execute(select(AlertingGuard).where(AlertingGuard.tenant_id == tenant_a))).scalars().all()
    )
    assert len(guard_rows) >= 1, "cold-start pass must still seed a guard row for the qualifying pair"
    assert all(row.fired_at is None for row in guard_rows), "seeded (not fired) rows must have fired_at IS NULL"


async def test_new_kev_match_fires_once(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """Once a tenant is past cold-start, a genuinely NEW qualifying pair
    fires exactly once and inserts its own guard row with `fired_at` set."""
    from app.notifications.models import AlertingGuard
    from app.tenants.models import Tenant

    vuln, asset, _owner = kev_epss_finding
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()

    await alerts._check_new_kev_epss(db_session, tenant)  # cold-start pass, seeds `vuln`

    new_vuln = await _make_kev_vuln(db_session, tenant_a, asset.id)
    fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert fired == 1

    guard_row = (
        await db_session.execute(
            select(AlertingGuard).where(
                AlertingGuard.tenant_id == tenant_a,
                AlertingGuard.cve_id == new_vuln.cve_id,
                AlertingGuard.asset_id == asset.id,
            )
        )
    ).scalar_one()
    assert guard_row.fired_at is not None


async def test_guard_prevents_refire(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """Once a pair has fired, an immediate second pass must NOT re-fire it
    -- the guard's UniqueConstraint is the correctness backstop for
    "exactly once" (D-05)."""
    from app.tenants.models import Tenant

    _vuln, asset, _owner = kev_epss_finding
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()

    await alerts._check_new_kev_epss(db_session, tenant)  # cold-start, seeds the fixture's vuln
    await _make_kev_vuln(db_session, tenant_a, asset.id)
    first_pass_fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert first_pass_fired == 1

    second_pass_fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert second_pass_fired == 0, "re-running immediately must not re-fire an already-guarded pair"


async def test_excepted_suppressed_excluded(db_session: Any, tenant_a: uuid.UUID, kev_epss_finding: Any) -> None:
    """D-20: a SUPPRESSED/FALSE_POSITIVE finding (or one covered by an
    active Phase 39 exception) must never fire ALERT-01 -- reusing the
    Phase 39 exclusion predicate rather than re-deriving it. Suppressing a
    would-otherwise-fire NEW pair (not merely relying on cold-start) is
    what actually proves the exclusion, vs. test_first_pass_seeds_silently
    which is zero-fire for an unrelated reason."""
    from app.tenants.models import Tenant

    _vuln, asset, _owner = kev_epss_finding
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()

    await alerts._check_new_kev_epss(db_session, tenant)  # cold-start pass

    new_vuln = await _make_kev_vuln(db_session, tenant_a, asset.id)
    new_vuln.status = "SUPPRESSED"
    await db_session.flush()

    fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert fired == 0, "a SUPPRESSED finding must not fire even though it would otherwise be a new match"


async def test_owner_fallback_to_admins_and_channel(
    db_session: Any, tenant_a: uuid.UUID, admin_user: Any, kev_epss_finding: Any
) -> None:
    """D-10: when an asset's `assigned_user` does not resolve to a real
    tenant User (unlike the `kev_epss_finding` fixture's own asset, which
    DOES resolve), ALERT-01 must still notify -- falling back to the
    tenant's OWNER/ADMIN users plus the shared alert channel -- rather than
    silently dropping the alert because no owner was found."""
    from app.assets.models import Asset
    from app.tenants.models import Tenant

    _vuln, asset, _owner = kev_epss_finding
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()

    await alerts._check_new_kev_epss(db_session, tenant)  # cold-start pass

    asset.assigned_user = "no-such-person@tenant-a.test"  # deliberately unresolvable
    await db_session.flush()
    await _make_kev_vuln(db_session, tenant_a, asset.id)

    fired = await alerts._check_new_kev_epss(db_session, tenant)
    assert fired == 1, "an unresolvable owner must fall back to admins+channel, not silently drop the alert"

    refreshed_asset = (await db_session.execute(select(Asset).where(Asset.id == asset.id))).scalar_one()
    assert refreshed_asset.assigned_user == "no-such-person@tenant-a.test"
