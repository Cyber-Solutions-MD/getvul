"""Phase 39 Plan 04 (EXC-02 consumer sweep) -- threads the shared
`active_exception_subquery` seam (39-01) into the core "active work"
consumers named by RESEARCH's Consumer Sweep: the risk-score subquery
(Consumer 6), the remediation grouped view's shared helper + its one
hand-rolled bypass (Consumers 7/11), the campaign denominator + bulk
ticket creation (Consumers 8/9), and the governance-critical automated
ticket-creation rule engine (Consumer 10, Tier 2 #8).

Task 1 (this file, created here): risk score, remediation grouped view
(incl. the "ignored"/"all" branches staying untouched), the
`remediations_for_host` hand-rolled bypass, campaign progress, and
bulk-assign exclusion.

Task 2 (appended below): the rule-engine exclusion -- proves a scheduler
tick never auto-opens a ticket for an asset whose only qualifying finding
is under an active accept-risk exception.

Every test seeds a CONTROL finding alongside the excepted one (same asset
or same remediation_id/group) so a passing assertion proves CVE-pinned
exclusion (D-10), not a blanket per-asset/per-remediation wipe.

Uses the project's canonical inline-seed + `client_factory` harness
(`test_campaigns.py` / `test_exceptions_scope.py`) verbatim.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions_consumers.py -x
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability

_FAKE_URL_BASE = "https://acme.atlassian.net/browse"


def _seed_asset(tenant_id: uuid.UUID, *, humaans_email: str | None = None) -> Asset:
    """A minimal asset -- `mdm_details.humaans_email` is the same field
    `ticketing/service.py:614` / `campaigns/service.py` read for owner
    derivation (mirrors `test_campaigns.py::_seed_asset`)."""
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04",
        mdm_details={"humaans_email": humaans_email} if humaans_email else None,
    )


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    asset_id: uuid.UUID | None = None,
    status: str = "OPEN",
    severity: str = "HIGH",
    remediation_id: str | None = None,
    affected_product: str | None = None,
    cve_id: str | None = None,
    source: str = "MOCK",
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=cve_id or f"CVE-CONS-{uuid.uuid4().hex[:6]}",
        severity=severity,
        status=status,
        source=source,
        source_vuln_id=str(uuid.uuid4()),
        remediation_id=remediation_id,
        affected_product=affected_product,
        first_detected_at=now - timedelta(days=3),
        last_seen_at=now,
    )


def _grant_body(
    *,
    scope_type: str,
    approver_id: uuid.UUID,
    exc_type: str = "ACCEPTED_RISK",
    days: int = 30,
    vulnerability_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    asset_group_id: uuid.UUID | None = None,
    cve_id: str | None = None,
) -> dict:
    """Mirrors `test_exceptions_scope.py::_grant_body` -- a FINDING-scope
    grant is all this file needs (every consumer here reads
    `active_exception_subquery`'s already-proven FINDING branch; scope
    resolution itself is 39-02's concern, not re-tested here)."""
    body: dict = {
        "type": exc_type,
        "scope_type": scope_type,
        "justification": "Compensating control in place while vendor patch is scheduled",
        "approver_user_id": str(approver_id),
        "expires_at": (datetime.now(UTC) + timedelta(days=days)).isoformat(),
    }
    if vulnerability_id is not None:
        body["vulnerability_id"] = str(vulnerability_id)
    if asset_id is not None:
        body["asset_id"] = str(asset_id)
    if asset_group_id is not None:
        body["asset_group_id"] = str(asset_group_id)
    if cve_id is not None:
        body["cve_id"] = cve_id
    return body


class FakeTicketingClient:
    """Records every `.create()` call; returns a distinct provider-shaped
    fake URL per call (mirrors `test_campaigns.py::FakeTicketingClient`) --
    scoped locally here per that file's own "campaigns is a new caller, not
    a new provider" precedent."""

    def __init__(self) -> None:
        self.created: list[tuple[str, str, dict]] = []
        self._seq = 0

    async def create(self, title: str, body: str, **kwargs: Any) -> str | None:
        self._seq += 1
        self.created.append((title, body, kwargs))
        return f"{_FAKE_URL_BASE}/ref-{self._seq}"


# ── Task 1: compute_risk_scores' raw-score subquery (Consumer 6) ────────────


@pytest.mark.asyncio
async def test_excluded_from_risk_scores(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An actively-excepted CRITICAL finding is excluded from
    compute_risk_scores' raw-score subquery (EXC-02, D-15) -- a co-located
    un-excepted LOW finding on the SAME asset proves the exclusion is
    CVE-pinned (D-10), not a blanket per-asset suppression."""
    from app.assets.risk_score import SEVERITY_WEIGHTS, _normalize_raw_score, compute_risk_scores

    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    critical_vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="CRITICAL")
    low_vuln = _seed_vuln(tenant_a, asset_id=asset.id, severity="LOW")
    db_session.add_all([critical_vuln, low_vuln])
    await db_session.commit()

    await compute_risk_scores(db_session, tenant_a)
    await db_session.commit()
    baseline = (await db_session.execute(select(Asset.risk_score).where(Asset.id == asset.id))).scalar_one()
    low_only_score = _normalize_raw_score(float(SEVERITY_WEIGHTS["LOW"]))
    assert baseline > low_only_score, f"baseline must reflect both vulns, got {baseline}"

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=critical_vuln.id),
    )
    assert r.status_code == 200, r.text

    await compute_risk_scores(db_session, tenant_a)
    await db_session.commit()
    after = (await db_session.execute(select(Asset.risk_score).where(Asset.id == asset.id))).scalar_one()
    assert after == low_only_score, f"expected score to reflect ONLY the un-excepted LOW vuln, got {after}"


# ── Task 1: _base_open_vulns' "active" branch (Consumer 7) ──────────────────


@pytest.mark.asyncio
async def test_excluded_from_remediations_grouped(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An actively-excepted finding's remediation group is excluded from
    get_remediations_grouped's default 'active' view; a sibling
    remediation_id's un-excepted finding still appears (D-15)."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped

    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    rem_excepted = f"remediation-{uuid.uuid4().hex[:8]}"
    rem_control = f"remediation-{uuid.uuid4().hex[:8]}"
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=rem_excepted)
    control_vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=rem_control)
    db_session.add_all([vuln, control_vuln])
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id),
    )
    assert r.status_code == 200, r.text

    result = await get_remediations_grouped(db_session, tenant_a)
    rem_ids = {item["remediation_id"] for item in result["items"]}
    assert rem_excepted not in rem_ids, rem_ids
    assert rem_control in rem_ids, rem_ids


@pytest.mark.asyncio
async def test_ignored_all_branches_still_show(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """The show_suppressed='all' branch of get_remediations_grouped is NOT
    filtered by active_exception_subquery -- an actively-excepted (but
    still-OPEN, since exceptions never flip Vulnerability.status per D-01)
    finding remains visible there, proving the predicate was added to the
    'active' branch ONLY (T-39-18: no over-exclusion)."""
    from app.vulnerabilities.remediation_service import get_remediations_grouped

    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=remediation_id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=vuln.id),
    )
    assert r.status_code == 200, r.text

    active_result = await get_remediations_grouped(db_session, tenant_a, show_suppressed="active")
    assert remediation_id not in {i["remediation_id"] for i in active_result["items"]}, "must be excluded (active)"

    all_result = await get_remediations_grouped(db_session, tenant_a, show_suppressed="all")
    assert remediation_id in {i["remediation_id"] for i in all_result["items"]}, "'all' branch must stay untouched"


# ── Task 1: remediations_for_host hand-rolled bypass (Consumer 11 / Pitfall 5) ──


@pytest.mark.asyncio
async def test_excluded_from_remediations_for_host_bypass(
    client_factory, db_session, tenant_a, analyst_user, admin_user
):
    """GET /hosts/{asset_id}/remediations is a hand-rolled ad hoc query
    that bypasses `_base_open_vulns`/`_apply_filters` entirely -- it gets
    its OWN active_exception_subquery predicate so an excepted finding
    never resurfaces there either (Pitfall 5). Grouped by
    (remediation_action, affected_product), so distinct affected_product
    values distinguish the two rows."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    excepted_vuln = _seed_vuln(tenant_a, asset_id=asset.id, affected_product="OpenSSL")
    control_vuln = _seed_vuln(tenant_a, asset_id=asset.id, affected_product="curl")
    db_session.add_all([excepted_vuln, control_vuln])
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=excepted_vuln.id),
    )
    assert r.status_code == 200, r.text

    r = await analyst_client.get(f"/api/v1/vulnerabilities/hosts/{asset.id}/remediations")
    assert r.status_code == 200, r.text
    products = {item["product"] for item in r.json()}
    assert "OpenSSL" not in products, products
    assert "curl" in products, products


