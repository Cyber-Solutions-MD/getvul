# Phase 42: Risk Trend Analytics & Burndown - Pattern Map

**Mapped:** 2026-08-21
**Files analyzed:** 18 (12 new, 6 modified)
**Analogs found:** 18 / 18 — every file has at least a role-match analog. 3 sub-pieces of *logic* (not whole files) have zero precedent anywhere in the codebase — see `## Novel Logic (No Precedent)` at the end; do not go looking for an analog for these, RESEARCH.md's sketches are the only source.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/analytics/__init__.py` | config | n/a | `backend/app/coverage/__init__.py` | exact (both empty) |
| `backend/app/analytics/router.py` | controller | request-response | `backend/app/coverage/router.py` | exact |
| `backend/app/analytics/service.py` | service | transform (time-series aggregation) | `backend/app/vulnerabilities/trends.py` (query/cast idiom) + `backend/app/coverage/service.py` (tenant-scoped predicate-composition shape) | exact / role-match |
| `backend/app/analytics/schemas.py` | model | transform | `backend/app/coverage/schemas.py` | exact |
| `backend/tests/test_analytics.py` | test | n/a | `backend/tests/test_risk_boundary_guard.py` | exact |
| `backend/app/main.py` *(modify)* | config | n/a | itself — `coverage_router` registration, line 323 | exact |
| `backend/app/vulnerabilities/trends.py` *(modify additively)* | service | transform | itself — the codebase's own additive-optional-param idiom | exact |
| `frontend/src/app/(authed)/dashboard/analytics/page.tsx` | component (page) | request-response | `frontend/src/app/(authed)/dashboard/coverage/page.tsx` | exact |
| `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` | test | n/a | `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` | exact |
| `frontend/src/components/analytics/risk-trend-chart.tsx` | component (chart) | transform | `frontend/src/components/ui/trend-chart.tsx` | role-match (scaffolding exact; segmentation is novel — see below) |
| `frontend/src/components/analytics/backlog-aging-chart.tsx` | component (chart) | transform | `frontend/src/components/ui/trend-chart.tsx` | exact (stacked bar + `SEVERITY_FILLS` reused verbatim; only x-axis bucketing differs) |
| `frontend/src/components/analytics/burndown-tile.tsx` | component | transform | `frontend/src/components/campaigns/campaign-burndown-card.tsx` | role-match |
| `frontend/src/components/analytics/scope-window-controls.tsx` | component (form) | request-response | `frontend/src/components/dashboard/trend-section.tsx` (range idiom) + `frontend/src/components/ui/dropdown-menu.tsx` (scope) + `frontend/src/components/exceptions/exception-grant-dialog.tsx` (native date input) | role-match (composite) |
| `frontend/src/components/analytics/analytics-page-skeleton.tsx` | component | transform | `frontend/src/components/ui/trend-chart-skeleton.tsx` + `coverage/page.tsx`'s inline `CoverageStripSkeleton` | exact |
| `frontend/src/components/analytics/microcopy.ts` | utility (copy) | n/a | `frontend/src/components/coverage/microcopy.ts` | exact |
| `frontend/src/lib/queries/use-analytics.ts` | hook | request-response | `frontend/src/lib/queries/use-coverage-summary.ts` (no-arg single-payload shape) + `frontend/src/lib/queries/use-trends.ts` (range-param shape) | exact |
| `frontend/src/lib/queries/keys.ts` *(modify)* | utility | n/a | itself — `coverage` block, lines 153-157 | exact |
| `frontend/src/components/shell/nav-items.ts` *(modify)* | config | n/a | itself — `Coverage` entry, lines 53-55 | exact |

---

## Pattern Assignments

### `backend/app/analytics/__init__.py` (config, n/a)

**Analog:** `backend/app/coverage/__init__.py` — zero bytes, empty file. Create the same: an empty file, nothing else. Python resolves the package via the directory + this file alone; every other coverage-module convention (docstring-at-top-of-file, not in `__init__`) lives in `router.py`/`service.py`/`schemas.py` instead.

---

### `backend/app/analytics/router.py` (controller, request-response)

**Analog:** `backend/app/coverage/router.py` (99 lines, exact structural match — brand-new top-level module).

