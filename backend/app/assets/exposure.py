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

internet_facing (v1 proxy — Plan 04 upgrades this to real per-connector
detection wherever the vendor payload supports it, e.g. Wiz publicExposure /
cloud security-group signals; no existing connector currently extracts such
a signal, verified again this session):
  True  — "internet-facing" is present in `tags` (case-insensitive) OR
          `external_ip` is not None
  False — otherwise

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

from app.assets.models import Asset
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
) -> tuple[str, str, bool]:
    """Pure, no DB. Returns (business_criticality, data_sensitivity, internet_facing).

    Never mutates the caller's `tags` list — reads it into a local, lower-cased
    set only.
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

    # v1 proxy (Plan 04 upgrades to real per-connector detection wherever the
    # vendor payload supports it — no existing connector currently extracts
    # such a signal).
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


async def recompute_exposure_context(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Full-tenant recompute (mirrors `risk_score.py::compute_risk_scores`).

    Per asset, per field: `*_source == ASSET_OVERRIDE` -> skip (Plan 03
    inserts the GROUP_OVERRIDE middle tier here). Else auto-tier via
    `apply_inference_to_asset`. Audits actual changes only, actor
    `system:exposure-inference`. Returns `{"assets_updated": int}`.
    """
    result = await db.execute(select(Asset).where(Asset.tenant_id == tenant_id))
    assets = result.scalars().all()

    updated = 0
    for asset in assets:
        changes = apply_inference_to_asset(asset)
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
