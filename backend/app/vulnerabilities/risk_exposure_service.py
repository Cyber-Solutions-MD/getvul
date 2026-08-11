"""Per-finding risk-exposure score (Phase 33 — RISK-01/02/03/06 LEAD TRACER).

This is a NEW, ADDITIVE per-finding scoring model. It does not replace or
modify `app/assets/risk_score.py` (the existing per-ASSET aggregate, which
sums weighted contributions across all of an asset's open vulnerabilities and
squashes the unbounded sum through a piecewise power/log curve into 0-100).
That curve exists specifically to tame the *volume* of vulns on one asset --
a single finding has no volume dimension, so this module uses a fixed
100-point additive weighted-sum instead. Do NOT reuse `_normalize_raw_score`.

100-point budget (tracer scope -- severity/CVSS and EPSS are REAL; native
exploitability, exposure context, and cross-scanner corroboration are zeroed
PLACEHOLDER components in this plan, replaced with real logic by Plan 33-02):

    severity / CVSS                    35 pts  (REAL)
    EPSS (exploit probability)         20 pts  (REAL)
    native exploitability              15 pts  (placeholder, Plan 33-02)
    exposure -- business criticality   10 pts  (placeholder, Plan 33-02)
    exposure -- internet facing         6 pts  (placeholder, Plan 33-02)
    exposure -- data sensitivity        4 pts  (placeholder, Plan 33-02)
    cross-scanner corroboration        10 pts  (placeholder, Plan 33-02)
    ---------------------------------------------
    subtotal                          100 pts

    KEV floor (applied last, a FLOOR via max(), never an additive bonus --
    a finding already scoring above the floor must not be pushed past 100):
        final_score = max(round(subtotal), KEV_FLOOR_SCORE) if cisa_kev
                       else round(subtotal)

A missing/unavailable input contributes exactly 0 points out of its own
fixed budget -- it is NEVER renormalized against the signals that ARE
present. Renormalizing (e.g. "average only the signals we have") would
produce a misleadingly high score for a finding with a tiny sample of
available signals; the additive weighted-points design avoids that trap.

Pitfall 1 (important, easy to miss): the unique constraint on
`Vulnerability` is `(tenant_id, cve_id, asset_id, source)` -- the SAME
logical CVE-on-asset issue seen by N scanners produces N separate rows, and
this function scores PER ROW, not per logical issue. All N rows receive the
same score inputs (once Plan 33-02 wires in the real corroboration count,
keyed on `(cve_id, asset_id)`, all N rows will get the identical
corroboration bonus too). This is intentional -- de-duplicating the finding
LIST view is an explicit later-phase decision, not something this module
attempts.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# RISK-06: module-level version stamped on every scored row. Bump this
# string whenever the weight table or formula changes -- Phase 34's cutover
# and any future recompute can filter WHERE risk_model_version = 'v1' to
# distinguish "scored under the target version" from "stale or never
# scored" (NULL).
RISK_MODEL_VERSION = "v1"

# RISK-03: an internal design choice expressing CISA BOD 22-01's KEV
# "must-remediate" spirit -- no external prescriptive numeric floor exists.
KEV_FLOOR_SCORE = 90

WEIGHT_SEVERITY_CVSS = 35
WEIGHT_EPSS = 20
WEIGHT_NATIVE = 15
WEIGHT_EXPOSURE_CRITICALITY = 10
WEIGHT_EXPOSURE_INTERNET_FACING = 6
WEIGHT_EXPOSURE_DATA_SENSITIVITY = 4
WEIGHT_CORROBORATION = 10

# Proportioned from risk_score.py's SEVERITY_WEIGHTS ratios, used only when
# no cvss_v3_score is available for this finding.
SEVERITY_FALLBACK = {"CRITICAL": 35, "HIGH": 20, "MEDIUM": 8, "LOW": 2, "INFO": 0}


@dataclass(frozen=True)
class FindingScoreInputs:
    """FULL input spine -- every field defined here in the tracer so Plan
    33-02 fills in real logic for the still-zeroed components, not shape."""

    severity: str
    cvss_v3_score: Decimal | None
    epss_score: Decimal | None
    cisa_kev: bool
    source: str
    native_priority_score: Decimal | None
    native_priority_rating: str | None
    sources_count: int  # default 1 when no VulnerabilityCorrelation row exists
    business_criticality: str
    data_sensitivity: str
    internet_facing: bool


@dataclass(frozen=True)
class RiskBreakdownComponent:
    key: str
    label: str
    raw_value: str
    points: float
    max_points: float


@dataclass(frozen=True)
class RiskBreakdown:
    final_score: int
    subtotal: float
    kev_floor_applied: bool
    risk_model_version: str
    components: list[RiskBreakdownComponent]


def score_finding(inputs: FindingScoreInputs) -> RiskBreakdown:
    """Pure, no DB, fully deterministic: identical inputs always yield an
    identical final_score + identical breakdown (RISK-01).

    TRACER SCOPE: severity/CVSS and EPSS components are REAL; the KEV floor
    is REAL. native_exploitability / exposure_* / corroboration components
    each emit a row with points=0.0 and a raw_value flagged "# PLAN 33-02"
    -- Plan 33-02 replaces those zeros with real logic.
    """
    components: list[RiskBreakdownComponent] = []

    # -- Severity / CVSS (REAL) --
    if inputs.cvss_v3_score is not None:
        severity_points = (float(inputs.cvss_v3_score) / 10.0) * WEIGHT_SEVERITY_CVSS
        severity_raw = str(inputs.cvss_v3_score)
    else:
        severity_points = float(SEVERITY_FALLBACK.get(inputs.severity, 0))
        severity_raw = f"{inputs.severity} (no CVSS)"
    components.append(
        RiskBreakdownComponent(
            key="severity_cvss",
            label="Severity / CVSS",
            raw_value=severity_raw,
            points=round(severity_points, 2),
            max_points=float(WEIGHT_SEVERITY_CVSS),
        )
    )

    # -- EPSS (REAL) --
    if inputs.epss_score is not None:
        epss_points = float(inputs.epss_score) * WEIGHT_EPSS
        epss_raw = str(inputs.epss_score)
    else:
        epss_points = 0.0
        epss_raw = "not provided"
    components.append(
        RiskBreakdownComponent(
            key="epss",
            label="EPSS (exploit probability)",
            raw_value=epss_raw,
            points=round(epss_points, 2),
            max_points=float(WEIGHT_EPSS),
        )
    )

    # -- Native exploitability (PLACEHOLDER -- Plan 33-02) --
    components.append(
        RiskBreakdownComponent(
            key="native_exploitability",
            label="Native exploitability",
            raw_value=f"not scored by {inputs.source} -- # PLAN 33-02",
            points=0.0,
            max_points=float(WEIGHT_NATIVE),
        )
    )

    # -- Exposure context (PLACEHOLDER -- Plan 33-02), 3 sub-components --
    components.append(
        RiskBreakdownComponent(
            key="exposure_business_criticality",
            label="Exposure -- business criticality",
            raw_value=f"{inputs.business_criticality} -- # PLAN 33-02",
            points=0.0,
            max_points=float(WEIGHT_EXPOSURE_CRITICALITY),
        )
    )
    components.append(
        RiskBreakdownComponent(
            key="exposure_internet_facing",
            label="Exposure -- internet facing",
            raw_value=f"{inputs.internet_facing} -- # PLAN 33-02",
            points=0.0,
            max_points=float(WEIGHT_EXPOSURE_INTERNET_FACING),
        )
    )
    components.append(
        RiskBreakdownComponent(
            key="exposure_data_sensitivity",
            label="Exposure -- data sensitivity",
            raw_value=f"{inputs.data_sensitivity} -- # PLAN 33-02",
            points=0.0,
            max_points=float(WEIGHT_EXPOSURE_DATA_SENSITIVITY),
        )
    )

    # -- Cross-scanner corroboration (PLACEHOLDER -- Plan 33-02) --
    components.append(
        RiskBreakdownComponent(
            key="corroboration",
            label="Cross-scanner corroboration",
            raw_value=f"{inputs.sources_count} scanner(s) -- # PLAN 33-02",
            points=0.0,
            max_points=float(WEIGHT_CORROBORATION),
        )
    )

    subtotal = sum(c.points for c in components)
    rounded_subtotal = round(subtotal)

    if inputs.cisa_kev:
        final_score = max(rounded_subtotal, KEV_FLOOR_SCORE)
        kev_floor_applied = rounded_subtotal < KEV_FLOOR_SCORE
    else:
        final_score = rounded_subtotal
        kev_floor_applied = False

    return RiskBreakdown(
        final_score=final_score,
        subtotal=subtotal,
        kev_floor_applied=kev_floor_applied,
        risk_model_version=RISK_MODEL_VERSION,
        components=components,
    )


async def compute_finding_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Full-tenant recompute (mirrors compute_risk_scores's shape,
    risk_score.py:84-147). Bulk-fetches every OPEN/IN_PROGRESS Vulnerability
    row for the tenant, outer-joined to its Asset for exposure fields, calls
    score_finding per row, and persists risk_exposure_score +
    risk_exposure_breakdown + risk_model_version.

    TRACER: sources_count defaults to 1 for every row (Plan 33-02 adds the
    VulnerabilityCorrelation bulk-join, keyed on (cve_id, asset_id), single
    query -- never a per-row lookup). Does NOT roll up Asset.risk_exposure_score
    (Plan 33-03 owns the MAX rollup) -- left NULL by this tracer.

    Every query filters tenant_id (V4 access control) -- a bulk-fetch across
    tenants would leak cross-tenant Vulnerability/Asset rows.
    """
    query = (
        select(Vulnerability, Asset)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    rows = (await db.execute(query)).all()

    updated = 0
    for vuln, asset in rows:
        inputs = FindingScoreInputs(
            severity=vuln.severity,
            cvss_v3_score=vuln.cvss_v3_score,
            epss_score=vuln.epss_score,
            cisa_kev=vuln.cisa_kev,
            source=vuln.source,
            native_priority_score=vuln.native_priority_score,
            native_priority_rating=vuln.native_priority_rating,
            sources_count=1,  # TRACER placeholder -- Plan 33-02 bulk-joins VulnerabilityCorrelation.
            business_criticality=asset.business_criticality if asset is not None else "MEDIUM",
            data_sensitivity=asset.data_sensitivity if asset is not None else "INTERNAL",
            internet_facing=asset.internet_facing if asset is not None else False,
        )
        breakdown = score_finding(inputs)
        serialized_breakdown = [asdict(component) for component in breakdown.components]

        await db.execute(
            update(Vulnerability)
            .where(Vulnerability.id == vuln.id)
            .values(
                risk_exposure_score=breakdown.final_score,
                risk_exposure_breakdown=serialized_breakdown,
                risk_model_version=RISK_MODEL_VERSION,
            )
        )
        updated += 1

    logger.info(
        "finding_risk_scores_computed",
        tenant_id=str(tenant_id),
        findings_updated=updated,
    )

    return {"findings_updated": updated}
