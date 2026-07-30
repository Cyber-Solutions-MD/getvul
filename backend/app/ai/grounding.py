"""Grounding-record assemblers for the host + remediation 'explain' views
(D-15/D-16, Plan 08).

`get_asset_posture()` produces the per-host posture-summary shape
(HOST_ALLOWLIST) -- T-24-32's highest-PII-risk boundary is defended STARTING
HERE, not just at the prompt builder: this query never even SELECTs owner-PII
columns (directory_user is assembled elsewhere via a separate lookup;
assigned_user/managed_by/building/serial_number are simply not fetched),
ahead of `build_explain_host_prompt`'s own field-by-field allowlist
discipline (PATTERNS Pitfall 5) as a second, independent line of defense.

`get_remediation_group()` produces the D-16 Option A "cross-asset CVE
grouping" shape recorded at the 24-06 TRACER checkpoint (24-06-SUMMARY.md
"Decision detail") -- a NEW tenant-scoped aggregate query keyed on `cve_id`
(the correlation key GetVul's own core value is built on), not the existing
`remediation_id`-keyed queries in `vulnerabilities/remediation_service.py`
(a scanner-specific identifier, and the accepted cost explicitly recorded at
the checkpoint: "no existing query groups a tenant's affected assets by
CVE").

Both functions are tenant-scoped identically to `get_asset`/`get_vulnerability`
(app.assets.service / app.vulnerabilities.service): a foreign-tenant id (or a
CVE with zero vulnerabilities in this tenant) returns None, never partial or
cross-tenant data.

`get_remediation_guidance_context()` (D-01/D-10, Plan 01 Task 2) produces the
Phase 25 "asset-aware remediation guidance" grounding record -- a NEW,
narrow, single-row `Vulnerability` outer-joined to `Asset`, keyed on
`finding_id` (UUID). It is neither `get_vulnerability()`
(app.vulnerabilities.service -- has no `os_name`/`os_version` columns, so it
cannot ground "OS/package-aware" guidance) nor `get_remediation_group()`
above (a cross-asset CVE aggregate -- the wrong scope for a single finding's
drill-panel action, D-06). Tenant-scoped identically to every other function
in this module: a foreign-tenant `finding_id` returns None. Owner-PII columns
(assigned_user/directory_user/managed_by/building/serial_number/department)
are never named in its SELECT -- mirrors `get_asset_posture()`'s "never even
fetched" discipline (Phase 24 D-15 defense-in-depth, T-25-01).

`has_actionable_remediation_text()` is the D-01 deterministic pre-generation
refuse predicate: `Vulnerability.remediation_action`/`remediation_info` must
be treated as ABSENT when empty-string, a generic placeholder, or below a
small minimum length -- never just `is not None` (Rapid7's own
fetch-failure path persists a literal `""`; 25-RESEARCH.md Pattern 1).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.vulnerabilities.models import Vulnerability

# Severity -> numeric rank, mirroring
# `vulnerabilities/remediation_service.py::get_remediations_grouped`'s own
# CASE-ranking convention exactly, so "priority" reads consistently with the
# rest of the product's severity vocabulary.
_SEVERITY_RANK: dict[str, int] = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
_RANK_TO_SEVERITY: dict[int, str] = {v: k for k, v in _SEVERITY_RANK.items()}


async def get_asset_posture(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Assemble the per-host posture-summary grounding record. Returns None
    (tenant-scoped, exactly like `get_asset`) when `asset_id` does not
    belong to `tenant_id`.

    Only HOST_ALLOWLIST columns are ever selected off `Asset` -- owner PII
    (directory_user, assigned_user, managed_by, building, serial_number) is
    never queried here, let alone passed through.
    """
    result = await db.execute(
        select(
            Asset.hostname,
            Asset.os_name,
            Asset.os_version,
            Asset.device_category,
            Asset.risk_score,
            Asset.tags,
            Asset.last_checkin_at,
        ).where(Asset.id == asset_id, Asset.tenant_id == tenant_id)
    )
    asset = result.one_or_none()
    if asset is None:
        return None

    # Vuln counts by severity + exploitable/kev/sla_breach -- the SAME
    # aggregate shape `assets/router.py::get_asset`'s own vuln_q already
    # computes for the /assets/[id] detail page (mirrored here rather than
    # imported, since that router builds a much larger PII-bearing dict
    # this grounding record must never carry).
    vuln_q = select(
        func.count().label("total"),
        func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
        func.count().filter(Vulnerability.severity == "HIGH").label("high"),
        func.count().filter(Vulnerability.severity == "MEDIUM").label("medium"),
        func.count().filter(Vulnerability.severity == "LOW").label("low"),
        func.count().filter(Vulnerability.exploit_available).label("exploitable"),
        func.count().filter(Vulnerability.cisa_kev).label("kev"),
        func.count()
        .filter(Vulnerability.sla_due_at.isnot(None), Vulnerability.sla_due_at < func.now())
        .label("sla_breach"),
    ).where(
        Vulnerability.asset_id == asset_id,
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
    )
    vc = (await db.execute(vuln_q)).one()

    return {
        "hostname": asset.hostname,
        "os_name": asset.os_name,
        "os_version": asset.os_version,
        "device_category": asset.device_category,
        "risk_score": asset.risk_score,
        "vuln_counts": {
            "total": vc.total,
            "critical": vc.critical,
            "high": vc.high,
            "medium": vc.medium,
            "low": vc.low,
            "exploitable": vc.exploitable,
            "kev": vc.kev,
            "sla_breach": vc.sla_breach,
        },
        "tags": asset.tags or [],
        "sla_breach": vc.sla_breach,
        "last_checkin_at": asset.last_checkin_at,
    }


