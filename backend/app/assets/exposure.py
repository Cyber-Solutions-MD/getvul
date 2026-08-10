"""Asset exposure-context inference — Phase 32 Plan 01 (LEAD TRACER).

New module (NOT an extension of `classification.py`/`classifier.py`, which
classify only `device_category`, or the dead `service.py`/`schemas.py`).
Mirrors `classification.py`'s pure ordered-priority inference-function shape
for `infer_exposure_context`, and `risk_score.py::compute_risk_scores`'s
full-tenant recompute-and-persist shape for `recompute_exposure_context`.

Phase 32 Plan 02 fills in the two fields Plan 01 left as documented
defaults — `data_sensitivity` (real tag/department signals) and
`internet_facing` (the v1 external_ip/tag proxy) — and adds
`check_criticality_calibration` (EXPO-06).

Phase 32 Plan 03 adds the real `AssetGroup` entity's GROUP_OVERRIDE
precedence tier: `apply_precedence_to_asset` resolves, per field, per-asset
ASSET_OVERRIDE (permanent) > group override (most-recently-updated group
wins on a multi-group conflict) > auto-inference. `recompute_exposure_context`
now calls it instead of the group-unaware `apply_inference_to_asset`.

business_criticality tier mapping (ordered priority, first match wins;
Claude's Discretion per PLAN.md — documented here for auditability):
  CRITICAL — job_title contains an executive keyword (ceo/cto/ciso/cfo/coo/
             chief) OR department is one of {finance, legal, security,
             executive} OR tags contain "pci" or "tier-1"
  HIGH     — job_title contains a senior-leadership keyword (vp, vice
             president, director, head of) OR department is one of
             {hr, human resources, it, engineering}
  LOW      — department is one of {dev, development, qa, test, sandbox}
             (a deliberately weak, non-production signal)
  MEDIUM   — default (no strong signal either way)

data_sensitivity tier mapping (ordered priority, first match wins;
Claude's Discretion per PLAN.md — documented here for auditability, and the
exact set of tags/departments EXPO-06's calibration reasons about):
  RESTRICTED   — tags contain "pii", "phi", or "restricted" (regulated
                 personal/health data — the strongest signal)
  CONFIDENTIAL — tags contain "pci" or "confidential" OR department is one
                 of {finance, legal} (financial/legal material, not
                 necessarily regulated personal data)
  PUBLIC       — tags contain "public" or "www" OR department is
                 "marketing" (deliberately weak, public-facing signal)
  INTERNAL     — default (no strong signal either way)

internet_facing (Plan 04, EXPO-02 — real per-connector detection where the
vendor payload genuinely supports it; the v1 external_ip/tag proxy
elsewhere):
  `internet_facing_detected` if not None, else the v1 proxy:
    True  — "internet-facing" is present in `tags` (case-insensitive) OR
            `external_ip` is not None
    False — otherwise
  A connector-supplied `internet_facing_detected` (Asset column, raw
  provenance, mirrors `external_ip`) always wins over the proxy when a
  connector actually set it; an ASSET_OVERRIDE/GROUP_OVERRIDE still
  permanently wins over BOTH (EXPO-03/04, unchanged).

Per-connector internet-facing coverage (honest — inspected this session
against each connector's actual raw payload/GraphQL response shape in this
codebase, not guessed; re-confirms 32-PATTERNS.md's "No Analog Found"
finding for every connector, no exceptions):

  | Connector   | Real signal?                      | Notes |
  |-------------|------------------------------------|-------|
  | CrowdStrike | FALLBACK (no distinct signal)      | Falcon Host device dict (`/devices/entities/devices/v2`) exposes `external_ip` (already the v1 proxy's own signal, wired since before this plan) but no separate public-exposure/security-group/DMZ field. Re-deriving `internet_facing_detected` from the same `external_ip` value would be circular (identical information, not a second signal) — not wired. |
  | Wiz         | FALLBACK                           | `vulnerabilityFindings.nodes.vulnerableAsset` (both `VULNERABILITY_QUERY` and the EPSS-enriched `VULNERABILITY_QUERY_ENRICHED`, wiz.py) exposes `cloudPlatform`/`region`/`ipAddresses`/`operatingSystem` — no `publicExposure`/`isInternetFacing`/security-group field is queried. Wiz's real product does model network exposure (Attack Path graph), but no such field is present in this connector's live GraphQL query today, and none is added without confirming it against a real schema (T-32-12 — no guessed field names). |
  | Qualys      | FALLBACK                           | `/api/2.0/fo/asset/host/` host records feed only `ip`/`dns`/`os` into `_normalize_detection` (qualys.py) — no `TRACKING_METHOD`/network-zone/public-IP flag is extracted. |
  | Nessus      | FALLBACK                           | Scan host detail (`_get_scan`, nessus.py) surfaces `hostname`/`ip`/`os` plus plugin output — no exposure/network-zone field is extracted. |
  | Rapid7      | FALLBACK                           | InsightVM `/api/3/assets` resource dict (rapid7.py) surfaces `hostName`/`ip`/`os` — no `exposures`/tag-based internet-facing field is extracted (InsightVM does support asset tags/sites, but none is currently queried by this connector). |
  | Defender    | FALLBACK                           | `/api/machines` + `/api/vulnerabilities/machinesVulnerabilities` (defender.py) surface `computerDnsName`/`ipAddresses`/health/exploit fields — Defender's `exposureScore` is a per-tenant risk metric, not a per-machine public-exposure boolean, and is not queried by this connector. |

  Every connector's `NormalizedVulnerability.internet_facing` therefore stays
  the dataclass default of `None` today — `Asset.internet_facing_detected`
  is never set from a live sync, and `infer_exposure_context` always falls
  through to the v1 external_ip/tag proxy in production. The full
  detected-signal spine (dataclass field, `Asset` column, sync passthrough,
  inference precedence — all landed this plan) is deliberately wired ahead
  of any real per-connector mapping so that the day a vendor schema is
  confirmed to expose a genuine signal, only that one connector's normalize
  step needs a one-line change — no schema/precedence work remains.

Auto-inference seeds from — never overwrites — existing `Asset.tags` and
existing MDM (Jamf)/HR (Humaans) enrichment (`Asset.department`,
`Asset.mdm_details["humaans_job_title"]`) plus `Asset.external_ip`. Per
CONTEXT.md's "[RESOLVED post-plan-check]" note, IdP-directory signals
(Entra/Okta/Google `User.department`/groups) are DEFERRED for v1 — wiring
them in would require a DB join inside what is otherwise a pure function,
for low marginal value. Documented future work, not a silent drop.

EXPO-06 calibration (`check_criticality_calibration`): measures the
proportion of a tenant's assets that are auto-classified (source == "AUTO")
at the highest business_criticality tier (CRITICAL). Admin/group overrides
are deliberately EXEMPT from the numerator — the criterion targets auto
inflation, not deliberate admin decisions, which resolves the tension with
EXPO-03's "override permanently wins" guarantee (32-CONTEXT.md). Default
behavior is flag+report ONLY: `over_cap` is informational, never mutates any
asset. A per-tenant `exposure_hard_cap_enabled` flag exists (migration 038)
but is OFF by default and has no enforcement path wired in this plan —
silently down-ranking a genuinely critical asset is worse than flagging.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset, AssetGroupExposureOverride, AssetGroupMember
from app.audit import AuditLog

logger = structlog.get_logger()

# EXPO-06 default cap (tenant-configurable via Tenant.exposure_criticality_cap,
# migration 038). Used only as a fallback if the tenant row is somehow
# missing — the model/migration default is the source of truth in practice.
_DEFAULT_CRITICALITY_CAP = 0.15

_RESTRICTED_TAGS = {"pii", "phi", "restricted"}
_CONFIDENTIAL_TAGS = {"pci", "confidential"}
_CONFIDENTIAL_DEPARTMENTS = {"finance", "legal"}
_PUBLIC_TAGS = {"public", "www"}
_PUBLIC_DEPARTMENTS = {"marketing"}

# The three exposure-context fields this module infers/writes. Order matches
# the interfaces contract (business_criticality, data_sensitivity,
# internet_facing) and the migration's column order.
EXPOSURE_FIELDS = ("business_criticality", "data_sensitivity", "internet_facing")

_CRITICAL_JOB_TITLE_KEYWORDS = ("ceo", "cto", "ciso", "cfo", "coo", "chief")
_HIGH_JOB_TITLE_KEYWORDS = ("vp", "vice president", "director", "head of")
_CRITICAL_DEPARTMENTS = {"finance", "legal", "security", "executive"}
_HIGH_DEPARTMENTS = {"hr", "human resources", "it", "engineering"}
_LOW_DEPARTMENTS = {"dev", "development", "qa", "test", "sandbox"}
_CRITICAL_TAGS = {"pci", "tier-1"}


def infer_exposure_context(
    *,
    tags: list[str] | None,
    department: str | None,
    job_title: str | None,
    external_ip: str | None,
    internet_facing_detected: bool | None = None,
) -> tuple[str, str, bool]:
    """Pure, no DB. Returns (business_criticality, data_sensitivity, internet_facing).

    Never mutates the caller's `tags` list — reads it into a local, lower-cased
    set only.

    `internet_facing_detected` (Plan 04, EXPO-02) is the REAL per-connector
    signal captured on `Asset.internet_facing_detected` — when it is not
    None, it wins over the external_ip/tag proxy below. When it is None (no
    connector currently supplies a signal for this asset), the v1 proxy
    formula applies unchanged.
    """
    job_title_lower = (job_title or "").lower()
    department_lower = (department or "").strip().lower()
    tag_set = {t.lower() for t in (tags or [])}

    business_criticality = "MEDIUM"
    if (
        any(keyword in job_title_lower for keyword in _CRITICAL_JOB_TITLE_KEYWORDS)
        or department_lower in _CRITICAL_DEPARTMENTS
        or (tag_set & _CRITICAL_TAGS)
    ):
        business_criticality = "CRITICAL"
    elif (
        any(keyword in job_title_lower for keyword in _HIGH_JOB_TITLE_KEYWORDS) or department_lower in _HIGH_DEPARTMENTS
    ):
        business_criticality = "HIGH"
    elif department_lower in _LOW_DEPARTMENTS:
        business_criticality = "LOW"

    data_sensitivity = "INTERNAL"
    if tag_set & _RESTRICTED_TAGS:
        data_sensitivity = "RESTRICTED"
    elif (tag_set & _CONFIDENTIAL_TAGS) or department_lower in _CONFIDENTIAL_DEPARTMENTS:
        data_sensitivity = "CONFIDENTIAL"
    elif (tag_set & _PUBLIC_TAGS) or department_lower in _PUBLIC_DEPARTMENTS:
        data_sensitivity = "PUBLIC"

    # Plan 04 (EXPO-02): a real per-connector detected signal wins over the
    # v1 proxy ("internet-facing" tag OR external_ip IS NOT NULL) whenever a
    # connector actually supplied one (internet_facing_detected is not None).
    if internet_facing_detected is not None:
        internet_facing = internet_facing_detected
    else:
        internet_facing = ("internet-facing" in tag_set) or (external_ip is not None)

    return business_criticality, data_sensitivity, internet_facing


def apply_inference_to_asset(asset: Asset) -> list[dict]:
    """Writes each inferred field onto `asset` ONLY when its `*_source` is
    still "AUTO" AND the inferred value actually differs from the current
    one. Returns a list of {field, old, new} change records (empty if
    nothing changed) for the caller to audit.

    This AUTO-gate is what makes an ASSET_OVERRIDE permanent across every
    future re-run (EXPO-03) — a field whose source has been flipped to
    ASSET_OVERRIDE (or, from Plan 03, GROUP_OVERRIDE) is never touched here.
    """
    job_title = (asset.mdm_details or {}).get("humaans_job_title")
    inferred_criticality, inferred_sensitivity, inferred_internet_facing = infer_exposure_context(
        tags=asset.tags,
        department=asset.department,
        job_title=job_title,
        external_ip=asset.external_ip,
        internet_facing_detected=asset.internet_facing_detected,
    )
    inferred_values: dict[str, object] = {
        "business_criticality": inferred_criticality,
        "data_sensitivity": inferred_sensitivity,
        "internet_facing": inferred_internet_facing,
    }

    changes: list[dict] = []
    for field in EXPOSURE_FIELDS:
        if getattr(asset, f"{field}_source", "AUTO") != "AUTO":
            continue
        old_value = getattr(asset, field)
        new_value = inferred_values[field]
        if old_value != new_value:
            setattr(asset, field, new_value)
            changes.append({"field": field, "old": old_value, "new": new_value})
    return changes


def audit_auto_inference_changes(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
    changes: list[dict],
) -> None:
    """Direct `AuditLog` construction for the system actor.

    `app.audit.audit()` derives its actor from a `CurrentUser` and cannot
    express a literal `system:*` actor — mirrors the precedent at
    `app/encryption.py:256-276` (`user_email="system:cli"`) and
    `app/ai/batch.py` (`user_email="system:scheduler"`). Logged only when
    `changes` is non-empty — never a re-affirmation — per EXPO-05 (avoids
    flooding `audit_logs` on every scanner sync / bulk recompute). No
    `db.commit()` here — callers commit once at their own transaction
    boundary, same as `audit()`'s audit-then-commit convention.
    """
    if not changes:
        return
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=None,
            user_email="system:exposure-inference",
            action="asset.exposure_recompute",
            resource_type="asset",
            resource_id=str(asset_id),
            details={"changes": changes},
            created_at=datetime.now(UTC),
        )
    )


async def _resolve_group_overrides_for_asset(db: AsyncSession, asset_id: uuid.UUID) -> dict[str, tuple[str, uuid.UUID]]:
    """For each exposure field, the most-recently-updated group override
    (value, group_id) among the asset's group memberships — absent from the
    returned dict if no group the asset belongs to has an override for that
    field. Multi-group conflicts on the same field resolve to the
    most-recently-updated override (32-CONTEXT.md's deterministic tiebreak,
    unit-tested in test_asset_exposure.py::test_conflicting_group_overrides_tiebreak).
    """
    q = (
        select(
            AssetGroupExposureOverride.field,
            AssetGroupExposureOverride.value,
            AssetGroupExposureOverride.group_id,
            AssetGroupExposureOverride.updated_at,
        )
        .join(AssetGroupMember, AssetGroupMember.group_id == AssetGroupExposureOverride.group_id)
        .where(AssetGroupMember.asset_id == asset_id)
    )
    rows = (await db.execute(q)).all()

    best: dict[str, tuple[str, uuid.UUID, datetime]] = {}
    for field, value, group_id, updated_at in rows:
        current = best.get(field)
        if current is None or updated_at > current[2]:
            best[field] = (value, group_id, updated_at)

    return {field: (value, group_id) for field, (value, group_id, _updated_at) in best.items()}


async def apply_precedence_to_asset(db: AsyncSession, asset: Asset) -> list[dict]:
    """Full per-asset precedence resolution (Phase 32 Plan 03 — EXPO-04):
    per-asset ASSET_OVERRIDE (permanent) > group override (most-recently-
    updated group wins on a multi-group conflict) > auto-inference. Returns
    change records (`{field, old, new}`) for actual value changes only, for
    the caller to audit — never a source-only churn with no value change.

    DB-aware wrapper around `infer_exposure_context`'s pure auto tier — used
    by `recompute_exposure_context` (full-tenant), the group-scope override
    PATCH endpoint (re-applies to every member), and
    `groups_service.add_member`/`remove_member` (re-applies to the single
    affected asset immediately, per 32-CONTEXT.md's execution note, so a
    newly-added member picks up an existing group override — or a removed
    member reverts to the auto tier — without waiting for a full recompute).
    """
    group_overrides = await _resolve_group_overrides_for_asset(db, asset.id)

    changes: list[dict] = []
    fields_for_auto: list[str] = []

    for field in EXPOSURE_FIELDS:
        current_source = getattr(asset, f"{field}_source", "AUTO")
        if current_source == "ASSET_OVERRIDE":
            continue  # permanent per-asset override always wins (EXPO-03)

        if field in group_overrides:
            raw_value, _group_id = group_overrides[field]
            new_value: str | bool = raw_value.strip().lower() == "true" if field == "internet_facing" else raw_value
            old_value = getattr(asset, field)
            if old_value != new_value:
                setattr(asset, field, new_value)
                changes.append({"field": field, "old": old_value, "new": new_value})
            if current_source != "GROUP_OVERRIDE":
                setattr(asset, f"{field}_source", "GROUP_OVERRIDE")
        else:
            fields_for_auto.append(field)

    if fields_for_auto:
        job_title = (asset.mdm_details or {}).get("humaans_job_title")
        inferred_criticality, inferred_sensitivity, inferred_internet_facing = infer_exposure_context(
            tags=asset.tags,
            department=asset.department,
            job_title=job_title,
            external_ip=asset.external_ip,
            internet_facing_detected=asset.internet_facing_detected,
        )
        inferred_values: dict[str, object] = {
            "business_criticality": inferred_criticality,
            "data_sensitivity": inferred_sensitivity,
            "internet_facing": inferred_internet_facing,
        }
        for field in fields_for_auto:
            current_source = getattr(asset, f"{field}_source", "AUTO")
            old_value = getattr(asset, field)
            new_value = inferred_values[field]
            if old_value != new_value:
                setattr(asset, field, new_value)
                changes.append({"field": field, "old": old_value, "new": new_value})
            if current_source != "AUTO":
                # A field that was GROUP_OVERRIDE-sourced but no longer has an
                # applicable group override (group deleted / membership
                # removed) reverts to the auto tier.
                setattr(asset, f"{field}_source", "AUTO")

    return changes


async def recompute_exposure_context(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Full-tenant recompute (mirrors `risk_score.py::compute_risk_scores`).

    Per asset, per field: `*_source == ASSET_OVERRIDE` -> skip (permanent).
    Else group override via membership (most-recently-updated group wins) ->
    GROUP_OVERRIDE. Else auto-tier. See `apply_precedence_to_asset`. Audits
    actual changes only, actor `system:exposure-inference`. Returns
    `{"assets_updated": int}`.
    """
    result = await db.execute(select(Asset).where(Asset.tenant_id == tenant_id))
    assets = result.scalars().all()

    updated = 0
    for asset in assets:
        changes = await apply_precedence_to_asset(db, asset)
        if changes:
            updated += 1
            audit_auto_inference_changes(db, tenant_id, asset.id, changes)

    logger.info("exposure_context_recomputed", tenant_id=str(tenant_id), assets_updated=updated)

    return {"assets_updated": updated}


