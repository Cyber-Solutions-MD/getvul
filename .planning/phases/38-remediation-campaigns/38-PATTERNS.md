# Phase 38: Remediation Campaigns - Pattern Map

**Mapped:** 2026-08-17
**Files analyzed:** 16 (backend: 6 new, 2 modified; frontend: 8 new, 2 modified)
**Analogs found:** 16 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/app/campaigns/models.py` | model | CRUD | `backend/app/vulnerabilities/models.py` (`RemediationEvent`, `SlaEscalationEvent`) | exact (identical Mixin/FK/Index conventions) |
| `backend/alembic/versions/049_add_campaigns.py` | migration | batch/DDL | `backend/alembic/versions/020_add_sla_tracking.py` (`postgresql_where`) + `047_add_remediation_events.py` (table-create shape) | exact |
| `backend/app/campaigns/schemas.py` | model (DTO) | request-response | `backend/app/ticketing/schemas.py` (`extra="forbid"` convention) | role-match |
| `backend/app/campaigns/service.py` | service | CRUD + aggregation (compute-on-read) | `backend/app/vulnerabilities/sla_tier_service.py:395-440` (race-safe get-or-create) + `backend/app/vulnerabilities/service.py:481-504` (`get_mttr_by_tier`, aggregation shape) + `backend/app/ticketing/service.py:548-706` (`create_remediation_ticket`, bulk ticketing to re-carve) | exact (composite of 3 direct precedents) |
| `backend/app/campaigns/router.py` | router/controller | request-response | `backend/app/vulnerabilities/router.py:811-871` (`suppress_remediation`, bulk-write-over-a-remediation-group + RBAC + audit) | exact |
| `backend/app/main.py` (modified — add import + `include_router`) | config | request-response | `backend/app/main.py:33/315` (`cspm_router` registration — same "new small top-level domain" shape) | exact |
| `backend/tests/test_campaigns.py` | test | CRUD/event-driven | `backend/tests/test_finding_reopen.py` (fixture surface, env-var requirement) | role-match |
| `frontend/src/lib/queries/use-campaigns.ts` | hook | request-response | `frontend/src/lib/queries/use-vuln-escalations.ts` | exact |
| `frontend/src/lib/queries/keys.ts` (modified — add `campaigns` block) | config | request-response | `frontend/src/lib/queries/keys.ts:65-73` (`tickets` block, the most structurally similar list+detail namespace) | exact |
| `frontend/src/components/campaigns/campaigns-chip-bar.tsx` | component | request-response | `frontend/src/components/tickets/tickets-chip-bar.tsx` | exact |
| `frontend/src/components/campaigns/campaigns-table.tsx` | component | request-response | `frontend/src/components/tickets/tickets-table.tsx` | exact |
| `frontend/src/components/campaigns/campaign-burndown-card.tsx` | component | request-response | `frontend/src/components/ui/RiskRing.tsx` (composed, score=`pct_remediated`) | role-match (reuse, not clone) |
| `frontend/src/components/campaigns/campaign-status-ribbon.tsx` | component | request-response | `frontend/src/components/assets/severity-ribbon.tsx` | role-match (status-colored sibling) |
| `frontend/src/app/(authed)/dashboard/vulnerabilities/remediations/page.tsx` | component (page) | request-response | `frontend/src/app/(authed)/dashboard/tickets/page.tsx` (list page: ErrorBoundary>Suspense>Inner, chip-bar+table+states) | role-match |
| `frontend/src/app/(authed)/dashboard/campaigns/page.tsx` | component (page) | request-response | `frontend/src/app/(authed)/dashboard/tickets/page.tsx` | exact |
| `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx` | component (page) | request-response | `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` (two-column-sticky-rail detail) | exact |
| `frontend/src/components/shell/nav-items.ts` (modified — add `Campaigns` to `WORKFLOW_ITEMS`) | config | request-response | `frontend/src/components/shell/nav-items.ts:34-46` (existing `WORKFLOW_ITEMS` array, e.g. the `Asset groups` entry) | exact |

## Pattern Assignments

### `backend/app/campaigns/models.py` (model, CRUD)

**Analog:** `backend/app/vulnerabilities/models.py` — `RemediationEvent` (lines 253-297) and its imports (lines 1-13); partial-unique-index mechanics confirmed against `backend/alembic/versions/020_add_sla_tracking.py:27-32`.

**Imports pattern** (`backend/app/vulnerabilities/models.py:1-13`):
```python
"""Vulnerability and Correlation SQLAlchemy models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
```
For `campaigns/models.py`, additionally import `Index` and `text` (needed for the partial index) — neither is imported in `vulnerabilities/models.py` today.

**Core model pattern — FK + Mixin conventions** (`backend/app/vulnerabilities/models.py:253-297`):
```python
class RemediationEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "remediation_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tier_at_remediation: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remediated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```
Copy this shape verbatim for `Campaign`'s `tenant_id`/`created_by_user_id`/`closed_by_user_id` FK columns (`ondelete="CASCADE"` for tenant, `ondelete="SET NULL"` for user FKs, matching `AuditLog.user_id` at `backend/app/audit.py:43`).

**Partial unique index (D-11)** — RESEARCH.md's Code Example 1 already gives the exact `__table_args__` shape; verified precedent is `020_add_sla_tracking.py:27-32` (`op.create_index(..., postgresql_where=sa.text(...))` — not `unique=True` there, but the identical `postgresql_where` mechanic). Use `sqlalchemy.Index(..., unique=True, postgresql_where=text("closed_at IS NULL"))` inside `__table_args__` — **never** `UniqueConstraint` (Postgres/SQLAlchemy has no `postgresql_where` on `UniqueConstraint`; see RESEARCH.md Pitfall 3).

**Docstring convention** — every recent model in this file (`RemediationEvent`, presumably `SlaEscalationEvent`) documents its provenance phase/decision IDs and its uniqueness-guarantee source in the class docstring (see the 30-line `RemediationEvent` docstring). Follow this for `Campaign`: state which decision (D-01/D-02/D-07/D-11) each design choice satisfies.

---

### `backend/alembic/versions/049_add_campaigns.py` (migration, batch/DDL)

**Analog:** `backend/alembic/versions/020_add_sla_tracking.py` (partial index) + `backend/alembic/versions/048_add_clean_scan_streak.py` (confirm as literal `down_revision` — verify head at plan time, do not hardcode from research alone).

**Full migration pattern** (`020_add_sla_tracking.py`, full file, 40 lines):
```python
"""020 - Add SLA tracking fields.

