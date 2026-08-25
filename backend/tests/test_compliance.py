"""Phase 43 Plan 01 (RPT-03) -- compliance backend package: the built-in
framework-control catalog (pure evaluator) + the compute-once service +
GET /api/v1/compliance/overview (tenant-scoped, require_viewer-gated).

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret python -m pytest tests/test_compliance.py -x -q
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.assets.models import Asset
from app.auth.schemas import CurrentUser
from app.compliance.catalog import CATALOG, evaluate_catalog
from app.compliance.service import get_compliance_overview
from app.ticketing.models import ConnectorConfig
from app.vulnerabilities.models import RemediationEvent, Vulnerability


def _viewer_user_for(tenant_id: uuid.UUID) -> CurrentUser:
    """An ad hoc VIEWER `CurrentUser` scoped to `tenant_id` -- no DB row
    needed since `client_factory`'s dependency override bypasses
    `get_current_user` entirely (mirrors test_coverage.py)."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
        role="VIEWER",
    )


def _base_metrics(**overrides: object) -> dict[str, object]:
    """A fully not_measured metrics dict (every key None/empty) with
    selected keys overridden -- lets each catalog.py unit test vary
    exactly one metric without repeating the whole shape."""
    base: dict[str, object] = {
        "coverage_pct": None,
        "sla_compliance_pct": None,
        "critical_sla_health_pct": None,
        "has_active_scanning": None,
        "mttr_by_tier": None,
        "tier_days": None,
    }
    base.update(overrides)
    return base


# ── catalog.py: pure evaluator, zero I/O ──────────────────────────────────────


def test_catalog_covers_all_four_frameworks():
    frameworks = {c.framework for c in CATALOG}
    assert frameworks == {"soc2", "iso27001", "pci_dss", "nist_csf"}, frameworks


def test_evaluate_catalog_none_metric_is_never_pass_or_fail():
    """Pitfall 1: every metric None -> every control not_measured, value
    None -- never a fabricated pass or fail on absent data."""
    rows = evaluate_catalog(_base_metrics())
    assert len(rows) == len(CATALOG)
    assert all(r["status"] == "not_measured" for r in rows), rows
    assert all(r["value"] is None for r in rows), rows


def test_evaluate_catalog_boundary_thresholds():
    """soc2 CC7.1 (coverage_pct, pass=90/partial=50): value AT the pass
    threshold -> pass; just below pass but >= partial -> partial; below
    partial -> fail."""

    def cc71_status(coverage_pct: float) -> str:
        rows = evaluate_catalog(_base_metrics(coverage_pct=coverage_pct))
        row = next(r for r in rows if r["control_id"] == "CC7.1")
        return str(row["status"])

    assert cc71_status(90) == "pass"
    assert cc71_status(89) == "partial"
    assert cc71_status(50) == "partial"
    assert cc71_status(49) == "fail"


def test_evaluate_catalog_boolean_control_special_cased():
    """pci_dss 6.3.1 (has_active_scanning) is a boolean control -- pass
    when True, fail when False, not_measured only when the signal itself
    is absent (never forced through a numeric >= compare)."""
    rows_true = evaluate_catalog(_base_metrics(has_active_scanning=True))
    row_true = next(r for r in rows_true if r["control_id"] == "6.3.1")
    assert row_true["status"] == "pass"
    assert row_true["value"] == 1.0

    rows_false = evaluate_catalog(_base_metrics(has_active_scanning=False))
    row_false = next(r for r in rows_false if r["control_id"] == "6.3.1")
    assert row_false["status"] == "fail"
    assert row_false["value"] == 0.0

    rows_none = evaluate_catalog(_base_metrics(has_active_scanning=None))
    row_none = next(r for r in rows_none if r["control_id"] == "6.3.1")
    assert row_none["status"] == "not_measured"
    assert row_none["value"] is None


