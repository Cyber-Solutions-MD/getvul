"""Phase 39 Plan 01 (EXC-01/EXC-02/EXC-03/EXC-04) -- exception & risk-
acceptance tracer slice: grant -> excluded -> auto-resurface (+ lazy-audit)
-> revoke -> audited, proven end-to-end against `list_vulnerabilities`
before any horizontal expansion (scope semantics, SLA subtraction, the
full consumer sweep, dashboards, UI -- all later plans).

Uses the project's canonical inline-seed + `client_factory` harness
(`test_campaigns.py` / `test_asset_groups.py`) verbatim -- an ad hoc
`CurrentUser` (not persisted to the `users` table) stands in for "a
tenant_b analyst" since `client_factory`'s dependency override bypasses
`get_current_user` entirely.

Backend env gotcha (MEMORY.md `getvul-backend-pytest-env`): run with a REAL
Fernet ENCRYPTION_KEY (`Fernet.generate_key()`, NOT a placeholder string) +
JWT_SECRET_KEY set, per-file (not the whole tests/ dir):

    ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
    JWT_SECRET_KEY=test-secret pytest tests/test_exceptions.py -x
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import AuditLog
from app.auth.schemas import CurrentUser
from app.exceptions.models import ExceptionRecord
from app.exceptions.service import active_exception_subquery
from app.vulnerabilities.models import Vulnerability


def _seed_asset(tenant_id: uuid.UUID) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:6]}",
        os_name="Ubuntu 22.04",
    )


def _seed_vuln(tenant_id: uuid.UUID, *, asset_id: uuid.UUID | None = None, status: str = "OPEN") -> Vulnerability:
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        asset_id=asset_id,
        cve_id=f"CVE-EXC-{uuid.uuid4().hex[:6]}",
        severity="HIGH",
        status=status,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        first_detected_at=now - timedelta(days=3),
        last_seen_at=now,
    )


def _seed_exception(
    tenant_id: uuid.UUID,
    *,
    vulnerability_id: uuid.UUID,
    cve_id: str,
    approver_user_id: uuid.UUID,
    granted_by_user_id: uuid.UUID,
    expires_at: datetime,
    exc_type: str = "ACCEPTED_RISK",
    scope_type: str = "FINDING",
    revoked_at: datetime | None = None,
) -> ExceptionRecord:
    """Directly-inserted exception row, bypassing the grant endpoint --
    used for the expiry cases (RESEARCH: compute-on-read means no tick is
    needed to resurface, so an explicit past `expires_at` proves EXC-04
    without invoking any scheduler)."""
    return ExceptionRecord(
        tenant_id=tenant_id,
        type=exc_type,
        scope_type=scope_type,
        cve_id=cve_id,
        vulnerability_id=vulnerability_id,
        justification="Seeded directly for tracer test",
        approver_user_id=approver_user_id,
        granted_by_user_id=granted_by_user_id,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _analyst_user_for(tenant_id: uuid.UUID) -> CurrentUser:
    """An ad hoc ANALYST `CurrentUser` scoped to `tenant_id` -- no DB row
    needed since `client_factory`'s dependency override bypasses
    `get_current_user` entirely (mirrors test_campaigns.py's
    `_analyst_user_for`)."""
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"analyst-{uuid.uuid4().hex[:8]}@test.local",
        role="ANALYST",
    )


async def _audit_rows(db_session, tenant_id: uuid.UUID, action: str, resource_id: str) -> list[AuditLog]:
    return list(
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action == action,
                    AuditLog.resource_id == resource_id,
                )
            )
        )
        .scalars()
        .all()
    )


def _grant_body(vuln_id: uuid.UUID, approver_id: uuid.UUID, *, exc_type: str = "ACCEPTED_RISK", days: int = 30) -> dict:
    return {
        "type": exc_type,
        "scope_type": "FINDING",
        "vulnerability_id": str(vuln_id),
        "justification": "Compensating control in place while vendor patch is scheduled",
        "approver_user_id": str(approver_id),
        "expires_at": (datetime.now(UTC) + timedelta(days=days)).isoformat(),
    }


# ── EXC-01 / D-06: all four fields (justification/approver/scope/expiry) mandatory ──


@pytest.mark.asyncio
async def test_grant_requires_all_fields(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """Omitting justification, approver, scope, or expiry each 422s --
    D-06's "all mandatory, for both types" (EXC-01)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    base_body = _grant_body(vuln.id, admin_user.id)
    analyst_client = client_factory(analyst_user)

    for missing_field in ("justification", "approver_user_id", "scope_type", "expires_at"):
        body = dict(base_body)
        del body[missing_field]
        r = await analyst_client.post("/api/v1/exceptions", json=body)
        assert r.status_code in (400, 422), f"missing {missing_field} -> {r.status_code}: {r.text}"

    # Sanity: the full body (nothing missing) DOES succeed, proving the 4
    # failures above are genuinely about the missing field, not something
    # else wrong with the request shape.
    r = await analyst_client.post("/api/v1/exceptions", json=base_body)
    assert r.status_code == 200, r.text