async def check_criticality_calibration(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """EXPO-06 — measure AUTO-only CRITICAL proportion against the tenant's cap.

    Numerator counts ONLY assets where `business_criticality == "CRITICAL"`
    AND `business_criticality_source == "AUTO"` — admin/group overrides are
    exempt (32-CONTEXT.md: exempting them resolves the tension with EXPO-03's
    "override permanently wins" guarantee; the calibration criterion targets
    auto inflation, not deliberate admin decisions).

    `cap` and `hard_cap_enabled` are read from the tenant's row (migration
    038's `exposure_criticality_cap` / `exposure_hard_cap_enabled` columns,
    default 0.15 / False). Default behavior is flag+report ONLY: `over_cap`
    is informational and this function never mutates any asset, regardless
    of `hard_cap_enabled` — hard-cap enforcement is a documented, deliberately
    unwired stub (see module docstring; CONTEXT.md's explicit flag+report
    default).

    Returns `{"pct": float, "cap": float, "over_cap": bool,
    "critical_auto": int, "total": int, "hard_cap_enabled": bool}`.
    """
    from app.tenants.models import Tenant

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    cap = tenant.exposure_criticality_cap if tenant is not None else _DEFAULT_CRITICALITY_CAP
    hard_cap_enabled = tenant.exposure_hard_cap_enabled if tenant is not None else False

    # Single aggregate query (mirrors router.py::asset_stats's risk_distribution
    # count-aggregate shape) — one count() for the denominator, one filtered
    # count() for the AUTO-only-CRITICAL numerator.
    counts_q = select(
        func.count().label("total"),
        func.count()
        .filter(Asset.business_criticality == "CRITICAL", Asset.business_criticality_source == "AUTO")
        .label("critical_auto"),
    ).where(Asset.tenant_id == tenant_id)
    row = (await db.execute(counts_q)).one()
    total = row.total or 0
    critical_auto = row.critical_auto or 0
    pct = (critical_auto / total) if total else 0.0

    # hard-cap enforcement (off by default) — deliberately NOT wired here.
    # Even when hard_cap_enabled is True, this function only reports
    # over_cap; it never downranks an asset's business_criticality. Wiring
    # an actual enforcement path is out of scope per CONTEXT.md's EXPO-06
    # decision (flag+report is the safe default; silently down-ranking a
    # genuinely critical asset is worse than flagging).

    return {
        "pct": pct,
        "cap": cap,
        "over_cap": pct > cap,
        "critical_auto": critical_auto,
        "total": total,
        "hard_cap_enabled": hard_cap_enabled,
    }