Revision ID: 020_sla_tracking
Revises: 019_asset_ignored
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "020_sla_tracking"
down_revision = "019_asset_ignored"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vulnerabilities", sa.Column("sla_breached", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("tenants", sa.Column("sla_config", postgresql.JSONB, nullable=True))

    op.create_index(
        "ix_vuln_sla_due_at",
        "vulnerabilities",
        ["sla_due_at"],
        postgresql_where=sa.text("status IN ('OPEN', 'IN_PROGRESS')"),
    )


def downgrade() -> None:
    op.drop_index("ix_vuln_sla_due_at", table_name="vulnerabilities")
    op.drop_column("tenants", "sla_config")
    op.drop_column("vulnerabilities", "sla_breached")
    op.drop_column("vulnerabilities", "sla_due_at")
```
For D-11's *unique* partial index, add `unique=True` to `op.create_index(...)` — the RESEARCH.md Code Example 2 (lines 522-580 of `38-RESEARCH.md`) already gives the full table-creation + partial-unique-index migration body; treat that as the concrete template, this analog as the proof the `postgresql_where` kwarg compiles correctly in this codebase's Alembic setup. **Verify `down_revision = "048_add_clean_scan_streak"` against the actual current head before writing** (`ls backend/alembic/versions | tail -3` at plan/execute time — RESEARCH.md's citation may drift if another phase lands a migration first).

---

### `backend/app/campaigns/schemas.py` (model/DTO, request-response)

**Analog:** `backend/app/ticketing/schemas.py` — `extra="forbid"` convention (ASVS V5 mass-assignment defense, cited at `ticketing/schemas.py:69` per RESEARCH.md).
```python
# Pattern to copy (exact shape confirmed by RESEARCH.md citation of ticketing/schemas.py:69):
class TicketCreateRequest(BaseModel):
    """... T-25-06, ASVS V5 ..."""
    model_config = ConfigDict(extra="forbid")
    # fields...
```
Apply `model_config = ConfigDict(extra="forbid")` to `CampaignCreateRequest` and `CampaignBulkAssignRequest`.

---

### `backend/app/campaigns/service.py` (service, CRUD + compute-on-read aggregation)

**Analog 1 — race-safe get-or-create (D-11):** `backend/app/vulnerabilities/sla_tier_service.py:406-428`
```python
try:
    async with db.begin_nested():
        db.add(event)
        await db.flush()