def test_evaluate_catalog_mttr_tier_control_is_tenant_calibrated():
    """nist_csf PR.PS-02 (mttr_by_tier) is tenant-calibrated -- compared
    against THIS tenant's own tier_days policy, never a hardcoded absolute
    day count; a tier with zero remediation history is excluded from the
    ratio, not counted as a failure."""
    tier_days = {"critical": 7, "high": 30, "moderate": 90}
    mttr_rows = [
        {"tier_at_remediation": "critical", "avg_seconds": 5 * 86400, "count": 3},  # 5d <= 7d -> on time
        {"tier_at_remediation": "high", "avg_seconds": 40 * 86400, "count": 2},  # 40d > 30d -> late
        {"tier_at_remediation": "not_tracked", "avg_seconds": 1000, "count": 1},  # excluded, not a tier
    ]
    rows = evaluate_catalog(_base_metrics(mttr_by_tier=mttr_rows, tier_days=tier_days))
    row = next(r for r in rows if r["control_id"] == "PR.PS-02")
    assert row["status"] == "partial"
    assert row["value"] == 50.0

    # No remediation history at all yet -> not_measured, never a fabricated
    # pass or fail.
    rows_empty = evaluate_catalog(_base_metrics(mttr_by_tier=[], tier_days=tier_days))
    row_empty = next(r for r in rows_empty if r["control_id"] == "PR.PS-02")
    assert row_empty["status"] == "not_measured"
    assert row_empty["value"] is None

    # A tenant whose policy is lenient enough that every tracked tier is
    # on time -> pass.
    rows_all_on_time = evaluate_catalog(
        _base_metrics(
            mttr_by_tier=[{"tier_at_remediation": "critical", "avg_seconds": 5 * 86400, "count": 1}],
            tier_days=tier_days,
        )
    )
    row_pass = next(r for r in rows_all_on_time if r["control_id"] == "PR.PS-02")
    assert row_pass["status"] == "pass"
    assert row_pass["value"] == 100.0


# ── service.py: compute-once orchestration ────────────────────────────────────


@pytest.mark.asyncio
async def test_compliance_overview_computes_each_metric_exactly_once(monkeypatch, db_session, tenant_a):
    """43-RESEARCH.md Pattern 2: several catalog controls share the same
    metric_key (coverage_pct alone evidences one control in each of
    SOC2/ISO/PCI/NIST), so this proves the catalog LOOP itself issues zero
    additional calls -- each underlying service is invoked exactly once
    per compliance/service.py.get_compliance_overview() call."""
    import app.compliance.service as compliance_service

    call_counts = {"coverage": 0, "sla": 0, "aging": 0, "mttr": 0}
    orig_coverage = compliance_service.get_coverage_summary
    orig_sla = compliance_service.get_sla_metrics
    orig_aging = compliance_service.get_aging_distribution
    orig_mttr = compliance_service.get_mttr_by_tier

    async def counting_coverage(*args, **kwargs):
        call_counts["coverage"] += 1
        return await orig_coverage(*args, **kwargs)

    async def counting_sla(*args, **kwargs):
        call_counts["sla"] += 1
        return await orig_sla(*args, **kwargs)

    async def counting_aging(*args, **kwargs):
        call_counts["aging"] += 1
        return await orig_aging(*args, **kwargs)

    async def counting_mttr(*args, **kwargs):
        call_counts["mttr"] += 1
        return await orig_mttr(*args, **kwargs)

    monkeypatch.setattr(compliance_service, "get_coverage_summary", counting_coverage)
    monkeypatch.setattr(compliance_service, "get_sla_metrics", counting_sla)
    monkeypatch.setattr(compliance_service, "get_aging_distribution", counting_aging)
    monkeypatch.setattr(compliance_service, "get_mttr_by_tier", counting_mttr)

    result = await get_compliance_overview(db_session, tenant_a)

    assert call_counts == {"coverage": 1, "sla": 1, "aging": 1, "mttr": 1}, call_counts
    assert len(result.controls) == len(CATALOG)


@pytest.mark.asyncio
async def test_compliance_overview_fresh_tenant_all_not_measured(db_session, tenant_a):
    """A brand-new tenant with zero data anywhere -> every PERCENTAGE-
    based control renders not_measured, never a fabricated pass (Pitfall 1
    applied end-to-end: sla_compliance_pct's remediated_total==0 must not
    surface as the function's own compliance_pct==100.0 fallback).

    The one exception is the boolean `has_active_scanning` control
    (6.3.1): "zero connectors configured" IS a real, measured answer (not
    an absent-denominator case) -- so it honestly renders "fail", not
    "not_measured". Never a fabricated pass either way."""
    result = await get_compliance_overview(db_session, tenant_a)
    assert len(result.controls) == len(CATALOG)
    by_control = {c.control_id: c for c in result.controls}

    assert by_control["6.3.1"].status == "fail"  # has_active_scanning -> real "no" answer
    assert by_control["6.3.1"].value == 0.0

    other_controls = [c for c in result.controls if c.control_id != "6.3.1"]
    assert all(c.status == "not_measured" for c in other_controls), other_controls
    assert all(c.value is None for c in other_controls)


