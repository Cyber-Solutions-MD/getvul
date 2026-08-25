# Phase 41: Coverage & Blind-Spot Detection - Pattern Map

**Mapped:** 2026-08-20
**Files analyzed:** 25 (17 new, 8 modified — 3 of the modified files are CONDITIONAL on a planner scoping decision, see `## Conditional Files`)
**Analogs found:** 25 / 25 — zero files with no analog. Every "hard part" of this phase (RBAC, audit, tenant-scoped 404, JSONB reconciliation, owner resolution + fallback, `DrillPanel` generalized `idKey`, mutation-hook toast/invalidate) already ships elsewhere in the codebase; Phase 41 is pure composition.

## Research Corrections Applied

The prompt flagged four RESEARCH.md corrections; all four are baked into the assignments below, not just noted:
1. **DrillPanel idKey precedent = tickets list page, NOT `/assets`.** `frontend/src/app/(authed)/dashboard/assets/page.tsx` deliberately navigates full-page (`router.push`) — its own header comment says "drill happens on the detail page, not in a panel on the list." The real `idKey`/`renderContent` precedent is `frontend/src/app/(authed)/dashboard/tickets/page.tsx:349-394` (`idKey="ticket"`). Coverage's blind-spot list must copy the tickets shape, `idKey="asset"`.
2. **RBAC = `app.auth.rbac.require_viewer`/`require_analyst`, never `app.auth.dependencies.require_role`.** `backend/app/assets/router.py` (the file this phase touches most for `get_directory_user`) still imports the legacy `require_role` — do not copy that import. Every v5.0 module (`exceptions/router.py`, `campaigns/router.py`) uses the `app.auth.rbac` singletons; Phase 41 must too.
3. **Route = `/dashboard/coverage`, not `/coverage`.** Confirmed against `frontend/src/components/shell/nav-items.ts` and `frontend/e2e/routes.ts`'s `STATIC_ROUTES` — every sibling destination lives under `/dashboard/{slug}`.
4. **`_fire_kev_epss_alert` (`backend/app/notifications/alerts.py:365-465`) is the resolve→notify-or-fallback→audit template for COV-03**, adapted to use `audit()` (not raw `AuditLog(...)`) because Phase 41 runs inside an authenticated HTTP request, not the scheduler's `user=None` context.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/coverage/__init__.py` | config (package marker) | n/a | `backend/app/exceptions/__init__.py` | exact (trivial) |
| `backend/app/coverage/router.py` | controller | request-response | `backend/app/exceptions/router.py` | exact |
| `backend/app/coverage/service.py` | service | CRUD (reads) + event-driven (write) | `backend/app/assets/router.py` (reconciliation query) + `backend/app/notifications/alerts.py::_fire_kev_epss_alert` (resolve-notify) | exact (composite) |
| `backend/app/coverage/schemas.py` | model (Pydantic schema) | transform | `backend/app/exceptions/schemas.py` | exact |
| `backend/tests/test_coverage.py` | test | request-response | `backend/tests/test_exceptions.py` + `backend/tests/test_campaigns.py` (RBAC-403 case) | exact |
| `backend/app/main.py` (modified) | config | n/a | itself — existing `include_router` block | exact |
| `backend/app/audit.py` (modified, comment-only) | utility | n/a | itself — existing action-name comment block | exact |
| `backend/app/connectors/intune_sync.py` (modified) — **CONDITIONAL** | service | batch (sync job) | `backend/app/connectors/jamf_sync.py` / `connectors/sync.py`'s correct `SyncLog(...)` construction | exact (defect fix, not new pattern) |
| `backend/app/notifications/alerting_config.py` (modified) — **CONDITIONAL** | config | transform | itself — existing `DEFAULT_ALERTING_CONFIG["routing"]` dict | exact |
| `backend/tests/test_intune_sync.py` (modified) — **CONDITIONAL** | test | batch | itself — existing pure-helper unit tests | exact |
| `frontend/src/app/(authed)/dashboard/coverage/page.tsx` | component (route/page) | request-response | `frontend/src/app/(authed)/dashboard/tickets/page.tsx` (DrillPanel wiring) + `.../assets/page.tsx` (chip-bar/list/skeleton/empty scaffolding) | exact (composite) |
| `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` | test | request-response | `frontend/src/app/(authed)/dashboard/assets/page.test.tsx` | exact |
| `frontend/src/components/coverage/coverage-connector-card.tsx` | component | request-response | `frontend/src/components/connectors/connector-card.tsx` | exact |
| `frontend/src/components/coverage/coverage-connector-card.test.tsx` | test | request-response | `frontend/src/components/connectors/connector-card.test.tsx` | exact |
| `frontend/src/components/coverage/coverage-asset-drill-content.tsx` | component | request-response | `frontend/src/components/tickets/ticket-drill-content.tsx` | exact |
| `frontend/src/components/coverage/route-to-owner-dialog.tsx` | component | request-response (mutation trigger) | `frontend/src/components/ui/ConfirmModal.tsx` (primary — 2-branch, no form fields) + `frontend/src/components/exceptions/exception-grant-dialog.tsx` (secondary — dialog chrome/error-banner conventions) | exact |
| `frontend/src/components/coverage/route-to-owner-dialog.test.tsx` | test | request-response | `frontend/src/components/exceptions/exceptions-table.test.tsx` (ConfirmModal usage assertions) | role-match |
| `frontend/src/components/coverage/microcopy.ts` | utility (copy) | n/a | `frontend/src/components/assets/microcopy.ts` | exact |
| `frontend/src/lib/queries/use-coverage-summary.ts` | hook | request-response | `frontend/src/lib/queries/use-exceptions.ts` (no-filter GET) | exact |
| `frontend/src/lib/queries/use-blind-spot-assets.ts` | hook | request-response | `frontend/src/lib/queries/use-assets.ts` (paginated GET) | exact |
| `frontend/src/lib/queries/use-route-to-owner.ts` | hook | request-response (mutation) | `frontend/src/lib/queries/use-reassign-asset.ts` | exact |
| `frontend/src/lib/queries/use-route-to-owner.test.tsx` | test | request-response | `frontend/src/lib/queries/use-reassign-asset.test.tsx` | exact |
| `frontend/src/lib/queries/keys.ts` (modified) | utility | n/a | itself — existing `exceptions`/`campaigns` key-group entries | exact |
| `frontend/src/components/shell/nav-items.ts` (modified) | config | n/a | itself — existing `WORKFLOW_ITEMS` entries | exact |
| `frontend/e2e/routes.ts` (modified) | config/test-fixture | n/a | itself — existing `STATIC_ROUTES` array | exact |

## Conditional Files

Three modified files are **not automatically in scope** — RESEARCH.md's Open Questions #1 and #6 explicitly say to raise these to the planner rather than silently deciding:

- **`backend/app/connectors/intune_sync.py` + `backend/tests/test_intune_sync.py`** (Open Question 6 / Pitfall 1): `run_intune_sync` cannot currently write to the database at all (verified defect, not a hypothesis — see Pattern Assignment below). If Intune-sync is left broken, any Intune-only tenant sees the D-11 "no inventory" empty state forever, which undercuts D-01. Fixing it is a small, contained, independently testable change. Patterns are included below either way.
- **`backend/app/notifications/alerting_config.py`** (Open Question 1 / Pitfall 7): D-09's "tenant alert channel" fallback leg has no ready-made routing key (`DEFAULT_ALERTING_CONFIG["routing"]` has exactly 3 keys, none for coverage). The email-to-admins leg of D-09 is fully satisfiable without touching this file (`_email_owners_and_admins` alone). Only add the routing key + channel-dispatch leg if the planner wants D-09's "and the tenant alert channel" phrase taken literally this phase.

