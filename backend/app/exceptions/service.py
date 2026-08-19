"""Exception business logic (Phase 39 Plan 01 -- EXC-01/EXC-02/EXC-03/EXC-04
tracer slice): the shared "effective exclusion" seam
(`active_exception_subquery`), expiry validation (D-14), the Pattern 4
lazy-on-read expiry-audit sweep, and grant/list/revoke.

D-01: `exceptions` is the exclusion SOURCE OF TRUTH; exclusion itself is
derived at read time via `active_exception_subquery` -- granting/revoking/
expiring an exception never flips `Vulnerability.status`. D-04: an
exception is active only while `now < expires_at AND revoked_at IS NULL` --
once either condition flips the join simply stops matching, so an expired
or revoked exception's finding resurfaces on the very next read with zero
scheduler involvement.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Exists, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import AssetGroupMember
from app.audit import AuditLog
from app.exceptions.models import ExceptionRecord
from app.exceptions.schemas import ExceptionCreate
from app.tenants.models import User
from app.vulnerabilities.models import Vulnerability

# D-14: [ASSUMED -- 39-RESEARCH.md Assumptions Log A2, CONTEXT's own
# example value "e.g. <= 1 year"]. The hard cap is enforced here regardless
# of what a client sends -- server-authoritative, closing the "2099 date
# quietly defeats never-permanently-silenced" threat (T-39-05).
MAX_EXPIRY_DAYS = 365


def active_exception_subquery(tenant_id: uuid.UUID, now: datetime) -> Exists:
    """Correlated EXISTS: does an active (non-expired, non-revoked)
    exception cover the OUTER `Vulnerability` row this is joined against?
    (39-RESEARCH.md Pattern 1, copied schema-complete.)

    Caller applies `~active_exception_subquery(...)` to EXCLUDE actively-
    excepted rows from an "active work" query, or the bare form to SELECT
    them.

    D-10: always CVE-pinned -- never a blanket whole-asset/whole-group
    silence of unrelated CVEs (T-39... never matches on asset_id/
    asset_group_id alone). D-12: OR semantics across the three scope
    branches -- a row matched by ANY currently-active exception (finding-
    level OR asset-level OR group-level) is excluded; multiple
    simultaneous matches are permitted (no partial-unique index on the
    table, see models.py).
    """
    return exists(
        select(ExceptionRecord.id).where(
            ExceptionRecord.tenant_id == tenant_id,
            ExceptionRecord.revoked_at.is_(None),
            ExceptionRecord.expires_at > now,  # strict: now == expires_at is lapsed (EXC-04 boundary)
            or_(
                ExceptionRecord.vulnerability_id == Vulnerability.id,
                and_(
                    ExceptionRecord.scope_type == "ASSET",
                    ExceptionRecord.cve_id == Vulnerability.cve_id,
                    ExceptionRecord.asset_id == Vulnerability.asset_id,
                ),
                and_(
                    ExceptionRecord.scope_type == "ASSET_GROUP",
                    ExceptionRecord.cve_id == Vulnerability.cve_id,
                    exists(
                        select(AssetGroupMember.asset_id).where(
                            AssetGroupMember.group_id == ExceptionRecord.asset_group_id,
                            AssetGroupMember.asset_id == Vulnerability.asset_id,
                        )
                    ),
                ),
            ),
        )
    )


def validate_expiry(expires_at: datetime, now: datetime) -> None:
    """D-14: expiry must be strictly in the future and capped at
    `MAX_EXPIRY_DAYS` -- server-authoritative regardless of what the
    client sends. EXC-04's activeness boundary is `expires_at > now`
    (strict) everywhere, so an `expires_at <= now` grant would be
    dead-on-arrival (lapsed the instant it's created) -- rejected here,
    not silently accepted.
    """
    if expires_at <= now:
        raise HTTPException(400, "Pick a date between tomorrow and the maximum allowed date.")
    max_allowed = now + timedelta(days=MAX_EXPIRY_DAYS)
    if expires_at > max_allowed:
        raise HTTPException(400, f"Pick a date between tomorrow and {max_allowed.date()}.")


async def sweep_expired_audits(db: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> None:
    """Pattern 4 (lazy-on-read expiry audit -- RESEARCH Open Question Q2,
    ADOPTED). For every tenant row that has naturally lapsed
    (`expires_at <= now`), was never revoked, and was never previously
    swept (`resurfaced_audited_at IS NULL`), writes ONE system-attributed
    `exception.expire` audit row -- mirroring `reopen_vulnerability`'s
    direct-`AuditLog`-construction system-actor precedent
    (`vulnerabilities/service.py:464-476`; there is no human actor for a
    pure time-based lapse) -- and stamps `resurfaced_audited_at = now` in
    the same write. The `resurfaced_audited_at IS NULL` guard makes this
    idempotent: a second sweep over an already-swept row is a no-op, so
    EXC-03's audit trail gap closes without ever double-writing.

    Called from `GET /api/v1/exceptions` BEFORE the list is read back, so
    every response reflects a fully-swept state.
    """
    rows = (
        (
            await db.execute(
                select(ExceptionRecord).where(
                    ExceptionRecord.tenant_id == tenant_id,
                    ExceptionRecord.expires_at <= now,
                    ExceptionRecord.revoked_at.is_(None),
                    ExceptionRecord.resurfaced_audited_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return
    for record in rows:
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=None,
                user_email="system:exception-expiry",
                action="exception.expire",
                resource_type="exception",
                resource_id=str(record.id),
                details={"cve_id": record.cve_id, "scope_type": record.scope_type},
                ip_address=None,
                created_at=now,
            )
        )
        record.resurfaced_audited_at = now
    await db.commit()


async def grant_exception(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
    body: ExceptionCreate,
    now: datetime,
) -> ExceptionRecord:
    """EXC-01/D-06/D-07: resolve the scope target server-side, validate,
    and insert. Does NOT audit or commit -- the caller (router) owns
    audit-then-commit ordering, exactly mirroring `ignore_cve`.

    Pitfall 9: for FINDING scope the `Vulnerability` is resolved
    server-side by `vulnerability_id` + `tenant_id` and `cve_id`/`asset_id`
    are DERIVED from it -- the client's own `cve_id` is never trusted
    independently (T-39-03).

    D-03 (Pattern 2 reconciliation): the OPEN/IN_PROGRESS precondition
    applies ONLY to FINDING scope, which targets one concrete existing
    row. ASSET/ASSET_GROUP scope is explicitly forward-looking (D-11) and
    lands in Plan 02 -- naively applying the same precondition there would
    wrongly reject a legitimate "accept risk before any member is
    detected" grant, so those two scope types 400 here rather than being
    half-implemented.
    """
    validate_expiry(body.expires_at, now)

    # D-08 / T-39-01: approver_user_id must resolve to a real user WITHIN
    # THIS TENANT. Without this check the FK alone would happily accept
    # another tenant's (guessable) user id, and that cross-tenant user's
    # display_name/email would later leak to this tenant's viewers via the
    # list endpoint's approver_display_name lookup -- an IDOR/information-
    # disclosure gap, not just a data-integrity nicety.
    approver_exists = (
        await db.execute(select(User.id).where(User.id == body.approver_user_id, User.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if approver_exists is None:
        raise HTTPException(400, "Approver must be an active user in your organization.")

    if body.scope_type == "FINDING":
        if body.vulnerability_id is None:
            raise HTTPException(400, "vulnerability_id is required for FINDING scope.")
        vuln = (
            await db.execute(
                select(Vulnerability).where(
                    Vulnerability.id == body.vulnerability_id,
                    Vulnerability.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if vuln is None:
            raise HTTPException(404, "Vulnerability not found")
        if vuln.status not in ("OPEN", "IN_PROGRESS"):
            raise HTTPException(400, "This finding is already remediated — nothing to except.")
        if not vuln.cve_id:
            raise HTTPException(400, "This finding has no CVE — cannot scope an exception to it.")
        cve_id = vuln.cve_id
        vulnerability_id: uuid.UUID | None = vuln.id
        asset_id: uuid.UUID | None = vuln.asset_id
        asset_group_id: uuid.UUID | None = None
    else:
        # ASSET / ASSET_GROUP scope resolution lands in Plan 02 (39-CONTEXT.md
        # Open Question Q1 / Pattern 2) -- 400 clearly rather than
        # half-implement live-membership resolution in the tracer plan.
        raise HTTPException(400, f"{body.scope_type} scope is not yet supported.")

    record = ExceptionRecord(
        tenant_id=tenant_id,
        type=body.type,
        scope_type=body.scope_type,
        cve_id=cve_id,
        vulnerability_id=vulnerability_id,
        asset_id=asset_id,
        asset_group_id=asset_group_id,
        justification=body.justification,
        approver_user_id=body.approver_user_id,
        granted_by_user_id=granted_by_user_id,
        expires_at=body.expires_at,
    )
    db.add(record)
    await db.flush()
    return record


async def list_exceptions(db: AsyncSession, tenant_id: uuid.UUID) -> list[ExceptionRecord]:
    """All exceptions for a tenant, newest first (deterministic tiebreak on
    `id` so equal-timestamp rows never reorder between reads)."""
    result = await db.execute(
        select(ExceptionRecord)
        .where(ExceptionRecord.tenant_id == tenant_id)
        .order_by(ExceptionRecord.created_at.desc(), ExceptionRecord.id)
    )
    return list(result.scalars().all())


def revoke_exception(record: ExceptionRecord, revoked_by_user_id: uuid.UUID, now: datetime) -> None:
    """D-17: early revocation. Mutates `record` in place; the caller
    (router) owns tenant-scoped lookup (`_get_exception_or_404`),
    audit-then-commit, and the compute_risk_scores refresh -- mirrors
    `close_campaign` setting `Campaign` fields directly in the router."""
    record.revoked_at = now
    record.revoked_by_user_id = revoked_by_user_id