async def get_remediation_group(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    cve_id: str,
) -> dict[str, Any] | None:
    """Assemble the D-16 Option A ('Cross-asset CVE grouping') grounding
    record. Returns None (tenant-scoped) when this tenant has no
    open/in-progress vulnerability for `cve_id` -- covers both a genuinely
    unknown CVE and a foreign-tenant's CVE, identically to how
    `get_vulnerability` 404s on a foreign-tenant `finding_id`.
    """
    rows = (
        await db.execute(
            select(
                Asset.hostname,
                Asset.os_name,
                Asset.os_version,
                Vulnerability.severity,
                Vulnerability.exploit_available,
                Vulnerability.cisa_kev,
                Vulnerability.remediation_info,
                Vulnerability.fixed_version,
            )
            .join(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.cve_id == cve_id,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Asset.is_ignored.is_(False),
            )
            .order_by(Asset.hostname)
        )
    ).all()
    if not rows:
        return None

    affected_assets = [
        {
            "hostname": r.hostname,
            "os_name": r.os_name,
            "os_version": r.os_version,
            "severity": r.severity,
            "exploit_available": r.exploit_available,
            "cisa_kev": r.cisa_kev,
        }
        for r in rows
    ]

    # "fix" -- the first non-null vendor solution text found across the
    # group (remediation_info, falling back to a fixed-version note). None
    # (never fabricated) when no row in the group carries either -- the
    # empty-grounding contract (T-24-35) then routes the downstream model
    # to grounded=false via FEW_SHOT_REMEDIATION's own second exemplar.
    fix = next((r.remediation_info for r in rows if r.remediation_info), None)
    if fix is None:
        fixed_version = next((r.fixed_version for r in rows if r.fixed_version), None)
        fix = f"Upgrade to {fixed_version}." if fixed_version else None

    # priority -- deterministic, backend-computed (mirrors ASSET-02's own
    # "deterministic risk score... augmented/explained, never replaced by
    # the model" principle, applied here to a fleet-wide aggregate instead
    # of a single asset): max severity across the group, escalated to
    # CRITICAL if ANY affected instance is CISA KEV-listed or has a public
    # exploit -- the same exploit/KEV-escalation convention ASSET-02's risk
    # score already uses.
    max_rank = max(_SEVERITY_RANK.get(r.severity, 0) for r in rows)
    priority = _RANK_TO_SEVERITY.get(max_rank, "LOW")
    if any(r.cisa_kev or r.exploit_available for r in rows):
        priority = "CRITICAL"

    return {
        "cve": cve_id,
        "fix": fix,
        "affected_assets": affected_assets,
        "priority": priority,
    }