---

## Pattern Assignments

### `backend/app/coverage/__init__.py`

**Analog:** `backend/app/exceptions/__init__.py` — an empty or near-empty package marker. No excerpt needed; every sibling v5.0 domain package (`exceptions/`, `campaigns/`) is a bare `__init__.py`.

---

### `backend/app/coverage/router.py` (controller, request-response)

**Analog:** `backend/app/exceptions/router.py` (155 lines, read in full)

**Module-level framing** (lines 1-13) — copy this docstring shape (what each endpoint does + which threat/decision IDs it satisfies):
```python
"""Exception API routes (Phase 39 Plan 01 -- EXC-01/EXC-02/EXC-03/EXC-04
tracer slice; ...):
POST / (grant), GET / (list, runs the Pattern 4 expiry-audit sweep first),
POST /{id}/revoke.

Mirrors `campaigns/router.py`'s shape throughout: `_get_exception_or_404`
tenant-scoped lookup (T-39-01 IDOR -- cross-tenant 404s, never
fetch-then-403), `require_analyst` on writes / `require_viewer` on list
(T-39-02, D-09), and audit-then-commit ordering exactly as `ignore_cve`
(T-39-04 -- any audit failure aborts the whole write since `db.commit()`
never runs).
"""
```

**Imports pattern** (lines 15-34) — note `app.auth.rbac`, NOT `app.auth.dependencies.require_role` (Pitfall 4 — the codebase has two parallel RBAC systems, `assets/router.py` is the one file that still uses the legacy one, do not copy from it here):
```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.audit import audit
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.dependencies import DBSession
from app.exceptions.models import ExceptionRecord
from app.exceptions.schemas import ExceptionCreate, ExceptionResponse
from app.exceptions.service import grant_exception, list_exceptions, revoke_exception, sweep_expired_audits
from app.tenants.models import User

router = APIRouter()
```
For `coverage/router.py`, this becomes `from app.auth.rbac import require_analyst, require_viewer` (identical), `from app.coverage.service import get_coverage_summary, list_blind_spot_assets, route_to_owner`, `from app.coverage.schemas import CoverageSummaryResponse, BlindSpotAssetListResponse, RouteToOwnerResponse`.

**Tenant-scoped 404 helper** (lines 37-47) — this is the IDOR pattern (Security Domain table: "IDOR on the blind-spot list / route-to-owner endpoint... tenant_id in the WHERE clause on every lookup; 404 (not 403) on a cross-tenant id"). Copy verbatim, retarget to `Asset`:
```python
async def _get_exception_or_404(db: DBSession, tenant_id: uuid.UUID, exception_id: uuid.UUID) -> ExceptionRecord:
    """T-39-01 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant exception_id must 404, never a
    fetch-then-403 (mirrors campaigns/router.py::_get_campaign_or_404)."""
    result = await db.execute(
        select(ExceptionRecord).where(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    return record
```
Coverage's version: `_get_asset_or_404(db, tenant_id, asset_id) -> Asset`, same shape, message `"Asset not found"`.

**RBAC-gated GET (viewer) pattern** (lines 118-130):
```python
@router.get("", response_model=list[ExceptionResponse])
async def list_exceptions_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> list[ExceptionResponse]:
    ...
    records = await list_exceptions(db, user.tenant_id)
    return await _to_responses(db, user.tenant_id, records)
```
Coverage needs two `require_viewer` GETs: `GET /summary` (COV-02) and `GET /blind-spots` (COV-01), both delegating to `service.py` functions that take `db` + `user.tenant_id`.

**RBAC-gated mutation (analyst) + audit-then-commit pattern** (lines 133-155) — this is the exact shape for `POST /assets/{asset_id}/route-to-owner`:
```python
@router.post("/{exception_id}/revoke", response_model=ExceptionResponse)
async def revoke_exception_endpoint(
    exception_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> ExceptionResponse:
    """... Audited with who/when (EXC-03). WR: idempotent guard -- 409 on
    an already-revoked exception rather than silently overwriting..."""
    record = await _get_exception_or_404(db, user.tenant_id, exception_id)
    if record.revoked_at is not None:
        raise HTTPException(409, "Exception is already revoked.")
    now = datetime.now(UTC)
    revoke_exception(record, user.id, now)

    await compute_risk_scores(db, user.tenant_id)
    await audit(db, user, "exception.revoke", "exception", str(record.id), {"revoked_by_user_id": str(user.id)})
    await db.commit()
    return (await _to_responses(db, user.tenant_id, [record]))[0]
```
Coverage's `route_to_owner_endpoint` mirrors this exactly: `_get_asset_or_404` → call `service.route_to_owner(db, user, asset)` (which internally resolves owner, sends the notification, and returns a result dict) → `audit(db, user, "coverage.route_to_owner", "asset", str(asset.id), {...})` → `await db.commit()`. No `compute_risk_scores` call needed (a blind-spot asset has no findings to re-score). No 409-idempotency guard is needed here (unlike revoke) since route-to-owner is a repeatable notify action, not a state transition — confirm this with the planner if idempotency-guarding repeated notifications is desired.

---

### `backend/app/coverage/service.py` (service, CRUD reads + event-driven write)

This file has two structurally distinct halves with two different analogs.

**Half A — reconciliation queries (COV-01/COV-02).** Analog: `backend/app/assets/router.py`'s existing `.contains()` facet-filter block (lines 82-170, read in full) generalized per RESEARCH.md's Code Example B.

**Imports + source partition** (constants file read in full, `backend/app/assets/constants.py`):
```python
from app.vulnerabilities.models import VulnSource

SCANNER_SOURCES: frozenset[str] = frozenset(s.value for s in VulnSource)
ENRICHMENT_SOURCES: frozenset[str] = frozenset({"JAMF", "HUMAANS", "INTUNE"})
```

**The existing `.contains()` idiom to generalize** (`backend/app/assets/router.py:126-152`):
```python
if scanner:
    # seen_by_sources is a JSONB array like ["CROWDSTRIKE", "NESSUS"].
    # SRC-03 bug fix: OR-default via `or_(*contains)`, true-AND gated
    # behind the explicit `source_mode=and` toggle. SRC-06: clamped to
    # SCANNER_SOURCES so an enrichment source can never leak into a
    # scanner-corroboration filter.
    from sqlalchemy import false, or_

    scanners = [s.strip().upper() for s in scanner.split(",") if s.strip()]
    scanners = [s for s in scanners if s in SCANNER_SOURCES]
    if scanners:
        if mode == "and":
            for s in scanners:
                query = query.where(Asset.seen_by_sources.contains([s]))
        else:
            query = query.where(or_(*[Asset.seen_by_sources.contains([s]) for s in scanners]))
    else:
        query = query.where(false())
```
Coverage's blind-spot query (D-01/D-02) is the AND of "authoritative" (OR across `ENRICHMENT_SOURCES`) and "never scanned" (NOT OR across `SCANNER_SOURCES`) — same `.contains()` primitive, different boolean composition:
```python
from sqlalchemy import not_, or_, select
from app.assets.constants import ENRICHMENT_SOURCES, SCANNER_SOURCES
from app.assets.models import Asset

authoritative = or_(*[Asset.seen_by_sources.contains([e]) for e in ENRICHMENT_SOURCES])   # D-01
never_scanned = not_(or_(*[Asset.seen_by_sources.contains([s]) for s in SCANNER_SOURCES]))  # D-02

blind_spots = select(Asset).where(
    Asset.tenant_id == tenant_id,
    Asset.is_ignored.is_(False),   # mirrors list_assets' default (assets/router.py:117)
    authoritative,
    never_scanned,
)
```

