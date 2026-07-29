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
