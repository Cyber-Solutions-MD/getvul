"""Per-finding risk-exposure score (Phase 33 — RISK-01..06, FULL FORMULA).

This is a NEW, ADDITIVE per-finding scoring model. It does not replace or
modify `app/assets/risk_score.py` (the existing per-ASSET aggregate, which
sums weighted contributions across all of an asset's open vulnerabilities and
squashes the unbounded sum through a piecewise power/log curve into 0-100).
That curve exists specifically to tame the *volume* of vulns on one asset --
a single finding has no volume dimension, so this module uses a fixed
100-point additive weighted-sum instead. Do NOT reuse `_normalize_raw_score`.

100-point budget (Plan 33-02: FULL formula, every component real):

    severity / CVSS                    35 pts
    EPSS (exploit probability)         20 pts
    native exploitability              15 pts  (per-source 0-1 normalized)
    exposure -- business criticality   10 pts
    exposure -- internet facing         6 pts
    exposure -- data sensitivity        4 pts
    cross-scanner corroboration        10 pts
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

Asset rollup (Plan 33-03, RISK-02, CONTEXT RESOLVED Q2): after persisting
every per-finding score, `compute_finding_risk_scores` rolls each asset's
`Asset.risk_exposure_score` up to the MAX of its OPEN/IN_PROGRESS findings'
`risk_exposure_score` -- MAX ONLY, no volume-sensitive curve (a curve that
factors in HOW MANY urgent findings an asset has is explicitly deferred to
Phase 34). An asset with zero open findings is reset to NULL, never left at
a stale prior value. `Asset.risk_model_version` is stamped on every asset
touched by the rollup (both the MAX-set and the NULL-reset paths).

Native-exploitability normalization (CONTEXT lock, highest-risk task):
`native_priority_score` arrives on incompatible vendor scales (Nessus VPR
0-10, Qualys QDS 0-100, Rapid7 Risk Score 0-1000). CrowdStrike's numeric
`native_priority_score` (`exprt_score`) is UNVERIFIED (Phase 31's own
flagged risk) -- use its categorical `native_priority_rating` instead.
Defender/Wiz never populate either field. `_normalize_native_signal` NEVER
raises: any missing/unparseable/out-of-range input soft-nulls to 0.0
(neutral, never penalized), mirroring the connectors' own
`try/except (TypeError, ValueError)` idiom.

Corroboration (RISK-04): `sources_count` comes from Phase 30's
`VulnerabilityCorrelation.sources_count`, bulk-fetched once per tenant (see
`compute_finding_risk_scores`) -- never a per-row lookup. A finding with no
correlation row is single-source (count=1), not "unknown."
`min((sources_count - 1) / 3, 1.0) * WEIGHT_CORROBORATION` -- a capped
linear fraction: 1 source contributes 0, 4+ sources contribute the full 10.

Pitfall 1 (important, easy to miss): the unique constraint on
`Vulnerability` is `(tenant_id, cve_id, asset_id, source)` -- the SAME
logical CVE-on-asset issue seen by N scanners produces N separate rows, and
this function scores PER ROW, not per logical issue. All N rows receive the
same score inputs, including the identical corroboration bonus (keyed on
`(cve_id, asset_id)`, not per-source). This is intentional -- de-duplicating
the finding LIST view is an explicit later-phase decision, not something
this module attempts.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from decimal import Decimal

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation

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

# Phase 32 exposure fractions (x WEIGHT_EXPOSURE_CRITICALITY / _DATA_SENSITIVITY).
_CRITICALITY_FRACTION = {"CRITICAL": 1.0, "HIGH": 0.67, "MEDIUM": 0.33, "LOW": 0.0}
_SENSITIVITY_FRACTION = {"RESTRICTED": 1.0, "CONFIDENTIAL": 0.67, "INTERNAL": 0.33, "PUBLIC": 0.0}

# CrowdStrike ExPRT categorical rating -> 0-1 (confirmed field; its numeric
# companion `exprt_score` is unverified per 31-RESEARCH.md and is never used).
_CROWDSTRIKE_RATING_FRACTION = {"UNKNOWN": 0.0, "LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "CRITICAL": 1.0}


def _normalize_native_signal(source: str, score: Decimal | None, rating: str | None) -> float:
    """Maps a vendor's native priority signal to a common 0.0-1.0 scale.

    NEVER raises -- any missing signal, unparseable value, or unexpected
    source soft-nulls to 0.0 (CONTEXT native-normalization lock). Per-source
    divisor is that vendor's own documented scale ceiling; the result is
    defensively clamped to [0.0, 1.0] so an out-of-range/garbage vendor value
    never produces a negative or >1.0 contribution.
    """
    try:
        if source == "NESSUS" and score is not None:
            return min(max(float(score) / 10.0, 0.0), 1.0)
        if source == "QUALYS" and score is not None:
            return min(max(float(score) / 100.0, 0.0), 1.0)
        if source == "RAPID7" and score is not None:
            return min(max(float(score) / 1000.0, 0.0), 1.0)
        if source == "CROWDSTRIKE" and rating is not None:
            return _CROWDSTRIKE_RATING_FRACTION.get(rating.upper(), 0.0)
    except (TypeError, ValueError):
        return 0.0
    return 0.0  # DEFENDER, WIZ, missing signal, or unrecognized source


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

    FULL FORMULA (Plan 33-02): all 6 categories are real -- severity/CVSS,
    EPSS, per-source-normalized native exploitability, the 3-way exposure
    split (business criticality / internet facing / data sensitivity), and
    cross-scanner corroboration -- plus the KEV floor via max().
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

    # -- Native exploitability --
    native_fraction = _normalize_native_signal(
        inputs.source, inputs.native_priority_score, inputs.native_priority_rating
    )
    native_points = native_fraction * WEIGHT_NATIVE
    if native_fraction > 0.0:
        native_raw = f"{native_fraction:.2f} (normalized from {inputs.source})"
    else:
        native_raw = f"not provided by {inputs.source}"
    components.append(
        RiskBreakdownComponent(
            key="native_exploitability",
            label="Native exploitability",
            raw_value=native_raw,
            points=round(native_points, 2),
            max_points=float(WEIGHT_NATIVE),
        )
    )

    # -- Exposure context, 3 sub-components (Phase 32 signals) --
    criticality_fraction = _CRITICALITY_FRACTION.get(inputs.business_criticality, 0.0)
    components.append(
        RiskBreakdownComponent(
            key="exposure_business_criticality",
            label="Exposure -- business criticality",
            raw_value=str(inputs.business_criticality),
            points=round(criticality_fraction * WEIGHT_EXPOSURE_CRITICALITY, 2),
            max_points=float(WEIGHT_EXPOSURE_CRITICALITY),
        )
    )
    components.append(
        RiskBreakdownComponent(
            key="exposure_internet_facing",
            label="Exposure -- internet facing",
            raw_value=str(inputs.internet_facing),
            points=round((WEIGHT_EXPOSURE_INTERNET_FACING if inputs.internet_facing else 0.0), 2),
            max_points=float(WEIGHT_EXPOSURE_INTERNET_FACING),
        )
    )
    sensitivity_fraction = _SENSITIVITY_FRACTION.get(inputs.data_sensitivity, 0.0)
    components.append(
        RiskBreakdownComponent(
            key="exposure_data_sensitivity",
            label="Exposure -- data sensitivity",
            raw_value=str(inputs.data_sensitivity),
            points=round(sensitivity_fraction * WEIGHT_EXPOSURE_DATA_SENSITIVITY, 2),
            max_points=float(WEIGHT_EXPOSURE_DATA_SENSITIVITY),
        )
    )

    # -- Cross-scanner corroboration -- capped linear fraction: 1 source
    # contributes 0, 4+ sources contribute the full budget (RISK-04).
    corroboration_fraction = min(max(inputs.sources_count - 1, 0) / 3.0, 1.0)
    components.append(
        RiskBreakdownComponent(
            key="corroboration",
            label="Cross-scanner corroboration",
            raw_value=f"{inputs.sources_count} scanner(s)",
            points=round(corroboration_fraction * WEIGHT_CORROBORATION, 2),
            max_points=float(WEIGHT_CORROBORATION),
        )
    )

    subtotal = sum(c.points for c in components)
    rounded_subtotal = round(subtotal)

    if inputs.cisa_kev:
        final_score = max(rounded_subtotal, KEV_FLOOR_SCORE)
        kev_floor_applied = rounded_subtotal < KEV_FLOOR_SCORE
        if kev_floor_applied:
            components.append(
                RiskBreakdownComponent(
                    key="kev_floor",
                    label="CISA KEV floor",
                    raw_value=f"raised {rounded_subtotal} -> {KEV_FLOOR_SCORE}",
                    points=float(KEV_FLOOR_SCORE - rounded_subtotal),
                    max_points=0.0,
                )
            )
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


async def compute_finding_risk_scores(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
    """Full-tenant recompute (mirrors compute_risk_scores's shape,
    risk_score.py:84-147). Bulk-fetches every OPEN/IN_PROGRESS Vulnerability
    row for the tenant, outer-joined to its Asset for exposure fields, calls
    score_finding per row, and persists risk_exposure_score +
    risk_exposure_breakdown + risk_model_version.

    Corroboration (RISK-04): a single tenant-scoped bulk-select of every
    VulnerabilityCorrelation row into a dict keyed by (cve_id, asset_id) --
    never a per-row lookup (correlation_service.py's get_correlation_for_vuln
    is the wrong shape here, it would be N+1 across thousands of findings).
    A finding with no correlation row scores as sources_count=1 (default,
    not "unknown").

    Also rolls Asset.risk_exposure_score up to the MAX of each asset's
    OPEN/IN_PROGRESS findings (Plan 33-03, RISK-02) -- MAX only, no volume
    curve (deferred to Phase 34). A single bulk subquery + outerjoin so
    assets with zero open findings reset to NULL (T-33-07: tenant-scoped,
    no cross-tenant leak).

    Every query filters tenant_id (V4 access control) -- a bulk-fetch across
    tenants would leak cross-tenant Vulnerability/Asset/Correlation rows.
    """
    corr_rows = (
        await db.execute(
            select(
                VulnerabilityCorrelation.cve_id,
                VulnerabilityCorrelation.asset_id,
                VulnerabilityCorrelation.sources_count,
            ).where(VulnerabilityCorrelation.tenant_id == tenant_id)
        )
    ).all()
    corr_by_key = {(row.cve_id, row.asset_id): row.sources_count for row in corr_rows}

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
        sources_count = corr_by_key.get((vuln.cve_id, vuln.asset_id), 1)
        inputs = FindingScoreInputs(
            severity=vuln.severity,
            cvss_v3_score=vuln.cvss_v3_score,
            epss_score=vuln.epss_score,
            cisa_kev=vuln.cisa_kev,
            source=vuln.source,
            native_priority_score=vuln.native_priority_score,
            native_priority_rating=vuln.native_priority_rating,
            sources_count=sources_count,
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

    # RISK-02 asset rollup (Plan 33-03) -- MAX only, no volume curve (CONTEXT
    # RESOLVED Q2; a curve is explicitly deferred to Phase 34). Single bulk
    # subquery grouped by asset_id, outerjoin'd to every tenant Asset so an
    # asset with zero OPEN/IN_PROGRESS findings resets to NULL rather than
    # keeping a stale value from a prior compute cycle.
    rollup_sub = (
        select(Vulnerability.asset_id, func.max(Vulnerability.risk_exposure_score).label("max_score"))
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.asset_id.isnot(None),
        )
        .group_by(Vulnerability.asset_id)
        .subquery()
    )
    rollup_query = (
        select(Asset.id, rollup_sub.c.max_score)
        .outerjoin(rollup_sub, Asset.id == rollup_sub.c.asset_id)
        .where(Asset.tenant_id == tenant_id)
    )
    rollup_rows = (await db.execute(rollup_query)).all()

    assets_rolled_up = 0
    for asset_id, max_score in rollup_rows:
        await db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(risk_exposure_score=max_score, risk_model_version=RISK_MODEL_VERSION)
        )
        assets_rolled_up += 1

    logger.info(
        "finding_risk_scores_computed",
        tenant_id=str(tenant_id),
        findings_updated=updated,
        assets_rolled_up=assets_rolled_up,
    )

    return {"findings_updated": updated, "assets_rolled_up": assets_rolled_up}
