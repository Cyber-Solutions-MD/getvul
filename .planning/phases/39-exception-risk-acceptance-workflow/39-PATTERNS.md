# Phase 39: Exception & Risk-Acceptance Workflow - Pattern Map

**Mapped:** 2026-08-18
**Files analyzed:** 32 (7 new backend, 14 modified backend consumers, 2 backend infra touches, 7 new frontend, 4 modified frontend)
**Analogs found:** 30 / 32 exact-or-role-match; 2 flagged "No Analog Found" (native `<input type="date">` markup, D-16's Python interval-merge)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/exceptions/__init__.py` | config (package init) | — | `backend/app/campaigns/__init__.py` (0 bytes) | exact |
| `backend/app/exceptions/models.py` | model | CRUD | `backend/app/campaigns/models.py` | exact |
| `backend/app/exceptions/schemas.py` | model (Pydantic schema) | request-response | `backend/app/campaigns/schemas.py` | exact |
| `backend/app/exceptions/service.py` | service | CRUD + compute-on-read filter | `backend/app/campaigns/service.py` + `backend/app/assets/groups_service.py` (group join) + `backend/app/vulnerabilities/service.py` (batched corr lookup) | exact |
| `backend/app/exceptions/router.py` | controller/route | request-response | `backend/app/campaigns/router.py` + `backend/app/vulnerabilities/router.py::ignore_cve` | exact |
| `backend/alembic/versions/050_add_exceptions.py` | migration | batch (DDL) | `backend/alembic/versions/049_add_campaigns.py` | exact |
| `backend/tests/test_exceptions.py` | test | — | `backend/tests/test_campaigns.py` | exact |
| `backend/app/vulnerabilities/service.py::_apply_filters` (43-106) | service (filter builder) | CRUD/read | self — insertion point identified | exact |
| `backend/app/vulnerabilities/service.py::get_vulnerability` (276-347) | service (read) | request-response | self — inherits fix via `resolve_state_for_vuln` | exact |
| `backend/app/vulnerabilities/sla_tier_service.py::compute_sla_state`/`resolve_state_for_vuln` (111-159) | service (transform) | transform | self — D-16 subtraction seam | exact |
| `backend/app/vulnerabilities/sla_tier_service.py::run_sla_tier_pass` (162-224) | service (batch) | batch | self — persisted-mirror WHERE clause | exact |
| `backend/app/vulnerabilities/sla_tier_service.py::detect_and_escalate` (353-534) | service | event-driven | self — governance-critical (Tier 2, not in CONTEXT's named list) | exact |
| `backend/app/assets/risk_score.py::compute_risk_scores` (91-154) | service (batch) | batch | self — raw-score subquery WHERE | exact |
| `backend/app/vulnerabilities/remediation_service.py::_base_open_vulns` (14-32) | service (filter builder) | CRUD/read | self — "active" branch only | exact |
| `backend/app/campaigns/service.py::get_campaign_progress` (88-118) | service (aggregate) | CRUD/read | self — member-count WHERE | exact |
| `backend/app/campaigns/service.py::bulk_create_campaign_tickets` (249-384) | service | batch | self — live-members WHERE (271-286) | exact |
| `backend/app/ticketing/rule_engine.py::find_matching_assets`/`run_rule` (~43-234) | service | event-driven | self — governance-critical (Tier 2) | exact |
| `backend/app/vulnerabilities/router.py::remediations_for_host` (936-999) | controller (ad hoc query) | request-response | self — bypasses shared helpers entirely | exact |
| Tier 2 #11-16: `assets/router.py` badges, `users/router.py` owner-risk, `dashboard.py`/`service.py::get_dashboard_stats`, `export.py`, `risk_exposure_service.py` rollup | controller/service | request-response/batch | same `active_exception_subquery` seam (line ranges per RESEARCH.md Consumer Sweep, grep-verified this session) | role-match |
| `backend/app/audit.py` (Actions comment, 53-76) | config/doc | — | self | exact |
| `backend/app/main.py` (router registration, 310-324) | config | — | self, `campaigns_router` at line 319 | exact |
| `frontend/src/app/(authed)/dashboard/exceptions/page.tsx` | route/page | request-response | `frontend/src/app/(authed)/dashboard/campaigns/page.tsx` | exact |
| `frontend/src/components/exceptions/exception-grant-dialog.tsx` | component (form) | request-response | `ResponsiveDialog` shell + campaigns `[id]/page.tsx`'s ConfirmModal-children form pattern + `drill-content.tsx` confirm-wiring | role-match |
| `frontend/src/components/exceptions/approver-combobox.tsx` | component | request-response | `frontend/src/components/assets/reassign-combobox.tsx` | role-match, **NOT verbatim** (Pitfall 6) |
| `frontend/src/components/exceptions/exceptions-table.tsx` | component (table) | CRUD/read | `frontend/src/components/campaigns/campaigns-table.tsx` | exact |
| `frontend/src/components/exceptions/exceptions-chip-bar.tsx` (implied — see note) | component (filter) | request-response | `frontend/src/components/campaigns/campaigns-chip-bar.tsx` | exact |
| `frontend/src/lib/queries/use-exceptions.ts` | hook | request-response | `frontend/src/lib/queries/use-campaigns.ts` | exact |
| `frontend/src/lib/queries/use-exception-mutations.ts` (implied — see note) | hook | request-response | `frontend/src/lib/queries/use-campaign-mutations.ts` | exact |
| `frontend/src/components/vulnerabilities/drill-content.tsx` (Actions section, 922-945) | component | request-response | self — existing "Create ticket"/"Snooze 24h" buttons | exact |
| `frontend/src/components/vulnerabilities/microcopy.ts` (drill block, 47-69) | config (copy) | — | self | exact |
| `frontend/src/components/shell/nav-items.ts` (`WORKFLOW_ITEMS`, 34-50) | config (nav) | — | self | exact |
| `frontend/src/lib/queries/keys.ts` (campaigns block, ~118-132) | config (query keys) | — | self | exact |

**Note on RESEARCH.md's recommended tree vs. this classification:** RESEARCH.md's "Recommended Project Structure" lists only `exception-grant-dialog.tsx` / `approver-combobox.tsx` / `exceptions-table.tsx` / `use-exceptions.ts` under frontend. Two files are missing from that list but are structurally required once you look at campaigns (the phase's own closest sibling): a **chip-bar** component (`exceptions-chip-bar.tsx` — UI-SPEC's mockup explicitly shows `[chip-bar: search-target · Type: … · Scope: … · Clear all]`) and a **mutations hook** (`use-exception-mutations.ts` — grant/revoke are POSTs, not covered by `use-exceptions.ts`'s `useQuery`-only shape). Both added to the classification table above. Also: RESEARCH wrote the page path as `frontend/src/app/dashboard/exceptions/page.tsx` — the codebase's actual route group is `frontend/src/app/(authed)/dashboard/...` (verified via `find`), corrected above.

---

## Pattern Assignments

### A. New backend module — `backend/app/exceptions/{models,schemas,service,router}.py`

**Analog:** `backend/app/campaigns/` (Phase 38) — the closest prior "new governed table + compute-on-read + audit + RBAC" module in this codebase. Same shape recommended by RESEARCH.md and confirmed by direct read.

**Model pattern** (`backend/app/campaigns/models.py:1-74`, full file):
```python
"""Campaign SQLAlchemy model (Phase 38 -- CAMP-01/CAMP-04)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index(
            "uq_campaign_active_remediation",
            "tenant_id",
            "remediation_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    close_trigger: Mapped[str | None] = mapped_column(String(20))
```
Copy verbatim: `Base, UUIDPrimaryKeyMixin, TimestampMixin` base classes; `tenant_id` FK-CASCADE-indexed column shape; DB-nullable user FKs with `ondelete="SET NULL"` even though the field is app-required (Pitfall 3 — `approver_user_id`/`granted_by_user_id`/`revoked_by_user_id` all follow `created_by_user_id`'s exact shape here). `ExceptionRecord` needs NO partial-unique `Index` (D-12 explicitly permits overlapping active exceptions on the same finding) — that piece of this analog does **not** transfer.

**Schema pattern** (`backend/app/campaigns/schemas.py:1-69`, full file — key excerpt):
```python
class CampaignCreateRequest(BaseModel):
    """... `extra="forbid"` is a deliberate mass-assignment defense (T-38-02, ASVS
    V5) ..."""
    model_config = ConfigDict(extra="forbid")
    remediation_id: str = Field(..., min_length=1, max_length=200)

class CampaignSummary(BaseModel):
    id: uuid.UUID
    remediation_id: str
    status: Literal["ACTIVE", "COMPLETE"]
    total: int
    ...
```
Copy: `ConfigDict(extra="forbid")` on every request body (mass-assignment defense — `ExceptionCreate` needs this too, per RESEARCH Security Domain V5); `Literal[...]` for closed enums (`type: Literal["FALSE_POSITIVE", "ACCEPTED_RISK"]`, `scope_type: Literal["FINDING", "ASSET", "ASSET_GROUP"]`) rather than free `str`.

**Router pattern — get-or-create + audit-then-commit + tenant-scoped 404** (`backend/app/campaigns/router.py:100-151`):
```python
async def _get_campaign_or_404(db: DBSession, tenant_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
    """T-38-01 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant campaign_id must 404, never a
    fetch-then-403 ..."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id))
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("", response_model=CampaignCreateResponse)
async def create_campaign(
    body: CampaignCreateRequest,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
) -> CampaignCreateResponse:
    campaign, is_new = await get_or_create_campaign(db, user.tenant_id, body.remediation_id, user.id)
    if is_new:
        await audit(db, user, "campaign.create", "campaign", str(campaign.id), {"remediation_id": body.remediation_id})
    await db.commit()
    return CampaignCreateResponse(id=campaign.id, remediation_id=campaign.remediation_id, already_existed=not is_new)


@router.get("", response_model=list[CampaignSummary])
async def campaigns_list(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> list[CampaignSummary]:
    campaigns = await list_campaigns(db, user.tenant_id)
    ...
```
This is the direct template for `POST /` (grant), `GET /` (list), `POST /{id}/revoke` — `require_analyst` on every write, `require_viewer` on list, `audit(...)` called **before** `db.commit()` (never after — audit.py's fail-closed contract depends on this ordering), tenant scoping baked into the WHERE clause of every lookup (never fetch-then-filter).

**Service pattern — compute-on-read progress aggregation with zero-guard** (`backend/app/campaigns/service.py:88-118`):
```python
async def get_campaign_progress(db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str) -> dict[str, int]:
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Vulnerability.status == "REMEDIATED").label("done"),
                func.count().filter(Vulnerability.status == "IN_PROGRESS").label("in_progress"),
            ).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.remediation_id == remediation_id,
                Vulnerability.status.in_(_CAMPAIGN_MEMBER_STATUSES),
            )
        )
    ).one()
    total, done, in_progress = row.total, row.done, row.in_progress
    return {
        "total": total, "open": total - done - in_progress, "in_progress": in_progress, "done": done,
        "pct_remediated": round(done / total * 100) if total else 0,
    }
```
The `if total else 0` zero-guard is the exact shape needed for the exceptions list's per-row "is this still active" computation and any list-side aggregate.

**Service pattern — lazy-on-read, system-attributed audit** (`backend/app/campaigns/service.py:151-211`, the direct analog for the OPTIONAL D-19/Pattern-4 expiry-audit row):
```python
async def apply_lifecycle_transition(
    db: AsyncSession, tenant_id: uuid.UUID, campaign: Campaign, progress: dict[str, int]
) -> None:
    is_complete = progress["total"] > 0 and progress["done"] == progress["total"]
    now = datetime.now(UTC)

    if is_complete and campaign.closed_at is None:
        campaign.closed_at = now
        campaign.close_trigger = "auto_complete"
        db.add(
            AuditLog(
                tenant_id=tenant_id, user_id=None, user_email="system:campaign-complete",
                action="campaign.close", resource_type="campaign", resource_id=str(campaign.id),
                details={"trigger": "auto_complete"}, ip_address=None, created_at=now,
            )
        )
        await db.commit()
```
Copy this exact shape for the exceptions list endpoint's optional lazy-audit sweep: for every row where `expires_at <= now AND revoked_at IS NULL AND resurfaced_audited_at IS NULL`, construct `AuditLog` directly (not via `audit()`, which requires a real `user`) with `user_id=None, user_email="system:exception-expiry"`, `action="exception.expire"`, then set `resurfaced_audited_at = now`. Note the guard-then-single-write idempotence pattern (`closed_at IS NULL` / `resurfaced_audited_at IS NULL`) — a second read of an already-transitioned row takes no action and writes no duplicate audit row.

**Service pattern — race-safe get-or-create via `begin_nested()` + `IntegrityError`** (`backend/app/campaigns/service.py:36-85`) — not needed for exceptions (D-12 permits duplicates, no unique index to race against), but relevant if the planner adds any dedup-on-insert behavior later; noted for completeness, not required this phase.

---

### B. New Alembic migration — `backend/alembic/versions/050_add_exceptions.py`

**Analog:** `backend/alembic/versions/049_add_campaigns.py` (full file, 87 lines) — confirmed current head via `ls backend/alembic/versions | tail`.

```python
"""Add campaigns table (Phase 38 Plan 01 -- CAMP-01/CAMP-04, D-11 partial unique index).
...
Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"049_add_campaigns" is 18 chars -- safe.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "049_add_campaigns"
down_revision = "048_add_clean_scan_streak"


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remediation_id", sa.String(200), nullable=False),
        ...
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_remediation_id", "campaigns", ["remediation_id"])
    op.create_index(
        "uq_campaign_active_remediation", "campaigns", ["tenant_id", "remediation_id"],
        unique=True, postgresql_where=sa.text("closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_campaign_active_remediation", table_name="campaigns")
    op.drop_index("ix_campaigns_remediation_id", table_name="campaigns")
    op.drop_index("ix_campaigns_tenant_id", table_name="campaigns")
    op.drop_table("campaigns")
```

Copy the skeleton exactly: `revision`/`down_revision` string convention (`down_revision = "049_add_campaigns"`), `op.create_table` with plain `postgresql.UUID`/`sa.ForeignKey(..., ondelete=...)` columns (never a native Postgres enum — zero precedent anywhere in this codebase per RESEARCH), `server_default=sa.text("now()")` for `created_at`/`updated_at`, one `op.create_index` call per index, `downgrade()` drops indexes explicitly before `op.drop_table` (though RESEARCH's own Code Examples §1 notes indexes drop automatically with the table in Postgres — 049 drops them explicitly anyway; match that convention for consistency). **Do NOT copy** the partial-unique `uq_campaign_active_remediation` index — D-12 requires the opposite (multiple overlapping active exceptions allowed). **Do copy** the `revoked_at IS NULL` partial-index pattern's *mechanism* (`postgresql_where=sa.text(...)`) for `ix_exceptions_not_revoked`, but the predicate must stay a pure NULL check — Pitfall 2 (`now()` is STABLE not IMMUTABLE, fails at migration time in an index predicate).

---

### C. Legacy suppress/ignore precedent (union semantics, D-02) — read-only reference, not modified

**Analog:** `backend/app/vulnerabilities/router.py:527-560` (`ignore_cve`) — the audit-then-commit shape every new exception mutation should mirror:
```python
@router.post("/cve/{cve_id}/ignore")
async def ignore_cve(cve_id: str, db: DBSession, user: Annotated[CurrentUser, Depends(require_analyst)], body: dict = None):
    now = datetime.now(UTC)
    result = await db.execute(
        sql_update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.cve_id == cve_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(status="SUPPRESSED", updated_at=now)
    )
    count = result.rowcount
    await compute_risk_scores(db, user.tenant_id)
    await audit(db, user, "vuln.ignore_cve", "vulnerability", cve_id, {"suppressed": count, "reason": body.get("reason", "")})
    await db.commit()
    return {"message": f"Ignored CVE {cve_id}", "suppressed": count, "cve_id": cve_id}
```
Three things to copy directly into `grant_exception`: (1) `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])` — the exact D-03 precondition text (for `FINDING` scope only, per Pattern 2 below); (2) `await compute_risk_scores(db, user.tenant_id)` called **before** `audit()` — Pitfall 7 confirms grant/revoke should call `compute_risk_scores` only, never `compute_finding_risk_scores` (matches this exact precedent, avoiding a new inconsistency); (3) `audit(...)` then `db.commit()` — never reversed.

`VulnStatus` enum (`backend/app/vulnerabilities/models.py:24-29`):
```python
class VulnStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    SUPPRESSED = "SUPPRESSED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
```
Confirms the `str, enum.Enum` + plain-string-column convention (never a native Postgres enum) that `ExceptionRecord.type`/`scope_type` must follow.

`Asset.is_ignored` + `AssetGroup`/`AssetGroupMember` (`backend/app/assets/models.py:74-76, 141-164`):
```python
is_ignored: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
ignored_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
ignored_reason: Mapped[str | None] = mapped_column(String(500))
...
class AssetGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "asset_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_asset_group_tenant_name"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

class AssetGroupMember(Base):
    __tablename__ = "asset_group_members"
    __table_args__ = (PrimaryKeyConstraint("group_id", "asset_id"),)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
```
`AssetGroupMember` is the exact live-membership join table D-11's `ASSET_GROUP` scope resolves through — confirmed by `assets/groups_service.py::list_members` (below).

---

### D. Compute-on-read exclusion join — the shared seam + Tier 1 consumer excerpts

This is the phase's central cross-cutting pattern (RESEARCH's "primary recommendation" + "research emphasis #2"). One new function, `active_exception_subquery(tenant_id, now)` in `app/exceptions/service.py`, gets applied (via `~active_exception_subquery(...)` to exclude, bare to select) to every consumer below. Each excerpt shows the **exact existing WHERE clause** the new predicate joins.

**Live-membership join precedent this seam is built from** (`backend/app/assets/groups_service.py:123-136`):
```python
async def list_members(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID) -> list[Asset] | None:
    group = await get_group(db, tenant_id, group_id)
    if group is None:
        return None
    result = await db.execute(
        select(Asset)
        .join(AssetGroupMember, AssetGroupMember.asset_id == Asset.id)
        .where(AssetGroupMember.group_id == group_id, Asset.tenant_id == tenant_id)
        .order_by(Asset.hostname)
    )
    return list(result.scalars().all())
```
This `.join(AssetGroupMember, AssetGroupMember.asset_id == Asset.id)` shape is what the `ASSET_GROUP` branch of `active_exception_subquery`'s inner correlated `exists()` must reproduce (see RESEARCH.md Pattern 1's code block, already schema-complete — no changes recommended to that draft).

**Consumer 1 — `_apply_filters` (the 3-for-1 choke point)** (`backend/app/vulnerabilities/service.py:43-46`):
```python
def _apply_filters(query: Select, tenant_id: uuid.UUID, filters: VulnerabilityFilter) -> Select:
    """Apply filter conditions to a vulnerability query."""
    query = query.where(Vulnerability.tenant_id == tenant_id)

    if filters.severity:
        ...
```
Insertion point: immediately after `query = query.where(Vulnerability.tenant_id == tenant_id)` (line 45), add `query = query.where(~active_exception_subquery(tenant_id, datetime.now(UTC)))`. This one edit covers `list_vulnerabilities`, `list_vulnerabilities_by_host`, and `get_facets` — all three funnel through `_apply_filters`.

**Consumer 2 — `get_vulnerability`'s SLA inheritance** (`backend/app/vulnerabilities/service.py:306-310`):
```python
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    sla_policy = get_tier_policy(tenant)
    sla_due_at, sla_state = resolve_state_for_vuln(vuln, sla_policy, datetime.now(UTC))
```
No exclusion/404 change needed here (the detail page must stay reachable from the exceptions list's "View finding" cross-link) — it inherits the D-16 fix automatically once `resolve_state_for_vuln` (Consumer 3) is corrected.

**Consumer 3 — `resolve_state_for_vuln`/`compute_sla_state` (D-16 seam)** — see Pattern E below.

**Consumer 4 — `run_sla_tier_pass`'s persisted-mirror WHERE** (`backend/app/vulnerabilities/sla_tier_service.py:181-186`):
```python
    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.tenant_id == tenant.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    vulns = result.scalars().all()
```
Add `~active_exception_subquery(tenant.id, now)` to this WHERE. Pitfall 1 warns this is a **second, independent** fix from Consumer 3 — the persisted `sla_due_at`/`sla_breached` mirror (read by `assets/router.py`'s `sla_breach` badge count, Tier 2 #11) goes stale until the next scheduler tick unless this exact query also learns the join, and also needs the D-16 subtraction (not just the two direct read-time callers).

**Consumer 5 — `detect_and_escalate` (governance-critical, Tier 2 #9, not in CONTEXT's named list)** (`backend/app/vulnerabilities/sla_tier_service.py:379-386`):
```python
    result = await db.execute(
        select(Vulnerability, Asset)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    rows = result.all()
```
Same one-line addition. **Do not skip this one** — without it, an accepted-risk finding still fires Slack/Teams/email/PagerDuty + the in-app `sla_escalation` breach notification (lines 497-519 of the same file), directly contradicting the phase's purpose.

**Consumer 6 — `compute_risk_scores`'s raw-score subquery** (`backend/app/assets/risk_score.py:119-131`):
```python
    raw_score_sub = (
        select(
            Vulnerability.asset_id,
            func.coalesce(func.sum(weighted_score), 0).label("raw_score"),
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.asset_id.isnot(None),
        )
        .group_by(Vulnerability.asset_id)
        .subquery()
    )
```
Add the exclusion predicate to this WHERE only — `compute_risk_scores` is grant/revoke's own recompute call (Pitfall 7: call this function only, never `compute_finding_risk_scores`).

**Consumer 7 — `_base_open_vulns`'s "active" branch ONLY** (`backend/app/vulnerabilities/remediation_service.py:14-32`, full function):
```python
def _base_open_vulns(tenant_id: uuid.UUID, show_suppressed: str = "active"):
    """Base conditions for vulns.
    show_suppressed: "active" (default), "ignored", or "all"
    """
    if show_suppressed == "ignored":
        return and_(Vulnerability.tenant_id == tenant_id, Vulnerability.status == "SUPPRESSED")
    if show_suppressed == "all":
        return and_(Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "SUPPRESSED"]))
    return and_(Vulnerability.tenant_id == tenant_id, Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]))
```
This is the exact precedent for a "filter-on-read exclusion axis" parameter — `show_suppressed` already demonstrates the codebase's convention for a caller-selectable exclusion mode. Add `and_(~active_exception_subquery(...))` only to the final (`"active"`, default) branch's `and_(...)` — the `"ignored"`/`"all"` branches intentionally show suppressed/excepted items and must stay untouched. This single function covers `get_remediations_grouped`, `get_hosts_for_remediation`, and `get_remediations_for_host` (all three call it, lines 87/174/231 respectively of the same file).

**Consumer 8 — `get_campaign_progress`** — already shown in full under Pattern Assignment A above (`backend/app/campaigns/service.py:98-110`); add the exclusion predicate to its `.where(...)` clause.

**Consumer 9 — `bulk_create_campaign_tickets`'s live-members query** (`backend/app/campaigns/service.py:275-286`):
```python
    rows = (
        await db.execute(
            select(Vulnerability, Asset.hostname, Asset.mdm_details)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.remediation_id == campaign.remediation_id,
                Vulnerability.status.in_(("OPEN", "IN_PROGRESS")),
            )
            .order_by(Asset.hostname)
        )
    ).all()
```
Same addition — an excepted campaign member must not get ticketed.

**Consumer 10 — `find_matching_assets` (governance-critical, Tier 2 #8)** (`backend/app/ticketing/rule_engine.py:102-111`):
```python
        counts_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev.is_(True)).label("kev"),
        ).where(
            Vulnerability.asset_id == asset.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
```
**Do not skip this one either** — the automated ticket-creation rule engine (`run_rule`, called from a scheduler tick) would otherwise auto-open a ticket for an asset whose only qualifying finding is under an active accept-risk exception.

**Consumer 11 — `remediations_for_host` (hand-rolled bypass, proves the shared-helper is necessary but not sufficient)** (`backend/app/vulnerabilities/router.py:966-970`):
```python
        .where(
            Vulnerability.asset_id == asset_id,
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
```
This endpoint never calls `_base_open_vulns` or `_apply_filters` — it is a direct ad hoc query (Pitfall 5). Must get its own one-line addition; patching only the two shared helpers is not enough.

**Tier 2 #11-16 (role-match, not independently re-read this session — RESEARCH.md's Consumer Sweep table already grep-verified exact line ranges):** `assets/router.py:261-274,388-403` (asset list/detail vuln-count/critical/high/exploitable/kev/**sla_breach** badges — note `sla_breach` reads the persisted column directly, so Consumer 4 above is a prerequisite); `users/router.py:130-149,358-381` (owner-risk aggregate); `vulnerabilities/dashboard.py:43,189-208,311` + `service.py:750` (`get_dashboard_stats`, dashboard tiles/top-vuln/nav counts); `export.py:266,318` (CSV/exec-summary export); `risk_exposure_service.py:392-399` (the `Asset.risk_exposure_score` MAX rollup subquery — **not** the per-finding score-write loop at 347-385, which is untouched). Each is a 1-3 line addition to an existing WHERE, identical in shape to Consumers 1-11 above.

**Explicitly out of scope (Tier 3, do not add the join here):** `connectors/sync.py:234-256` (ingestion bookkeeping — the finding must stay OPEN "under the hood" per D-01); `ticketing/service.py`/`ticketing/daily_sync.py` (status write-back, a different lane); `search.py::_search_vulnerabilities` (already returns every status today — adding exclusion would be a new asymmetry, not a fix); `ai/grounding.py`, `trends.py`, `cspm/service.py` (flagged as open questions / separate lanes — see RESEARCH.md Open Questions Q3/Q4 and Tier 3 #22).

---

### E. D-16 SLA-subtraction seam

**Structural fact this pattern depends on:** `resolve_state_for_vuln` (`backend/app/vulnerabilities/sla_tier_service.py:131-159`) only ever runs on findings that have **already passed** the Pattern D exclusion filter — so the subtraction problem is bounded to **lapsed** (expired or revoked) exception windows only, never a live overlap.

**Current code to extend** (`backend/app/vulnerabilities/sla_tier_service.py:111-159`, full functions):
```python
def compute_sla_state(
    *,
    first_detected_at: datetime,
    tier_days: int,
    approaching_pct: float,
    now: datetime,
) -> tuple[datetime, str]:
    """D-02: the tier+elapsed-% state formula. ..."""
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    if now >= sla_due_at:
        return sla_due_at, "breached"
    if now >= approaching_at:
        return sla_due_at, "approaching"
    return sla_due_at, "on_track"


def resolve_state_for_vuln(
    vuln: Vulnerability,
    policy: dict[str, Any],
    now: datetime,
) -> tuple[datetime | None, str]:
    score = vuln.risk_exposure_score
    tier: str | None
    if score is None:
        tier = severity_to_tier(vuln.severity)
    else:
        tier = tier_for_score(score)
        if tier is None:
            return None, "not_tracked"

    tier_days = policy["tier_days"][tier]
    approaching_pct = policy["approaching_pct"]
    return compute_sla_state(
        first_detected_at=vuln.first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=now,
    )
```
RESEARCH.md's recommended signature change adds one keyword-only parameter to `compute_sla_state`:
```python
def compute_sla_state(
    *, first_detected_at: datetime, tier_days: int, approaching_pct: float,
    now: datetime, excepted_seconds: int = 0,
) -> tuple[datetime, str]:
    effective_start = first_detected_at + timedelta(seconds=excepted_seconds)
    sla_due_at = effective_start + timedelta(days=tier_days)
    ...
```
`resolve_state_for_vuln` must be extended to accept a batched, pre-computed `excepted_seconds` lookup (mirroring the `corr_by_key` batching pattern below) rather than querying per-row.

**Batching precedent to copy** (`backend/app/vulnerabilities/service.py:217-240`):
```python
    # Phase 35 / SRC-01 / SRC-08: page-scoped batched provenance fetch.
    page_keys = {(v.cve_id, v.asset_id) for v in page_rows if v.cve_id and v.asset_id}
    corr_by_key: dict[tuple[str, uuid.UUID], VulnerabilityCorrelation] = {}
    if page_keys:
        corr_rows = (
            (
                await db.execute(
                    select(VulnerabilityCorrelation).where(
                        VulnerabilityCorrelation.tenant_id == tenant_id,
                        tuple_(VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id).in_(page_keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        corr_by_key = {(c.cve_id, c.asset_id): c for c in corr_rows}
```
Copy this exact "collect page-scoped keys → one extra batched query → dict lookup" shape for the lapsed-exception lookup: one extra query per page fetching every lapsed exception (`revoked_at IS NOT NULL OR expires_at <= now`) matching the page's `(cve_id, asset_id)` set (+ covering asset-groups), grouped into a dict, with overlapping `[created_at, COALESCE(revoked_at, expires_at)]` intervals merged in Python before summing (Pitfall 4 — D-12 permits overlap, naive `SUM()` would double-count). For `run_sla_tier_pass`/`detect_and_escalate` (whole-tenant scans, not paginated), batch the same lookup tenant-wide once per tick instead of per-row.

---

### F. Frontend — exceptions list page, table, chip-bar, query hooks

**Analog:** `frontend/src/app/(authed)/dashboard/campaigns/` (Phase 38) — page.tsx, `components/campaigns/campaigns-table.tsx`, `components/campaigns/campaigns-chip-bar.tsx`, `lib/queries/use-campaigns.ts`.

**List page — state-branch order + skeleton/empty/error composition** (`frontend/src/app/(authed)/dashboard/campaigns/page.tsx:96-145`):
```tsx
  const isLoading = q.isPending;

  return (
    <div className="space-y-4 p-6">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wide text-text-muted">
          Campaigns · {items.length} {items.length === 1 ? 'campaign' : 'campaigns'}
        </div>
        <h1 className="text-2xl font-semibold text-text">Campaigns</h1>
      </header>

      <CampaignsChipBar />

      {/* WR-13: state branches are mutually exclusive — error > loading > empty > data. */}
      {q.error ? (
        <PartialFailureBanner errors={[{ code: 'http_error', requestId: String((q.error as Error).message) || 'unknown' }]} onRetry={() => q.refetch()} />
      ) : isLoading ? (
        <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
      ) : items.length === 0 ? (
        <EmptyState>
          <EmptyState.Title>No campaigns yet</EmptyState.Title>
          <EmptyState.Body>...</EmptyState.Body>
          <EmptyState.Actions>...</EmptyState.Actions>
        </EmptyState>
      ) : (
        <CampaignsTable rows={items} onRowClick={onRowClick} />
      )}
    </div>
  );
```
Copy verbatim: the `ErrorBoundary > Suspense > <Page>Inner` outer composition (lines 1-32, 147-162 of the same file); the mutually-exclusive `error > loading > empty > data` branch order (WR-13); `SkeletonColumn[]` shape for `SkeletonTable`; `EmptyState.Title`/`.Body`/`.Actions` compound-component usage. For the exceptions list specifically, the empty-state copy and the filtered-to-zero variant are already locked in `39-UI-SPEC.md`'s Copywriting Contract — use those strings verbatim, not the campaigns copy shown here.

**Table — keyboard nav + row-click contract (table never calls `useRouter`)** (`frontend/src/components/campaigns/campaigns-table.tsx:56-121`, structure only):
```tsx
export function CampaignsTable({ rows, onRowClick }: CampaignsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);
  const onRowKeyDown = useCallback((e, campaign, idx) => {
    const rowsEls = tbodyRef.current?.querySelectorAll<HTMLTableRowElement>('tr[tabindex="0"]');
    if (!rowsEls) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); rowsEls[Math.min(idx + 1, rowsEls.length - 1)]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); rowsEls[Math.max(idx - 1, 0)]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); rowsEls[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); rowsEls[rowsEls.length - 1]?.focus(); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(campaign); }
  }, [onRowClick]);
  ...
  <tr key={r.id} tabIndex={0} onClick={() => onRowClick(r)} onKeyDown={(e) => onRowKeyDown(e, r, idx)}
      className={cn('cursor-pointer border-b border-border-subtle', 'hover:bg-surface-2 focus-visible:bg-surface-2',
                    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet')}>
```
Per UI-SPEC, `exceptions-table.tsx` deviates from this analog in one respect: row click does **not** navigate/open a drill panel — it toggles an inline accordion expand for justification + audit metadata. Keep the `tabIndex={0}` + Arrow/Home/End keyboard-nav shape, but the click/Enter handler opens local expand state instead of calling `onRowClick`/`router.push`. Column cells: mono truncate-with-title for long values (`className="block truncate font-mono text-text" title={r.remediation_id}`) is the exact precedent for the CVE/target and approver-name overflow backstop UI-SPEC calls for.

**Chip-bar — single/multi-axis filter composition** (`frontend/src/components/campaigns/campaigns-chip-bar.tsx`, full file):
```tsx
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

const STATUS_ALLOW = ['ACTIVE', 'COMPLETE'] as const;
const STATUS_LABEL: Record<(typeof STATUS_ALLOW)[number], string> = { ACTIVE: 'Active', COMPLETE: 'Complete' };

export function CampaignsChipBar() {
  const axes: ChipAxis[] = [
    { key: 'status', label: 'Status', allowList: STATUS_ALLOW, chips: STATUS_ALLOW.map((s) => ({ value: s, label: STATUS_LABEL[s] })) },
  ];
  return <ChipBar axes={axes} searchPlaceholder="Search remediation label…" searchAriaLabel="Search campaigns" />;
}
```
Copy this exact shape for `exceptions-chip-bar.tsx` with **two** axes instead of one: `type` (`FALSE_POSITIVE`/`ACCEPTED_RISK`, labels "False positive"/"Accept risk" per UI-SPEC) and `scope_type` (`FINDING`/`ASSET`/`ASSET_GROUP`, labels "Finding"/"Asset"/"Asset group"). The hardcoded `*_ALLOW` const array is a deliberate allow-list clamp (T-38-09/T-12-05 precedent) — reflected URL values outside it are dropped, not passed through.

**Query hook — `staleTime: 0` for a compute-on-read backend field** (`frontend/src/lib/queries/use-campaigns.ts`, full file):
```tsx
export function useCampaigns() {
  return useQuery({
    queryKey: queryKeys.campaigns.list(),
    queryFn: ({ signal }) => api<CampaignSummary[]>('/api/v1/campaigns', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
```
The `staleTime: 0` choice is explicitly because campaign progress/status is computed fresh on every backend read with zero persisted snapshot (D-07) — a stale client cache would show an out-of-date value. **The identical reasoning applies to the exceptions list's "expiring soon" pill and active/revoked state** — copy `staleTime: 0` for `useExceptions()`, not the `30_000` seen elsewhere (e.g. `use-assignable-users.ts`).

**`queryKeys` block to extend** (`frontend/src/lib/queries/keys.ts:122-125`):
```ts
  campaigns: {
    all: ['campaigns'] as const,
    list: () => ['campaigns', 'list'] as const,
    detail: (id: string) => ['campaigns', 'detail', id] as const,
  },
```
Add an `exceptions: { all: ['exceptions'] as const, list: () => ['exceptions', 'list'] as const }` block in the identical shape (no `detail` key needed unless a single-exception GET is added — UI-SPEC's inline-expand accordion reads from the already-fetched list array, not a per-row fetch).

**Mutations hook — grant/revoke, `retry: 0`, toast-on-settle** (`frontend/src/lib/queries/use-campaign-mutations.ts:57-87, 141-159`):
```tsx
export function useStartCampaign() {
  const router = useRouter();
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation<CampaignCreateResponse, Error, string>({
    mutationFn: (remediationId) =>
      api<CampaignCreateResponse>('/api/v1/campaigns', {
        method: 'POST', body: JSON.stringify({ remediation_id: remediationId }), headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: (data, remediationId) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.all });
      toast({ variant: 'success', message: `Campaign started for ${remediationId}.` });
      router.push(`/dashboard/campaigns/${data.id}`);
    },
    onError: () => { toast({ variant: 'error', message: "Couldn't start campaign — try again." }); },
    retry: 0,
  });
}

export function useCloseCampaign() {
  const qc = useQueryClient();
  const { toast } = useToast();
  return useMutation<CloseCampaignResponse, Error, string>({
    mutationFn: (campaignId) => api<CloseCampaignResponse>(`/api/v1/campaigns/${campaignId}/close`, { method: 'POST' }),
    onSuccess: (_data, campaignId) => {
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.campaigns.list() });
    },
    onError: () => { toast({ variant: 'error', message: "Couldn't close campaign — try again." }); },
    retry: 0,
  });
}
```
Copy directly for `useGrantException()` (mirrors `useStartCampaign` — POST, invalidate-all, toast, closes the dialog on success instead of routing) and `useRevokeException(id)` (mirrors `useCloseCampaign` — POST `/revoke`, invalidate list, **caller MUST route this through `ConfirmModal` per the `useCloseCampaign` doc-comment's explicit "never invoke `.mutate()` from a bare click handler" contract**, which matches UI-SPEC's Revoke → `ConfirmModal` requirement exactly). `retry: 0` on every mutation — never silently retried (audit attribution > convenience, per this file's own header comment).

---

### G. Frontend — Grant dialog, approver-combobox, drill-panel entry point, microcopy

**Drill-panel entry point — Actions section, exact button chrome to copy** (`frontend/src/components/vulnerabilities/drill-content.tsx:922-945`):
```tsx
        <section aria-labelledby="drill-actions-h">
          <h4 id="drill-actions-h" className="mb-2 text-xs uppercase tracking-wide text-text-muted">
            {microcopy.drill.sections.actions}
          </h4>
          <div className="flex flex-col gap-2">
            <button type="button" onClick={() => setConfirmOpen(true)}
              className="btn-cta inline-flex items-center justify-center gap-1.5 rounded-md bg-gradient-sunset px-4 py-2 text-sm font-medium text-text-inverse shadow-glow-cta hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet">
              {microcopy.drill.createTicket}
            </button>
            <button type="button" onClick={fireSnooze}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-text hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet">
              {microcopy.drill.snooze24h}
            </button>
          </div>
        </section>
```
Per UI-SPEC's Layout & Entry Points §1, add two more buttons in this exact `flex flex-col gap-2` stack, using the **secondary** button chrome (the second `<button>` shown above — `border border-border bg-surface-2`, not the gradient CTA) for both "Accept risk" and "Mark false positive": each `onClick` opens the new `ExceptionGrantDialog` with `type` pre-set and scope pre-defaulted to `FINDING` (the drill panel's own CVE × asset).

**Microcopy centralization to extend** (`frontend/src/components/vulnerabilities/microcopy.ts:47-69`):
```ts
  drill: {
    sections: { cvss: 'CVSS', riskExposure: 'Risk exposure', hosts: 'Affected hosts', description: 'Description', remediation: 'Remediation', activity: 'Activity', actions: 'Actions' },
    createTicket: 'Create ticket',
    snooze24h: 'Snooze 24h',
    copyNvd: 'Copy NVD link',
    closeAria: 'Close drill panel',
  },
```
Add `acceptRisk: 'Accept risk'` and `markFalsePositive: 'Mark false positive'` alongside `createTicket`/`snooze24h` in this exact object — this file is the single source of truth for every drill-panel string (copy-voice.md compliance is grep-verified against it at acceptance, per the file's own header comment).

**Approver field — pattern to copy, NOT the component to import (Pitfall 6)** (`frontend/src/components/assets/reassign-combobox.tsx`, full file, 198 lines):
```tsx
export function ReassignCombobox({ assetId, initialEmail, onDone }: ReassignComboboxProps) {
  const [input, setInput] = useState(initialEmail ?? '');
  const [debounced, setDebounced] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const users = useAssignableUsers(debounced);
  const mutation = useReassignAsset(assetId);   // <-- hardcoded mutation, the exact problem

  useEffect(() => { const t = setTimeout(() => setDebounced(input), DEBOUNCE_MS); return () => clearTimeout(t); }, [input]);

  const commit = (email: string) => {
    if (!email) return;
    mutation.mutate(email, { onSuccess: () => onDone() });   // <-- fires its own mutation on selection
  };

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); onDone(); }
    else if (e.key === 'Enter') { e.preventDefault(); const target = items[highlightIdx]; if (!target) return; commit(target.email); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setHighlightIdx((i) => Math.min(i + 1, Math.max(items.length - 1, 0))); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlightIdx((i) => Math.max(i - 1, 0)); }
  };
  // ... renders <input role="combobox" aria-controls/aria-expanded/aria-autocomplete/aria-activedescendant>
  // ... <ul role="listbox"><li role="option" aria-selected>...<Avatar name=.. email=.. size={24}/>...
}
```
Confirmed directly (Pitfall 6, verified this session): `ReassignCombobox` hardcodes `useReassignAsset(assetId)` and calls `mutation.mutate(email)` on selection — there is no `assetId` in the exception-grant dialog, and the approver field must NOT fire its own mutation (it is one field inside a larger form that submits once via "Grant exception"). **Build `approver-combobox.tsx` as a new sibling** that copies verbatim: the 250ms debounce effect, the `useAssignableUsers(debounced)` data source, the `highlightIdx` state + Arrow/Enter/Escape keyboard handling, the full WAI-ARIA combobox markup (`role="combobox"` on the `<input>`, `aria-controls`/`aria-expanded`/`aria-autocomplete`/`aria-activedescendant`, `role="listbox"`/`role="option"`), and the `<Avatar name=... email=... size={24}/>` + two-line name/email `<li>` rendering. **Change only the data-flow contract**: replace `initialEmail`/`onDone` + internal `useReassignAsset` mutation with `value: {email, display_name} | null` and `onSelect(user: DirectoryUser) => void` props — no internal mutation call at all.

**Data source the combobox depends on** (`frontend/src/lib/queries/use-assignable-users.ts`, full file, unmodified — reused verbatim):
```ts
export function useAssignableUsers(search: string) {
  return useQuery({
    queryKey: queryKeys.assignableUsers.search(search),
    queryFn: ({ signal }) => {
      const sp = new URLSearchParams();
      sp.set('status', 'active');
      if (search) sp.set('search', search);
      sp.set('page_size', '25');
      return api<AssignableUsersResponse>(`/api/v1/users/directory?${sp.toString()}`, { signal });
    },
    enabled: search.trim().length >= 2,
    staleTime: 30_000,
    retry: 1,
  });
}
```
No changes needed — `approver-combobox.tsx` imports this hook exactly as `reassign-combobox.tsx` does.

**Dialog shell — props contract** (`frontend/src/components/ui/responsive-dialog.tsx:22-44`):
```tsx
interface ResponsiveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  dismissOnBackdropClick?: boolean;
  children: React.ReactNode;
}
```
`exception-grant-dialog.tsx` wraps this directly (desktop centered modal / mobile vaul bottom sheet, per UI-SPEC's explicit "same dual-surface pattern as `ConfirmModal`"), rather than reusing `ConfirmModal` itself — `ConfirmModal`'s API (`title`/`message`/`confirmLabel`/`variant="danger"|"warning"|"info"`) is confirmation-shaped, not a 4-field form. UI-SPEC's mockup (chip + fixed CVE/asset header, segmented control, combobox, textarea, date input, gradient submit) needs the bespoke children-composition freedom `ResponsiveDialog` gives directly.

**Multi-field-form-inside-a-dialog precedent** (`frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx:334-354`) — shows the codebase's only existing multi-field dialog form, useful for the *field-composition* pattern even though it uses `ConfirmModal`'s `children` slot rather than a bespoke `ResponsiveDialog` wrapper:
```tsx
      <ConfirmModal
        open={createDialogOpen} title="Create tickets" ... confirmDisabled={!provider || !projectKey.trim()}
        onConfirm={onConfirmCreateTickets} onCancel={() => setCreateDialogOpen(false)}
      >
        <div className="space-y-3">
          <TicketProviderPicker value={provider} onChange={setProvider} />
          <Input aria-label="Project key" placeholder="Project key (e.g. SEC)" value={projectKey} onChange={(e) => setProjectKey(e.target.value)} />
        </div>
      </ConfirmModal>
```
The pattern to copy: `confirmDisabled={...}` (or the gradient submit button's own `disabled`) gates on **every required field being non-empty simultaneously** — the exact shape UI-SPEC requires for "Grant exception" staying disabled until scope target + approver + justification + expiry are all filled (D-06).

**Revoke confirmation — verbatim reuse** (`frontend/src/components/ui/ConfirmModal.tsx`, full file, 113 lines — no changes needed, import directly):
```tsx
export default function ConfirmModal({ open, title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", variant = "info", onConfirm, onCancel, children, confirmDisabled = false }: ConfirmModalProps) {
  ...
  const btnColor = variant === "danger" ? "bg-severity-critical text-white hover:bg-severity-critical/90" : variant === "warning" ? "bg-amber text-surface hover:bg-amber/90" : "bg-violet text-white hover:bg-violet/90";
  return (
    <ResponsiveDialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }} ariaLabel={title}>
      ...
    </ResponsiveDialog>
  );
}
```
Per UI-SPEC, the Revoke button opens this exact component with `variant="warning"` and the exact copy already locked in UI-SPEC's Copywriting Contract (title "Revoke this exception?", confirmLabel "Revoke exception").

**Native `<select>`/date-input styling convention** (`frontend/src/components/settings/sla-escalation-pane.tsx:267-268, 650-665`) — the precedent UI-SPEC cites for the Scope-target picker:
```tsx
const FIELD_CLASS = 'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
...
              <label htmlFor="sla-tier-floor" className="mb-1 block text-sm font-medium text-text">Escalate at</label>
              <select id="sla-tier-floor" disabled={!isOwner} value={values.tierFloor}
                onChange={(e) => setField('tierFloor', e.target.value as 'critical' | 'high' | 'moderate')}
                className={`${FIELD_CLASS} max-w-xs`}>
                <option value="critical">Critical only</option>
                <option value="high">High and critical</option>
                <option value="moderate">All tracked tiers</option>
              </select>
```
Copy `FIELD_CLASS`'s exact Tailwind string (or the equivalent already-shared `field-input` utility UI-SPEC refers to by that name) for both the asset-group `<select>` and the `<input type="date">` — this codebase's convention for `<select>`/date inputs is a plain native element, never shadcn's Radix `select`/`popover`/`calendar` (confirmed: UI-SPEC's own Design System section states "no new shadcn components required this phase").

**Textarea char-counter — the justification field's 1000-char cap** (`frontend/src/components/tickets/comment-input.tsx:20-21, 34-35, 57-77`):
```tsx
const MAX_LENGTH = 10000;
const WARN_THRESHOLD = 9500;
...
  const charsLeft = MAX_LENGTH - body.length;
  const showCount = body.length >= WARN_THRESHOLD;
...
        <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={MAX_LENGTH} rows={3}
          className="w-full resize-none rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-violet focus:outline-none focus-visible:ring-2 focus-visible:ring-violet disabled:opacity-50" />
        <div className="flex items-center justify-between">
          {showCount ? <span className="font-mono text-xs text-text-muted">{microcopy.charLimitWarning(charsLeft)}</span> : <span />}
```
Copy this exact `MAX_LENGTH`/`WARN_THRESHOLD`/`charsLeft`/`showCount` shape for the Justification field: `MAX_LENGTH = 1000` (UI-SPEC's cap), `maxLength={1000}` on the `<textarea>` (defense-in-depth mirroring the backend's `Text` column app-layer cap), counter appears only near the limit — never a permanently-visible counter.

**Nav entry** (`frontend/src/components/shell/nav-items.ts:34-50`):
```ts
export const WORKFLOW_ITEMS: NavItem[] = [
  { label: 'Tickets',    href: '/dashboard/tickets',       icon: Ticket, chip: 'ticket_open' },
  { label: 'Rules',      href: '/dashboard/tickets/rules', icon: Zap },
  { label: 'Connectors', href: '/dashboard/connectors',    icon: Plug },
  { label: 'Asset groups', href: '/dashboard/asset-groups', icon: FolderKanban },
  { label: 'Campaigns', href: '/dashboard/campaigns', icon: Target },
];
```
Add `{ label: 'Exceptions', href: '/dashboard/exceptions', icon: ShieldOff }` (import `ShieldOff` from `lucide-react` alongside the existing icon imports at the top of the file) after the `Campaigns` entry — no `chip` key, per this file's own `D-N-01` rule (only `vuln_open`/`asset_total`/`ticket_open` carry live-count chips), matching UI-SPEC's explicit Navigation note.

---

## Shared Patterns

### RBAC — `require_analyst` / `require_viewer`
**Source:** `backend/app/auth/rbac.py` (full file, 53 lines):
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
**Apply to:** `POST /` (grant), `POST /{id}/revoke` → `Depends(require_analyst)`; `GET /` (list) → `Depends(require_viewer)`. No new RBAC primitive needed — inject the existing dependency exactly as `campaigns/router.py` does.

### Audit — fail-closed `audit()`, action-then-commit ordering
**Source:** `backend/app/audit.py:143-196` (signature + fail-closed contract):
```python
async def audit(
    db: AsyncSession, user: CurrentUser | None, action: str, resource_type: str,
    resource_id: str | None = None, details: dict | None = None, ip_address: str | None = None,
) -> None:
    """... fail-closed. ... Caller pattern is `audit(...); await db.commit()`,
    so any exception raised here propagates and the commit is skipped ..."""
```
And the Actions comment block to extend (`backend/app/audit.py:53-76`):
```python
# ── Actions ──
# auth.login, auth.register, ...
# asset_group.create, asset_group.update, asset_group.delete, ...
# risk_cutover.threshold_ack (Phase 34 Plan 03 — RISK-09, admin-only, ...)
```
**Apply to:** every mutating exceptions endpoint. Add `exception.grant`, `exception.revoke` (and `exception.expire` if the optional Pattern-4 lazy audit is adopted) to this comment list, matching how every prior phase has appended its own action names here. Grant payload: `{"type", "scope_type", "cve_id", "approver_user_id", "justification", "expires_at"}` (EXC-03's who/why/scope/expiry). Revoke payload: who/when (implicit in `AuditLog.user_id`/`created_at`).

### Router registration
**Source:** `backend/app/main.py:31, 271, 310-324`:
```python
from app.campaigns.router import router as campaigns_router
...
def create_app() -> FastAPI:
    ...
    app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
```
**Apply to:** add `from app.exceptions.router import router as exceptions_router` near line 31, and `app.include_router(exceptions_router, prefix="/api/v1/exceptions", tags=["Exceptions"])` near line 319-324 (alongside the other feature routers, before `notifications_router`/`search_router`).

### Frontend dialog shell + destructive confirmation
**Source:** `ResponsiveDialog` (`frontend/src/components/ui/responsive-dialog.tsx`) wraps every modal in this codebase; `ConfirmModal` (`frontend/src/components/ui/ConfirmModal.tsx`) wraps `ResponsiveDialog` for the confirm/cancel shape. **Apply to:** `exception-grant-dialog.tsx` wraps `ResponsiveDialog` directly (bespoke form); the Revoke action reuses `ConfirmModal` verbatim with `variant="warning"`.

### Copy centralization
**Source:** `frontend/src/components/vulnerabilities/microcopy.ts` — every vulnerabilities-surface string lives in one exported `const microcopy` object, grep-verified against `copy-voice.md` at acceptance. **Apply to:** either extend this file's `drill` block (for the two new Actions buttons, since they live inside `drill-content.tsx`) or create a sibling `frontend/src/components/exceptions/microcopy.ts` for the list/dialog-specific strings already locked in `39-UI-SPEC.md`'s Copywriting Contract — either is consistent with the established convention; UI-SPEC's copy is already final either way.

---

## No Analog Found

Genuinely novel pieces this session found no existing codebase precedent for (planner should follow RESEARCH.md's reasoning directly rather than hunt further — these are small, bounded, and RESEARCH.md's Code Examples/Pattern sections already spell them out):

| Item | Role | Data Flow | Reason |
|---|---|---|---|
| `<input type="date">` element | frontend form field | request-response | `grep -rl 'type="date"' frontend/src --include="*.tsx"` returned zero matches anywhere in the codebase — this is the first native date input. The **styling convention** (`FIELD_CLASS`/`field-input`) transfers from `sla-escalation-pane.tsx`'s `<select>` (Pattern G above), but the `min`/`max` attribute wiring for D-14's future-only + hard-cap validation has no prior example to copy. |
| D-16 interval-merge (lapsed-exception overlap summation) | service (pure computation) | transform | No interval-algebra code of any kind exists in this codebase today (confirmed via the "Don't Hand-Roll" table in RESEARCH.md — recommends a ~10-line merge-adjacent-sorted-intervals loop, explicitly rejecting a dependency). This is new logic, not a pattern extension of anything existing. |

Everything else in this phase — including the `active_exception_subquery`'s three-way `OR` across `FINDING`/`ASSET`/`ASSET_GROUP` branches — is a **recombination** of existing, separately-precedented pieces (the `EXISTS`-correlated-subquery shape from `_apply_filters`'s correlation-array check, the `AssetGroupMember` join from `groups_service.py`) rather than a wholly new mechanism, so it is not listed here as "no analog."

## Metadata

**Analog search scope directories:** `backend/app/{campaigns,vulnerabilities,assets,ticketing,auth,exceptions(absent)}`, `backend/alembic/versions`, `backend/tests`, `frontend/src/{app/(authed)/dashboard,components/{campaigns,vulnerabilities,assets,shell,tickets,settings,ui},lib/queries}`.
**Files read this session (full or targeted, non-overlapping):** 34 — `campaigns/{models,schemas,service,router}.py`, `alembic/versions/049_add_campaigns.py`, `vulnerabilities/{models,service,sla_tier_service,remediation_service,router}.py`, `assets/{models,risk_score,groups_service}.py`, `ticketing/rule_engine.py`, `audit.py`, `auth/rbac.py`, `main.py` (grep + targeted), `tests/test_campaigns.py` (header), `app/(authed)/dashboard/campaigns/page.tsx`, `app/(authed)/dashboard/campaigns/[id]/page.tsx` (targeted), `components/campaigns/{campaigns-table,campaigns-chip-bar}.tsx`, `components/assets/reassign-combobox.tsx`, `components/vulnerabilities/{drill-content (targeted),microcopy}.tsx`, `components/ui/{ConfirmModal,responsive-dialog (targeted)}.tsx`, `components/settings/sla-escalation-pane.tsx` (targeted), `components/tickets/comment-input.tsx` (targeted), `components/shell/nav-items.ts`, `lib/queries/{use-campaigns,use-campaign-mutations,use-assignable-users,keys (grep)}.ts`.
**Pattern extraction date:** 2026-08-18