**Imports pattern** (`coverage/router.py:16-36`):
```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.assets.models import Asset
from app.audit import audit
from app.auth.rbac import require_analyst, require_viewer
from app.auth.schemas import CurrentUser
from app.coverage.schemas import BlindSpotAssetListResponse, CoverageSummaryResponse, RouteToOwnerResponse
from app.coverage.service import DEFAULT_PAGE_SIZE
from app.coverage.service import get_coverage_summary as _get_coverage_summary
from app.coverage.service import list_blind_spot_assets as _list_blind_spot_assets
from app.coverage.service import route_to_owner as _route_to_owner
from app.dependencies import DBSession
from app.tenants.models import Tenant

router = APIRouter()
```
For `analytics/router.py`: swap the coverage schema/service imports for `app.analytics.schemas` / `app.analytics.service`; keep `require_viewer` (D-14 — no `require_analyst`, this phase has no mutating endpoint at all, unlike Coverage's `route_to_owner`).

**RBAC + thin-handler pattern** (`coverage/router.py:67-76`, the `require_viewer`-only GET — the closer precedent than `route_to_owner_endpoint`, since D-14 makes every Analytics endpoint viewer-gated with no analyst-only mutation):
```python
@router.get("/summary", response_model=CoverageSummaryResponse)
async def get_coverage_summary_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CoverageSummaryResponse:
    """COV-02: ... Tenant-scoped throughout (T-41-07)."""
    return await _get_coverage_summary(db, user.tenant_id)
```
The new `GET /api/v1/analytics/overview` (or whatever D-15 names it) follows this exact shape: one `require_viewer` dependency, one call into a `service.py` function passing `user.tenant_id`, `response_model=` set. Query params for scope/window mirror the existing `days: int = Query(30, ge=7, le=365)` idiom on `GET /trends` below.

**The RBAC/param precedent this phase's endpoint(s) must follow** (`backend/app/vulnerabilities/router.py:187-196`):
```python
@router.get("/trends")
async def trend_analytics(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
    days: int = Query(30, ge=7, le=365),
):
    """Get trend data — vuln timeline, MTTR trend, risk score history."""
    from app.vulnerabilities.trends import get_all_trends

    return await get_all_trends(db, user.tenant_id, days)
```
D-14/security-domain note: cap any new `window`/custom-range param analogously (`ge=`/`le=` or an explicit max-span check) — never leave a custom date range unbounded server-side.

**Registration in `main.py`** — see the dedicated `main.py` pattern assignment below.

---

### `backend/app/analytics/service.py` (service, transform)

**Primary analog (query/cast idiom):** `backend/app/vulnerabilities/trends.py` (411 lines). **Secondary analog (tenant-scoped predicate composition, brand-new-module shape):** `backend/app/coverage/service.py` (288 lines).

**The `DailySnapshot` model this phase reads from, verbatim** (`trends.py:23-32`):
```python
class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

**Reusable, HTTP-agnostic function-signature convention (D-16 — the exact shape Phase 43 must be able to call directly)** (`trends.py:38`):
```python
async def get_vuln_trends(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
```
Every new `analytics/service.py` function (`get_scoped_trend_series`, `get_aging_distribution`, `get_burndown_rate`) takes `db: AsyncSession` + plain params — never `Request`/`Depends` — so `router.py` and a future Phase 43 report generator call the identical function.

**The function this phase's tenant-scope trend must NOT call as-is** (`trends.py:166-215` — shown so the new function can supersede both problems D-12/D-13 flag; do not copy its `LIMIT(90)` or its flag-branch):
```python
rows = (
    await db.execute(
        select(DailySnapshot.snapshot_date, DailySnapshot.metrics)
        .where(DailySnapshot.tenant_id == tenant_id)
        .order_by(DailySnapshot.snapshot_date.desc())
        .limit(90)   # D-13: must become a date-range filter for 1y/custom windows
    )
).all()
metric_key = "avg_risk_exposure_score" if cutover_enabled else "avg_risk_score"  # D-12: always avg_risk_exposure_score
```
The raw `select(DailySnapshot.snapshot_date, DailySnapshot.metrics).where(DailySnapshot.tenant_id == tenant_id)` shape IS reusable — just replace `.order_by(...desc()).limit(90)` with `.where(DailySnapshot.snapshot_date.between(start, end)).order_by(DailySnapshot.snapshot_date.asc())` for a real window, and always key on `"avg_risk_exposure_score"` (never branch on `Tenant.cutover_risk_exposure_scoring`).

**The new-vs-resolved feed the burndown rate composes from** (`trends.py:38-126`, full `get_vuln_trends` — note the exact WHERE-clause vocabulary: `Vulnerability.status.in_(["OPEN", "IN_PROGRESS"])` for open, `Vulnerability.status.in_(["REMEDIATED", "SUPPRESSED"])` for resolved, `Vulnerability.first_detected_at` / `Vulnerability.remediated_at` for timestamps). Per Pitfall 5, add an optional `asset_ids: list[uuid.UUID] | None = None` param and thread `Vulnerability.asset_id.in_(asset_ids)` into the WHERE clauses when scope=group (default `None` preserves every existing call site byte-for-byte).

**Decimal-to-JSON-safe cast idiom — copy exactly, every new aggregate must do this** (`trends.py:159`, `get_mttr_trend`):
```python
"mttr_days": round(float(r.avg_days), 1) if r.avg_days else None,
```
and (`trends.py:374,380`, `capture_daily_snapshot`):
```python
"avg_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
...
"avg_risk_exposure_score": round(float(avg_risk_exposure), 1) if avg_risk_exposure else 0,
```
Any new `func.avg`/`func.sum` this phase introduces (e.g. burndown's average net-per-week) must pass through the identical `round(float(x), N) if x is not None else None` before entering a Pydantic response — this is Pitfall 6, and every existing trend/snapshot function already does it.

**Tenant-scoped composable-predicate shape (coverage's brand-new-module idiom — the model for small helper functions like an SLA-tier-bucket predicate or an in-scope-asset filter)** (`coverage/service.py:54-61`):
```python
def _authoritative_clause() -> ColumnElement[bool]:
    """D-01: authoritative inventory = seen by >=1 ENRICHMENT source."""
    return or_(*[Asset.seen_by_sources.contains([e]) for e in ENRICHMENT_SOURCES])


def _never_scanned_clause() -> ColumnElement[bool]:
    """D-02: never scanned = seen by 0 SCANNER_SOURCES."""
    return not_(or_(*[Asset.seen_by_sources.contains([s]) for s in SCANNER_SOURCES]))
```
The same "small named boolean-clause builder, composed into the main query" idiom applies to e.g. an aging-bucket predicate built from `sla_tier_service` output.

**SLA-tier policy — reuse verbatim, do not re-derive** (`backend/app/vulnerabilities/sla_tier_service.py:49,57-88,91-109`):
```python
DEFAULT_TIER_POLICY: dict[str, int] = {"critical": 7, "high": 30, "moderate": 90}

def tier_for_score(score: int | None) -> str | None: ...   # risk_exposure_score -> tier
def severity_to_tier(severity: str) -> str: ...             # NULL-score fallback
def get_tier_policy(tenant: Tenant | None) -> dict[str, Any]: ...  # tenant sla_config override merge
```
Import and call these three functions for the aging chart's bucket boundaries (D-08) — do NOT reach for `sla_service.py::DEFAULT_SLA_DAYS` (the legacy, no-longer-live-writing severity-keyed engine — Pitfall 2).

**Exclusion predicate — reuse verbatim** (`backend/app/exceptions/service.py:50-71`, full signature + the correlated-EXISTS shape):
```python
def active_exception_subquery(tenant_id: uuid.UUID, now: datetime) -> Exists:
    """Correlated EXISTS: does an active (non-expired, non-revoked)
    exception cover the OUTER `Vulnerability` row this is joined against?
    ...
    """
    return exists(
        select(ExceptionRecord.id).where(
            ExceptionRecord.tenant_id == tenant_id,
            ExceptionRecord.revoked_at.is_(None),
            ExceptionRecord.expires_at > now,  # strict
            or_(
                ExceptionRecord.vulnerability_id == Vulnerability.id,
                and_(ExceptionRecord.scope_type == "ASSET", ...),
                and_(ExceptionRecord.scope_type == "ASSET_GROUP", ...),
            ),
        )
    )
```
Apply as `~active_exception_subquery(tenant_id, now)` to every open-backlog query this phase writes (D-10) — never a hand-rolled `status NOT IN (...)`.

**Tenant-scoped, 404-safe group membership fetch — reuse verbatim** (`backend/app/assets/groups_service.py:123-136`):
```python
async def list_members(db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID) -> list[Asset] | None:
    """Returns the group's member assets (tenant-scoped), or `None` if the
    group itself does not exist/belong to this tenant (router converts to
    404 — same not-found convention as every other lookup in this module)."""
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
Call this for D-05/D-06 group scoping; a `None` return means the router must 404 (IDOR guard — mirrors `coverage/router.py::_get_asset_or_404`), never a fetch-then-403.

**IDOR-safe tenant-scoped 404 helper — mirror this exact shape for a `group_id` scope param** (`coverage/router.py:39-49`):
```python
async def _get_asset_or_404(db: DBSession, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
    """T-41-02 (IDOR): tenant scoping belongs IN the WHERE clause, not a
    post-fetch filter -- a cross-tenant asset_id must 404, never a
    fetch-then-403 (mirrors exceptions/router.py::_get_exception_or_404)."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
```
Since `list_members` already returns `None` for a cross-tenant group, `analytics/router.py` just needs `if members is None: raise HTTPException(404, "Asset group not found")` — no separate helper needed, but the *shape* (tenant filter in the WHERE clause, `None`/404 not fetch-then-403) is the load-bearing pattern to replicate for any group_id validation you add.

---

### `backend/app/analytics/schemas.py` (model, transform)

**Analog:** `backend/app/coverage/schemas.py` (111 lines, exact match).

**Pydantic v2 convention** (`coverage/schemas.py:14-32`):
```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BlindSpotAssetResponse(BaseModel):
    """A single never-scanned authoritative-inventory asset row (D-01/D-02)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostname: str
    category: str | None
    os: str | None
    last_seen_at: datetime | None
    seen_by_sources: list[str]
```

**List-envelope convention** (`coverage/schemas.py:85-111`, `BlindSpotAssetListResponse` — same shape any paginated analytics sub-list would follow, though D-13's single-combined-payload recommendation means most of this phase's response is probably one flat object, not a paginated list):
```python
class BlindSpotAssetListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[BlindSpotAssetResponse]
    total: int
    page: int
    page_size: int
    pages: int
    has_authoritative_inventory: bool
    total_authoritative_assets: int
```

**Nullable-vs-zero discipline (D-06's "None means gap, not 0")** — mirrors `CoverageConnectorCardResponse`'s own null-guard comment (`coverage/schemas.py:44-46`):
```python
    # D-11 misleading-number guard: null (never 0 or 100) when the
    # authoritative-asset denominator is zero.
    coverage_pct: int | None
```
Apply the identical discipline to the trend series' `avg_risk_exposure_score: float | None` (None = zero-scored-members gap, D-06) and to the aging chart's `coverage_pct`-equivalent ("% of backlog overdue" tile, if built).

---

### `backend/tests/test_analytics.py` (test, n/a)

**Analog:** `backend/tests/test_risk_boundary_guard.py` (247 lines — the ONLY existing test file that hand-constructs `DailySnapshot` rows with custom `metrics` dicts).

**Asset-seeding helper pattern** (`test_risk_boundary_guard.py:42-48`):
```python
def _seed_asset(tenant_id: uuid.UUID, *, risk_score: int | None, risk_exposure_score: int | None) -> Asset:
    return Asset(
        tenant_id=tenant_id,
        hostname=f"host-{uuid.uuid4().hex[:8]}",
        risk_score=risk_score,
        risk_exposure_score=risk_exposure_score,
    )
```

**Hand-constructed `DailySnapshot` fixture — the exact pattern to extend with a varying `risk_model_version_snapshot` (Pitfall 1 — no existing test varies this field)** (`test_risk_boundary_guard.py:106-114`):
```python
yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
db_session.add(
    DailySnapshot(
        tenant_id=tenant_a,
        snapshot_date=yesterday,
        metrics={"asset_risk_scores": {str(asset.id): 10}},
        created_at=datetime.now(UTC),
    )
)
await db_session.commit()
```
For TREND-03's test, add a second/third snapshot row with `metrics={"risk_model_version_snapshot": "v1", ...}` then `"v2"` — this exact field has never been varied in any existing fixture; this test file is the first.

**Multi-snapshot version-drift fixture shape (closest existing precedent for "two snapshots, deliberately different metrics dicts, assert continuity")** (`test_risk_boundary_guard.py:200-220`, `test_trend_no_cliff`):
```python
day1 = (datetime.now(UTC) - timedelta(days=2)).date()
day2 = (datetime.now(UTC) - timedelta(days=1)).date()

db_session.add(DailySnapshot(tenant_id=tenant_a, snapshot_date=day1,
    metrics={"avg_risk_score": 20, "avg_risk_exposure_score": 21}, created_at=datetime.now(UTC)))
db_session.add(DailySnapshot(tenant_id=tenant_a, snapshot_date=day2,
    metrics={"avg_risk_score": 85, "avg_risk_exposure_score": 23}, created_at=datetime.now(UTC)))
await db_session.commit()
```
Same idea, but this phase's test varies `risk_model_version_snapshot` across the two rows instead of the score fields, and asserts the new `detect_version_boundaries`/segmentation function treats it as a boundary (see Novel Logic below).

**Fixtures used (no new shared-fixture infrastructure needed):** `db_session`, `tenant_a` — both already established and imported implicitly via pytest fixture discovery; `test_analytics.py` needs `from app.vulnerabilities.trends import DailySnapshot, capture_daily_snapshot` and `from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION` exactly as this analog does (`test_risk_boundary_guard.py:35-39`).

---

### `backend/app/main.py` (config, n/a) — modify

**Analog:** itself — the existing router-registration block.

**Exact insertion point and idiom** (`main.py:311-328`):
```python
    # ── Routes ──
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(vuln_router, prefix="/api/v1/vulnerabilities", tags=["Vulnerabilities"])
    app.include_router(asset_router, prefix="/api/v1/assets", tags=["Assets"])
    app.include_router(asset_groups_router, prefix="/api/v1/asset-groups", tags=["Asset Groups"])
    app.include_router(tenant_router, prefix="/api/v1/tenant", tags=["Tenant & Users"])
    app.include_router(connector_router, prefix="/api/v1/connectors", tags=["Connectors"])
    app.include_router(cspm_router, prefix="/api/v1/cspm", tags=["CSPM"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(tickets_router, prefix="/api/v1/tickets", tags=["Tickets"])
    app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["Campaigns"])
    app.include_router(exceptions_router, prefix="/api/v1/exceptions", tags=["Exceptions"])
    app.include_router(coverage_router, prefix="/api/v1/coverage", tags=["Coverage"])
```
Add one line: `app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])` immediately after the `coverage_router` line (most-recently-added precedent), plus the corresponding `from app.analytics.router import router as analytics_router`-style import near the top of the file (mirror wherever `from app.coverage.router import router as coverage_router` is imported).

---

### `backend/app/vulnerabilities/trends.py` (service, transform) — modify additively

**Analog:** itself — this codebase's own additive-optional-parameter idiom, so `get_vuln_trends` gains a group-scoping `asset_ids` param (Pitfall 5) without breaking any existing caller.

**Current signature to extend** (`trends.py:38`):
```python
async def get_vuln_trends(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
```

**The exact prior-art for "add a new optional param, default preserves old behavior byte-for-byte"** (`sla_tier_service.py:112-119`, `compute_sla_state`):
```python
def compute_sla_state(
    *,
    first_detected_at: datetime,
    tier_days: int,
    approaching_pct: float,
    now: datetime,
    excepted_seconds: int = 0,
) -> tuple[datetime, str]:
```
`excepted_seconds: int = 0` was added in Phase 39 for every existing call site to remain unaffected; `resolve_state_for_vuln` (`sla_tier_service.py:144-150`) does the same (`excepted_seconds: int = 0`). Follow this exactly: `async def get_vuln_trends(db, tenant_id, days=30, asset_ids: list[uuid.UUID] | None = None)`, and inside, only add `Vulnerability.asset_id.in_(asset_ids)` to each WHERE clause when `asset_ids is not None` — every existing call site (`GET /trends` → `get_all_trends` → `get_vuln_trends(db, tenant_id, days)`) is untouched.

---

### `frontend/src/app/(authed)/dashboard/analytics/page.tsx` (component/page, request-response)

**Analog:** `frontend/src/app/(authed)/dashboard/coverage/page.tsx` (441 lines, exact match — the most recent new-top-level-page precedent).

**ErrorBoundary > Suspense > PageInner wrapper** (`coverage/page.tsx:426-441`):
```tsx
const PAGE_FALLBACK = (
  <div className="space-y-4 p-6">
    <h1 className="sr-only">{microcopy.page.h1}</h1>
    <SkeletonTable columns={SKELETON_COLUMNS} rows={10} />
  </div>
);

export default function CoveragePage() {
  return (
    <ErrorBoundary fallback={pageErrorFallback} boundaryName="CoveragePage">
      <Suspense fallback={PAGE_FALLBACK}>
        <CoveragePageInner />
      </Suspense>
    </ErrorBoundary>
  );
}
```
For `AnalyticsPage`, swap `PAGE_FALLBACK` for the new `<AnalyticsPageSkeleton />` component and `boundaryName="AnalyticsPage"`.

**Crash-fallback pattern** (`coverage/page.tsx:103-113`):
```tsx
function pageErrorFallback(err: Error, reset: () => void): ReactNode {
  return (
    <div className="space-y-4 p-6">
      <h1 className="sr-only">{microcopy.page.h1}</h1>
      <PartialFailureBanner
        errors={[{ code: 'crash', requestId: err.message || 'unknown' }]}
        onRetry={reset}
      />
    </div>
  );
}
```

**Header pattern** (`coverage/page.tsx:302-311`):
```tsx
return (
  <div className="space-y-4 p-6">
    <header className="space-y-1">
      <h1 className="text-3xl font-semibold text-text">{microcopy.page.h1}</h1>
      {showSubtitle && (
        <p className="text-sm text-text-muted">{microcopy.page.subtitle(total)}</p>
      )}
    </header>
```
Matches 42-UI-SPEC.md's Typography row (`Heading` = 32px/600 for the `<h1>`). Below the header, per D-02/UI-SPEC visual hierarchy, render `<ScopeWindowControls>` then the 3 chart sections top-to-bottom (trend line → aging → burndown), each `xl` (32px) gap apart.

**State-branch ordering — error FIRST, then loading, then empty variant(s), then populated (WR-13 discipline)** (`coverage/page.tsx:318-388`, structure only):
```tsx
{queryError ? (
  <PartialFailureBanner errors={[...]} onRetry={() => { q.refetch(); }} />
) : isLoading ? (
  <AnalyticsPageSkeleton />
) : belowMinimumHistoryThreshold ? (
  <EmptyState>
    <EmptyState.Title>{microcopy.empty.insufficientHistory.title}</EmptyState.Title>
    <EmptyState.Body>{microcopy.empty.insufficientHistory.body(scopeLabel)}</EmptyState.Body>
  </EmptyState>
) : (
  <div className="space-y-8">
    {/* RiskTrendChart, BacklogAgingChart, BurndownTile */}
  </div>
)}
```
This page has ONE combined query (D-13/A2 — single compute pass), so there is exactly one `isLoading`/`error` branch pair for the whole page, unlike Coverage's two independent queries (`q` + `summaryQ`) — simpler than the analog in this one respect.

**Skeleton-strip-while-pending pattern (for the analytics-page-skeleton component)** (`coverage/page.tsx:213-225`):
```tsx
function CoverageStripSkeleton() {
  return (
    <StatStrip aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-[168px] rounded-lg border border-border-subtle bg-surface-2 p-6 animate-pulse"
        />
      ))}
    </StatStrip>
  );
}
```

**URL-driven drill/deep-link precedent** (`coverage/page.tsx:264-290`) is NOT needed here (this page has no per-row drill panel) — omit; the only URL state this page needs is scope + window (see `scope-window-controls.tsx` below).

---

### `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` (test, n/a)

**Analog:** `frontend/src/app/(authed)/dashboard/coverage/page.test.tsx` (354 lines).

**Mock-the-query-hook-directly pattern (`vi.spyOn` on the module, not a factory `vi.mock`)** (`coverage/page.test.tsx:31-35,68-80`):
```tsx
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => '/dashboard/coverage',
  useSearchParams: () => searchParamsMock,
}));

import * as useBlindSpotAssetsModule from '@/lib/queries/use-blind-spot-assets';
...
function mockQuery(overrides: { data?: ...; isPending?: boolean; error?: Error | null }) {
  vi.spyOn(useBlindSpotAssetsModule, 'useBlindSpotAssets').mockReturnValue({
    data: overrides.data,
    isPending: overrides.isPending ?? false,
    isLoading: overrides.isPending ?? false,
    error: overrides.error ?? null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useBlindSpotAssetsModule.useBlindSpotAssets>);
}
```
For `page.test.tsx`, `vi.spyOn` on `use-analytics` module's exported hook the same way — one test per UI-SPEC state branch (loading / error / empty-insufficient-history / populated, plus the zero-one-many single-point-renders-as-a-dot case and the version-boundary-marker-renders case per the UI-SPEC's E2 table).

**QueryClient test-wrapper helper** (`coverage/page.test.tsx:63-66`):
```tsx
function renderWithClient(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}
```

---

### `frontend/src/components/analytics/risk-trend-chart.tsx` (component/chart, transform)

**Analog:** `frontend/src/components/ui/trend-chart.tsx` (283 lines) — role-match for ALL scaffolding (CSS-variable fills, `ResponsiveContainer` sizing, `prefers-reduced-motion` gating, sr-only data table); the segmented-line/`ReferenceLine` rendering itself has **no existing precedent** (see Novel Logic below) — RESEARCH.md's Code Examples §4 is the primary source for that specific piece, not this analog.

**Reusable scaffolding to copy verbatim (rename, don't refork):**

`ResponsiveContainer` + accessibility-layer wrapper (`trend-chart.tsx:230-236`):
```tsx
<div aria-hidden="true">
  <ResponsiveContainer width="100%" height={200}>
    <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }} accessibilityLayer>
```
(swap `BarChart` for `LineChart`, keep the `aria-hidden` wrapper — the sr-only table below is the real accessible data path).

`prefers-reduced-motion` gating (`trend-chart.tsx:220-222`):
```tsx
const reduced = usePrefersReducedMotion();
// recharts' TS types don't yet expose 'auto'; the runtime accepts it (v2.10+).
const anim: false | 'auto' = reduced ? false : 'auto';
```

sr-only `ChartDataTable` — the CANONICAL accessible-data path (SVG is `aria-hidden`) (`trend-chart.tsx:188-216`):
```tsx
function ChartDataTable({ data }: { data: TrendDatum[] }) {
  return (
    <table className="sr-only" aria-label={microcopy.trend.h2}>
      <caption>Daily counts of open vulnerabilities by severity</caption>
      <thead><tr><th scope="col">Date</th>...</tr></thead>
      <tbody>{data.map(d => <tr key={d.date}><th scope="row">{fmtFullDate(d.date)}</th>...</tr>)}</tbody>
    </table>
  );
}
```
For `RiskTrendChart`, the sr-only table's rows are `{date, score, version}` — and per D-11, the boundary itself should be readable in this table too (e.g. an extra "Model version" column), not just visually via `ReferenceLine`.

CSS-variable-routed color (violet per UI-SPEC, not a severity color — this is the ONE trend line, not stacked severities) — mirrors the fill-routing convention at `trend-chart.tsx:46-51`:
```tsx
export const SEVERITY_FILLS = {
  critical: 'var(--color-severity-critical)',
  high: 'var(--color-severity-high)',
  medium: 'var(--color-severity-medium)',
  low: 'var(--color-severity-low)',
} as const;
```
`RiskTrendChart` uses a single `stroke="var(--color-violet)"` per UI-SPEC's Color section — no new hex value, no severity palette (there's only one series here).

**The genuinely new piece — copy from RESEARCH.md, not from this codebase (no existing usage of `Line`/`ReferenceLine`/`connectNulls` anywhere)** — see `## Novel Logic (No Precedent)` below for the full sketch. Do not attempt to find a codebase precedent for the pivot-by-version-segment / `ReferenceLine`-per-boundary rendering — there isn't one.

---

### `frontend/src/components/analytics/backlog-aging-chart.tsx` (component/chart, transform)

**Analog:** `frontend/src/components/ui/trend-chart.tsx` — exact match for the stacked-bar mechanics; only the x-axis category changes (SLA-tier bucket instead of date).

**Stacked-bar-with-shared-`stackId` pattern, `SEVERITY_FILLS` reused VERBATIM per UI-SPEC** (`trend-chart.tsx:252-276`):
```tsx
{/* Same stackId="s" → all 4 stack. Paint order = stack order: low at base. */}
<Bar dataKey="low" stackId="s" fill={SEVERITY_FILLS.low} isAnimationActive={anim as unknown as boolean} />
<Bar dataKey="medium" stackId="s" fill={SEVERITY_FILLS.medium} isAnimationActive={anim as unknown as boolean} />
<Bar dataKey="high" stackId="s" fill={SEVERITY_FILLS.high} isAnimationActive={anim as unknown as boolean} />
<Bar dataKey="critical" stackId="s" fill={SEVERITY_FILLS.critical} isAnimationActive={anim as unknown as boolean} />
```
`import { SEVERITY_FILLS } from '@/components/ui/trend-chart';` directly — do not redefine the 4 hex/CSS-var mappings a second time. Only the `XAxis dataKey` changes: `date` → a bucket-id field (`"within_sla" | "recently_breached" | "long_overdue"`), with `tickFormatter` mapping to the UI-SPEC's exact 3 labels (`Within SLA` / `Recently breached` / `Long overdue`) instead of `fmtTick`'s date formatting.

**Tooltip pattern to adapt** (`trend-chart.tsx:84-141`, `SeverityTooltip`) — same per-severity breakdown-with-total shape; swap the `headline` derivation (`isLatestDay`/`todaySoFar`) for the bucket label, since there's no "today" concept in a point-in-time distribution.

**`RangeToggle`/window control does NOT apply to this chart** — the aging chart has no time window of its own (D-08: it's a live point-in-time snapshot); it inherits scope from the page-level `ScopeWindowControls` but ignores the window preset entirely (only scope matters for aging).

---

### `frontend/src/components/analytics/burndown-tile.tsx` (component, transform)

**Analog:** `frontend/src/components/campaigns/campaign-burndown-card.tsx` (106 lines) — role-match (card chrome + a headline number + directional/status copy), NOT a `RiskRing` reuse (UI-SPEC explicitly: "no RiskRing — this is a rate, not a %").

**Card chrome to reuse verbatim** (`campaign-burndown-card.tsx:69-73`):
```tsx
<section
  className={cn('rounded-lg border border-border-subtle bg-surface-2 p-4', className)}
  aria-label="Campaign burndown"
  data-testid="campaign-burndown-card"
>
```
`BurndownTile` uses the identical `rounded-lg border border-border-subtle bg-surface-2 p-4` chrome (`aria-label="Burndown"`, `data-testid="burndown-tile"`).

**Directional/status-color copy row pattern (green/amber-style "which way is it going" text)** (`campaign-burndown-card.tsx:90-99`):
```tsx
<div className="flex items-center justify-center gap-2 border-t border-border-subtle py-3 font-mono text-sm text-text-muted">
  <span className="text-violet">{open} open</span>
  <span aria-hidden="true">·</span>
  <span className="text-amber">{inProgress} in progress</span>
  <span aria-hidden="true">·</span>
  <span className="text-success">{done} done</span>
</div>
```
`BurndownTile` swaps this for the UI-SPEC's shrinking/growing/no-change branches: `text-success` (green) for "Backlog shrinking — {N} findings/week net", `text-danger` (red) for "Backlog growing — {N} findings/week net" — per UI-SPEC Color section ("reuses the existing SLA/status directional-color convention verbatim").

**Zero-denominator guard discipline (Pitfall 5 in that file's own docstring — never divide by a value that could be 0 inside the component)** (`campaign-burndown-card.tsx:19-23`, docstring):
```
* Pitfall 5 (zero-member guard): `pctRemediated`/`open`/`inProgress`/`done`
* are all passed in as plain numbers from the backend's already-computed
* ... response ... this component never divides by
* a denominator itself, so it can never crash on 0/0.
```
`BurndownTile` must receive the already-computed net-velocity + projected-days-to-clear (or the explicit "growing"/"no change" branch flag) as plain props from the backend — never compute a division client-side.

**Duration-formatting helper pattern** (`campaign-burndown-card.tsx:52-58`, `formatMttr` — the closest existing "format a derived time quantity, null-safe" helper):
```tsx
export function formatMttr(seconds: number | null): string {
  if (seconds === null) return '—';
  const totalHours = Math.floor(seconds / 3600);
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  return `${days}d ${hours}h`;
}
```
`BurndownTile`'s own days-to-clear formatter follows the same null-safe-dash shape, plus the UI-SPEC's explicit overflow cap (`500+ d to clear`) — a capped-value branch this analog does not need but the new component must add.

---

### `frontend/src/components/analytics/scope-window-controls.tsx` (component/form, request-response)

**Analog (range idiom):** `frontend/src/components/dashboard/trend-section.tsx` (71 lines) + `frontend/src/components/ui/trend-chart.tsx`'s `RangeToggle` (lines 143-186). **Analog (scope dropdown):** `frontend/src/components/ui/dropdown-menu.tsx` (201 lines, Radix wrapper, reused verbatim per UI-SPEC). **Analog (custom date fields):** `frontend/src/components/exceptions/exception-grant-dialog.tsx` (native `<input type="date">`, no new dependency).

**`useUrlState` + enum-clamped range control — the D-03 idiom to EXTEND (3→5 options), not replace** (`trend-section.tsx:23-27`):
```tsx
const ALLOWED_RANGES = ['7d', '30d', '90d'] as const;

export function TrendSection() {
  const [range, setRange] = useUrlState<Range>('range', ALLOWED_RANGES, '30d');
  const q = useTrends(range);
```
For the Analytics page: `const ALLOWED_WINDOWS = ['7d', '30d', '90d', '1y', 'custom'] as const;` — same hook, same clamp-to-allowlist safety (`useUrlState`'s XSS defense, per Pitfall 3 do NOT bypass it for the enum part).

**`useUrlState` itself — reuse as-is, do NOT modify** (`frontend/src/hooks/use-url-state.ts:11-28`, full function):
```tsx
export function useUrlState<T extends string>(
  key: string,
  allowed: readonly T[],
  defaultValue: T
): [T, (next: T) => void] {
  ...
  const value: T =
    raw !== null && (allowed as readonly string[]).includes(raw)
      ? (raw as T)
      : defaultValue;
  ...
}
```
Per Pitfall 3: this hook's fixed-allowlist shape is right for the 5-way preset selector, but WRONG for free-form `from`/`to` custom dates (not a finite enum). Handle `from`/`to` as two SEPARATE plain `useSearchParams`-driven string params with their OWN validation (ISO-date-format check + `to > from` guard) — do not pass an open-ended allow-list into `useUrlState`.

**`RangeToggle` button-group pattern to extend from 3 to 5 options** (`trend-chart.tsx:143-186`, full function — the `role="group"`/`aria-pressed` accessible-toggle shape):
```tsx
function RangeToggle({ value, onChange }: { value: Range; onChange: (n: Range) => void }) {
  const opts: { id: Range; label: string; a11y: string }[] = [
    { id: '7d', label: microcopy.trend.range7d, a11y: microcopy.trend.range7dA11y },
    { id: '30d', label: microcopy.trend.range30d, a11y: microcopy.trend.range30dA11y },
    { id: '90d', label: microcopy.trend.range90d, a11y: microcopy.trend.range90dA11y },
  ];
  return (
    <div role="group" aria-label="Trend range" className="inline-flex rounded-md border border-border-subtle p-0.5">
      {opts.map(o => {
        const active = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.id)}
            className={cn('rounded-sm px-3 py-1 text-xs font-mono transition-colors',
              active ? 'bg-surface-2 text-text' : 'text-text-muted hover:text-text')}
          >
            {o.label}
            <span className="sr-only">{' '}({o.a11y})</span>
          </button>
        );
      })}
    </div>
  );
}
```
Add `1y` and `Custom range` entries to `opts`; selecting `Custom range` reveals the two date fields below instead of firing a query immediately.

**Radix dropdown for the scope selector — reuse verbatim** (`frontend/src/components/ui/dropdown-menu.tsx:9-15`, the primitive exports already wired to sunset tokens):
```tsx
const DropdownMenu = DropdownMenuPrimitive.Root
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
...
const DropdownMenuContent = ... // already styled: bg-surface, border-border, shadow-md
const DropdownMenuItem = ...    // already styled: focus:bg-surface-2
```
Compose `<DropdownMenu><DropdownMenuTrigger>{scopeLabel}</DropdownMenuTrigger><DropdownMenuContent><DropdownMenuItem onSelect={...}>All (tenant)</DropdownMenuItem>{groups.map(...)}</DropdownMenuContent></DropdownMenu>` — per UI-SPEC's overflow resolution, add an inline search/filter input inside `DropdownMenuContent` when the group list is long (no existing precedent for the search-inside-dropdown part — compose it from the `DropdownMenuContent` + a plain controlled `<input>` at the top).

**Native `<input type="date">`, zero new dependency — the exact styling + field convention** (`exception-grant-dialog.tsx:61-62,313-335`):
```tsx
const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
...
<div>
  <label htmlFor="exception-expires" className={FIELD_LABEL_CLASS}>Expires</label>
  <input
    id="exception-expires"
    type="date"
    min={minDate}
    max={maxDate}
    value={expiresAt}
    onChange={(e) => setExpiresAt(e.target.value)}
    className={FIELD_CLASS}
  />
  {expiryFieldError ? (
    <p role="alert" className="mt-1 text-xs text-danger">{expiryFieldError}</p>
  ) : (
    <p className="mt-1 text-xs text-text-muted">Mandatory — this decision resurfaces for review on this date.</p>
  )}
</div>
```
Use `type="date"` for both `From`/`To` fields; the field-level `role="alert"` error-text pattern is the exact shape for the UI-SPEC's `End date must be after start date.` validation message. Note: `components/ui/input.tsx`'s shared `InputProps.type` union does NOT currently include `'date'` (verified — zero matches for a `'date'` variant) — either hand-roll a plain `<input>` with `FIELD_CLASS` (as this analog does, bypassing the shared `Input` wrapper entirely) or extend `InputProps.type` additively first.

**Group-scope semantic caption (D-06 — mandatory whenever scope ≠ "All (tenant)")** — no existing analog renders this exact kind of "here's what this data means" caveat text; it's a plain conditional `<p className="text-xs text-text-muted">` rendering the UI-SPEC's locked copy: `Shows {group name}'s current members, applied retroactively across this window.` Render it directly under the scope control, not buried in a tooltip (UI-SPEC: "Caption the semantic on the chart").

---

### `frontend/src/components/analytics/analytics-page-skeleton.tsx` (component, transform)

**Analog:** `frontend/src/components/ui/trend-chart-skeleton.tsx` (19 lines, full file) + `coverage/page.tsx`'s inline `CoverageStripSkeleton` (lines 213-225).

**Chart-shimmer shape** (`trend-chart-skeleton.tsx`, full):
```tsx
export function TrendChartSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      <div className="flex justify-end gap-1">
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
        <div className="h-7 w-12 rounded-md bg-surface-2 animate-pulse" />
      </div>
      <div className="h-[200px] rounded-md bg-surface-2 animate-pulse" />
    </div>
  );
}
```

**Card-shimmer shape** (`coverage/page.tsx:214-225`):
```tsx
function CoverageStripSkeleton() {
  return (
    <StatStrip aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-[168px] rounded-lg border border-border-subtle bg-surface-2 p-6 animate-pulse" />
      ))}
    </StatStrip>
  );
}
```
`AnalyticsPageSkeleton` composes: a controls-row shimmer (mirrors the 3 `h-7 w-12` pills above, extended to account for the scope dropdown trigger too) + a `h-[200px]` block for the trend chart + a similarly-sized block for the aging chart + one `h-[168px]`-style card block for the burndown tile — same layout slots as the real page, `aria-busy="true" aria-live="polite"` on the outer wrapper (never a separate `role="status"`, matching the `TrendChartSkeleton` convention exactly, not `EmptyState`'s `role="status"`).

---

### `frontend/src/components/analytics/microcopy.ts` (utility, n/a)

**Analog:** `frontend/src/components/coverage/microcopy.ts` (98 lines, exact structural match — co-located microcopy module, one export named `microcopy`, nested by page-section).

**Structure to mirror** (`coverage/microcopy.ts:30-63`, abbreviated):
```ts
export const microcopy = {
  page: {
    h1: 'Coverage',
    subtitle: (n: number) => `${n} device${n === 1 ? '' : 's'} in inventory ${n === 1 ? 'has' : 'have'} never been touched by a scanner`,
  },
  empty: {
    noInventory: { title: '...', body: '...', action: '...' },
    allCovered: { title: '...', body: (n: number) => `...` },
  },
  columns: { hostname: 'Hostname', ... },
  badge: { noScannerCoverage: 'No scanner coverage' },
} as const;
```
`analytics/microcopy.ts` mirrors this exactly, transcribing 42-UI-SPEC.md's Copywriting Contract verbatim into a `const microcopy = {...} as const` with `page` (h1: `'Analytics'`), `scope` (dropdown labels), `window` (preset + sr-only expansions), `trend` (section heading, group-scope caption, version-boundary label/tooltip), `aging` (section heading, 3 bucket labels, headline tile), `burndown` (section heading, shrinking/growing/no-change copy, projected-clear copy), `mttr` (toggle label), `empty` (insufficient-history title/body). Every string is already locked in the UI-SPEC — this file is a transcription task, not a copywriting task.

**Pluralization-safe interpolation pattern to copy** (`coverage/microcopy.ts:36-37`):
```ts
subtitle: (n: number) =>
  `${n} device${n === 1 ? '' : 's'} in inventory ${n === 1 ? 'has' : 'have'} never been touched by a scanner`,
```
Apply the identical `n === 1 ? '' : 's'` guard anywhere the new copy has a count (e.g. the "% of backlog overdue" tile, if it needs a findings-count variant — though the locked copy `{N}% of open backlog is overdue` has no singular/plural branch needed).

---

### `frontend/src/lib/queries/use-analytics.ts` (hook, request-response)

**Analog (no-arg single-payload shape — the closer match, since D-13/A2 recommend ONE combined endpoint):** `frontend/src/lib/queries/use-coverage-summary.ts` (48 lines, full file). **Analog (range-param shape, needed since this hook DOES take scope+window params unlike coverage/summary):** `frontend/src/lib/queries/use-trends.ts` (25 lines, full file).

**`useCoverageSummary` — full file, the single-flat-object-response shape:**
```ts
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type CoverageSummaryResponse = {
  cards: CoverageConnectorCard[];
  total_authoritative_assets: number;
  has_authoritative_inventory: boolean;
  has_scanner_connector: boolean;
};

export function useCoverageSummary() {
  return useQuery({
    queryKey: queryKeys.coverage.summary(),
    queryFn: ({ signal }) => api<CoverageSummaryResponse>('/api/v1/coverage/summary', { signal }),
    staleTime: 0,
    retry: 1,
  });
}
```

**`useTrends` — full file, the range-param-in-key shape:**
```ts
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from './keys';

export type Range = '7d' | '30d' | '90d';

export function useTrends(range: Range = '30d') {
  const days = range === '7d' ? 7 : range === '90d' ? 90 : 30;
  return useQuery({
    queryKey: queryKeys.vulnerabilities.trends(range), // key carries range param
    queryFn: ({ signal }) => api<TrendsResponse>(`/api/v1/vulnerabilities/trends?days=${days}`, { signal }),
    staleTime: 60_000,
    retry: 1,
    refetchOnWindowFocus: false, // chart redraw on alt-tab is jarring
  });
}
```
`useAnalytics(scope, window, customFrom?, customTo?)` merges both shapes: single combined endpoint (coverage's no-arg simplicity) but WITH params that must be part of the query key (trends' range-in-key discipline) — `queryKey: queryKeys.analytics.overview({ scope, window, from: customFrom, to: customTo })`, `staleTime` closer to `0` than `60_000` (D-13 is explicitly live-compute-on-read, not a cacheable-for-a-minute dashboard tile), `refetchOnWindowFocus: false` (same chart-redraw-is-jarring reasoning as trends).

---

### `frontend/src/lib/queries/keys.ts` (utility, n/a) — modify

**Analog:** itself — the most recently added `coverage` block, the literal template.

**Exact block to copy-and-adapt** (`keys.ts:153-157`):
```ts
  // Phase 41 (41-01, COV-01) — /dashboard/coverage blind-spot-detection
  // tracer slice. GET /api/v1/coverage/blind-spots supports page/page_size
  // (mirrors tickets.list's opts-object shape so pagination stays part of
  // the cache key). `summary()` is added now (no opts) so Plan 02 (COV-02
  // coverage strip, GET /api/v1/coverage/summary) needs no re-touch here.
  coverage: {
    all: ['coverage'] as const,
    summary: () => ['coverage', 'summary'] as const,
    blindSpots: (opts: { page: number }) => ['coverage', 'blind-spots', opts] as const,
  },
```
Add, following the identical comment-then-block convention:
```ts
  // Phase 42 (TREND-01..03) — /dashboard/analytics surface. ONE combined
  // read (D-13/A2 single compute pass) so overview() takes the full
  // scope+window opts object as its cache key (mirrors tickets.list's
  // opts-object shape), not a no-arg key like coverage.summary().
  analytics: {
    all: ['analytics'] as const,
    overview: (opts: { scope: string; window: string; from?: string; to?: string }) =>
      ['analytics', 'overview', opts] as const,
  },
```
(exact param names are D-15 planner discretion — this is the shape, not the literal final field names).

---

### `frontend/src/components/shell/nav-items.ts` (config, n/a) — modify

**Analog:** itself — the most recently added `Coverage` entry inside `WORKFLOW_ITEMS`.

**Exact block to copy-and-adapt** (`nav-items.ts:53-55`):
```ts
  // Phase 41 (41-01, COV-01) — blind-spot detection list view. No chip per
  // D-N-01 (not one of the three chip-carrying destinations).
  { label: 'Coverage', href: '/dashboard/coverage', icon: Radar },
```
Add immediately after it (per UI-SPEC: `Analytics`, no chip):
```ts
  // Phase 42 (TREND-01..03) — risk-trend analytics & burndown deep-view. No
  // chip per D-N-01 (not one of the three chip-carrying destinations).
  { label: 'Analytics', href: '/dashboard/analytics', icon: LineChart },
```
Also add `LineChart` to the `lucide-react` import line at the top of the file (`nav-items.ts:4-6`, currently `Home, Bug, Server, Cloud, Ticket, Plug, Users, Settings, Zap, FolderKanban, Target, ShieldOff, Radar` — append `LineChart`). No other array (`TRIAGE_ITEMS`, `UNLABELED_ITEMS`, `BOTTOM_NAV_PRIMARY`) needs a change — `ALL_ITEMS`/`MORE_ITEMS` derive automatically from `WORKFLOW_ITEMS` via spread (`nav-items.ts:64-84`), so Analytics automatically appears in the tablet drawer's full list and the phone "More" sheet with zero additional edits.

---

## Shared Patterns

### RBAC — `require_viewer` on every new GET
**Source:** `backend/app/coverage/router.py:52-56,67-70` / `backend/app/vulnerabilities/router.py:187-190`
**Apply to:** `analytics/router.py`'s only endpoint(s) — D-14 is viewer+, no analyst-gated mutation exists this phase (no write path at all).
```python
async def get_coverage_summary_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CoverageSummaryResponse:
```

### Tenant scoping — every WHERE clause carries `tenant_id`
**Source:** every query in `trends.py`, `coverage/service.py`, `sla_tier_service.py` (`Vulnerability.tenant_id == tenant_id` / `DailySnapshot.tenant_id == tenant_id` / `Asset.tenant_id == tenant_id`, always inline in the `.where(...)`, never a post-fetch filter)
**Apply to:** every new query in `analytics/service.py` — this is the ASVS V4 control this codebase enforces everywhere; a missing `tenant_id` filter on a `DailySnapshot`/`Vulnerability` aggregate is the single most consequential mistake this phase could make (cross-tenant score/backlog leak).

### IDOR-safe scoped lookup — 404, never fetch-then-403
**Source:** `backend/app/coverage/router.py:39-49` (`_get_asset_or_404`) + `backend/app/assets/groups_service.py:123-136` (`list_members` returning `None`)
**Apply to:** the `group_id` scope param on the new `/analytics` endpoint — a cross-tenant `group_id` must 404 via the tenant filter being IN the query, never a fetch-then-authorize-in-Python check.

### Exclusion predicate — reuse verbatim, never re-derive
**Source:** `backend/app/exceptions/service.py:50-71` (`active_exception_subquery`)
**Apply to:** every open-backlog query in `get_aging_distribution`/`get_burndown_rate` (D-10) — always `~active_exception_subquery(tenant_id, now)`.

### SLA-tier policy — reuse verbatim, never re-derive
**Source:** `backend/app/vulnerabilities/sla_tier_service.py:49,57-109` (`DEFAULT_TIER_POLICY`, `tier_for_score`, `severity_to_tier`, `get_tier_policy`)
**Apply to:** the aging chart's bucket boundaries (D-08) — never `sla_service.py`'s legacy severity-keyed constants (Pitfall 2).

### Decimal-to-JSON-safe numeric cast
**Source:** `backend/app/vulnerabilities/trends.py:159,374,380` (`round(float(x), N) if x else 0/None`)
**Apply to:** every new aggregate value in `analytics/service.py` (burndown's net-velocity average, any new `func.avg`/`func.sum`) before it enters a Pydantic response (Pitfall 6).

### Additive-optional-param backward compatibility
**Source:** `backend/app/vulnerabilities/sla_tier_service.py:118` (`excepted_seconds: int = 0`)
**Apply to:** `get_vuln_trends(db, tenant_id, days=30, asset_ids: list[uuid.UUID] | None = None)` — the group-scoping extension for aging/burndown (Pitfall 5) must not change any existing call site's behavior.

### Pydantic v2 response-schema convention
**Source:** `backend/app/coverage/schemas.py:19,25` (`ConfigDict(from_attributes=True)`)
**Apply to:** every class in `analytics/schemas.py`.

### State-branch ordering — error > loading > empty variant(s) > populated
**Source:** `frontend/src/app/(authed)/dashboard/coverage/page.tsx:318-388` (WR-13 discipline, explicit code comment)
**Apply to:** `AnalyticsPageInner`'s single combined branch chain (simpler than Coverage's two-query chain, since D-13 is one compute pass).

### Canonical state-primitive triad
**Source:** `frontend/src/components/states/{empty-state.tsx, partial-failure-banner.tsx}` (compound `EmptyState.Title`/`.Body`/`.Actions`; `role="alert"` amber `PartialFailureBanner` with `onRetry`)
**Apply to:** every chart/tile section's empty and error rendering — reuse verbatim per UI-SPEC, do not build a new empty/error primitive.

### `useUrlState` enum-clamp for URL-driven controls
**Source:** `frontend/src/hooks/use-url-state.ts:11-28`
**Apply to:** the window-preset selector (extend the allow-list array, do not modify the hook) — but NOT the custom `from`/`to` dates (Pitfall 3 — those need separate, non-enum validation).

### TanStack query-key registry, domain-first nesting
**Source:** `frontend/src/lib/queries/keys.ts:153-157` (the `coverage` block, most recent addition)
**Apply to:** the new `analytics` block — opts-object-in-key shape (mirrors `tickets.list`/`coverage.blindSpots`, not the no-arg `coverage.summary` shape, since this hook DOES take scope+window params).

### Nav entry — static array, no data dependency
**Source:** `frontend/src/components/shell/nav-items.ts:53-55` (the `Coverage` entry)
**Apply to:** the new `Analytics` entry inside `WORKFLOW_ITEMS` — automatically flows into `ALL_ITEMS`/`MORE_ITEMS` via existing spread/filter logic, zero extra wiring.

---

## Novel Logic (No Precedent)

Every FILE in this phase has at least a role-match analog (see classification table above). These three pieces of *logic* — sub-parts of the files above — have **zero precedent anywhere in this codebase**. Do not spend time searching for an analog for these; RESEARCH.md's sketches (already verified against recharts docs / this codebase's data shapes) are the only available source, and the plan should say so explicitly rather than imply a copy-paste origin.

1. **Version-boundary detection** (`analytics/service.py`) — comparing each snapshot's `risk_model_version_snapshot` to the previous one to emit a boundary list. RESEARCH.md Code Examples §3 has the only sketch (`detect_version_boundaries`). Confirmed via grep: `RISK_MODEL_VERSION` has never been bumped past `"v1"` in any real data — this function's multi-version behavior can only be proven against the synthetic fixture in `test_analytics.py` (see that file's pattern assignment above), never against production data.

2. **Segmented-line + `ReferenceLine` boundary marker rendering** (`risk-trend-chart.tsx`) — no existing component in this codebase uses recharts' `Line`, `ReferenceLine`, or `connectNulls` in any form; `trend-chart.tsx` is a `BarChart`. RESEARCH.md Architecture Patterns Pattern 4 has the full pivot-by-version-segment sketch (one `dataKey` per version, `null` outside that version's range, one `<ReferenceLine>` per boundary) — this is the primary source, not a codebase file.

3. **Retroactive group-membership intersection against historical per-asset score dicts** (`analytics/service.py`, D-05/D-06) — intersecting `DailySnapshot.metrics["asset_risk_exposure_scores"]` (a per-snapshot dict) against the group's CURRENT `AssetGroupMember` set, per historical row. RESEARCH.md Architecture Patterns Pattern 3 has the only sketch, composed from verified-but-never-before-combined primitives (`groups_service.list_members` + the raw `DailySnapshot` select shape from `get_risk_score_trend`). The `None`-vs-`0` distinction for a zero-scored-members day (D-06) is load-bearing and has no existing analog either — every prior average-computation in this codebase (`capture_daily_snapshot`'s `avg_risk`/`avg_risk_exposure`) defaults to `0`, not `None`, when its denominator is empty; this phase's group series is the first to require `None` (a real gap) instead.

---

## Metadata

**Analog search scope:** `backend/app/coverage/`, `backend/app/vulnerabilities/{trends,router,sla_tier_service}.py`, `backend/app/exceptions/service.py`, `backend/app/assets/groups_service.py`, `backend/app/main.py`, `backend/tests/test_risk_boundary_guard.py`, `frontend/src/components/{dashboard,ui,campaigns,coverage,exceptions,states,shell}/`, `frontend/src/app/(authed)/dashboard/coverage/`, `frontend/src/lib/queries/{use-trends,use-coverage-summary,use-asset-groups,keys}.ts`, `frontend/src/hooks/use-url-state.ts`.
**Files scanned (read in full or targeted range):** 30
**Pattern extraction date:** 2026-08-21
