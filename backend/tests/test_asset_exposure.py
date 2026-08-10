"""Phase 32 Plans 01+02 — tests for exposure-context inference, per-asset
override permanence, RBAC, audit trail, and EXPO-06 calibration.

Covers:
  - infer_exposure_context: pure-function business_criticality inference
    (real logic) and, since Plan 02, real data_sensitivity/internet_facing
    inference too — never mutating the caller's `tags` list.
  - GET /assets/{id} surfaces all 6 exposure keys with sane AUTO defaults
    on a freshly-upserted asset (EXPO-01).
  - apply_inference_to_asset re-infers an AUTO field after MDM/HR enrichment
    changes department/job_title, without flipping its source, and skips
    ALL fields once ASSET_OVERRIDE-sourced (EXPO-02).
  - PATCH /assets/{id}/exposure-context flips business_criticality to
    ASSET_OVERRIDE and that override survives a subsequent full-tenant
    recompute (EXPO-03).
  - RBAC (403 for analyst/viewer) + cross-tenant 404-not-403 on the
    override endpoint (access control).
  - Audit: exactly one row per manual override; auto-inference audits
    only when a value actually changes, never on re-affirmation (EXPO-05).
  - check_criticality_calibration (EXPO-06): AUTO-only CRITICAL proportion
    against a realistic 100-asset fixture, tenant-configurable cap, override
    exemption, and the admin-gated GET /assets/exposure-context/calibration
    endpoint.

Uses the project's canonical inline-seed + client_factory pattern from
test_asset_owner_reassign.py / test_ai_status.py. No respx/pytest-httpx —
this plan touches no HTTP-bound connector code directly.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog

# `_reset_engine_pool` (autouse) lives in conftest.py.


def _seed_asset(
    tenant_id,
    hostname: str,
    *,
    department: str | None = None,
    job_title: str | None = None,
    tags: list[str] | None = None,
    external_ip: str | None = None,
    os_name: str = "Ubuntu 22.04 LTS",
) -> Asset:
    mdm_details = {"humaans_job_title": job_title} if job_title else None
    return Asset(
        tenant_id=tenant_id,
        hostname=hostname,
        department=department,
        mdm_details=mdm_details,
        tags=tags,
        external_ip=external_ip,
        os_name=os_name,
    )


# ── Unit tests (no DB) ──────────────────────────────────────────────────


def test_infer_exposure_context_high_signal_asset():
    """A CFO/Finance/pci-tagged asset infers into the top criticality tiers."""
    from app.assets.exposure import infer_exposure_context

    criticality, _sensitivity, _internet_facing = infer_exposure_context(
        tags=["pci"], department="Finance", job_title="CFO", external_ip=None
    )
    assert criticality in ("CRITICAL", "HIGH")


def test_infer_exposure_context_defaults_with_no_signal():
    """No department/job_title/tags/external_ip → MEDIUM criticality + the
    documented (Plan-02-owned) defaults for the other two fields."""
    from app.assets.exposure import infer_exposure_context

    result = infer_exposure_context(tags=None, department=None, job_title=None, external_ip=None)
    assert result == ("MEDIUM", "INTERNAL", False)


def test_infer_exposure_context_does_not_mutate_tags():
    """The pure inference function must never mutate the caller's tags list."""
    from app.assets.exposure import infer_exposure_context

    tags = ["x"]
    infer_exposure_context(tags=tags, department=None, job_title=None, external_ip=None)
    assert tags == ["x"]


# ── Unit tests: real data_sensitivity + internet_facing (Plan 02, EXPO-01) ─


def test_infer_all_three_fields():
    """All three exposure fields infer from real signals (Plan 02 replaces
    the two static Plan-01 defaults with real logic)."""
    from app.assets.exposure import infer_exposure_context

    # RESTRICTED: pii tag is the strongest data_sensitivity signal.
    criticality, sensitivity, internet_facing = infer_exposure_context(
        tags=["pii"], department="Finance", job_title="CFO", external_ip="1.2.3.4"
    )
    assert criticality in ("CRITICAL", "HIGH")
    assert sensitivity == "RESTRICTED"
    assert internet_facing is True

    # PUBLIC: marketing department + public/www tags, no other signal.
    _criticality, sensitivity, _internet_facing = infer_exposure_context(
        tags=["public", "www"], department="Marketing", job_title=None, external_ip=None
    )
    assert sensitivity == "PUBLIC"

    # INTERNAL: no signal at all falls back to the safe default.
    _criticality, sensitivity, _internet_facing = infer_exposure_context(
        tags=None, department=None, job_title=None, external_ip=None
    )
    assert sensitivity == "INTERNAL"

    # CONFIDENTIAL: pci tag or finance/legal department (no pii/phi/restricted).
    _criticality, sensitivity, _internet_facing = infer_exposure_context(
        tags=["pci"], department=None, job_title=None, external_ip=None
    )
    assert sensitivity == "CONFIDENTIAL"