**Per-connector coverage % + staleness** (COV-02) — reuses the same `authoritative` filter as a denominator, iterates `ConnectorConfig` rows for the numerator, and MUST wire-normalize `last_sync_status` through `_normalize_sync_status` (Pitfall 3) — `backend/app/connectors/service.py:29-44` (read in full):
```python
# Wire-boundary normalization (CR-06 precedent): the DB/sync harness only ever
# writes uppercase "SUCCESS"/"FAILED"/None to last_sync_status (see sync.py),
# but the frontend SyncStatusPill union is 'ok'|'failed'|'syncing'|null.
_SYNC_STATUS_MAP = {"SUCCESS": "ok", "FAILED": "failed", "SYNCING": "syncing"}

def _normalize_sync_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    return _SYNC_STATUS_MAP.get(raw, raw)
```
Import `_normalize_sync_status` from `app.connectors.service` directly — do not re-derive the map (Pitfall 3's exact warning: "a function the new `app/coverage/service.py` won't inherit automatically just by importing `ConnectorConfig`"). `ConnectorConfig`'s sync-health fields (`backend/app/ticketing/models.py:39-56`, read in full):
```python
class ConnectorConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "connector_configs"
    tenant_id: Mapped[uuid.UUID] = mapped_column(...)
    connector_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(20))
    last_sync_record_count: Mapped[int | None] = mapped_column(Integer)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    consecutive_failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```
D-06's fixed 7-day stale threshold is a one-line comparison: `is_stale = bool(conn.last_sync_at and (now - conn.last_sync_at) > timedelta(days=7))`.

**Half B — resolve-then-notify-with-fallback (COV-03, D-07/D-09).** Analog: `backend/app/notifications/alerts.py::_fire_kev_epss_alert` (lines 365-465, read in full) — **this is the exact resolve→notify-or-fallback→audit template the prompt flagged**:
```python
async def _fire_kev_epss_alert(
    db: AsyncSession, tenant: Tenant, vuln: Vulnerability, asset: Asset | None,
    trigger_type: str, config: dict[str, Any],
) -> None:
    from app.assets.directory import get_directory_user
    from app.audit import AuditLog
    from app.notifications.escalation_channels import dispatch_channel
    from app.notifications.service import _send_notification_email
    from app.vulnerabilities.sla_tier_service import _build_channel_config

    hostname = asset.hostname if asset else "Unknown host"
    title = f"New {trigger_type.upper()} Match: {vuln.cve_id}"
    message = f"{vuln_name} on {hostname} newly qualifies for {trigger_type.upper()} alerting"

    # D-10 (this phase's D-09 equivalent): resolved owner gets emailed
    # directly; an unresolved owner falls back to OWNER/ADMIN users.
    directory_user = await get_directory_user(db, tenant.id, asset) if asset is not None else None
    if directory_user and directory_user.get("email"):
        await _send_notification_email(db, tenant.id, directory_user["email"], title, message, "new_kev_epss")
    else:
        await _email_owners_and_admins(db, tenant, title, message, "new_kev_epss")

    # D-07/D-19: tenant channel push — fail-isolated, never blocks the rest.
    sla_config = tenant.sla_config or {}
    routing = config.get("routing") or {}
    channels = routing.get("new_kev_epss") or []
    for channel in channels:
        try:
            channel_config = _build_channel_config(sla_config, channel, tenant)
            outcome = await dispatch_channel(channel, channel_config, {...})
        except Exception as e:
            outcome = {"ok": False, "error": str(e)}
        if not outcome.get("ok"):
            logger.warning("kev_epss_channel_dispatch_failed", ...)

    db.add(AuditLog(tenant_id=tenant.id, user_id=None, user_email="system:scheduler", action="alert.fire", ...))
```
**Owner resolution** (`backend/app/assets/directory.py`, read in full — 67 lines):
```python
async def get_directory_user(db: AsyncSession, tenant_id: uuid.UUID, asset: Asset) -> dict[str, Any] | None:
    """Precedence: MDM `humaans_email` -> `assigned_user` -> `last_login_user`
    (first email that resolves to a real, tenant-scoped `User` row wins)."""
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
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, or_(*[User.email == e for e in emails_to_try])).limit(1)
    )
    u = result.scalar_one_or_none()
    if not u:
        return None
    return {"email": u.email, "display_name": u.display_name, ...}
```
**Admin fallback** (`backend/app/notifications/alerts.py:496-521`, read in full):
```python
async def _email_owners_and_admins(db: AsyncSession, tenant: Tenant, title: str, message: str, category: str) -> None:
    """Send notification email to all OWNER and ADMIN users of a tenant."""
    users = (await db.execute(
        select(User).where(User.tenant_id == tenant.id, User.is_active.is_(True), User.role.in_(["OWNER", "ADMIN"]))
    )).scalars().all()
    for user in users:
        await _send_notification_email(db, tenant.id, user.email, title, message, category)
```

**Critical adaptation — the ONE thing to change, not copy:** `_fire_kev_epss_alert` runs in the scheduler (`user=None`), so it constructs `AuditLog(...)` directly and never calls `db.commit()` itself (the router's caller commits). Coverage's `route_to_owner` runs inside an **authenticated HTTP request** — a real `CurrentUser` exists — so it must call the standard `audit()` helper (`backend/app/audit.py`, read in full) instead, and `service.py`'s `route_to_owner()` function should NOT commit (leave `await db.commit()` to `router.py`, matching the exceptions/campaigns convention above). Anti-Pattern explicitly called out in RESEARCH.md: *"Don't construct `AuditLog(...)` directly. That raw-insert shape exists only because the scheduler has no `CurrentUser`."*

**Return-shape convention for the resolve leg** — the frontend copy contract needs `routed_to` (owner display name or `"your admins"`) and `hostname`, per RESEARCH.md's Pattern 2 worked example:
```python
directory_user = await get_directory_user(db, tenant_id, asset)
if directory_user and directory_user.get("email"):
    await _send_notification_email(db, tenant_id, directory_user["email"], title, message, "coverage_route_to_owner")
    routed_to = directory_user["display_name"] or directory_user["email"]
else:
    await _email_owners_and_admins(db, tenant, title, message, "coverage_route_to_owner")  # D-09
    routed_to = "your admins"
```

---

### `backend/app/coverage/schemas.py` (model/schema, transform)

**Analog:** `backend/app/exceptions/schemas.py` (101 lines, read in full)

**Mass-assignment defense + response shape conventions:**
```python
from __future__ import annotations
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ExceptionCreate(BaseModel):
    """`extra="forbid"` is a deliberate mass-assignment defense (T-39-06)."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["FALSE_POSITIVE", "ACCEPTED_RISK"]
    ...

class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ...
```
Coverage's request surface is the smallest of any v5.0 mutation to date (Security Domain table: "no free-text request body this phase" — D-09 rejected manual owner entry) — `route_to_owner` likely needs **no request body at all** (just a path-param `asset_id`), so `schemas.py` is mostly response models: `CoverageSummaryResponse` (list of per-connector cards + optional headline), `BlindSpotAssetResponse`/`BlindSpotAssetListResponse` (mirrors the existing `AssetsResponse` envelope — see `use-blind-spot-assets.ts` below), and `RouteToOwnerResponse` (`hostname: str`, `routed_to: str`). If planner decides `route_to_owner` needs a body eventually, follow `ExceptionCreate`'s `extra="forbid"` pattern, never a looser schema (Security Domain table's explicit mass-assignment guidance).

---

### `backend/tests/test_coverage.py` (test, request-response)

**Analogs:** `backend/tests/test_exceptions.py` (443 lines; targeted read of the cross-tenant-404 test) + `backend/tests/test_campaigns.py` (RBAC-403 pattern, since `test_exceptions.py` itself has no explicit viewer-403 test)

**Cross-tenant 404 (IDOR) test shape** (`backend/tests/test_exceptions.py:375-397`):
```python
# ── T-39-01: cross-tenant exception_id 404s (IDOR) ──
@pytest.mark.asyncio
async def test_cross_tenant_404(client_factory, db_session, tenant_a, tenant_b, analyst_user, admin_user):
    """Another tenant's exception_id 404s on revoke -- tenant-scoped
    lookup, never fetch-then-403 (existence stays private, T-39-01)."""
    ...
    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/exceptions", json=_grant_body(vuln.id, admin_user.id))
    exception_id = r.json()["id"]

    tenant_b_client = client_factory(_analyst_user_for(tenant_b))
    r = await tenant_b_client.post(f"/api/v1/exceptions/{exception_id}/revoke")
    assert r.status_code == 404, r.text
```
Coverage's version: `test_route_to_owner_cross_tenant_404` — create a blind-spot asset in tenant A, POST route-to-owner from a tenant-B client, assert 404.

**RBAC-403 test shape** (`backend/tests/test_campaigns.py:346-364`, since this is the actual viewer-gets-403 precedent in the codebase):
```python
@pytest.mark.asyncio
async def test_campaign_rbac(client_factory, db_session, tenant_a, analyst_user, viewer_user):
    """A viewer gets 403 on POST; a viewer CAN GET (list + detail)."""
    analyst_client = client_factory(analyst_user)
    r = await analyst_client.post("/api/v1/campaigns", json={...})
    assert r.status_code == 200, r.text
    campaign_id = r.json()["id"]

    viewer_client = client_factory(viewer_user)
    r = await viewer_client.post("/api/v1/campaigns", json={...})
    assert r.status_code == 403, r.text

    r = await viewer_client.get("/api/v1/campaigns")
    assert r.status_code == 200, r.text
```
Coverage's `test_route_to_owner_rbac`: viewer GETs `/summary` and `/blind-spots` → 200; viewer POSTs `/route-to-owner` → 403; analyst POSTs same → 200.

**Audit-row assertion helper** (`backend/tests/test_exceptions.py:30, 103`):
```python
from app.audit import AuditLog

async def _audit_rows(db_session, tenant_id: uuid.UUID, action: str, resource_id: str) -> list[AuditLog]:
    ...
```
Reuse this helper shape for `test_route_to_owner_resolved`/`test_route_to_owner_fallback` — assert exactly one `coverage.route_to_owner` row with `details["routed_to"]` matching the resolved-owner vs. `"your admins"` branch.

**Env-var gotcha (MEMORY.md `getvul-backend-pytest-env`):** run per-file with `ENCRYPTION_KEY`/`JWT_SECRET_KEY` set, never the whole `tests/` directory — confirmed again in RESEARCH.md's Test Framework table.

---

### `backend/app/main.py` (modified, config)

**Pattern — router registration** (`backend/app/main.py:31, 36, 320-321`, grep-verified):
```python
from app.campaigns.router import router as campaigns_router
from app.exceptions.router import router as exceptions_router
...
app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(exceptions_router, prefix="/api/v1/exceptions", tags=["Exceptions"])
```
Add, alphabetically near these two: `from app.coverage.router import router as coverage_router` and `app.include_router(coverage_router, prefix="/api/v1/coverage", tags=["Coverage"])`.

---

### `backend/app/audit.py` (modified, comment-only, utility)

**Pattern — the action-name reference list** (lines 53-80, read in full; not an enforced enum, developer reference only):
```python
# ── Actions ──
...
# exception.grant, exception.revoke (Phase 39 Plan 01 -- EXC-01/EXC-03,
#   analyst-actor, audit-then-commit), exception.expire (Phase 39 Plan 01 --
#   EXC-03/EXC-04, system actor "system:exception-expiry", lazy-on-read
#   Pattern 4 sweep guarded by resurfaced_audited_at IS NULL so it fires
#   exactly once per naturally-lapsed exception)
```
Append a new block: `# coverage.route_to_owner (Phase 41 -- COV-03, analyst-actor, audit-then-commit; details={hostname, routed_to})`. RESEARCH.md flags this explicitly ("Whoever implements COV-03 should append `coverage.route_to_owner` to that list for consistency").

---

### `backend/app/connectors/intune_sync.py` (CONDITIONAL — Pitfall 1 defect fix)

**The verified defect** (`backend/app/connectors/intune_sync.py:122-129`, read in full):
```python
sync_log = SyncLog(
    connector_config_id=connector_config.id,   # BUG: SyncLog has no such field (only connector_id)
    status="running",                           # BUG: lowercase; SyncStatus enum + _normalize_sync_status expect uppercase
    started_at=datetime.now(UTC),
    records_fetched=0,
    records_created=0,
    records_updated=0,
    # BUG: tenant_id is required (NOT NULL, indexed) and is never passed
)
```
Confirmed against the real model (`backend/app/ticketing/models.py:60-76`, read in full):
```python
class SyncLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sync_logs"
    connector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("connector_configs.id", ...), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    ...
```
SQLAlchemy's declarative `__init__` raises `TypeError` on `connector_config_id=...` immediately — this crashes before `db.add()`/`db.flush()` ever runs, on every single Intune sync attempt, for every tenant. Additionally (masked by the crash today): the two `select(Asset).where(Asset.hostname == device_name)` / `select(Asset).where(Asset.serial_number == serial)` lookups (lines 153, 158) and `Asset(hostname=device_name)` (line 165) carry **no `tenant_id`** at all — a naive fix of only the `SyncLog` kwargs would introduce a cross-tenant asset-matching bug.

**The correct pattern to copy** — every sibling sync file constructs `SyncLog` correctly. Fix shape (uppercase status matches `SyncStatus` enum in `ticketing/models.py:32-36` and `_normalize_sync_status`'s map):
```python
sync_log = SyncLog(
    connector_id=connector_config.id,
    tenant_id=connector_config.tenant_id,
    status="RUNNING",
    started_at=datetime.now(UTC),
    records_fetched=0, records_created=0, records_updated=0,
)
...
# both Asset lookups AND the Asset(...) constructor need:
select(Asset).where(Asset.tenant_id == connector_config.tenant_id, Asset.hostname == device_name)
select(Asset).where(Asset.tenant_id == connector_config.tenant_id, Asset.serial_number == serial)
Asset(tenant_id=connector_config.tenant_id, hostname=device_name)
```
Also: `sync_log.status = "success"` / `"error"` (lines 170, 181) should become `"SUCCESS"`/`"FAILED"` to match the enum and `_normalize_sync_status`'s map (only `SUCCESS`/`FAILED`/`SYNCING` are recognized; anything else falls through unchanged and `SyncStatusPill` degrades to `__never`).

**Existing test file to extend** (`backend/tests/test_intune_sync.py`, 79 lines, read in full) — currently tests only the pure helpers (`_parse_iso`, `_fetch_managed_devices`, `_enrich_asset`); `run_intune_sync` itself has zero test coverage today (its own docstring says "run_intune_sync itself is DB/graph integration"). A fix should add an integration test asserting a `SyncLog` row is actually created with `status="SUCCESS"` and `tenant_id` set correctly, mirroring whatever DB-integration test pattern `test_jamf_sync.py`/`test_humaans_sync.py` use (not read — check for the closest sibling test at implementation time).

---

### `backend/app/notifications/alerting_config.py` (CONDITIONAL — Open Question 1)

**Analog:** itself — the existing routing-key dict (76 lines, read in full):
```python
DEFAULT_ALERTING_CONFIG: dict[str, Any] = {
    "kev_enabled": True,
    "epss_threshold": 0.5,
    "cadence": "daily",
    "send_hour": 8,
    "per_owner_digests": True,
    "per_team_digests": True,
    "routing": {
        "new_kev_epss": ["slack"],   # ALERT-01 real-time push (D-07).
        "digest_owner": ["email"],   # ALERT-02 per-owner digest channel (D-09).
        "digest_team": ["slack"],    # ALERT-02 per-team digest channel (D-09).
    },
}

def merged_alerting_config(tenant: Any) -> dict[str, Any]:
    """Return `DEFAULT_ALERTING_CONFIG` overlaid with `tenant.alerting_config`."""
    overrides = getattr(tenant, "alerting_config", None) or {}
    merged: dict[str, Any] = {**DEFAULT_ALERTING_CONFIG, **overrides}
    merged["routing"] = {**DEFAULT_ALERTING_CONFIG["routing"], **(overrides.get("routing") or {})}
    return merged
```
If the planner scopes in a real channel-push leg for D-09 (rather than email-only), add a 4th routing key: `"coverage_unmanaged_asset": []` (empty default — `dispatch_channel` treats an unconfigured/empty channel list as a no-op per RESEARCH.md's Open Question 1 recommendation). This is a one-line, zero-migration change (the column is an unconstrained JSONB). **The lighter alternative — and the one that requires zero change to this file — is to satisfy D-09 with `_email_owners_and_admins` alone**, which already fully satisfies "notify admins"; only the "and the tenant alert channel" clause needs this file touched.

---

### `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (component/route, request-response)

**Analog A — DrillPanel wiring:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:349-394` (targeted read) — **this is the precedent, not `/assets`** (Pitfall 8 / research correction #1):
```tsx
{/* Drill panel — desktop (D-D-02, idKey="ticket") */}
<DrillPanel
  idKey="ticket"
  id={ticketIdFromUrl}
  ariaLabel="Ticket detail"
  renderContent={({ id, onClose }) => (
    <TicketDrillContent
      ticketId={id}
      ticket={selectedTicket ? { ...mapped fields... } : undefined}
      onClose={onClose}
      renderBlockedToggle={({ ticketId }) => (
        <BlockedToggle ... />
      )}
    />
  )}
/>
```
Coverage's version: `<DrillPanel idKey="asset" id={assetIdFromUrl} ariaLabel="Device detail" renderContent={({ id, onClose }) => <CoverageAssetDrillContent assetId={id} asset={selectedAsset} onClose={onClose} />} />`. Note `DrillPanel`'s own contract (`frontend/src/components/vulnerabilities/drill-panel.tsx`, 106 lines, read in full) is fully generalized already — `idKey`/`renderContent` are additive props, vuln callers still work via `cveId` back-compat defaults (lines 15-30, 39-40, 101-103). No changes needed to `drill-panel.tsx` itself.

**Analog B — chip-bar / skeleton / empty / error scaffolding:** `frontend/src/app/(authed)/dashboard/assets/page.tsx` (210 lines, read in full) — copy the state-branching shape (NOT the row-click handler):
```tsx
{q.error ? (
  <PartialFailureBanner errors={[{ code: 'http_error', requestId: String((q.error as Error).message) || 'unknown' }]} onRetry={() => q.refetch()} />
) : isLoading ? (
  <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
) : items.length === 0 ? (
  <EmptyState>
    <EmptyState.Title>{microcopy.empty.noResults.title}</EmptyState.Title>
    <EmptyState.Body>{microcopy.empty.noResults.body}</EmptyState.Body>
  </EmptyState>
) : (
  <>
    <AssetsTable rows={items} onRowOpen={onRowOpen} />
    {(q.data?.pages ?? 1) > 1 && <Pagination ... />}
  </>
)}
```
**WR-13 mutual-exclusivity note baked into this shape:** `q.error` is checked FIRST, before `isLoading`/`items.length === 0` — the assets page's own comment explains why (both branches would otherwise render simultaneously since `items` defaults to `[]` on error). Coverage's page has THREE empty-state branches to route between (D-11 no-inventory / "quiet win" all-covered / UI-SPEC's E4 backstop scanner-absent-but-inventory-present) — branch on the summary response's `total_authoritative_assets`/connector-count fields, not on `items.length` alone.

**Route + nav correction (Pitfall 2 / research correction #3):** file must live at `frontend/src/app/(authed)/dashboard/coverage/page.tsx` — NOT `frontend/src/app/coverage/page.tsx` (outside the authed shell, no sidebar/topbar/auth guard).

**RBAC-gating the "Route to owner" action (D-08, E2 partial-state row):** `frontend/src/app/(authed)/dashboard/connectors/page.tsx:98-99` shows the frontend role-check convention:
```tsx
import { useAuth } from '@/lib/auth';
...
const { user } = useAuth();
const isAdmin = user?.role === 'OWNER' || user?.role === 'ADMIN';
```
Coverage needs the analyst-or-higher variant: `const canRouteToOwner = user?.role === 'OWNER' || user?.role === 'ADMIN' || user?.role === 'ANALYST';` — pass down to the blind-spot list row action and the drill-panel content so a viewer sees the button disabled/hidden (never a 403 they have to react to; the backend 403 is defense-in-depth only, per every other v5.0 phase's asymmetric-RBAC precedent).

---

### `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` (test, request-response)

**Analog:** `frontend/src/app/(authed)/dashboard/assets/page.test.tsx` (110 lines, read in full):
```tsx
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => '/assets',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/queries/use-assets', async () => {
  const actual = await vi.importActual(...);
  return { ...actual, useAssets: vi.fn(() => ({ data: {...}, isPending: false, error: null, refetch })) };
});

function renderWithClient(ui) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}
```
Mirror this exactly, mocking `useCoverageSummary`/`useBlindSpotAssets`/`useRouteToOwner` instead of `useAssets`. Branch-coverage convention: one `it()` per state (loading/error/populated/each empty variant), matching this file's one-assertion-per-branch style rather than a single mega-test.

---

### `frontend/src/components/coverage/coverage-connector-card.tsx` (component, request-response)

**Analog:** `frontend/src/components/connectors/connector-card.tsx` (196 lines, read in full) — composes exactly the primitives UI-SPEC names:
```tsx
import { ConnectorMark } from './connector-mark';
import { SyncStatusPill } from './sync-status-pill';

<div data-connector-card data-enabled={connector.is_enabled} className="rounded-lg border border-border-subtle bg-surface-2 p-4 ...">
  <div className="flex items-start justify-between gap-2">
    <div className="flex min-w-0 items-center gap-2.5">
      <ConnectorMark provider={provider} className="shrink-0" />
      <span className="truncate text-sm font-medium text-text">{connector.connector_name}</span>
    </div>
    <SyncStatusPill status={connector.last_sync_status} className="shrink-0" />
  </div>
  <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
    <span>{syncTime}</span>
    ...
  </div>
  {connector.last_sync_status === 'failed' && (
    <details className="mt-2 rounded-md border border-severity-critical/30 bg-severity-critical/10 px-2.5 py-1.5 text-xs">
      ...
    </details>
  )}
</div>
```
`CoverageConnectorCard` swaps the metadata row and failure-detail `<details>` for: the 40px Display-size `{N}% covered` headline (UI-SPEC Typography — JetBrains Mono, `tabular-nums`), the 3-tier coverage-% color (UI-SPEC Color table: ≥90% `--color-success`, 50-89% `--color-warning`/`--color-amber`, <50% `--color-danger`), and the `stale · {N}d` amber pill (D-06) computed via the day-math helper below — alongside the SAME `SyncStatusPill` this card already reuses. `ConnectorMark`'s provider-gradient lookup (`frontend/src/components/connectors/connector-mark.tsx`, 85 lines, read in full) needs no changes — it already covers all 6 scanner providers (`crowdstrike, nessus, defender, wiz, qualys, rapid7` — Pitfall 6: these are the ONLY real values, "Tenable"/"AWS Inspector" from CLAUDE.md's product copy are not real `connector_type`s).

**Container:** `StatStrip` (`frontend/src/components/ui/stat-strip.tsx`, 41 lines, read in full) — a plain responsive grid, zero data logic:
```tsx
export function StatStrip({ children, className, ...rest }: StatStripProps) {
  const count = Children.count(children);
  const desktop = Math.min(count, 4);
  ...
  return <div className={cn('grid grid-cols-1 gap-4 md:grid-cols-2', desktopClass, className)} {...rest}>{children}</div>;
}
```
Wrap N `CoverageConnectorCard`s in `<StatStrip>` directly — no changes to `stat-strip.tsx` needed (UI-SPEC E1 "overflow" row explicitly confirms this: "`StatStrip` already owns its own responsive column ladder").

**Day-count helper (no date library — Don't Hand-Roll table):** `frontend/src/components/exceptions/exceptions-table.tsx:92-97` (targeted read):
```tsx
// "Nd ago" relative-day format (copy-voice.md: "3d left" not "3 days left").
function grantedAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const days = Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24));
  return days <= 0 ? 'Today' : `${days}d ago`;
}
```
Coverage's stale-badge copy (`stale · {N}d`) is the same math, different string template — do not add `date-fns`/`dayjs`.

---

### `frontend/src/components/coverage/coverage-asset-drill-content.tsx` (component, request-response)

**Analog:** `frontend/src/components/tickets/ticket-drill-content.tsx` (249 lines, read in full) — the exact `renderContent` slot-content shape paired with `idKey="ticket"`:
```tsx
type TicketDrillContentProps = {
  ticketId: string;
  ticket?: TicketDrillData;   // caller (list row) supplies pre-fetched summary — presentational only, no data fetching
  onClose: () => void;
  renderBlockedToggle?: (args: { ticketId: string }) => React.ReactNode;  // slot for a row-level action
};