# ── Task 1: campaign progress + bulk ticket creation (Consumers 8, 9) ───────


@pytest.mark.asyncio
async def test_excluded_from_campaign_progress(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An actively-excepted campaign member is excluded from
    get_campaign_progress's member count (D-15) -- a sibling un-excepted
    OPEN member on the same remediation_id proves CVE-pinned exclusion,
    not a blanket wipe of the whole campaign."""
    from app.campaigns.service import get_campaign_progress

    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    excepted_vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=remediation_id)
    control_vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=remediation_id)
    db_session.add_all([excepted_vuln, control_vuln])
    await db_session.commit()

    baseline = await get_campaign_progress(db_session, tenant_a, remediation_id)
    assert baseline["total"] == 2, baseline

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=excepted_vuln.id),
    )
    assert r.status_code == 200, r.text

    after = await get_campaign_progress(db_session, tenant_a, remediation_id)
    assert after["total"] == 1, after


@pytest.mark.asyncio
async def test_excepted_member_not_ticketed(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An actively-excepted campaign member is excluded from
    bulk_create_campaign_tickets' live-members query -- it is never
    ticketed (D-15)."""
    from app.campaigns.models import Campaign
    from app.campaigns.service import bulk_create_campaign_tickets

    await db_session.commit()
    owner = "alice@acme.test"
    asset = _seed_asset(tenant_a, humaans_email=owner)
    db_session.add(asset)
    await db_session.flush()
    remediation_id = f"remediation-{uuid.uuid4().hex[:8]}"
    excepted_vuln = _seed_vuln(tenant_a, asset_id=asset.id, remediation_id=remediation_id)
    db_session.add(excepted_vuln)
    campaign = Campaign(tenant_id=tenant_a, remediation_id=remediation_id)
    db_session.add(campaign)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=excepted_vuln.id),
    )
    assert r.status_code == 200, r.text

    fake = FakeTicketingClient()
    result = await bulk_create_campaign_tickets(
        db=db_session,
        tenant_id=tenant_a,
        user_id=None,
        campaign=campaign,
        provider="JIRA",
        project_key="PROJ",
        client=fake,
    )
    await db_session.commit()

    assert result["owners"] == 0, result
    assert result["created_tickets"] == 0, result
    assert result["tickets_linked"] == 0, result
    assert len(fake.created) == 0, "the excepted member must never reach client.create()"