def test_internet_facing_from_tag_or_external_ip():
    """internet_facing is True from either the "internet-facing" tag OR a
    non-null external_ip — and False when neither signal is present."""
    from app.assets.exposure import infer_exposure_context

    _c, _s, internet_facing = infer_exposure_context(
        tags=["internet-facing"], department=None, job_title=None, external_ip=None
    )
    assert internet_facing is True

    _c, _s, internet_facing = infer_exposure_context(
        tags=None, department=None, job_title=None, external_ip="203.0.113.5"
    )
    assert internet_facing is True

    _c, _s, internet_facing = infer_exposure_context(tags=None, department=None, job_title=None, external_ip=None)
    assert internet_facing is False


@pytest.mark.asyncio
async def test_reinference_skips_all_overridden_fields(db_session, tenant_a):
    """apply_inference_to_asset skips EVERY field whose source has been
    flipped to ASSET_OVERRIDE — not just business_criticality — even when a
    strong signal for that field is newly present."""
    from app.assets.exposure import apply_inference_to_asset

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()

    # Manually override all three fields (simulating three separate PATCH
    # /exposure-context calls) before any strong signal exists.
    a.business_criticality = "LOW"
    a.business_criticality_source = "ASSET_OVERRIDE"
    a.data_sensitivity = "PUBLIC"
    a.data_sensitivity_source = "ASSET_OVERRIDE"
    a.internet_facing = False
    a.internet_facing_source = "ASSET_OVERRIDE"
    await db_session.commit()

    # Now introduce signals that would push every field to its opposite
    # extreme if inference were allowed to run.
    a.department = "Finance"
    a.mdm_details = {"humaans_job_title": "CFO"}
    a.tags = ["pii", "internet-facing"]
    a.external_ip = "198.51.100.7"

    changes = apply_inference_to_asset(a)
    await db_session.commit()

    assert changes == []
    assert a.business_criticality == "LOW"
    assert a.data_sensitivity == "PUBLIC"
    assert a.internet_facing is False


# ── Integration: upsert + defaults (EXPO-01) ───────────────────────────