export function TicketDrillContent({ ticketId, ticket, onClose, renderBlockedToggle }: TicketDrillContentProps) {
  if (!ticket) {
    return <div aria-busy="true" className="p-6 text-text-muted text-sm">Loading…</div>;
  }
  return (
    <div className="flex h-full flex-col">
      {/* Header: mark + mono ID + title + close button */}
      <div className="flex items-start justify-between border-b border-border-subtle px-5 py-4">
        ...
        <button type="button" onClick={onClose} aria-label="Close">...</button>
      </div>
      {/* Body: labeled <section aria-labelledby> blocks */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        <section aria-labelledby="tdrill-vulns-h">...</section>
        <section aria-labelledby="tdrill-status-h">...</section>
      </div>
      {/* Sticky footer: primary action buttons */}
      <div className="flex flex-col gap-2 border-t border-border-subtle p-4">
        <a href={externalUrl} ...>Open in {providerLabel}</a>
        <Link href={detailHref} className="... bg-gradient-sunset ...">Open full detail</Link>
        {renderBlockedToggle ? renderBlockedToggle({ ticketId }) : <button disabled>Mark blocked</button>}
      </div>
    </div>
  );
}
```
`CoverageAssetDrillContent` copies this exact 3-region shape: Header (hostname mono + device-category label + close), Body (sections: "Never scanned" badge + which authoritative source(s) placed it in the baseline + last-seen-by-authoritative-source), sticky Footer (single "Route to owner" button in place of the ticket's two-link footer — UI-SPEC explicitly says this is a secondary-weight action, so use the connectors-style bordered button, NOT the `bg-gradient-sunset` CTA class the ticket footer's "Open full detail" link uses — that gradient is reserved and this page has no page-level primary CTA per UI-SPEC's Design System section). The `!ticket`/`!asset` loading branch (`aria-busy="true"`, "Loading…") carries over verbatim.

---

### `frontend/src/components/coverage/route-to-owner-dialog.tsx` (component, request-response mutation trigger)

**Primary analog:** `frontend/src/components/ui/ConfirmModal.tsx` (114 lines, read in full) — UI-SPEC explicitly describes this dialog as "2 branches, no form fields," which is a confirm-dialog shape, not `ExceptionGrantDialog`'s 4-field form:
```tsx
interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
  children?: React.ReactNode;       // extra body content between message and action row
  confirmDisabled?: boolean;
}