@pytest.mark.asyncio
async def test_compliance_overview_reflects_real_posture_when_data_exists(db_session, tenant_a):
    """Seeding real coverage + remediation history moves the corresponding
    controls off not_measured -- proves the metrics genuinely flow through
    the catalog, not just the all-empty default path."""
    # seen_by_sources needs BOTH an authoritative (JAMF) AND a scanner
    # (QUALYS) source -- coverage_pct's denominator is the authoritative
    # (MDM/HR) inventory count (app/coverage/service.py::_authoritative_
    # clause), which a scanner-only asset would leave at zero.
    asset = Asset(tenant_id=tenant_a, hostname="host-1", seen_by_sources=["JAMF", "QUALYS"])
    connector = ConnectorConfig(tenant_id=tenant_a, connector_type="QUALYS", is_enabled=True)
    db_session.add_all([asset, connector])
    await db_session.flush()

    now = datetime.now(UTC)
    due = now - timedelta(days=1)
    remediated = Vulnerability(
        tenant_id=tenant_a,
        cve_id="CVE-2026-0001",
        severity="CRITICAL",
        source="QUALYS",
        source_vuln_id=str(uuid.uuid4()),
        status="REMEDIATED",
        first_detected_at=now - timedelta(days=10),
        last_seen_at=now,
        sla_due_at=due,
        remediated_at=due - timedelta(days=1),
        asset_id=asset.id,
    )
    db_session.add(remediated)
    await db_session.flush()
    db_session.add(
        RemediationEvent(
            tenant_id=tenant_a,
            vulnerability_id=remediated.id,
            tier_at_remediation="critical",
            duration_seconds=5 * 86400,
            first_detected_at=now - timedelta(days=10),
            remediated_at=due - timedelta(days=1),
        )
    )
    await db_session.commit()

    result = await get_compliance_overview(db_session, tenant_a)
    by_control = {c.control_id: c for c in result.controls}

    assert by_control["CC7.1"].status != "not_measured"  # coverage_pct now measured
    assert by_control["6.3.1"].status == "pass"  # has_active_scanning -> True
    assert by_control["ID.RA-06"].status != "not_measured"  # sla_compliance_pct now measured
    assert by_control["PR.PS-02"].status != "not_measured"  # mttr_by_tier now measured


# ── router.py: tenant-scoped, require_viewer-gated ────────────────────────────


@pytest.mark.asyncio
async def test_compliance_overview_endpoint_200_for_viewer(client_factory, tenant_a, viewer_user):
    """require_viewer is satisfied by the weakest role tier -- a plain
    VIEWER gets 200, all four frameworks present."""
    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/compliance/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "controls" in body
    assert len(body["controls"]) == len(CATALOG)
    frameworks = {c["framework"] for c in body["controls"]}
    assert frameworks == {"soc2", "iso27001", "pci_dss", "nist_csf"}


@pytest.mark.asyncio
async def test_compliance_overview_cross_tenant_isolation(client_factory, db_session, tenant_a, tenant_b, viewer_user):
    """Seed tenant_a with real posture data (an enabled scanner connector,
    which flips the 6.3.1 has_active_scanning control to "pass"); tenant_b's
    own read must still show 6.3.1 as "fail" (its own real, honest "no
    scanner" answer) -- proves the has_scanner_connector signal stays
    tenant-scoped, never fetch-then-filter (T-43-01)."""
    asset = Asset(tenant_id=tenant_a, hostname="host-a", seen_by_sources=["QUALYS"])
    connector = ConnectorConfig(tenant_id=tenant_a, connector_type="QUALYS", is_enabled=True)
    db_session.add_all([asset, connector])
    await db_session.commit()

    viewer_client = client_factory(viewer_user)
    r_a = await viewer_client.get("/api/v1/compliance/overview")
    assert r_a.status_code == 200, r_a.text
    body_a = r_a.json()
    by_control_a = {c["control_id"]: c for c in body_a["controls"]}
    assert by_control_a["6.3.1"]["status"] == "pass"  # tenant_a really is measured

    tenant_b_client = client_factory(_viewer_user_for(tenant_b))
    r_b = await tenant_b_client.get("/api/v1/compliance/overview")
    assert r_b.status_code == 200, r_b.text
    body_b = r_b.json()
    by_control_b = {c["control_id"]: c for c in body_b["controls"]}
    # tenant_b never sees tenant_a's connector -- its OWN honest "no
    # scanner" fail, not tenant_a's leaked "pass".
    assert by_control_b["6.3.1"]["status"] == "fail"
    other_controls_b = [c for c in body_b["controls"] if c["control_id"] != "6.3.1"]
    assert all(c["status"] == "not_measured" for c in other_controls_b), other_controls_b


@pytest.mark.asyncio
async def test_compliance_overview_registered_under_compliance_prefix(client_factory, tenant_a, viewer_user):
    """The endpoint is registered at /api/v1/compliance/overview (not
    e.g. left at the package's bare router path)."""
    viewer_client = client_factory(viewer_user)
    r = await viewer_client.get("/api/v1/compliance/overview")
    assert r.status_code == 200, r.text