@pytest.mark.asyncio
async def test_upsert_sets_default_exposure_fields(client, db_session, tenant_a):
    """A brand-new scanner-only asset (no department yet) carries all 6
    exposure keys with sane AUTO defaults, surfaced via GET /assets/{id}."""
    from app.connectors.base import NormalizedVulnerability
    from app.connectors.sync import _upsert_asset

    v = NormalizedVulnerability(
        cve_id="CVE-2024-0001",
        vulnerability_name="Test finding",
        cvss_v3_score=5.0,
        severity="MEDIUM",
        hostname=f"scan-host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04 LTS",
    )
    asset = await _upsert_asset(db_session, tenant_a, v, "NESSUS")
    await db_session.commit()
    asset_id = asset.id

    r = await client.get(f"/api/v1/assets/{asset_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["business_criticality"] == "MEDIUM"
    assert body["business_criticality_source"] == "AUTO"
    assert body["data_sensitivity"] == "INTERNAL"
    assert body["data_sensitivity_source"] == "AUTO"
    assert body["internet_facing"] is False
    assert body["internet_facing_source"] == "AUTO"


# ── Integration: re-inference after enrichment (EXPO-02) ───────────────


@pytest.mark.asyncio
async def test_reinference_updates_auto_field(db_session, tenant_a):
    """Re-running inference after department/job_title enrichment raises
    business_criticality while the field is still AUTO-sourced."""
    from app.assets.exposure import apply_inference_to_asset

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    assert a.business_criticality == "MEDIUM"
    assert a.business_criticality_source == "AUTO"

    # Simulate MDM/HR enrichment landing after the initial scanner upsert.
    a.department = "Finance"
    a.mdm_details = {"humaans_job_title": "CFO"}

    changes = apply_inference_to_asset(a)
    await db_session.commit()

    assert a.business_criticality in ("CRITICAL", "HIGH")
    assert a.business_criticality_source == "AUTO"
    assert any(c["field"] == "business_criticality" for c in changes)


# ── Integration: override permanence (EXPO-03) ──────────────────────────


@pytest.mark.asyncio
async def test_asset_override_wins_over_reinference(client_factory, db_session, tenant_a, admin_user):
    """Admin override flips source to ASSET_OVERRIDE; a subsequent
    recompute with a high-criticality signal present leaves it untouched."""
    from app.assets.exposure import recompute_exposure_context

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    admin_client = client_factory(admin_user)
    r = await admin_client.patch(
        f"/api/v1/assets/{asset_id}/exposure-context",
        json={"field": "business_criticality", "value": "LOW"},
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(a)
    assert a.business_criticality == "LOW"
    assert a.business_criticality_source == "ASSET_OVERRIDE"

    # A high-criticality signal now present would, absent the override,
    # push business_criticality up — but the override must permanently win.
    a.department = "Finance"
    a.mdm_details = {"humaans_job_title": "CFO"}
    await db_session.commit()

    await recompute_exposure_context(db_session, tenant_a)
    await db_session.commit()
    await db_session.refresh(a)

    assert a.business_criticality == "LOW"
    assert a.business_criticality_source == "ASSET_OVERRIDE"


# ── Access control ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_override_requires_admin_role(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """Non-admin roles (analyst, viewer) are rejected with 403."""
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    for user in (analyst_user, viewer_user):
        c = client_factory(user)
        r = await c.patch(
            f"/api/v1/assets/{asset_id}/exposure-context",
            json={"field": "business_criticality", "value": "LOW"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_override_cross_tenant_returns_404_not_403(client_factory, db_session, tenant_b, admin_user):
    """T-32-02 mitigation — cross-tenant probe returns 404 (not 403), even
    for an admin, keeping cross-tenant existence private."""
    foreign_asset = _seed_asset(tenant_b, f"tenant-b-host-{uuid.uuid4().hex[:6]}")
    db_session.add(foreign_asset)
    await db_session.commit()

    admin_client = client_factory(admin_user)
    r = await admin_client.patch(
        f"/api/v1/assets/{foreign_asset.id}/exposure-context",
        json={"field": "business_criticality", "value": "LOW"},
    )
    assert r.status_code == 404
    # Assert the handler's own "Asset not found" 404 (not FastAPI's generic
    # unmatched-route 404, which would spuriously pass this test before the
    # endpoint exists — RED-phase fail-fast check).
    assert r.json()["detail"] == "Asset not found"


# ── Audit trail (EXPO-05) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_asset_override_writes_audit_row(client_factory, db_session, tenant_a, admin_user):
    """A manual override writes exactly one asset.exposure_override audit row."""
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    admin_client = client_factory(admin_user)
    r = await admin_client.patch(
        f"/api/v1/assets/{asset_id}/exposure-context",
        json={"field": "business_criticality", "value": "CRITICAL"},
    )
    assert r.status_code == 200, r.text

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "asset.exposure_override",
                    AuditLog.resource_id == str(asset_id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"expected exactly one audit row, got {len(rows)}"
    row = rows[0]
    assert row.details["field"] == "business_criticality"
    assert row.details["old"] == "MEDIUM"
    assert row.details["new"] == "CRITICAL"
    assert row.user_email == admin_user.email
    assert row.resource_type == "asset"


@pytest.mark.asyncio
async def test_auto_inference_audits_only_on_change(db_session, tenant_a):
    """Auto-inference audits with actor system:exposure-inference only
    when a value actually changes — re-running recompute on an unchanged
    asset writes zero additional rows (no re-affirmation flooding)."""
    from app.assets.exposure import recompute_exposure_context

    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}", department="Finance", job_title="CFO")
    db_session.add(a)
    await db_session.commit()
    asset_id = a.id

    await recompute_exposure_context(db_session, tenant_a)
    await db_session.commit()

    first_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.user_email == "system:exposure-inference",
                    AuditLog.resource_id == str(asset_id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(first_rows) == 1, f"expected exactly one auto-inference audit row, got {len(first_rows)}"

    # Second recompute against the now-stable asset must NOT write another row.
    await recompute_exposure_context(db_session, tenant_a)
    await db_session.commit()

    second_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.user_email == "system:exposure-inference",
                    AuditLog.resource_id == str(asset_id),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(second_rows) == 1, "recompute on an unchanged asset must not write a new audit row"


# ── EXPO-06 calibration check (Plan 02) ──────────────────────────────────


def _seed_calibration_fixture(tenant_id, *, critical_count: int, total: int) -> list[Asset]:
    """Build a realistic ~100-asset fixture with a skewed dept/tag
    distribution (per 32-RESEARCH §5 seed-fixture guidance): `critical_count`
    assets carry a genuine CRITICAL signal (Finance department + CFO
    job_title — the same real business_criticality tier mapping documented
    in exposure.py, not a hand-set value), the rest rotate through
    unremarkable departments (Engineering/IT/Marketing/Sales/none) that
    infer to MEDIUM or HIGH but never CRITICAL."""
    assets = []
    non_critical_departments = ["Engineering", "IT", "Marketing", "Sales", None]
    for i in range(total):
        if i < critical_count:
            a = _seed_asset(
                tenant_id,
                f"calib-critical-{i}-{uuid.uuid4().hex[:6]}",
                department="Finance",
                job_title="CFO",
            )
        else:
            dept = non_critical_departments[i % len(non_critical_departments)]
            a = _seed_asset(tenant_id, f"calib-normal-{i}-{uuid.uuid4().hex[:6]}", department=dept)
        assets.append(a)
    return assets


@pytest.mark.asyncio
async def test_calibration_check_against_realistic_fixture(db_session, tenant_a):
    """A realistic 100-asset fixture with a skewed dept/tag distribution
    proves pct/cap/over_cap/critical_auto/total against real
    infer_exposure_context output, and proves the cap is tenant-configurable
    (EXPO-06)."""
    from app.assets.exposure import apply_inference_to_asset, check_criticality_calibration

    assets = _seed_calibration_fixture(tenant_a, critical_count=20, total=100)
    db_session.add_all(assets)
    await db_session.commit()  # establish AUTO/MEDIUM defaults before re-inferring
    for a in assets:
        apply_inference_to_asset(a)
    await db_session.commit()

    report = await check_criticality_calibration(db_session, tenant_a)
    assert report["total"] == 100
    assert report["critical_auto"] == 20
    assert report["pct"] == pytest.approx(0.20)
    assert report["cap"] == pytest.approx(0.15)  # tenant default (migration 038)
    assert report["over_cap"] is True
    assert report["hard_cap_enabled"] is False

    # Tenant-configurable cap: raising it above the observed pct flips
    # over_cap back to False without touching any asset (flag+report only —
    # critical_auto/total are unchanged, no down-ranking happened).
    from app.tenants.models import Tenant

    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    tenant.exposure_criticality_cap = 0.25
    await db_session.commit()

    report2 = await check_criticality_calibration(db_session, tenant_a)
    assert report2["cap"] == pytest.approx(0.25)
    assert report2["over_cap"] is False
    assert report2["critical_auto"] == 20
    assert report2["total"] == 100


@pytest.mark.asyncio
async def test_calibration_exempts_manual_overrides(client_factory, db_session, tenant_a, admin_user):
    """An admin-set CRITICAL override (via the real PATCH endpoint) does NOT
    count toward critical_auto — only AUTO-sourced CRITICAL assets
    contribute to the calibration proportion (EXPO-06, CONTEXT.md's
    calibration decision: exempting overrides resolves the tension with
    EXPO-03's 'override permanently wins' guarantee)."""
    from app.assets.exposure import apply_inference_to_asset, check_criticality_calibration

    auto_critical = _seed_asset(
        tenant_a, f"auto-critical-{uuid.uuid4().hex[:6]}", department="Finance", job_title="CFO"
    )
    others = [_seed_asset(tenant_a, f"other-{i}-{uuid.uuid4().hex[:6]}") for i in range(4)]

    db_session.add(auto_critical)
    db_session.add_all(others)
    await db_session.commit()  # establish AUTO/MEDIUM defaults before re-inferring
    apply_inference_to_asset(auto_critical)
    await db_session.commit()
    assert auto_critical.business_criticality == "CRITICAL"
    assert auto_critical.business_criticality_source == "AUTO"

    override_target_id = others[0].id
    admin_client = client_factory(admin_user)
    r = await admin_client.patch(
        f"/api/v1/assets/{override_target_id}/exposure-context",
        json={"field": "business_criticality", "value": "CRITICAL"},
    )
    assert r.status_code == 200, r.text

    report = await check_criticality_calibration(db_session, tenant_a)
    assert report["total"] == 5
    # Only the one genuinely AUTO-sourced CRITICAL asset counts — the manual
    # override on `others[0]` is exempt, even though it's also CRITICAL now.
    assert report["critical_auto"] == 1


@pytest.mark.asyncio
async def test_calibration_endpoint_admin_only(
    client_factory, db_session, tenant_a, admin_user, analyst_user, viewer_user
):
    """GET /assets/exposure-context/calibration returns the report shape for
    admin; analyst/viewer get 403 (T-32-05)."""
    a = _seed_asset(tenant_a, f"host-{uuid.uuid4().hex[:6]}")
    db_session.add(a)
    await db_session.commit()

    admin_client = client_factory(admin_user)
    r = await admin_client.get("/api/v1/assets/exposure-context/calibration")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"pct", "cap", "over_cap", "critical_auto", "total", "hard_cap_enabled"}

    for user in (analyst_user, viewer_user):
        c = client_factory(user)
        r = await c.get("/api/v1/assets/exposure-context/calibration")
        assert r.status_code == 403, r.text