export default function ConfirmModal({ open, title, message, confirmLabel = "Confirm", ..., onConfirm, onCancel, children, confirmDisabled = false }: ConfirmModalProps) {
  ...
  const btnColor = variant === "danger" ? "bg-severity-critical text-white ..." : variant === "warning" ? "bg-amber text-surface ..." : "bg-violet text-white ...";
  return (
    <ResponsiveDialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }} ariaLabel={title}>
      <div>
        <h3 className="text-lg font-semibold text-text">{title}</h3>
        <p className="mt-2 text-sm text-text-muted whitespace-pre-wrap">{message}</p>
        {children && <div className="mt-4">{children}</div>}
        <div className="mt-6 flex justify-end gap-3 pb-[env(safe-area-inset-bottom)]">
          <button onClick={onCancel}>{cancelLabel}</button>
          <button ref={confirmRef} onClick={onConfirm} disabled={confirmDisabled} className={`... ${btnColor}`}>{confirmLabel}</button>
        </div>
      </div>
    </ResponsiveDialog>
  );
}
```
**Real call-site precedent** (`frontend/src/components/exceptions/exceptions-table.tsx:363-375`, targeted read):
```tsx
<ConfirmModal
  open={revokeTarget !== null}
  title="Revoke this exception?"
  message={revokeMessage}
  confirmLabel="Revoke exception"
  cancelLabel="Cancel"
  variant="warning"
  confirmDisabled={revokeMutation.isPending}
  onConfirm={() => { revokeMutation.mutate(undefined, { onSuccess: () => setRevokeTarget(null) }); }}
  onCancel={() => setRevokeTarget(null)}
