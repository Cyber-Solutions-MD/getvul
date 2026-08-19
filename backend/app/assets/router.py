"""Assets API router — CRUD, filtering, classification."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.classification import classify_asset
from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.exposure import EXPOSURE_FIELDS, resolve_group_override_names
from app.assets.models import Asset, BusinessCriticality, DataSensitivity
from app.assets.risk_score import RISK_SCORE_TIER_CRITICAL, RISK_SCORE_TIER_HIGH, RISK_SCORE_TIER_MEDIUM
from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.exceptions.service import active_exception_subquery
from app.vulnerabilities.models import Vulnerability

router = APIRouter(prefix="", tags=["Assets"])


# RFC 5321 email length cap. Regex is intentionally permissive (no full RFC
# 5322); the goal is to block XSS/oversize payloads (BL-01), not to be the
# authoritative email parser. Real email correctness is enforced when the
# directory lookup at _get_directory_user runs.
_EMAIL_RE = re.compile(r"^[^@\s<>'\"]+@[^@\s<>'\"]+\.[^@\s<>'\"]+$")


class _AssetOwnerUpdate(BaseModel):
    # T-12-08 (mass assignment via reassign body) is mitigated by the handler
    # explicitly copying body.assigned_user_email → asset.assigned_user only;
    # extras can't reach the ORM regardless. `extra="forbid"` is defensive so a
    # future maintainer can't accidentally introduce setattr-loop bulk assign.
    # field_validator blocks BL-01 (HTML/script payloads, oversize, non-email
    # strings propagating into Asana task descriptions and /tickets/assignees).
    model_config = {"extra": "forbid"}
    assigned_user_email: str = Field(..., min_length=3, max_length=320)

    @field_validator("assigned_user_email")
    @classmethod
    def _must_be_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("must be a valid email address")
        return v


class _ExposureOverrideUpdate(BaseModel):
    """Phase 32 (EXPO-03) — admin-only per-asset exposure-context override.

    T-32-03 mitigation: `extra="forbid"` (mass-assignment defense) + `field`
    allow-list + `value` validated against the enum matching `field` (a
    bool-string for `internet_facing`) — invalid combinations raise 422
    before the handler ever touches the ORM.
    """

    model_config = {"extra": "forbid"}
    field: str
    value: str

    @model_validator(mode="after")
    def _validate_field_and_value(self) -> _ExposureOverrideUpdate:
        if self.field not in EXPOSURE_FIELDS:
            raise ValueError(f"field must be one of {sorted(EXPOSURE_FIELDS)}")
        if self.field == "internet_facing":
            if self.value.strip().lower() not in {"true", "false"}:
                raise ValueError("value must be 'true' or 'false' for internet_facing")
        else:
            enum_cls = BusinessCriticality if self.field == "business_criticality" else DataSensitivity
            valid_values = {member.value for member in enum_cls}
            if self.value not in valid_values:
                raise ValueError(f"value must be one of {sorted(valid_values)}")
        return self


async def _get_directory_user(db: AsyncSession, tenant_id, asset) -> dict | None:
    """Find matching directory user for an asset by email."""
    from app.tenants.models import User

    # Try to match by humaans_email, assigned_user email, or last_login_user
    emails_to_try = []
    mdm = asset.mdm_details or {}
    if mdm.get("humaans_email"):
        emails_to_try.append(mdm["humaans_email"].lower())
    if asset.assigned_user and "@" in asset.assigned_user:
        emails_to_try.append(asset.assigned_user.lower())
    if asset.last_login_user and "@" in asset.last_login_user:
        emails_to_try.append(asset.last_login_user.lower())

    if not emails_to_try:
        return None

    from sqlalchemy import or_

    result = await db.execute(
        select(User)
        .where(
            User.tenant_id == tenant_id,
            or_(*[User.email == e for e in emails_to_try]),
        )
        .limit(1)
    )
    u = result.scalar_one_or_none()
    if not u:
        return None

    return {
        "email": u.email,
        "display_name": u.display_name,
        "department": u.department,
        "job_title": u.job_title,
        "avatar_url": u.avatar_url,
        "groups": u.groups or [],
        "idp_source": u.idp_source,
        "is_active": u.is_active,
        "role": u.role,
    }


@router.get("")
async def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", description="Search hostname or OS"),
    device_category: str = Query("", description="WORKSTATION,SERVER,NETWORK,MOBILE,OTHER"),
    scanner: str = Query("", description="CROWDSTRIKE,NESSUS,DEFENDER,WIZ,QUALYS,RAPID7 (scanner sources only)"),
    source_mode: str = Query("or", description="'or' (default, any selected scanner) or 'and' (all selected)"),
    enrichment_source: str = Query("", description="JAMF,HUMAANS,INTUNE — OR-only facet, no AND semantics"),
    min_risk: int = Query(0, ge=0, le=100),
    sort_by: str = Query("risk_score", description="risk_score,hostname,os_name,device_category"),
    sort_dir: str = Query("desc", description="asc or desc"),
    show_ignored: str = Query("active", description="active, ignored, or all"),
    os_family: str = Query("", description="comma-separated subset of {linux, windows, macos, other}"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List assets with filtering, pagination, sorting."""
    from fastapi import HTTPException

    # SRC-02: source_mode is a plain str Query param (this router builds
    # filters from explicit params, not a Pydantic Depends(Filter) model —
    # see os_family's identical inline-parse convention below), so the
    # or|and clamp is an explicit check here rather than a Literal[...]
    # field. Anything else is rejected with 422, never silently defaulted.
    mode = (source_mode or "or").strip().lower()
    if mode not in {"or", "and"}:
        raise HTTPException(422, "source_mode must be 'or' or 'and'")

    query = select(Asset).where(Asset.tenant_id == user.tenant_id)

    # Ignored filter
    if show_ignored == "ignored":
        query = query.where(Asset.is_ignored.is_(True))
    elif show_ignored != "all":
        query = query.where(Asset.is_ignored.is_(False))

    # Filters
    if search:
        query = query.where((Asset.hostname.ilike(f"%{search}%")) | (Asset.os_name.ilike(f"%{search}%")))
    if device_category:
        categories = [c.strip().upper() for c in device_category.split(",") if c.strip()]
        if categories:
            query = query.where(Asset.device_category.in_(categories))
    if scanner:
        # seen_by_sources is a JSONB array like ["CROWDSTRIKE", "NESSUS"].
        #
        # SRC-03 bug fix: this used to be a chained `.where(...)` loop, one
        # call per selected scanner — SQLAlchemy ANDs successive `.where()`
        # calls, so a multi-select silently meant "seen by ALL" (the
        # opposite of the intended OR-default). Now OR-default via
        # `or_(*contains)`, with the true-AND (real multi-scanner
        # corroboration) gated behind the explicit `source_mode=and` toggle.
        # SRC-06: clamped to SCANNER_SOURCES so an enrichment source (JAMF/
        # HUMAANS/INTUNE) can never leak into a scanner-corroboration filter.
        from sqlalchemy import false, or_

        scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
        scanners = [s for s in scanners if s in SCANNER_SOURCES]
        if scanners:
            if mode == "and":
                for s in scanners:  # explicit AND — true multi-scanner corroboration
                    query = query.where(Asset.seen_by_sources.contains([s]))
            else:
                query = query.where(or_(*[Asset.seen_by_sources.contains([s]) for s in scanners]))  # OR default
        else:
            # `scanner=` was given but every value was clamped out (e.g. an
            # enrichment-only source) — match nothing rather than silently
            # falling through to "no filter" (which would leak
            # enrichment-tagged assets into a scanner-only view).
            query = query.where(false())

    if enrichment_source:
        # SRC-06: plain OR facet, NO AND-corroboration semantics — these are
        # presence facts (an asset was seen by JAMF/HUMAANS/Intune), not
        # multi-tool corroboration signals, so there is no `source_mode`
        # equivalent here.
        from sqlalchemy import false, or_

        enr = [e.strip().upper() for e in enrichment_source.split(",") if e.strip()]
        enr = [e for e in enr if e in ENRICHMENT_SOURCES]
        # if/else (not a ternary) intentionally mirrors the scanner block's
        # shape above for readability at this call site.
        if enr:  # noqa: SIM108
            query = query.where(or_(*[Asset.seen_by_sources.contains([e]) for e in enr]))
        else:
            query = query.where(false())

    if min_risk > 0:
        query = query.where(Asset.risk_score >= min_risk)

    # T-12-01 mitigation: hardcoded ILIKE prefix patterns per family — values are baked
    # into source, never composed from user input. The `os_family` query param is parsed
    # comma-separated (W4: multi-select chip UI in 12-06) and clamped against an allow-list;
    # anything outside {linux, windows, macos, other} is silently dropped.
    OS_FAMILY_PATTERNS = {  # noqa: N806 — intentional constant-style local (allow-list lookup table)
        "linux": ["%linux%", "%ubuntu%", "%debian%", "%centos%", "%rhel%", "%fedora%"],
        "windows": ["%windows%"],
        "macos": ["%macos%", "%mac os%"],
    }
    if os_family:
        from sqlalchemy import and_, not_, or_

        requested = {f.strip().lower() for f in os_family.split(",") if f.strip()}
        # XSS / allow-list clamp — silently drop unknown values.
        valid = requested & ({"other"} | OS_FAMILY_PATTERNS.keys())
        ors = []
        known = valid & OS_FAMILY_PATTERNS.keys()
        if known:
            patterns = [p for fam in known for p in OS_FAMILY_PATTERNS[fam]]
            ors.append(or_(*[Asset.os_name.ilike(p) for p in patterns]))
        if "other" in valid:
            all_pat = [p for plist in OS_FAMILY_PATTERNS.values() for p in plist]
            ors.append(and_(Asset.os_name.isnot(None), not_(or_(*[Asset.os_name.ilike(p) for p in all_pat]))))
        if ors:
            query = query.where(or_(*ors))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort (allowlist to prevent SQL injection via column name)
    allowed_sort = {"risk_score", "hostname", "os_name", "device_category"}
    safe_sort_by = sort_by if sort_by in allowed_sort else "risk_score"
    sort_col = getattr(Asset, safe_sort_by)
    query = query.order_by(sort_col.asc()) if sort_dir == "asc" else query.order_by(sort_col.desc())

    # Paginate — clamp to safe integer range to satisfy SAST taint analysis
    safe_page = max(1, min(int(page), 10000))
    safe_size = max(1, min(int(page_size), 100))
    query = query.offset((safe_page - 1) * safe_size).limit(safe_size)
    result = await db.execute(query)  # nosemgrep: python.fastapi.db.generic-sql-fastapi.generic-sql-fastapi
    assets = result.scalars().all()

    # Enrich with vuln counts
    items = []
    for a in assets:
        vuln_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev).label("kev"),
            func.count()
            .filter(
                Vulnerability.sla_due_at.isnot(None),
                Vulnerability.sla_due_at < func.now(),
            )
            .label("sla_breach"),
        ).where(
            Vulnerability.asset_id == a.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            # EXC-02/D-15 (Phase 39 Tier 2 #11): an actively-excepted finding
            # never inflates the list-badge counts, INCLUDING sla_breach --
            # 39-03's run_sla_tier_pass fix already stopped updating the
            # persisted sla_due_at mirror for excepted rows, so this
            # read-time exclusion agrees with that stale-but-excluded state.
            ~active_exception_subquery(user.tenant_id, datetime.now(UTC)),
        )
        vcounts = (await db.execute(vuln_q)).one()

        items.append(
            {
                "id": str(a.id),
                "hostname": a.hostname,
                "os_name": a.os_name,
                "os_version": a.os_version,
                "device_category": a.device_category or "OTHER",
                "risk_score": a.risk_score or 0,
                "seen_by_sources": a.seen_by_sources or {},
                # SRC-01/08 (assets side): derived in-Python from the
                # already-selected seen_by_sources column — NO extra query,
                # so list_assets stays page-size-invariant in statement
                # count (SRC-08). sources_count counts SCANNER_SOURCES only
                # (excludes enrichment sources like JAMF, SRC-06).
                "sources": a.seen_by_sources or [],
                "sources_count": len([s for s in (a.seen_by_sources or []) if s in SCANNER_SOURCES]),
                "assigned_user": a.assigned_user,
                "department": a.department,
                "model": a.model,
                "serial_number": a.serial_number,
                "managed_by": a.managed_by,
                "ip_addresses": a.ip_addresses or [],
                "total_vulns": vcounts.total,
                "critical": vcounts.critical,
                "high": vcounts.high,
                "exploitable": vcounts.exploitable,
                "kev": vcounts.kev,
                "is_ignored": a.is_ignored,
                "ignored_at": a.ignored_at.isoformat() if a.ignored_at else None,
                "ignored_reason": a.ignored_reason,
                # Phase 12 — UX-04-02 (tags) + UX-04-03 row 2 (sla breach aggregate)
                "tags": a.tags or [],
                "sla_breach": vcounts.sla_breach,
                "sla_breach_count": vcounts.sla_breach,
                # Phase 32 — EXPO-01 exposure context (6 keys: 3 value + 3
                # *_source discriminator). Must be added here AND to the
                # detail dict below — dead schemas.py/service.py fields never
                # surface (32-PATTERNS Anti-Patterns).
                "business_criticality": a.business_criticality,
                "business_criticality_source": a.business_criticality_source,
                "data_sensitivity": a.data_sensitivity,
                "data_sensitivity_source": a.data_sensitivity_source,
                "internet_facing": a.internet_facing,
                "internet_facing_source": a.internet_facing_source,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/stats")
async def asset_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats for assets."""
    base = select(Asset).where(Asset.tenant_id == user.tenant_id, Asset.is_ignored.is_(False))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # By device category
    cat_q = (
        select(Asset.device_category, func.count())
        .where(Asset.tenant_id == user.tenant_id)
        .group_by(Asset.device_category)
    )
    cats = {row[0] or "OTHER": row[1] for row in (await db.execute(cat_q)).fetchall()}

    # Avg risk score
    avg_risk = (
        await db.execute(select(func.avg(Asset.risk_score)).where(Asset.tenant_id == user.tenant_id))
    ).scalar() or 0

    # Risk distribution
    risk_q = select(
        func.count().filter(Asset.risk_score >= RISK_SCORE_TIER_CRITICAL).label("critical"),
        func.count()
        .filter((Asset.risk_score >= RISK_SCORE_TIER_HIGH) & (Asset.risk_score < RISK_SCORE_TIER_CRITICAL))
        .label("high"),
        func.count()
        .filter((Asset.risk_score >= RISK_SCORE_TIER_MEDIUM) & (Asset.risk_score < RISK_SCORE_TIER_HIGH))
        .label("medium"),
        func.count().filter(Asset.risk_score < RISK_SCORE_TIER_MEDIUM).label("low"),
    ).where(Asset.tenant_id == user.tenant_id)
    risk_dist = (await db.execute(risk_q)).one()

    return {
        "total": total,
        "avg_risk_score": round(float(avg_risk), 1),
        "by_device_category": cats,
        "risk_distribution": {
            "critical": risk_dist.critical,
            "high": risk_dist.high,
            "medium": risk_dist.medium,
            "low": risk_dist.low,
        },
    }


async def _build_asset_detail(db: AsyncSession, user, asset: Asset) -> dict:
    """Build the full asset-detail response dict.

    Shared by `GET /assets/{id}` and `PATCH /assets/{id}/exposure-context`
    (Phase 32) so the override endpoint's response mirrors GET exactly,
    same convention `update_asset_owner` already uses for `directory_user`.
    """
    # Vuln breakdown
    vuln_q = select(
        func.count().label("total"),
        func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
        func.count().filter(Vulnerability.severity == "HIGH").label("high"),
        func.count().filter(Vulnerability.severity == "MEDIUM").label("medium"),
        func.count().filter(Vulnerability.severity == "LOW").label("low"),
        func.count().filter(Vulnerability.exploit_available).label("exploitable"),
        func.count().filter(Vulnerability.cisa_kev).label("kev"),
        func.count()
        .filter(
            Vulnerability.sla_due_at.isnot(None),
            Vulnerability.sla_due_at < func.now(),
        )
        .label("sla_breach"),
    ).where(
        Vulnerability.asset_id == asset.id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        # EXC-02/D-15 (Phase 39 Tier 2 #11): same detail-badge exclusion as
        # the list endpoint above, incl. sla_breach.
        ~active_exception_subquery(user.tenant_id, datetime.now(UTC)),
    )
    vc = (await db.execute(vuln_q)).one()

    # Phase 32 Plan 05 — which group (if any) currently drives a
    # GROUP_OVERRIDE-sourced field, for the frontend's "group: {name}" badge.
    # Read-side only lookup (no new column) — see exposure.py docstring.
    group_override_names = await resolve_group_override_names(db, asset.id)

    # NOTE (Phase 12 — fold-in #3): the inline `vulnerabilities[]` array previously
    # returned here was dropped. The v2.0 detail page uses `useAssetVulnerabilities`
    # (plan 12-05) to fetch the same data via `/api/v1/vulnerabilities?asset_id=<id>`,
    # so keeping the inline list created a double-fetch on every detail load. v1's
    # `/dashboard/assets/[id]/page.tsx` is being rewritten in plan 12-08; no external
    # consumers documented.

    return {
        "id": str(asset.id),
        "hostname": asset.hostname,
        "os_name": asset.os_name,
        "os_version": asset.os_version,
        "device_category": asset.device_category or "OTHER",
        "asset_type": asset.asset_type,
        "risk_score": asset.risk_score or 0,
        "ip_addresses": asset.ip_addresses or [],
        "mac_addresses": asset.mac_addresses or [],
        "external_ip": asset.external_ip,
        "seen_by_sources": asset.seen_by_sources or {},
        # Device identity
        "serial_number": asset.serial_number,
        "model": asset.model,
        "system_manufacturer": asset.system_manufacturer,
        # User & activity
        "last_login_user": asset.last_login_user,
        "last_login_at": asset.last_login_at.isoformat() if asset.last_login_at else None,
        "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
        "host_status": asset.host_status,
        "containment_status": asset.containment_status,
        # HR / MDM enrichment
        "assigned_user": asset.assigned_user,
        "department": asset.department,
        "building": asset.building,
        "managed_by": asset.managed_by,
        "last_checkin_at": asset.last_checkin_at.isoformat() if asset.last_checkin_at else None,
        "mdm_details": asset.mdm_details,
        # Humaans-specific (extracted from mdm_details for convenience)
        "humaans_email": (asset.mdm_details or {}).get("humaans_email"),
        "github_handle": (asset.mdm_details or {}).get("github_handle"),
        "linkedin_handle": (asset.mdm_details or {}).get("linkedin_handle"),
        "element_handle": (asset.mdm_details or {}).get("element_handle"),
        "humaans_teams": (asset.mdm_details or {}).get("humaans_teams"),
        "humaans_location": (asset.mdm_details or {}).get("humaans_location"),
        "humaans_timezone": (asset.mdm_details or {}).get("humaans_timezone"),
        # CrowdStrike
        "crowdstrike_aid": asset.crowdstrike_aid,
        # Directory user info (from Google Workspace / Azure / Okta sync)
        "directory_user": await _get_directory_user(db, user.tenant_id, asset),
        "is_ignored": asset.is_ignored,
        "ignored_at": asset.ignored_at.isoformat() if asset.ignored_at else None,
        "ignored_reason": asset.ignored_reason,
        # Phase 12 — UX-04-02 tag chips inline with hostname.
        "tags": asset.tags or [],
        # Phase 12 — UX-04-03 RiskCard row 2 ("SLA breaches"). Surfaced both
        # at the top level and inside `vuln_counts` so the rail card can read
        # either shape without a follow-up wiring change.
        "sla_breach": vc.sla_breach,
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
        # Phase 32 — EXPO-01 exposure context (6 keys: 3 value + 3 *_source
        # discriminator). Must be added here AND to the list dict above —
        # dead schemas.py/service.py fields never surface (32-PATTERNS
        # Anti-Patterns).
        "business_criticality": asset.business_criticality,
        "business_criticality_source": asset.business_criticality_source,
        "business_criticality_group_name": group_override_names.get("business_criticality"),
        "data_sensitivity": asset.data_sensitivity,
        "data_sensitivity_source": asset.data_sensitivity_source,
        "data_sensitivity_group_name": group_override_names.get("data_sensitivity"),
        "internet_facing": asset.internet_facing,
        "internet_facing_source": asset.internet_facing_source,
        "internet_facing_group_name": group_override_names.get("internet_facing"),
    }


@router.get("/{asset_id}")
async def get_asset(
    asset_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single asset with full details."""
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    return await _build_asset_detail(db, user, asset)


@router.post("/{asset_id}/ignore")
async def ignore_asset(
    asset_id: uuid.UUID,
    body: dict = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an asset as ignored — excludes from remediations and ticket creation."""
    from datetime import datetime

    from app.audit import audit

    if body is None:
        body = {}
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    asset.is_ignored = True
    asset.ignored_at = datetime.now(UTC)
    asset.ignored_reason = body.get("reason", "")
    await audit(
        db, user, "asset.ignore", "asset", str(asset.id), {"hostname": asset.hostname, "reason": asset.ignored_reason}
    )
    await db.commit()
    return {"message": f"Asset '{asset.hostname}' ignored", "is_ignored": True}


@router.post("/{asset_id}/unignore")
async def unignore_asset(
    asset_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unignore an asset — restores it to active remediation and ticket creation."""
    from app.audit import audit

    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        from fastapi import HTTPException

        raise HTTPException(404, "Asset not found")

    asset.is_ignored = False
    asset.ignored_at = None
    asset.ignored_reason = None
    await audit(db, user, "asset.unignore", "asset", str(asset.id), {"hostname": asset.hostname})
    await db.commit()
    return {"message": f"Asset '{asset.hostname}' restored", "is_ignored": False}


@router.post("/{asset_id}/owner")
async def update_asset_owner(
    asset_id: uuid.UUID,
    body: _AssetOwnerUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reassign an asset's owner (Phase 12 UX-04-04).

    Body: ``{assigned_user_email: str}``. Updates ``Asset.assigned_user`` —
    a string field, NOT an FK — per locked_decisions item 1 (no
    owner_user_id migration). Writes an ``asset.owner_changed`` audit row
    in the same transaction as the mutation (T-12-09 mitigation: audit
    failure short-circuits the commit, so the owner change cannot land
    without its audit row).

    Directory user is re-resolved at response time via ``_get_directory_user``
    so the response mirrors GET /assets/{id}.
    """
    from fastapi import HTTPException

    from app.audit import audit

    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        # T-12-20 mitigation — 404 (not 403) keeps cross-tenant existence private.
        raise HTTPException(404, "Asset not found")

    old_email = asset.assigned_user
    # T-12-11 mitigation — strip + lowercase before the empty-check so a
    # whitespace-only payload is rejected at the same gate as the missing
    # field (Pydantic raises 422 if `assigned_user_email` is absent entirely).
    new_email = body.assigned_user_email.strip().lower()
    if not new_email:
        raise HTTPException(422, "assigned_user_email is required")

    asset.assigned_user = new_email

    await audit(
        db,
        user,
        "asset.owner_changed",
        "asset",
        str(asset.id),
        {"from": old_email, "to": new_email, "hostname": asset.hostname},
    )
    await db.commit()
    await db.refresh(asset)

    directory_user = await _get_directory_user(db, user.tenant_id, asset)
    return {
        "id": str(asset.id),
        "hostname": asset.hostname,
        "assigned_user": asset.assigned_user,
        "directory_user": directory_user,
    }


@router.patch("/{asset_id}/exposure-context")
async def update_asset_exposure_context(
    asset_id: uuid.UUID,
    body: _ExposureOverrideUpdate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only per-asset exposure-context override (Phase 32 — EXPO-03).

    Setting a field here flips its ``*_source`` discriminator to
    ``ASSET_OVERRIDE``, which permanently wins over any future auto
    re-inference — ``apply_inference_to_asset``/``recompute_exposure_context``
    only ever write a field whose source is still ``AUTO``. Audit-then-commit
    in the same transaction (T-32-04/EXPO-05 — mirrors ``update_asset_owner``).
    """
    from fastapi import HTTPException

    from app.audit import audit

    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not asset:
        # T-32-02 mitigation — 404 (not 403) keeps cross-tenant existence private.
        raise HTTPException(404, "Asset not found")

    field = body.field
    new_value: str | bool = body.value.strip().lower() == "true" if field == "internet_facing" else body.value
    old_value = getattr(asset, field)

    setattr(asset, field, new_value)
    setattr(asset, f"{field}_source", "ASSET_OVERRIDE")

    await audit(
        db,
        user,
        "asset.exposure_override",
        "asset",
        str(asset.id),
        {"field": field, "old": old_value, "new": new_value},
    )
    await db.commit()
    await db.refresh(asset)

    return await _build_asset_detail(db, user, asset)


@router.post("/bulk-ignore")
async def bulk_ignore_assets(
    body: dict,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk ignore/unignore assets."""
    from datetime import datetime

    from app.audit import audit

    asset_ids = body.get("asset_ids", [])
    action = body.get("action", "ignore")  # "ignore" or "unignore"
    reason = body.get("reason", "")

    if not asset_ids:
        from fastapi import HTTPException

        raise HTTPException(400, "No asset IDs provided")

    result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids), Asset.tenant_id == user.tenant_id))
    assets = result.scalars().all()

    for a in assets:
        if action == "ignore":
            a.is_ignored = True
            a.ignored_at = datetime.now(UTC)
            a.ignored_reason = reason
        else:
            a.is_ignored = False
            a.ignored_at = None
            a.ignored_reason = None

    await audit(db, user, f"asset.bulk_{action}", "asset", None, {"count": len(assets), "reason": reason})
    await db.commit()
    return {"message": f"{len(assets)} assets {action}d"}


@router.post("/recompute-risk-scores")
async def recompute_risk_scores(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Recompute risk scores for all assets based on current vulnerabilities."""
    from app.assets.risk_score import compute_risk_scores

    stats = await compute_risk_scores(db, user.tenant_id)
    await db.commit()
    return {"message": "Risk scores recomputed", **stats}


@router.post("/exposure-context/recompute")
async def recompute_exposure_context_endpoint(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Full-tenant re-inference of exposure-context fields (Phase 32 — EXPO-02).

    Mirrors ``POST /assets/recompute-risk-scores``. Any field whose source
    is ``ASSET_OVERRIDE`` (and, from Plan 03, ``GROUP_OVERRIDE``) is skipped
    — an override permanently wins over auto re-inference (EXPO-03).
    """
    from app.assets.exposure import recompute_exposure_context

    stats = await recompute_exposure_context(db, user.tenant_id)
    await db.commit()
    return {"message": "Exposure context recomputed", **stats}


@router.get("/exposure-context/calibration")
async def get_exposure_context_calibration(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only EXPO-06 calibration report (Phase 32 Plan 02).

    Reports the proportion of AUTO-sourced CRITICAL assets against the
    tenant's configurable cap (default 15%). Admin/group overrides are
    exempt from the numerator (T-32-05/T-32-06 — see 32-02-PLAN.md threat
    model). Read-only: flag+report, never mutates any asset.
    """
    from app.assets.exposure import check_criticality_calibration

    return await check_criticality_calibration(db, user.tenant_id)


@router.post("/classify")
async def classify_all_assets(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Re-classify all assets by device type."""
    result = await db.execute(select(Asset).where(Asset.tenant_id == user.tenant_id))
    assets = result.scalars().all()

    counts: dict[str, int] = {}
    for asset in assets:
        category = classify_asset(asset)
        asset.device_category = category
        counts[category] = counts.get(category, 0) + 1

    await db.commit()
    return {"classified": len(assets), "by_category": counts}