# ── Task 2: governance-critical automated ticket rule engine (Consumer 10) ──


@pytest.mark.asyncio
async def test_excluded_from_rule_engine(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """An accept-risk exception on an asset's ONLY qualifying finding means
    find_matching_assets no longer matches it -- the automated
    ticket-creation rule engine must NOT auto-open a ticket for a governed
    accept-risk finding on the next scheduler tick (Tier 2 #8,
    governance-critical, D-15). A sibling asset whose finding stays
    un-excepted still matches, proving CVE-pinned exclusion, not a
    blanket rule-engine bypass."""
    from app.ticketing.rule_engine import find_matching_assets

    await db_session.commit()
    excepted_asset = _seed_asset(tenant_a)
    control_asset = _seed_asset(tenant_a)
    db_session.add_all([excepted_asset, control_asset])
    await db_session.flush()
    excepted_vuln = _seed_vuln(tenant_a, asset_id=excepted_asset.id, severity="CRITICAL")
    control_vuln = _seed_vuln(tenant_a, asset_id=control_asset.id, severity="CRITICAL")
    db_session.add_all([excepted_vuln, control_vuln])
    await db_session.commit()

    conditions = {"severity": ["CRITICAL"]}
    baseline = await find_matching_assets(db_session, tenant_a, conditions)
    baseline_ids = {a.id for a in baseline}
    assert excepted_asset.id in baseline_ids, "must match before any exception exists"
    assert control_asset.id in baseline_ids, "must match before any exception exists"

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post(
        "/api/v1/exceptions",
        json=_grant_body(scope_type="FINDING", approver_id=admin_user.id, vulnerability_id=excepted_vuln.id),
    )
    assert r.status_code == 200, r.text

    matched = await find_matching_assets(db_session, tenant_a, conditions)
    matched_ids = {a.id for a in matched}
    assert excepted_asset.id not in matched_ids, "excepted finding must not make the asset match"
    assert control_asset.id in matched_ids, "un-excepted sibling asset must still match"