/>
```
**Two-branch requirement (D-07 resolved vs. D-09 unresolvable):** since `variant` maps to a fixed color, and UI-SPEC's Color section says this dialog's primary button uses `.btn-secondary` chrome with a **violet** focus ring (NOT the danger/warning/info palette `ConfirmModal` ships) — either (a) call `ConfirmModal` with a 4th variant if the planner extends it, or (b) build a small local wrapper reusing `ResponsiveDialog` directly (as `ExceptionGrantDialog` does — see below) with the two copy/title branches switched on whether `mutation.data`/a pre-resolved-owner prop is present. Given the "no form fields" simplicity, (a) minimal-extend `ConfirmModal`, or a thin wrapper around `ResponsiveDialog`, are both reasonable; a full form-dialog rebuild (copying `ExceptionGrantDialog` wholesale) is over-engineering for a 0-field dialog.

**Secondary analog for dialog chrome + error-banner conventions:** `frontend/src/components/exceptions/exception-grant-dialog.tsx` (358 lines, read in full) — reuse only these pieces, not the field-form scaffolding:
```tsx
import { ResponsiveDialog } from '@/components/ui/responsive-dialog';
...
<ResponsiveDialog open={open} onOpenChange={onOpenChange} ariaLabelledBy={titleId}>
  <div className="p-6">
    <div className="mb-1 flex items-start justify-between gap-4">
      <h2 id={titleId} className="text-lg font-semibold text-text">Grant exception</h2>
      <button type="button" onClick={() => onOpenChange(false)} aria-label="Close">
        <X size={18} />
      </button>
    </div>
    {dialogBannerError && (
      <div role="alert" className="mb-4 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
        {dialogBannerError}
      </div>
    )}
    ...
    <button type="button" onClick={handleSubmit} disabled={!canSubmit} className="btn-cta ... bg-gradient-sunset ...">
      {mutation.isPending ? 'Granting…' : 'Grant exception'}
    </button>
  </div>
