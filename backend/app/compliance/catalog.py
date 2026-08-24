"""Built-in framework-control catalog (Phase 43 Plan 01, RPT-03 -- D-09) --
pure data + a pure evaluator, zero I/O.

Reproduction rule (43-RESEARCH.md Pitfall 7): SOC 2 (AICPA) / ISO 27001 /
PCI DSS control text is copyrighted -- this catalog cites control IDs plus
an independently-worded PARAPHRASE of intent only, never verbatim standard
text. NIST CSF 2.0 text is U.S. public domain (17 U.S.C. Sec 105) and is
quoted verbatim below. PCI DSS is pinned to v4.0.1 (v4.0 retired
2024-12-31; v4.0.1 keeps the same requirement numbers, clarifications
only).

D-08 (program-level control EVIDENCE, never per-CVE tagging): every
`metric_key` below resolves to a posture metric that
`compliance/service.py` computes ONCE from existing tenant-scoped read
services (coverage, SLA, aging, MTTR-by-tier) -- this module never issues
a query itself.

D-13 (status = thresholds on posture metrics): `evaluate_catalog()` is a
PURE function -- given the same metrics dict, it always returns the same
result, and it never touches the database. Several controls across
different frameworks legitimately reuse the SAME metric_key (e.g.
`coverage_pct` evidences one control in each of SOC 2 / ISO 27001 / PCI
DSS / NIST CSF) -- the metric is computed exactly once by the caller
(43-RESEARCH.md Pattern 2), never re-fetched per control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ControlStatus = Literal["pass", "partial", "fail", "not_measured"]

# The two metric_keys below don't fit the generic numeric `>=` threshold
# shape (43-PATTERNS.md's own note) -- evaluate_catalog special-cases them:
#   - "has_active_scanning": a plain boolean (has_scanner_connector),
#     pass/fail only, no partial state.
#   - "mttr_by_tier": tenant-CALIBRATED (compared against THIS tenant's own
#     sla_tier_service.get_tier_policy tier-day windows), never a hardcoded
#     absolute day count -- see _evaluate_mttr_tier_control below.
_BOOLEAN_METRIC_KEY = "has_active_scanning"
_TENANT_CALIBRATED_METRIC_KEY = "mttr_by_tier"


@dataclass(frozen=True)
class ControlDef:
    """One catalog row. `thresholds` is unused (left `{}`) for the two
    special-cased metric_keys above -- see `evaluate_catalog`'s dedicated
    branches."""

    framework: str  # "soc2" | "iso27001" | "pci_dss" | "nist_csf"
    control_id: str  # e.g. "CC7.1", "A.8.8", "6.3.3", "ID.RA-01"
    title: str  # short paraphrased title (verbatim only for nist_csf)
    metric_key: str  # one of the ~5 keys compliance/service.py computes
    thresholds: dict[str, float] = field(default_factory=dict)  # {"pass": 90, "partial": 50}


# D-12: all four frameworks ship day one. Control IDs + paraphrase
# cross-sourced against 2+ independent references per 43-RESEARCH.md
# ("D-09: The authoritative framework-control catalog").
CATALOG: list[ControlDef] = [
    ControlDef("soc2", "CC7.1", "Vulnerability detection & monitoring", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef(
        "iso27001",
        "A.8.8",
        "Management of technical vulnerabilities",
        "critical_sla_health_pct",
        {"pass": 90, "partial": 70},
    ),
    ControlDef("iso27001", "A.8.9", "Configuration management", "coverage_pct", {"pass": 90, "partial": 50}),
    ControlDef(
        "pci_dss",
        "6.3.1",
        "Vulnerabilities identified & risk-ranked (PCI DSS v4.0.1)",
        _BOOLEAN_METRIC_KEY,
        {},
    ),
    ControlDef(
        "pci_dss",
        "6.3.3",
        "Critical/high patches applied within a documented timeframe (PCI DSS v4.0.1)",
        "critical_sla_health_pct",
        {"pass": 95, "partial": 80},
    ),
    ControlDef(
        "pci_dss",
        "11.3.1",
        "Internal vulnerability scans at least quarterly (PCI DSS v4.0.1)",
        "coverage_pct",
        {"pass": 90, "partial": 50},
    ),
    ControlDef(
        "pci_dss",
        "11.3.1.1",
        "Critical/high vulnerabilities resolved per a risk-based timeframe (PCI DSS v4.0.1)",
        "critical_sla_health_pct",
        {"pass": 95, "partial": 80},
    ),
    ControlDef(
        "nist_csf",
        "ID.RA-01",
        "Vulnerabilities in assets are identified, validated, and recorded.",
        "coverage_pct",
        {"pass": 90, "partial": 50},
    ),
    ControlDef(
        "nist_csf",
        "ID.RA-06",
        "Risk responses are chosen, prioritized, planned, tracked, and communicated.",
        "sla_compliance_pct",
        {"pass": 90, "partial": 50},
    ),
    ControlDef(
        "nist_csf",
        "PR.PS-02",
        "Software is maintained, replaced, and removed commensurate with risk.",
        _TENANT_CALIBRATED_METRIC_KEY,
        {},
    ),
]


def _evaluate_mttr_tier_control(
    mttr_rows: list[dict[str, Any]] | None,
    tier_days: dict[str, int] | None,
) -> tuple[float | None, ControlStatus]:
    """PR.PS-02: % of risk tiers (critical/high/moderate) whose average
    remediation time (RemediationEvent.duration_seconds, grouped
    server-side by tier_at_remediation) falls within THIS TENANT'S OWN SLA
    tier-day policy (sla_tier_service.get_tier_policy) -- never a
    hardcoded absolute day count, so a tenant with a stricter or looser
    custom policy is judged against ITS policy, not a one-size-fits-all
    number.

    A tier with zero remediation history (`count <= 0` or
    `avg_seconds is None`) -- including the literal "not_tracked" bucket
    -- is EXCLUDED from the ratio, never counted as a failure (Pitfall 1's
    zero-denominator discipline, applied per-tier). `(None, "not_measured")`
    only when NO tier has any remediation history at all yet.
    """
    if not mttr_rows or not tier_days:
        return None, "not_measured"
    tracked = 0
    on_time = 0
    for row in mttr_rows:
        tier = row.get("tier_at_remediation")
        avg_seconds = row.get("avg_seconds")
        count = row.get("count") or 0
        if tier not in tier_days or avg_seconds is None or count <= 0:
            continue  # "not_tracked" tier, or a tier with zero remediations yet
        tracked += 1
        if (avg_seconds / 86400) <= tier_days[tier]:
            on_time += 1
    if tracked == 0:
        return None, "not_measured"
    pct = round(100 * on_time / tracked, 1)
    status: ControlStatus = "pass" if on_time == tracked else ("fail" if on_time == 0 else "partial")
    return pct, status


def evaluate_catalog(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Pure function, zero I/O: given the already-computed posture metrics
    (compute-once, per 43-RESEARCH.md Pattern 2), returns one status row
    per catalog control.

    `metrics[key] is None` means the caller's denominator was zero
    (Pitfall 1) -- MUST short-circuit to "not_measured" BEFORE any
    threshold compare, never a fabricated pass OR fail. `has_active_
    scanning` (bool) and `mttr_by_tier` (tenant-calibrated, needs the
    companion `tier_days` entry) are special-cased -- a generic `>=`
    threshold doesn't fit either shape.
    """
    results: list[dict[str, Any]] = []
    for c in CATALOG:
        value: float | None
        status: ControlStatus
        if c.metric_key == _BOOLEAN_METRIC_KEY:
            raw = metrics.get(_BOOLEAN_METRIC_KEY)
            if raw is None:
                value, status = None, "not_measured"
            else:
                value, status = (1.0, "pass") if raw else (0.0, "fail")
        elif c.metric_key == _TENANT_CALIBRATED_METRIC_KEY:
            value, status = _evaluate_mttr_tier_control(
                metrics.get(_TENANT_CALIBRATED_METRIC_KEY), metrics.get("tier_days")
            )
        else:
            raw_value = metrics.get(c.metric_key)
            value = float(raw_value) if raw_value is not None else None
            if value is None:
                status = "not_measured"
            elif value >= c.thresholds.get("pass", 999):
                status = "pass"
            elif value >= c.thresholds.get("partial", -1):
                status = "partial"
            else:
                status = "fail"
        results.append(
            {
                "framework": c.framework,
                "control_id": c.control_id,
                "title": c.title,
                "metric_key": c.metric_key,
                "value": value,
                "status": status,
            }
        )
    return results