except IntegrityError:
    # W4 hardening: another pass already reserved this exact
    # (finding, to_state, channel) -- skip the POST entirely,
    # the UniqueConstraint guards the outbound send itself.
    continue
```
This is the exact `IntegrityError` + `begin_nested()` shape to copy for `get_or_create_campaign()`. RESEARCH.md's Code Example (Pattern 3, `38-RESEARCH.md:266-295`) already adapts this precisely to the campaign SELECT-then-INSERT-then-catch shape — use it verbatim.

**Analog 2 — compute-on-read aggregation shape:** `backend/app/vulnerabilities/service.py:481-504` (`get_mttr_by_tier`)
```python
async def get_mttr_by_tier(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    mttr_q = (
        select(
            RemediationEvent.tier_at_remediation,
            func.avg(RemediationEvent.duration_seconds).label("avg_seconds"),
            func.count().label("count"),
        )
        .where(RemediationEvent.tenant_id == tenant_id)
        .group_by(RemediationEvent.tier_at_remediation)
    )
    rows = (await db.execute(mttr_q)).all()
    return [
        {
            "tier_at_remediation": r.tier_at_remediation,
            "avg_seconds": float(r.avg_seconds) if r.avg_seconds is not None else None,
            "count": r.count,
        }
        for r in rows
    ]
```
Copy the `func.avg(...)` + explicit `float(...) if ... is not None else None` Decimal-coercion (Pitfall 7) verbatim for `get_campaign_mttr()`.

**CRITICAL — do NOT copy this filter for campaign progress:** `backend/app/vulnerabilities/remediation_service.py:14-32` (`_base_open_vulns`)
```python
def _base_open_vulns(tenant_id: uuid.UUID, show_suppressed: str = "active"):
    ...
    return and_(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),   # <-- NEVER includes REMEDIATED
    )
```
D-18/Pitfall 2: campaign progress/membership must use its own filter — `Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "REMEDIATED"])` — never call or copy `_base_open_vulns()`. RESEARCH.md's Code Example 3 (`38-RESEARCH.md:590-629`, `get_campaign_progress()`/`get_campaign_mttr()`) is the corrected, ready-to-use version — use it as the primary template, with `get_mttr_by_tier()` above as the proof-of-shape precedent.

**Analog 3 — per-owner ticket carve-up (D-04/D-05/D-06/D-08):** `backend/app/ticketing/service.py:548-706` (`create_remediation_ticket`)
```python
vulns_q = (
    select(Vulnerability, Asset.hostname, Asset.assigned_user, Asset.mdm_details)
    .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
    .where(
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.remediation_id == remediation_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
    )
)
...
existing = await db.execute(
    select(Ticket).where(
        Ticket.tenant_id == tenant_id,
        Ticket.provider == provider,
        Ticket.resolved_at.is_(None),
        Ticket.created_by_rule == remediation_id,
    ).limit(1)
)
...
for vuln, hostname, assigned_user, mdm in rows:
    email = (mdm or {}).get("humaans_email")
...
url = await client.create(task_name, notes, **_provider_create_kwargs(provider, assignee_email, due_on))
ref = _extract_ref(url)
for vuln, _hostname, _, _ in rows:
    ticket = Ticket(
        tenant_id=tenant_id, vulnerability_id=vuln.id, provider=provider,
        external_ticket_id=f"{ref}:{vuln.id}", external_ticket_url=url,
        external_status="open", project_key=project_key, assignee=assignee_email,
        created_by_user_id=user_id, created_by_rule=remediation_id,
        detected_at=vuln.first_detected_at, ticket_created_at=now,
    )
    db.add(ticket)
    vuln.status = "IN_PROGRESS"