</ResponsiveDialog>
```
Note the gradient CTA class here is WRONG for route-to-owner (UI-SPEC: violet focus ring on `.btn-secondary` chrome, never the pink gradient) — copy the `role="alert"` error-banner pattern and the `mutation.isPending ? '…ing' : '…'` button-label convention, not the button's color classes.

---

### `frontend/src/lib/queries/use-coverage-summary.ts` (hook, request-response)

**Analog:** `frontend/src/lib/queries/use-exceptions.ts` (67 lines, read in full) — a no-filter, no-pagination GET, exactly matching COV-02's compute-on-read-every-time contract:
```tsx
export function useExceptions() {
  return useQuery({
    queryKey: queryKeys.exceptions.list(),
    queryFn: ({ signal }) => api<ExceptionResponse[]>('/api/v1/exceptions', { signal }),
    staleTime: 0,   // compute-on-read fields; a stale cache would show an out-of-date computed value
    retry: 1,
  });
}
```
`useCoverageSummary()`: `queryFn: ({ signal }) => api<CoverageSummaryResponse>('/api/v1/coverage/summary', { signal })`, `staleTime: 0` (D-10 mandates fresh compute-on-read every time the view loads — do not cache stale coverage %).

---

### `frontend/src/lib/queries/use-blind-spot-assets.ts` (hook, request-response)

**Analog:** `frontend/src/lib/queries/use-assets.ts` (paginated GET, targeted read of lines 1-40, 100-128):
```tsx
export type AssetsFilters = { category?: readonly string[]; ...; search?: string; };

export function useAssets(opts: { filters: AssetsFilters; page: number; sort: string; order: 'asc' | 'desc' }) {
  return useQuery({
    queryKey: queryKeys.assets.list({ filters: opts.filters, page: opts.page, sort: opts.sort, order: opts.order }),
    queryFn: ({ signal }) => api<AssetsResponse>(`/api/v1/assets?${buildSearchParams(opts).toString()}`, { signal }),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: true,
  });
}
```
The response envelope (`{items, total, page, page_size, pages}`) is confirmed in `assets/page.tsx:180-186` and `assets/page.test.tsx`'s mock — reuse it verbatim for `BlindSpotAssetListResponse` per RESEARCH.md's Open Question 2 recommendation ("reuse the `AssetsResponse` shape verbatim... avoids inventing a second pagination contract for a conceptually identical list"). `useBlindSpotAssets({ page })`: same shape, simpler `opts` (no multi-axis filters — the blind-spot list has at most a chip-bar over already-blind-spot-scoped rows, per D-04, not the 6-axis facet set `/assets` has).

---

### `frontend/src/lib/queries/use-route-to-owner.ts` (hook, request-response mutation)

**Analog:** `frontend/src/lib/queries/use-reassign-asset.ts` (93 lines, read in full) — mutation + toast + targeted invalidate, the exact shape RESEARCH.md's Code Example also derives:
```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { queryKeys } from './keys';

export function useReassignAsset(assetId: string) {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation<ReassignResponse, Error, string, SnapshotCtx>({
    mutationFn: (email) => api<ReassignResponse>(`/api/v1/assets/${assetId}/owner`, {
      method: 'POST',
      body: JSON.stringify({ assigned_user_email: email }),   // T-12-08: ONLY the declared field, never spread arbitrary form state
      headers: { 'Content-Type': 'application/json' },
    }),
    onError: (_err, _email, ctx) => {
      toast({ variant: 'error', message: 'Could not reassign owner. Try again.' });
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.assets.byId(assetId) });
      qc.invalidateQueries({ queryKey: queryKeys.assets.all });
      const newOwner = data.assigned_user ?? 'new owner';
      toast({ variant: 'success', message: `Owner reassigned to ${newOwner}` });
    },
    retry: 0,   // BL-06: audit attribution > convenience — never retry a mutation
  });
}
```
`useRouteToOwner(assetId)`: `mutationFn: () => api<RouteToOwnerResponse>(`/api/v1/coverage/assets/${assetId}/route-to-owner`, { method: 'POST' })` (no body — see schemas.py note above), `onSuccess` invalidates `queryKeys.coverage.all` and toasts `${data.hostname} routed to ${data.routed_to}` (UI-SPEC Copywriting Contract's exact success-toast template), `onError` toasts the UI-SPEC's exact error copy ("Couldn't send the notification. Try again, or check the device's owner directly in your directory connector."), `retry: 0`.

---

### `frontend/src/lib/queries/keys.ts` (modified, utility)

**Pattern — per-domain key-group entry** (lines 118-136, read in full):
```tsx
campaigns: {
  all: ['campaigns'] as const,
  list: () => ['campaigns', 'list'] as const,
  detail: (id: string) => ['campaigns', 'detail', id] as const,
},
exceptions: {
  all: ['exceptions'] as const,
  list: () => ['exceptions', 'list'] as const,
},
```
Add:
```tsx
coverage: {
  all: ['coverage'] as const,
  summary: () => ['coverage', 'summary'] as const,
  blindSpots: (opts: { page: number }) => ['coverage', 'blind-spots', opts] as const,
},
```
Matches `campaigns`'s no-filter-args `list()` shape for `summary()` and `tickets.list`'s opts-object shape for `blindSpots(opts)` (pagination is part of the cache key, per the `remediationsGrouped` precedent at lines 143-147).

---

### `frontend/src/components/shell/nav-items.ts` (modified, config)

**Pattern — `WORKFLOW_ITEMS` entry** (lines 34-53, read in full):
```tsx
export const WORKFLOW_ITEMS: NavItem[] = [
  { label: 'Tickets',    href: '/dashboard/tickets',       icon: Ticket, chip: 'ticket_open' },
  { label: 'Rules',      href: '/dashboard/tickets/rules', icon: Zap },
  { label: 'Connectors', href: '/dashboard/connectors',    icon: Plug },
  { label: 'Asset groups', href: '/dashboard/asset-groups', icon: FolderKanban },
  // Phase 38 (38-04, CAMP-01) — dedicated campaign list view. No chip per D-N-01.
  { label: 'Campaigns', href: '/dashboard/campaigns', icon: Target },
  // Phase 39 (39-06, EXC-02/EXC-03) — manage-only exceptions list view. No chip per D-N-01.
  { label: 'Exceptions', href: '/dashboard/exceptions', icon: ShieldOff },
];
```
Add, after Exceptions: `{ label: 'Coverage', href: '/dashboard/coverage', icon: Radar },` — import `Radar` from `lucide-react` in the top import line (`import { Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings, Zap, FolderKanban, Target, ShieldOff, Radar } from 'lucide-react';`). No chip per `ChipKey`'s closed union (`'vuln_open' | 'asset_total' | 'ticket_open'` — Coverage is not one of the three chip-carrying destinations, matching every other WORKFLOW_ITEMS entry's precedent). `ALL_ITEMS`/`MORE_ITEMS` derive automatically from `WORKFLOW_ITEMS` (lines 61-65, 76-79) — no separate edit needed there.

---

### `frontend/e2e/routes.ts` (modified, config/test-fixture)

**Pattern — `STATIC_ROUTES`** (lines 11-21, read in full):
```tsx
export const STATIC_ROUTES = [
  '/dashboard',
  '/dashboard/vulnerabilities',
  '/dashboard/assets',
  '/dashboard/tickets',
  '/dashboard/tickets/rules',
  '/dashboard/cspm',
  '/dashboard/connectors',
  '/dashboard/users',
  '/dashboard/settings',
] as const;
```
Add `'/dashboard/coverage'` to this array so `frontend/e2e/a11y-routes.spec.ts`'s existing per-route axe sweep (`test.describe('WCAG 2.1 AA axe sweep — all routes (blocking)', ...)`, lines 21-80 read) automatically covers the new page with zero new test-file work — satisfies RESEARCH.md's Phase Gate requirement ("extend `frontend/e2e/a11y-routes.spec.ts`'s per-route pattern... so the new route gets at least one smoke + axe pass"). **Flag for the planner (not this phase's bug to fix, but worth noting):** `STATIC_ROUTES` is also missing `/dashboard/campaigns` and `/dashboard/exceptions` (both shipped in Phases 38-39) — the array's own comment says "9 are static" and lists exactly 9, none of which are the two most recent WORKFLOW_ITEMS entries. Coverage should not be silently left out the same way.

---

## Shared Patterns

### RBAC — `app.auth.rbac` (never the legacy `app.auth.dependencies.require_role`)
**Source:** `backend/app/auth/rbac.py` (53 lines, read in full)
**Apply to:** `coverage/router.py`'s all three endpoints
```python
ROLE_HIERARCHY: dict[str, int] = {
    UserRole.OWNER.value: 40, UserRole.ADMIN.value: 30, UserRole.ANALYST.value: 20, UserRole.VIEWER.value: 10,
}

