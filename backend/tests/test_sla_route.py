"""Phase 43 Plan 04 (RPT-02) — route-level exception-consistency regression
for `GET /api/v1/vulnerabilities/sla/metrics`'s additive `exclude_exceptions`
query param (T-43-15 / 43-RESEARCH.md Pitfall 2, applied to the new
leadership/compliance dashboard-lens surface).

Mirrors `test_sla_service.py::test_exclude_exceptions_applies_to_compliance_pct_source_queries`
at the HTTP layer — proves the wiring from `router.py`'s new `Query` param
into `get_sla_metrics(..., exclude_exceptions=...)` end-to-end, so
`use-sla-metrics.ts` (which requests `?exclude_exceptions=true`) returns the
SAME `compliance_pct` the compliance page (Plan 01) and the board PDF
(Plan 02) already compute via a direct `exclude_exceptions=True` call — no
tenant ever sees a divergent SLA-compliance % across the three surfaces.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY + JWT_SECRET_KEY set, per-file (not the whole tests/
dir).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.assets.models import Asset
from app.exceptions.models import ExceptionRecord
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.sla_service import get_sla_metrics


def _remediated_vuln(
    tenant_id,
    *,
    sla_due_at: datetime,
    remediated_at: datetime,
    asset_id: uuid.UUID | None = None,
) -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-{uuid.uuid4().hex[:8]}",
        severity="HIGH",
        source="CROWDSTRIKE",
        source_vuln_id=str(uuid.uuid4()),
        status="REMEDIATED",
        first_detected_at=now - timedelta(days=10),
        last_seen_at=now,
        sla_due_at=sla_due_at,
        remediated_at=remediated_at,
        asset_id=asset_id,
    )


async def test_sla_metrics_route_default_omits_exclude_exceptions_byte_identical(
    client, db_session, tenant_a
):
    """No `exclude_exceptions` query param — byte-identical to every
    pre-existing consumer of this route (additive param, default False)."""
    now = datetime.now(UTC)
    due = now - timedelta(days=1)
    late = _remediated_vuln(tenant_a, sla_due_at=due, remediated_at=due + timedelta(hours=1))
    db_session.add(late)
    await db_session.commit()

    resp = await client.get("/api/v1/vulnerabilities/sla/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["remediated_total"] == 1
    assert body["compliance_pct"] == 0.0  # late remediation, no exclusion by default


async def test_sla_metrics_route_exclude_exceptions_matches_exception_consistent_source(
    client, db_session, tenant_a
):
    """`?exclude_exceptions=true` drops an actively-excepted late
    remediation from the `compliance_pct` computation — the exact number
    the compliance page/board PDF compute directly via
    `get_sla_metrics(exclude_exceptions=True)` (never a divergent board
    number, Pitfall 2)."""
    now = datetime.now(UTC)
    due = now - timedelta(days=1)
    asset = Asset(tenant_id=tenant_a, hostname=f"host-{uuid.uuid4().hex[:8]}")
    db_session.add(asset)
    await db_session.flush()

    on_time = _remediated_vuln(tenant_a, sla_due_at=due, remediated_at=due - timedelta(days=1))
    late_but_excepted = _remediated_vuln(
        tenant_a, sla_due_at=due, remediated_at=due + timedelta(hours=1), asset_id=asset.id
    )
    db_session.add_all([on_time, late_but_excepted])
    await db_session.flush()

    grant = ExceptionRecord(
        tenant_id=tenant_a,
        type="ACCEPTED_RISK",
        scope_type="ASSET",
        cve_id=late_but_excepted.cve_id,
        vulnerability_id=None,
        asset_id=late_but_excepted.asset_id,
        asset_group_id=None,
        justification="Compensating control in place.",
        approver_user_id=None,
        granted_by_user_id=None,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(grant)
    await db_session.commit()

    included = (await client.get("/api/v1/vulnerabilities/sla/metrics")).json()
    assert included["remediated_total"] == 2
    assert included["compliance_pct"] == 50.0

    excluded_resp = await client.get(
        "/api/v1/vulnerabilities/sla/metrics", params={"exclude_exceptions": "true"}
    )
    assert excluded_resp.status_code == 200
    excluded = excluded_resp.json()
    assert excluded["remediated_total"] == 1
    assert excluded["compliance_pct"] == 100.0

    # Route-level result must equal the service-level exception-consistent
    # source directly (the compliance page's/board PDF's own call shape).
    direct = await get_sla_metrics(db_session, tenant_a, exclude_exceptions=True)
    assert direct["compliance_pct"] == excluded["compliance_pct"]
    assert direct["remediated_total"] == excluded["remediated_total"]
