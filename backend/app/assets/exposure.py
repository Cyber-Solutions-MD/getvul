"""Asset exposure-context inference — Phase 32 Plan 01 (LEAD TRACER).

New module (NOT an extension of `classification.py`/`classifier.py`, which
classify only `device_category`, or the dead `service.py`/`schemas.py`).
Mirrors `classification.py`'s pure ordered-priority inference-function shape
for `infer_exposure_context`, and `risk_score.py::compute_risk_scores`'s
full-tenant recompute-and-persist shape for `recompute_exposure_context`.

TRACER SCOPE: only `business_criticality` has real inference logic in this
plan. `data_sensitivity` and `internet_facing` return static defaults —
Plan 02 replaces those two default-returns with real logic (data_sensitivity
from tags/tiering signals; internet_facing from real per-connector detection
+ the external_ip/tag fallback). Marked with `# PLAN 02:` comments below.

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

Auto-inference seeds from — never overwrites — existing `Asset.tags` and
existing MDM (Jamf)/HR (Humaans) enrichment (`Asset.department`,
`Asset.mdm_details["humaans_job_title"]`) plus `Asset.external_ip`. Per
CONTEXT.md's "[RESOLVED post-plan-check]" note, IdP-directory signals
(Entra/Okta/Google `User.department`/groups) are DEFERRED for v1 — wiring
them in would require a DB join inside what is otherwise a pure function,
for low marginal value. Documented future work, not a silent drop.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.audit import AuditLog

logger = structlog.get_logger()

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
    elif any(keyword in job_title_lower for keyword in _HIGH_JOB_TITLE_KEYWORDS) or department_lower in _HIGH_DEPARTMENTS:
        business_criticality = "HIGH"
    elif department_lower in _LOW_DEPARTMENTS:
        business_criticality = "LOW"

    # PLAN 02: real data_sensitivity inference (tags/tiering signals) lands here.
    data_sensitivity = "INTERNAL"

    # PLAN 02: real per-connector internet-facing detection + the
    # external_ip/"internet-facing" tag fallback lands here.
    internet_facing = False

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