class RequireRole:
    def __init__(self, minimum_role: str):
        self.minimum_role = minimum_role
    async def __call__(self, user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not _check_role(user, self.minimum_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires {self.minimum_role} role or higher")
        return user

require_viewer = RequireRole(UserRole.VIEWER.value)
require_analyst = RequireRole(UserRole.ANALYST.value)
```
`require_viewer` on `GET /summary` + `GET /blind-spots`; `require_analyst` on `POST /assets/{id}/route-to-owner` — this is D-08's asymmetric-RBAC requirement verbatim, and is the exact convention every v5.0 phase (36-40) follows. Pitfall 4's warning: do NOT import `require_role` from `app.auth.dependencies` even though that's what `assets/router.py` (the file supplying `get_directory_user`) itself uses for its own admin-only endpoints — two independently-implemented role systems coexist in this codebase, and only `app.auth.rbac` is current.

### Fail-closed audit — `audit()`
**Source:** `backend/app/audit.py:148-201` (read in full)
**Apply to:** the `route_to_owner` mutation only (the two GETs are pure reads, no audit row)
```python
async def audit(db, user, action, resource_type, resource_id=None, details=None, ip_address=None) -> None:
    """BL-04/WR-01/WR-12: fail-closed. Caller pattern is `audit(...); await db.commit()`,
    so any exception raised here propagates and the commit is skipped."""
    now = datetime.now(UTC)
    try:
        log = AuditLog(tenant_id=user.tenant_id if user else uuid.UUID(int=0), user_id=user.id if user else None,
                        user_email=user.email if user else None, action=action, resource_type=resource_type,
                        resource_id=str(resource_id) if resource_id else None, details=details, created_at=now)
        db.add(log)
    except SQLAlchemyError:
        _logger.warning("audit_add_failed", extra={...}, exc_info=True)
        raise
```
Call as `await audit(db, user, "coverage.route_to_owner", "asset", str(asset.id), {"hostname": ..., "routed_to": ...})` then `await db.commit()` in the router (never reverse the order; never wrap in try/except that swallows the exception).

### Tenant-scoped 404 (never fetch-then-403)
**Source:** `backend/app/exceptions/router.py:37-47` (read in full, see full excerpt above)
**Apply to:** the `_get_asset_or_404` helper in `coverage/router.py`, used by all three endpoints (the two GETs filter by `tenant_id` in the list query itself; the POST needs the explicit helper since it looks up one asset by id).

### Source-class partition — `SCANNER_SOURCES` / `ENRICHMENT_SOURCES`
**Source:** `backend/app/assets/constants.py` (25 lines, read in full)
**Apply to:** every reconciliation query in `coverage/service.py` — import, never re-derive the 9 literal strings (explicit warning in RESEARCH.md's Standard Stack table: "or Phase 41 and the existing Assets facet filter can drift apart").

### Sync-status wire normalization
**Source:** `backend/app/connectors/service.py:33-44` (read in full)
**Apply to:** every per-connector coverage card payload in `coverage/service.py` (Pitfall 3 — skipping this makes every real connector silently render "Never synced" in `SyncStatusPill`).

### Owner resolution + admin fallback
**Source:** `backend/app/assets/directory.py` (67 lines, read in full) + `backend/app/notifications/alerts.py:496-521` (read in full)
**Apply to:** `coverage/service.py::route_to_owner` — `get_directory_user` first, `_email_owners_and_admins` as the D-09 fallback. Do not hand-roll a new heuristic (Don't Hand-Roll table).

### Mutation hook: toast + query invalidate
**Source:** `frontend/src/lib/queries/use-reassign-asset.ts` (93 lines, read in full)
**Apply to:** `use-route-to-owner.ts` — `retry: 0` (never retry a mutation with audit/notification side effects), success/error toast via `useToast()`, `queryClient.invalidateQueries` targeted at the domain's `.all` key.

### Day-count copy (no date library)
**Source:** `frontend/src/components/exceptions/exceptions-table.tsx:92-97` (targeted read)
**Apply to:** `coverage-connector-card.tsx`'s `stale · {N}d` badge — plain `Math.floor` day-diff math, matches `copy-voice.md`'s quantity format; do not add `date-fns`/`dayjs`.

### RBAC-aware frontend gating (`useAuth().user.role`)
**Source:** `frontend/src/app/(authed)/dashboard/connectors/page.tsx:98-99` (grep-verified)
**Apply to:** `coverage/page.tsx` + `coverage-asset-drill-content.tsx` — compute `canRouteToOwner` once at the page level, pass down as a prop; disable/hide (never silently omit with no explanation) the "Route to owner" button for a viewer, mirroring D-08's asymmetric RBAC and UI-SPEC's E2 "partial" row.

---

## No Analog Found

None. Every file in the classification table above has an exact or role-match analog already in the codebase — consistent with CONTEXT.md's own framing of this phase ("mostly a read-side reconciliation over data GetVul already has") and RESEARCH.md's explicit conclusion ("every 'hard part' of this phase... was already built and is load-bearing for a different phase").

## Metadata

**Analog search scope:** `backend/app/{exceptions,campaigns,assets,connectors,notifications,ticketing,auth}/`, `backend/tests/`, `frontend/src/app/(authed)/dashboard/{tickets,assets,connectors}/`, `frontend/src/components/{exceptions,connectors,tickets,ui,states,vulnerabilities,assets}/`, `frontend/src/lib/queries/`, `frontend/src/components/shell/`, `frontend/e2e/`.
**Files read in full:** 27 (exact line counts noted per-file above; all ≤ 417 lines, no file exceeded the 2,000-line large-file threshold).
**Files read via targeted offset/limit (non-overlapping ranges):** `backend/app/assets/router.py` (82-170, 542-601), `backend/app/notifications/alerts.py` (365-472, 496-521), `backend/tests/test_exceptions.py` (375-403), `backend/tests/test_campaigns.py` (340-364), `frontend/src/app/(authed)/dashboard/tickets/page.tsx` (340-409), `frontend/src/components/exceptions/exceptions-table.tsx` (85-149, 320-349, 355-377), `frontend/e2e/a11y-routes.spec.ts` (1-85), `frontend/e2e/routes.ts` (1-40), `frontend/src/lib/queries/use-assets.ts` (1-40, 100-128).
**Pattern extraction date:** 2026-08-20
