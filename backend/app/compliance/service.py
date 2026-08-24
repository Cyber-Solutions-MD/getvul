"""Compliance business logic (Phase 43 Plan 01 -- RPT-03 tracer slice):
compute the ~5 underlying posture metrics exactly ONCE per tenant read,
then hand them to the pure `evaluate_catalog()` (D-08/D-09/D-13).

D-10 (vuln-only): this package NEVER imports `app.cspm.service` -- the
vuln-management compliance surface here stays deliberately separate from
CSPM's existing `get_compliance_dashboard`; a unified rollup is deferred.

Reuses four existing tenant-scoped read services directly, no HTTP
round-trip (D-01a's "call directly, never re-derive" precedent, extended
to RPT-03):
  - coverage/service.py::get_coverage_summary        (Phase 41)
  - vulnerabilities/sla_service.py::get_sla_metrics   (Phase 36, Pitfall 1/2 guarded)
  - analytics/service.py::get_aging_distribution      (Phase 42)
  - vulnerabilities/service.py::get_mttr_by_tier      (Phase 36)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import get_aging_distribution
from app.compliance.catalog import evaluate_catalog
from app.compliance.schemas import ComplianceOverviewResponse, ControlStatusResponse
from app.coverage.schemas import CoverageConnectorCardResponse
from app.coverage.service import get_coverage_summary
from app.tenants.models import Tenant
from app.vulnerabilities.service import get_mttr_by_tier
from app.vulnerabilities.sla_service import get_sla_metrics
from app.vulnerabilities.sla_tier_service import get_tier_policy


def _coverage_pct_from_cards(cards: list[CoverageConnectorCardResponse]) -> float | None:
    """D-11 zero-denominator convention carried forward: the BEST single
    enabled scanner's coverage of the authoritative inventory -- a
    conservative (never-overclaiming) proxy for "is the program actually
    scanning its assets." `get_coverage_summary` has no cross-connector
    UNION count to derive a true combined % from without an extra query
    (which would break "compute once"); taking the MAX never fabricates a
    higher number than any single connector has actually proven. `None`
    when no card has a real percentage -- zero enabled scanners, OR the
    authoritative-asset denominator itself is zero (each card already
    carries that same D-11 None-guard)."""
    pcts = [c.coverage_pct for c in cards if c.coverage_pct is not None]
    return float(max(pcts)) if pcts else None


def _critical_high_sla_health_pct(aging: dict[str, Any]) -> float | None:
    """The "is the CURRENT open backlog on-track" health % for the
    critical+high severities (the two severities the PCI 6.3.3/11.3.1.1
    control text names explicitly), from Phase 42's live aging-
    distribution buckets. Deliberately a DIFFERENT question than
    sla_compliance_pct's "were recently CLOSED items closed on time"
    (43-RESEARCH.md Pitfall 3) -- both are legitimate, distinct evidencing
    metrics for different controls in the catalog. Zero-denominator
    guarded: `None` when critical+high have zero open findings right now,
    never a fabricated 0% or 100%."""
    buckets = aging.get("buckets", {})
    within = 0
    total = 0
    for bucket_name, sev_counts in buckets.items():
        for sev in ("critical", "high"):
            count = sev_counts.get(sev, 0)
            total += count
            if bucket_name == "within_sla":
                within += count
    if total == 0:
        return None
    return round(100 * within / total, 1)


async def get_compliance_overview(db: AsyncSession, tenant_id: uuid.UUID) -> ComplianceOverviewResponse:
    """RPT-03: compute each of the ~5 posture metrics exactly ONCE, then
    evaluate the static catalog (compliance/catalog.py, zero additional
    queries) against them (43-RESEARCH.md Pattern 2 -- several controls
    across different frameworks legitimately reuse the same metric_key)."""
    now = datetime.now(UTC)
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    tier_policy = get_tier_policy(tenant)

    coverage = await get_coverage_summary(db, tenant_id)
    # Pitfall 2 fix: exclude_exceptions=True keeps this control internally
    # consistent with every other exception-aware surface in the app.
    sla = await get_sla_metrics(db, tenant_id, exclude_exceptions=True)
    aging = await get_aging_distribution(db, tenant_id, now=now)
    mttr = await get_mttr_by_tier(db, tenant_id)

    metrics: dict[str, Any] = {
        "coverage_pct": _coverage_pct_from_cards(coverage.cards),
        # Pitfall 1 fix: remediated_total==0 -> None, never the function's
        # own hardcoded 100.0 fake-pass fallback.
        "sla_compliance_pct": sla["compliance_pct"] if sla["remediated_total"] > 0 else None,
        "critical_sla_health_pct": _critical_high_sla_health_pct(aging),
        "has_active_scanning": coverage.has_scanner_connector,
        "mttr_by_tier": mttr,
        "tier_days": tier_policy["tier_days"],
    }

    rows = evaluate_catalog(metrics)
    return ComplianceOverviewResponse(controls=[ControlStatusResponse(**row) for row in rows])