# ── EXC-02 / D-01: active exception excludes the finding from the active list ──


@pytest.mark.asyncio
async def test_finding_exception_excludes_from_list(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """Granting a FINDING-scoped active exception removes exactly that
    finding from GET /api/v1/vulnerabilities; a non-excepted control
    finding stays visible (EXC-02, D-10 -- never a blanket silence)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    excepted_vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    control_vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add_all([excepted_vuln, control_vuln])
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(excepted_vuln.id, admin_user.id))
    assert r.status_code == 200, r.text

    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()["items"]}
    assert str(excepted_vuln.id) not in ids, ids
    assert str(control_vuln.id) in ids, ids


# ── EXC-04 / D-04: compute-on-read auto-resurface, no scheduler; strict expiry-instant boundary ──


@pytest.mark.asyncio
async def test_expiry_auto_resurface_no_retrigger(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """A naturally-expired (unrevoked) exception's finding is present in
    `list_vulnerabilities` on the very next read -- no scheduler/tick is
    ever invoked in this test, proving the resurface is free
    (compute-on-read, EXC-04/D-04). Also asserts the exact-instant
    boundary directly against the shared seam: `expires_at == now` must
    already read as LAPSED (the join uses a strict `expires_at > now`),
    tested precisely (not via a real-wall-clock race) by querying
    `active_exception_subquery` with a `now` pinned to the row's own
    `expires_at`.
    """
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    lapsed_vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    boundary_vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add_all([lapsed_vuln, boundary_vuln])
    await db_session.flush()

    lapsed_exc = _seed_exception(
        tenant_a,
        vulnerability_id=lapsed_vuln.id,
        cve_id=lapsed_vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    boundary_instant = datetime.now(UTC)
    boundary_exc = _seed_exception(
        tenant_a,
        vulnerability_id=boundary_vuln.id,
        cve_id=boundary_vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        expires_at=boundary_instant,
    )
    db_session.add_all([lapsed_exc, boundary_exc])
    await db_session.commit()

    # EXC-04/D-04: no scheduler/tick invoked anywhere in this test -- a
    # plain read is all it takes for the lapsed exception's finding to
    # resurface.
    analyst_client = client_factory(analyst_user)
    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()["items"]}
    assert str(lapsed_vuln.id) in ids, ids

    # Exact-instant boundary: `now == expires_at` must be lapsed (strict >).
    row = (
        await db_session.execute(
            select(
                Vulnerability.id,
                active_exception_subquery(tenant_a, boundary_instant).label("is_excepted"),
            ).where(Vulnerability.id == boundary_vuln.id)
        )
    ).one()
    assert row.is_excepted is False, "now == expires_at must be treated as lapsed, not active"


# ── Pattern 4 / EXC-03/EXC-04: lazy-on-read expiry audit fires exactly once ──


@pytest.mark.asyncio
async def test_expiry_lazy_audit_once(client_factory, db_session, tenant_a, analyst_user, admin_user, viewer_user):
    """The FIRST GET /api/v1/exceptions after a natural (unrevoked) expiry
    writes exactly one system-attributed `exception.expire` audit row and
    stamps `resurfaced_audited_at`; a SECOND GET writes no additional row
    (Pattern 4's idempotent guard)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.flush()

    expired_exc = _seed_exception(
        tenant_a,
        vulnerability_id=vuln.id,
        cve_id=vuln.cve_id,
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(expired_exc)
    await db_session.commit()
    exception_id = str(expired_exc.id)

    viewer_client = client_factory(viewer_user)
    r1 = await viewer_client.get("/api/v1/exceptions")
    assert r1.status_code == 200, r1.text

    rows_after_first = await _audit_rows(db_session, tenant_a, "exception.expire", exception_id)
    assert len(rows_after_first) == 1, rows_after_first
    assert rows_after_first[0].user_id is None
    assert rows_after_first[0].user_email == "system:exception-expiry"

    await db_session.refresh(expired_exc)
    assert expired_exc.resurfaced_audited_at is not None

    r2 = await viewer_client.get("/api/v1/exceptions")
    assert r2.status_code == 200, r2.text
    rows_after_second = await _audit_rows(db_session, tenant_a, "exception.expire", exception_id)
    assert len(rows_after_second) == 1, rows_after_second  # idempotent -- no duplicate on re-read


# ── D-17: early revocation immediately resurfaces ──


@pytest.mark.asyncio
async def test_early_revoke_resurfaces(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """Grant -> finding absent from the active list; POST /{id}/revoke ->
    finding present again on the very next read (D-17)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(vuln.id, admin_user.id))
    assert r.status_code == 200, r.text
    exception_id = r.json()["id"]

    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) not in ids, ids

    r = await analyst_client.post(f"/api/v1/exceptions/{exception_id}/revoke")
    assert r.status_code == 200, r.text

    r = await analyst_client.get("/api/v1/vulnerabilities", params={"page_size": 200})
    ids = {item["id"] for item in r.json()["items"]}
    assert str(vuln.id) in ids, ids


# ── EXC-03: grant/revoke audit payload shape, exactly one row each ──


@pytest.mark.asyncio
async def test_grant_revoke_audit_payload(client_factory, db_session, tenant_a, analyst_user, admin_user):
    """Exactly one `exception.grant` audit row (payload has type/
    scope_type/cve_id/approver_user_id/justification/expires_at) and
    exactly one `exception.revoke` row (real analyst actor) -- EXC-03's
    who/why/scope/expiry."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    body = _grant_body(vuln.id, admin_user.id, exc_type="FALSE_POSITIVE")
    r = await analyst_client.post("/api/v1/exceptions", json=body)
    assert r.status_code == 200, r.text
    exception_id = r.json()["id"]

    grant_rows = await _audit_rows(db_session, tenant_a, "exception.grant", exception_id)
    assert len(grant_rows) == 1, grant_rows
    payload = grant_rows[0].details
    assert payload["type"] == "FALSE_POSITIVE"
    assert payload["scope_type"] == "FINDING"
    assert payload["cve_id"] == vuln.cve_id
    assert payload["approver_user_id"] == str(admin_user.id)
    assert payload["justification"] == body["justification"]
    assert datetime.fromisoformat(payload["expires_at"]) == datetime.fromisoformat(body["expires_at"])
    assert grant_rows[0].user_email == analyst_user.email

    r = await analyst_client.post(f"/api/v1/exceptions/{exception_id}/revoke")
    assert r.status_code == 200, r.text

    revoke_rows = await _audit_rows(db_session, tenant_a, "exception.revoke", exception_id)
    assert len(revoke_rows) == 1, revoke_rows
    assert revoke_rows[0].user_email == analyst_user.email


# ── T-39-01: cross-tenant exception_id 404s (IDOR) ──


@pytest.mark.asyncio
async def test_cross_tenant_404(client_factory, db_session, tenant_a, tenant_b, analyst_user, admin_user):
    """Another tenant's exception_id 404s on revoke -- tenant-scoped
    lookup, never fetch-then-403 (existence stays private, T-39-01)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(vuln.id, admin_user.id))
    assert r.status_code == 200, r.text
    exception_id = r.json()["id"]

    tenant_b_client = client_factory(_analyst_user_for(tenant_b))
    r = await tenant_b_client.post(f"/api/v1/exceptions/{exception_id}/revoke")
    assert r.status_code == 404, r.text


# ── T-39-01 (self-review addendum): approver must be a same-tenant user ──


@pytest.mark.asyncio
async def test_grant_rejects_cross_tenant_approver(
    client_factory, db_session, tenant_a, tenant_b, analyst_user, admin_user
):
    """A grant naming another tenant's user as approver_user_id is
    rejected with 400, not silently accepted -- D-08's "tenant-user
    reference" is enforced at write time. Without this check, the FK
    alone would accept any existing user id regardless of tenant, and
    that cross-tenant user's display_name/email would later be resolvable
    via GET /api/v1/exceptions' approver_display_name lookup (an IDOR/
    information-disclosure gap, not just a data-integrity nicety)."""
    await db_session.commit()
    asset = _seed_asset(tenant_a)
    db_session.add(asset)
    await db_session.flush()
    vuln = _seed_vuln(tenant_a, asset_id=asset.id)
    db_session.add(vuln)
    await db_session.commit()

    # A real, persisted user -- but in tenant_b, not tenant_a.
    from app.tenants.models import User

    foreign_approver = User(
        tenant_id=tenant_b,
        email=f"foreign-approver-{uuid.uuid4().hex[:8]}@test.local",
        display_name="Foreign Approver",
        role="ADMIN",
        idp_subject=f"test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(foreign_approver)
    await db_session.commit()

    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(vuln.id, foreign_approver.id))
    assert r.status_code == 400, r.text

    # A same-tenant approver (admin_user, tenant_a) still succeeds --
    # proves the 400 above is specifically about tenant mismatch, not a
    # broken approver check in general.
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(vuln.id, admin_user.id))
    assert r.status_code == 200, r.text