# ── D-01 refuse predicate + per-finding remediation-guidance grounding ──

# Casefolded generic placeholders that must be treated as ABSENT even though
# they are non-null, non-empty strings (25-RESEARCH.md Pattern 1). The
# ticketing layer's own read-time fallback ("No remediation info available",
# app.ticketing.service.py:135) is never persisted back into this column,
# but connector-authored placeholders below DO reach the DB via other paths
# and must be denylisted here.
_GENERIC_REMEDIATION_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "no remediation info available",
        "no remediation info",
        "no remediation available",
        "unknown",
        "n/a",
        "none",
    }
)

# Excludes "Unknown"/"N/A"/"-" (already sub-minimum length) while passing a
# real short fix like "Upgrade to 1.3.2." (25-RESEARCH.md Pattern 1).
MIN_REMEDIATION_CHARS = 15


def has_actionable_remediation_text(remediation_action: str | None, remediation_info: str | None) -> bool:
    """D-01's deterministic pre-generation refuse predicate. Checks
    `remediation_action` (primary) then `remediation_info` (fallback); a
    candidate counts as actionable only when, after `.strip()`, it is at
    least `MIN_REMEDIATION_CHARS` long AND its `.casefold()` is not a member
    of `_GENERIC_REMEDIATION_PLACEHOLDERS`. Deliberately NEVER `is not None`
    (Pitfall 1) -- Rapid7's own fetch-failure path persists a literal `""`,
    and `sync.py`'s upsert `or`-chain makes `remediation_action` collapse to
    `remediation_info`'s exact value for 5 of 6 connectors, so an
    `is not None` check alone would wrongly treat an empty-string row as
    present.
    """
    for raw in (remediation_action, remediation_info):
        if raw is None:
            continue
        text = raw.strip()
        if len(text) < MIN_REMEDIATION_CHARS:
            continue
        if text.casefold() in _GENERIC_REMEDIATION_PLACEHOLDERS:
            continue
        return True
    return False


async def get_remediation_guidance_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Assemble the per-finding remediation-guidance grounding record
    (D-01/D-10). Returns None (tenant-scoped, exactly like `get_vulnerability`)
    when `finding_id` does not belong to `tenant_id`.

    Only these 12 columns are ever selected -- owner PII (assigned_user,
    directory_user, managed_by, building, serial_number, department) is
    never queried here, let alone passed through (T-25-01 defense-in-depth,
    mirroring `get_asset_posture()`'s "never even fetched" discipline).
    """
    result = await db.execute(
        select(
            Vulnerability.cve_id,
            Vulnerability.remediation_action,
            Vulnerability.remediation_info,
            Vulnerability.affected_product,
            Vulnerability.affected_version,
            Vulnerability.fixed_version,
            Vulnerability.severity,
            Vulnerability.exploit_available,
            Vulnerability.cisa_kev,
            Asset.hostname,
            Asset.os_name,
            Asset.os_version,
        )
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(Vulnerability.id == finding_id, Vulnerability.tenant_id == tenant_id)
    )
    row = result.one_or_none()
    if row is None:
        return None

    return {
        "cve_id": row.cve_id,
        "remediation_action": row.remediation_action,
        "remediation_info": row.remediation_info,
        "affected_product": row.affected_product,
        "affected_version": row.affected_version,
        "fixed_version": row.fixed_version,
        "severity": row.severity,
        "exploit_available": row.exploit_available,
        "cisa_kev": row.cisa_kev,
        "asset_hostname": row.hostname,
        "os_name": row.os_name,
        "os_version": row.os_version,
    }