```
**Owner-derivation line to reuse verbatim (D-05):** `(mdm or {}).get("humaans_email")` — line 614 of `ticketing/service.py`.
**N-rows-share-one-URL linkage to reuse verbatim (D-04/D-06):** `external_ticket_id=f"{ref}:{vuln.id}"`, `external_ticket_url=url` shared across all rows in the loop — lines 674-688.
**Dedup/adopt check to re-carve per-vulnerability (D-06), NOT group-level like the existing `Ticket.created_by_rule == remediation_id` check** — campaign adoption must check `Ticket.vulnerability_id.in_(vuln_ids), Ticket.resolved_at.is_(None)` per RESEARCH.md's Code Example (Pattern 4), not the group-level exact-match check this function itself uses at lines 591-602 (that check would incorrectly say "a ticket already exists for this whole group" the first time ANY member gets ticketed).
**Pitfall 1 / D-20 — `created_by_rule` value:** set campaign-created tickets' `created_by_rule = campaign.remediation_id` (the bare string, matching this function's own convention at line 684), NOT a `"campaign:{id}"`-prefixed string — this closes the rule-engine double-ticket gap for free (see RESEARCH.md Pitfall 1).
**Related sibling to study for the loop structure (not to copy verbatim):** `backend/app/ticketing/rule_engine.py:208-262` (`per_remediation` ticket mode) — precedent for looping a remediation-scoped query and calling ticket-creation once per bucket; campaigns loop by *owner* instead of by *remediation_id*.
**Provider dispatch (D-08 default-project fallback):** `backend/app/ticketing/dispatch.py:130-154` (`build_ticketing_client`) — reuse `TicketingClient.create(...)` unchanged; the "unassigned" bucket (owner_email=None) still calls the same `client.create()` with no assignee kwarg, landing in the connector's already-configured default project/board.

**Zero-member guard (Pitfall 5):**
```python
"pct_remediated": round(done / total * 100) if total else 0,
```

---

### `backend/app/campaigns/router.py` (router/controller, request-response)

**Analog:** `backend/app/vulnerabilities/router.py:811-871` (`suppress_remediation`) — the closest existing precedent for "a bulk write over an entire remediation_id group, `require_analyst`-gated, audited, committed."
```python
@router.post("/remediations/{remediation_id}/suppress")
async def suppress_remediation(
    remediation_id: str,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    """Suppress all vulnerabilities linked to a remediation. ..."""
    ...
    result = await db.execute(
        update(Vulnerability)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.remediation_id == remediation_id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .values(status="SUPPRESSED", updated_at=now)
    )
    suppressed_count = result.rowcount

    from app.audit import audit as _audit
    await _audit(
        db, user, "vuln.suppress", "remediation", remediation_id,
        {"suppressed": suppressed_count, "assets": len(affected_asset_ids)},
    )
    await db.commit()
    return {...}
```
**Read endpoint precedent:** `backend/app/vulnerabilities/router.py:781-808` (`remediations_grouped`) — `Depends(require_viewer)`, delegates all logic to a `service.py` function, returns its dict directly. Copy this shape for `GET /campaigns` and `GET /campaigns/{id}`.

**RBAC dependency imports** (`require_analyst`/`require_viewer`) — `backend/app/auth/rbac.py:50-53`:
```python
require_viewer = RequireRole(UserRole.VIEWER.value)
require_analyst = RequireRole(UserRole.ANALYST.value)
require_admin = RequireRole(UserRole.ADMIN.value)
require_owner = RequireRole(UserRole.OWNER.value)
```

**Audit call signature** (`backend/app/audit.py:143-151`):
```python
async def audit(
    db: AsyncSession,
    user: CurrentUser | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
```
Fail-closed by design (lines 152-196) — **never wrap `audit()` in try/except** (would defeat AUDIT-01). Call pattern is always `await audit(...)` immediately followed by `await db.commit()` in the same request, exactly as `suppress_remediation` does. Action-name convention (see `audit.py:53-76` comment block) is dotted-verb (`campaign.create`, `campaign.bulk_assign`, `campaign.close`) — matches D-15/RESEARCH.md Assumption A7.

**System-actor pattern for lazy-on-read auto-complete/reactivate (D-19, Pattern 6):** `backend/app/vulnerabilities/service.py:439-478` (`reopen_vulnerability`)
```python
db.add(
    AuditLog(
        tenant_id=vuln.tenant_id,
        user_id=None,
        user_email="system:rescan-reopen",
        action="vuln.reopen_recurrence",
        resource_type="vulnerability",
        resource_id=str(vuln.id),
        details={"source": vuln.source},
        ip_address=None,
        created_at=datetime.now(UTC),
    )
)
```
Mirror this for the campaign auto-complete/reactivate system-attributed rows: `user_id=None`, `user_email="system:campaign-complete"` (per RESEARCH.md's naming). Note this bypasses the `audit()` helper and constructs `AuditLog` directly — same as `reopen_vulnerability` does — because there is no `CurrentUser` to pass (the write happens inside a `require_viewer`-gated GET, attributed to the system, not the viewing user).

---

### `backend/app/main.py` (config, modified)

**Analog:** `backend/app/main.py:33` (import) + `:315` (registration) — `cspm_router`, the most recent "new small top-level domain" registration.
```python
from app.cspm.router import router as cspm_router
...
app.include_router(cspm_router, prefix="/api/v1/cspm", tags=["CSPM"])
```
Add:
```python
from app.campaigns.router import router as campaigns_router
...
app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
```
Place alongside the other domain routers in the `:309-322` block (after `tickets_router`, before `notifications_router`, matching alphabetical-ish grouping already loosely present).

---

### `backend/app/campaigns/__init__.py`, module layout

**Analog:** `backend/app/notifications/` and `backend/app/cspm/` directory listings — both are exactly `__init__.py`, `models.py`, `router.py`, `service.py` (+ `schemas.py` for cspm). Confirmed via direct `ls`:
```
backend/app/notifications/: __init__.py alerts.py escalation_channels.py models.py router.py service.py
backend/app/cspm/:          __init__.py models.py router.py schemas.py service.py
```
`app/campaigns/` should mirror `app/cspm/`'s exact 5-file shape (`__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`) — this is the codebase's own convention for "new small top-level domain," not an invented pattern. Do NOT nest under `app/ticketing/` or `app/vulnerabilities/` (see RESEARCH.md Pattern 1 rationale — campaigns read from `vulnerabilities` and write to `ticketing` roughly equally).

---

### `backend/tests/test_campaigns.py` (test)

**Analog:** `backend/tests/test_finding_reopen.py:8-10` — env-var + fixture-surface precedent.
- Fixture surface already covers everything needed with zero new fixtures: `db_session`, `tenant_a`, `analyst_user`, `viewer_user`, `client` (per `backend/tests/conftest.py`, confirmed by RESEARCH.md).
- **Run command convention** (project memory `getvul-backend-pytest-env`): `ENCRYPTION_KEY=<fernet-key> JWT_SECRET_KEY=test-secret pytest backend/tests/test_campaigns.py -x` — run **per-file**, never the whole `tests/` directory (false failures otherwise).

---

### `frontend/src/lib/queries/use-campaigns.ts` (hook, request-response)

**Analog:** `frontend/src/lib/queries/use-vuln-escalations.ts` (full file, 36 lines):
```typescript
'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type VulnEscalationEvent = { ... };

export function useVulnEscalations(id: string | null) {
  return useQuery({
    queryKey: queryKeys.vulnerabilities.escalations(id ?? ''),
    queryFn: ({ signal }) =>
      api<VulnEscalationEvent[]>(
        `/api/v1/vulnerabilities/${encodeURIComponent(id!)}/escalations`,
        { signal },
      ),
    enabled: id !== null && id !== '',
    staleTime: 30_000,
    retry: 1,
  });
}
```
Copy this exact shape for `useCampaignDetail(id)` — RESEARCH.md's Code Example 5 (`38-RESEARCH.md:693-724`) already has the adapted version. **Key deviation from this analog:** set `staleTime: 0` (not `30_000`) — D-07 compute-on-read means a stale cache is never authoritative for progress %, unlike escalation history which is append-only historical data safe to cache briefly.

**`campaigns` block for `keys.ts`** — analog is the existing `tickets` block (`frontend/src/lib/queries/keys.ts:65-73`):
```typescript
tickets: {
  all: ['tickets'] as const,
  list: (opts: { filters: object; page: number; view: string }) =>
    ['tickets', 'list', opts] as const,
  byId: (id: string) => ['tickets', 'detail', id] as const,
  comments: (id: string) => ['tickets', id, 'comments'] as const,
  watchers: (id: string) => ['tickets', id, 'watchers'] as const,
  rules: () => ['tickets', 'rules'] as const,
},
```
Add a sibling `campaigns` block with `all`/`list`/`detail` (matching RESEARCH.md's proposed shape at `38-RESEARCH.md:726-732`).

---

### `frontend/src/components/campaigns/campaigns-chip-bar.tsx` (component)

**Analog:** `frontend/src/components/tickets/tickets-chip-bar.tsx` (full file, 148 lines) — delegates to the generic `<ChipBar axes={...}>` primitive, hardcoded allow-lists per axis (T-12-05 XSS clamp pattern):
```typescript
import { ChipBar, type ChipAxis } from '@/components/ui/ChipBar';

const STATUS_ALLOW = ['open', 'in_progress', 'completed', 'blocked'] as const;
...
const axes: ChipAxis[] = [
  { key: 'status', label: 'Status', allowList: STATUS_ALLOW, chips: STATUS_ALLOW.map(...) },
  ...
];

return (
  <ChipBar axes={axes} searchPlaceholder="Search ID, title, or assignee…" searchAriaLabel="Search tickets" />
);
```
Campaign list chip-bar only needs a `status` axis (`ACTIVE`/`COMPLETE`, per the UI-SPEC), so this is a much simpler 1-axis version of the same `ChipBar` primitive composition — same allow-list-as-module-constant convention applies.

---

### `frontend/src/components/campaigns/campaigns-table.tsx` (component)

**Analog:** `frontend/src/components/tickets/tickets-table.tsx` — table shell composed with `SkeletonTable`/`EmptyState`/`PartialFailureBanner` states (see `tickets/page.tsx` composition below) and mono-formatted numeric columns (JetBrains Mono, tabular-nums, per CLAUDE.md + UI-SPEC). Columns per UI-SPEC: remediation label (mono) · member count · % remediated (mono, tabular-nums) · MTTR (mono) · status pill · owner-ticket count.

---

### `frontend/src/components/campaigns/campaign-burndown-card.tsx` (component)

**Analog:** `frontend/src/components/ui/RiskRing.tsx` (reused directly, not cloned — pass `score = pct_remediated`):
```typescript
export type RiskBand = 'critical' | 'high' | 'medium' | 'low' | 'unavailable';
export function getRiskBand(score: number | null): RiskBand { ... }
```
The UI-SPEC (`38-UI-SPEC.md` §Layout & Interaction Reuse item 3) mandates reusing "the asset-detail risk-ring's exact dimensions" with the sunset-gradient stroke ALWAYS, only the *semantic meaning* of the number changes (% remediated, not risk score) — do not fork the SVG math, wrap `RiskRing` with a campaign-specific label/caption instead.

---

### `frontend/src/components/campaigns/campaign-status-ribbon.tsx` (component)

**Analog:** `frontend/src/components/assets/severity-ribbon.tsx` — sibling component pattern, but **status-colored (violet/amber/green), never severity-colored (red/orange/yellow)** — UI-SPEC's Anti-Pattern: "mixing the families breaks the 'eye separates them' rule" (also stated in RESEARCH.md's Anti-Patterns section). Read `severity-ribbon.tsx` at plan/execute time for the exact ribbon-segment layout to replicate with the status palette instead.

---

### `frontend/src/app/(authed)/dashboard/vulnerabilities/remediations/page.tsx` (new entry-point page)

**Analog:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx` — list page composition (lines 1-70+):
```typescript
'use client';
/**
 * Composition mirrors assets/page.tsx:
 *   ErrorBoundary > Suspense > TicketsPageInner
 *
 * State branches (mutually exclusive, WR-13):
 *   q.error → PartialFailureBanner (full message, WR-10)
 *   isLoading → SkeletonTable
 *   items.length === 0 → EmptyState (connector deep-link variant for Asana, D-S-02)
 *   else → TicketsTable + Pagination
 */
import { Suspense, useCallback, useMemo, useState, type ReactNode } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { TicketsChipBar } from '@/components/tickets/tickets-chip-bar';
import { TicketsTable } from '@/components/tickets/tickets-table';
import {
  SkeletonTable, EmptyState, PartialFailureBanner, type SkeletonColumn,
} from '@/components/states';
import Pagination from '@/components/ui/Pagination';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { useUrlState } from '@/hooks/use-url-state';
import { useUrlStateList } from '@/hooks/use-url-state-list';
import { useDocumentTitle } from '@/hooks/use-document-title';
```
This is a **new page** (confirmed zero existing frontend consumers of `GET /remediations/grouped` — RESEARCH.md Pitfall 8), not a wire-up. Reuse the ErrorBoundary>Suspense>Inner shell, the mutually-exclusive state-branch order (WR-13: error > loading > empty > data), chip-bar-filter + table pattern verbatim, swapping in a `remediations`-scoped chip-bar/table and a `Start campaign` CTA per grouped row (UI-SPEC §Layout item 1). Backend data source: `GET /api/v1/vulnerabilities/remediations/grouped` (already exists, `backend/app/vulnerabilities/router.py:781-808`) — write a new `use-remediations-grouped.ts` hook mirroring `use-vuln-escalations.ts`'s shape, not `use-campaigns.ts` (this page reads remediations, not campaigns).

---

### `frontend/src/app/(authed)/dashboard/campaigns/page.tsx` (campaign list)

**Analog:** same as above (`tickets/page.tsx`) — dedicated campaign list view per CAMP-01, `status` chip axis only (Active/Complete), row click → drill panel or full nav to `[id]/page.tsx` (planner's discretion per UI-SPEC).

---

### `frontend/src/app/(authed)/dashboard/campaigns/[id]/page.tsx` (campaign detail, if full page chosen)

**Analog:** `frontend/src/app/(authed)/dashboard/assets/[id]/page.tsx` — two-column-sticky-rail detail pattern:
```typescript
/**
 * /assets/[id] — UX-04-02 two-column detail page.
 * Layout (>=900px):
 *   +----------------------+ rail 340px +
 *   | Breadcrumb           | RiskCard   |
 *   | H1 hostname + tags   | OwnerCard  |
 *   | SeverityRibbon       | Identity   |
 *   | AssetVulnsList       |   Metadata |
 *   +----------------------+------------+
 * Layout (<900px): rail stacks below main.
 */
import { RiskCard } from '@/components/assets/risk-card';
import { OwnerCard } from '@/components/assets/owner-card';
...
const asset = useAsset(id);
const vulns = useAssetVulnerabilities(id);
```
Per UI-SPEC §Layout item 3: main column = member-findings table (reuse existing vuln-table chrome filtered to `remediation_id`) + owner/ticket breakdown card; right rail = burndown card (`RiskRing` reuse) + MTTR + lifecycle actions (`Create tickets` CTA via bulk-assign endpoint, `Close campaign` secondary via `ConfirmModal`). Data fetching mirrors `useAsset(id)` → `useCampaignDetail(id)`.

**Confirmation dialog for "Close campaign" (manual early close):** `frontend/src/components/ui/ConfirmModal.tsx` (props: `open`, `title`, `message`, `confirmLabel`, `variant="danger"`, `onConfirm`, `onCancel`) — already handles mobile bottom-sheet vs. desktop modal.

---

### `frontend/src/components/shell/nav-items.ts` (modified)

**Analog:** existing `WORKFLOW_ITEMS` entries (`frontend/src/components/shell/nav-items.ts:34-46`):
```typescript
export const WORKFLOW_ITEMS: NavItem[] = [
  { label: 'Tickets',    href: '/dashboard/tickets',       icon: Ticket, chip: 'ticket_open' },
  { label: 'Rules',      href: '/dashboard/tickets/rules', icon: Zap },
  { label: 'Connectors', href: '/dashboard/connectors',    icon: Plug },
  { label: 'Asset groups', href: '/dashboard/asset-groups', icon: FolderKanban },
];
```
Add `{ label: 'Campaigns', href: '/dashboard/campaigns', icon: Target }` (or `Flag` per RESEARCH.md's icon suggestion) — no `chip` prop, matching the `Rules`/`Connectors`/`Asset groups` no-chip convention (D-N-01: campaigns aren't one of the three chip-carrying destinations).

---

## Shared Patterns

### Tenant-scoped RBAC + audit (every backend write)
**Source:** `backend/app/auth/rbac.py:50-53` (`require_analyst`/`require_viewer`) + `backend/app/audit.py:143-196` (`audit()`, fail-closed)
**Apply to:** `campaigns/router.py` — all 3 write endpoints (`POST /campaigns`, `POST /{id}/bulk-assign`, `POST /{id}/close`) gated `require_analyst`; both GET endpoints gated `require_viewer`. Every write calls `audit(db, user, "campaign.<verb>", "campaign", str(campaign.id), details)` immediately before `db.commit()`. Every query additionally filters `Campaign.tenant_id == user.tenant_id` / `Vulnerability.tenant_id == user.tenant_id` (IDOR defense — ASVS V4, see RESEARCH.md Security Domain table).
```python
@router.post("/{campaign_id}/close")
async def close_campaign(
    campaign_id: uuid.UUID,
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_analyst)],
):
    campaign = await _get_campaign_or_404(db, user.tenant_id, campaign_id)
    campaign.closed_at = datetime.now(UTC)
    campaign.closed_by_user_id = user.id
    campaign.close_trigger = "manual"
    await audit(db, user, "campaign.close", "campaign", str(campaign.id), {"trigger": "manual"})
    await db.commit()
    return {"id": str(campaign.id), "closed": True}
```

### Compute-on-read aggregation (never persisted)
**Source:** `backend/app/vulnerabilities/service.py:481-504` (`get_mttr_by_tier`)
**Apply to:** `campaigns/service.py::get_campaign_progress()` / `get_campaign_mttr()` — both run fresh on every `GET /campaigns` and `GET /campaigns/{id}` call, no caching layer, no persisted `progress_pct`/`mttr_seconds` column on `Campaign`. Corrected status filter is mandatory: `Vulnerability.status.in_(["OPEN", "IN_PROGRESS", "REMEDIATED"])`, never `_base_open_vulns()`.

### Decimal→float coercion for aggregate averages
**Source:** `backend/app/vulnerabilities/service.py:500` (`float(r.avg_seconds) if r.avg_seconds is not None else None`)
**Apply to:** `get_campaign_mttr()` — Postgres `AVG()` over an integer column returns `numeric`/`Decimal`; must coerce before entering a Pydantic response model (project memory: `getvul-decimal-serialized-as-string`).

### Owner-derivation, reused verbatim (D-05)
**Source:** `backend/app/ticketing/service.py:614` — `(mdm or {}).get("humaans_email")`
**Apply to:** `bulk_create_campaign_tickets()`'s owner-carve-up loop — never re-derive, never invent a "smarter" resolver.

### N-rows-share-one-URL ticket linkage (D-04/D-06)
**Source:** `backend/app/ticketing/service.py:674-692`
**Apply to:** per-owner ticket creation loop — one `client.create()` call per owner produces one `url`; every member `Vulnerability`'s owner bucket gets its own `Ticket` row with `external_ticket_id=f"{ref}:{vuln.id}"` sharing that same `external_ticket_url`. Never add a `vulnerability_ids` array column (`ticketing/models.py:84` confirms `Ticket.vulnerability_id` is singular — Pitfall 4).

### System-attributed audit rows for lazy-on-read transitions
**Source:** `backend/app/vulnerabilities/service.py:464-476` (`reopen_vulnerability`'s `system:rescan-reopen` `AuditLog` insert)
**Apply to:** the D-13/D-19 auto-complete and D-14 auto-reactivate transitions detected inside `GET /campaigns/{id}` — `user_id=None`, `user_email="system:campaign-complete"`, constructed directly as an `AuditLog` (not via the `audit()` helper, since there's no `CurrentUser` to attribute to), and gated so the write is derived only from server-computed state, never client input (STRIDE Tampering mitigation per RESEARCH.md Security Domain).

### Partial unique index via `Index(..., postgresql_where=...)`, never `UniqueConstraint`
**Source:** `backend/alembic/versions/020_add_sla_tracking.py:27-32`
**Apply to:** `Campaign.__table_args__` (model) and the migration's `op.create_index(..., unique=True, postgresql_where=sa.text("closed_at IS NULL"))` (Postgres has no partial `UNIQUE CONSTRAINT` syntax — Pitfall 3).

### List page composition shell (ErrorBoundary > Suspense > Inner, WR-13 state branches)
**Source:** `frontend/src/app/(authed)/dashboard/tickets/page.tsx:1-25`
**Apply to:** both new list pages (`vulnerabilities/remediations/page.tsx`, `campaigns/page.tsx`) — mutually exclusive branch order: `q.error → PartialFailureBanner`, `isLoading → SkeletonTable`, `items.length === 0 → EmptyState`, else → table + pagination.

## No Analog Found

None — every file in scope has at least a role-match analog. The one genuinely novel surface is the per-owner ticket carve-up loop in `campaigns/service.py` (RESEARCH.md Pattern 4 explicitly flags this as "the single largest net-new code surface in the phase" since `create_remediation_ticket()` has no `owner_email` filter parameter today) — it is a re-carve of three existing precedents (owner derivation, dedup-by-URL linkage, N-rows-share-one-URL) rather than a wholesale new pattern, so it is not listed as a true gap.

## Metadata

**Analog search scope:** `backend/app/vulnerabilities/`, `backend/app/ticketing/`, `backend/app/notifications/`, `backend/app/cspm/`, `backend/app/audit.py`, `backend/app/auth/rbac.py`, `backend/app/main.py`, `backend/alembic/versions/{020,047,048}*`, `frontend/src/lib/queries/`, `frontend/src/components/{tickets,assets,ui}/`, `frontend/src/app/(authed)/dashboard/{tickets,assets}/`, `frontend/src/components/shell/nav-items.ts`
**Files scanned:** 21 direct reads (backend: 11, frontend: 8, migration: 2)
**Pattern extraction date:** 2026-08-17
