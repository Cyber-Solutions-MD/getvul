# Phase 42: Risk Trend Analytics & Burndown - Research

**Researched:** 2026-08-21
**Domain:** Read-side time-series analytics over an existing FastAPI/SQLAlchemy/Postgres backend + Next.js/recharts frontend (no new external services)
**Confidence:** HIGH (backend data model, existing endpoints/patterns — all read directly from source) / MEDIUM (exact recharts segmented-line implementation shape — verified via docs/search, not yet exercised in this codebase) / LOW-flagged where noted (SLA-bucket exact day thresholds, group-scoping of burndown — explicit CONTEXT.md discretion or genuine ambiguity)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**TREND-01 — View placement, scope & window**
- **D-01:** New dedicated top-level "Analytics" nav page (sidebar entry, mirroring Phase 41's Coverage precedent), NOT an expansion of the existing dashboard `TrendSection`. The dashboard `TrendSection` stays as-is.
- **D-02:** Single scope dropdown as the primary selector — "All (tenant)" by default plus each `AssetGroup`. Changing it re-scopes **every** chart on the page (trend line, aging distribution, burndown) to one mental model.
- **D-03:** Selectable window = 7d / 30d / 90d / 1y preset buttons PLUS a custom start/end date-range picker. Default 30d. Reuses the existing `Range` control idiom (`trend-section.tsx` uses `useUrlState` over `['7d','30d','90d']`), extended with 1y + a custom range. Reversible.
- **D-04:** Guided empty state below a minimum-history threshold — render canonical `EmptyState` instead of a misleading 1–2-point line. Exact threshold + copy is planner discretion (follow `copy-voice.md`).

**TREND-01 — Team/asset-group series derivation**
- **D-05:** Group trend lines derived retroactively, on-read, from the per-asset score dicts already stored in each snapshot (`DailySnapshot.metrics["asset_risk_scores"]` / `["asset_risk_exposure_scores"]`, asset_id → score) intersected with the group's **current** `AssetGroupMember` set. No schema change, no forward-only wait.
- **D-06:** Group history uses CURRENT membership applied retroactively across the whole window (recompute each past point over exactly today's members), not point-in-time membership. Caption the semantic on the chart.
- **D-07:** The plotted aggregate is the AVERAGE risk-exposure score across the scope's assets — exactly what the tenant snapshot's `avg_risk_exposure_score` already stores. Not toggleable this phase.

**TREND-02 — Backlog aging & burndown**
- **D-08:** "Open findings by age × severity" = a point-in-time stacked aging chart, computed live from current open vulns. Age buckets are **SLA-tier aligned** (within-SLA / recently-breached / long-overdue), mirroring existing per-severity SLA windows (reuse Phase 36 SLA config). SLA-aligned buckets are severity-relative by construction.
- **D-09:** Burndown rate = net flow + a projected days-to-zero. From the daily new-vs-resolved series (already computed by `get_vuln_trends` from `first_detected_at`/`remediated_at`), show net burndown velocity (avg resolved − new per period) and a projected "days to clear the backlog at current rate" (or "backlog growing").
- **D-10 (exclusions):** Aging + burndown honor the Phase 39/40 exclusion predicate — open-backlog counts exclude `status IN (SUPPRESSED, FALSE_POSITIVE)` and findings under an active exception (EXC-02), reusing the Phase 39 predicate **verbatim** (do not re-derive).

**TREND-03 — Version-boundary awareness & which score**
- **D-11 (boundary rendering):** Segment the line at each version-change date (no interpolation across the boundary) AND drop a labeled vertical reference marker (e.g. "risk model v4.1 → v4.2"). A boundary is detectable as the date `DailySnapshot.metrics["risk_model_version_snapshot"]` changes value.
- **D-12 (which score):** Always plot the versioned risk-exposure score (`avg_risk_exposure_score` / the RISK-01..10 model), decoupled from the tenant's `cutover_risk_exposure_scoring` flag. Because Phase 34 RISK-10 dual-writes the exposure metrics unconditionally, the data exists for every tenant regardless of the consumer-cutover flag. This intentionally diverges from the existing dashboard `/trends` behavior (which honors the flag via `get_risk_score_trend`).

**Compute, RBAC & backend shape**
- **D-13 (compute):** Live compute on-read, tenant-bounded, matching Phase 41 D-10 and the existing `/trends`. Raise the current 90-row snapshot `LIMIT` (in `get_risk_score_trend`) to cover the 1y/custom windows. Reversible — pure read-side service.
- **D-14 (RBAC):** Viewer+ (any authenticated tenant user), any group. Match the existing `/trends` endpoint (`require_viewer`). No per-group access control (none exists today).
- **D-15 (endpoints):** New `/analytics` endpoint(s) taking scope + range/date params, leaving the existing `GET /trends` untouched. Extending `/trends` rejected.
- **D-16 (Phase 43 hand-off):** Shape the compute as a reusable service layer — service functions (like `trends.py`'s `get_*` functions) that BOTH the new HTTP route AND Phase 43's PDF/report generator can call directly, with no HTTP round-trip.

### Claude's Discretion
- Exact minimum-history threshold + empty-state copy (D-04) — follow `copy-voice.md`.
- Exact SLA-tier bucket boundaries/labels for the aging chart (D-08) and whether a headline "% of backlog overdue" tile accompanies it.
- Exact burndown metric presentation — number, sparkline, or "days-to-zero" tile (D-09).
- Whether a plain MTTR line appears as supporting context on the page (reusing `get_mttr_trend`) — allowed but not required.
- Exact `/analytics` route naming, param shape, and response schema (D-15); how the reusable service functions are decomposed (D-16).
- Whether the tenant "All" series reads the snapshot's stored `avg_risk_exposure_score` directly vs. re-aggregating the per-asset dict (both should agree; direct read is cheaper).
- Chart library reuse — the existing `TrendChart` primitive (recharts, dynamic-imported) vs. an extension for segmented lines + annotations.

### Deferred Ideas (OUT OF SCOPE)
- Materialized/pre-aggregated trend rollups — compute on-read; materialize only if a very large tenant demonstrates a real performance need.
- Point-in-time group membership (membership-history table) — current membership retroactively; a true historical-membership view needs a new audit/capture pipeline.
- Sum/total-exposure trend aggregate and a per-chart avg↔total toggle — average only.
- Per-group access control (RBAC) — any tenant user may scope any group.
- Aging bands trended over time (each age band as its own historical line) — point-in-time distribution only; the snapshots don't store age-at-each-past-date.
- MTTR-by-tier breakdown, exec/board PDF, role-scoped dashboards, framework-control compliance mapping — Phase 43 (RPT-01..03), which consumes this phase's data.

**UI-SPEC.md is APPROVED and locked** (verified 2026-08-21) — every color/typography/spacing/copy/state decision in this research defers to `42-UI-SPEC.md`; this document does not re-litigate those, only the underlying data/code contracts.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TREND-01 | Tenant / team / asset-group risk-exposure trend lines over a selectable window | `DailySnapshot.metrics["avg_risk_exposure_score"]` (tenant) + `asset_risk_exposure_scores` dict intersected with `AssetGroupMember` (group) — see Standard Stack / Code Examples §1-2. Existing `get_risk_score_trend` (`trends.py:166-215`) is the direct precedent to extend, not reuse as-is (its `LIMIT 90` and flag-gating both must change per D-12/D-13). |
| TREND-02 | Backlog aging (open findings by age × severity) and burndown rate | `Vulnerability.first_detected_at/sla_due_at/sla_breached/severity/status` (models.py:104-108) for aging; `get_vuln_trends` (`trends.py:38-126`) for the new-vs-resolved feed powering burndown; `sla_tier_service.py`'s tier windows (critical=7d/high=30d/moderate=90d) for SLA-aligned buckets; `active_exception_subquery` (`exceptions/service.py:50`) for D-10 exclusions. |
| TREND-03 | Trends are risk-model-version-boundary aware (annotate, never blend across a v4.0 model version change) | `RISK_MODEL_VERSION` constant (`risk_exposure_service.py:92`), stamped per-snapshot into `metrics["risk_model_version_snapshot"]` (`trends.py:383`). recharts `Line` gap-at-null + `ReferenceLine` verified capable of the segment+marker requirement (see Code Examples §4). **Gap:** the constant has never been bumped past `"v1"` — no real historical boundary exists yet; testing needs a synthetic fixture (see Common Pitfalls #1). |

</phase_requirements>

## Summary

Phase 42 is a pure read-side analytics feature over data GetVul already captures — no new ingestion, no new scoring model, no new table (beyond, at most, a schema-free reuse of the existing `daily_snapshots` JSONB). The entire historical substrate already exists in `backend/app/vulnerabilities/trends.py`: `DailySnapshot` (per-day tenant metrics + per-asset score dicts + `risk_model_version_snapshot`), written once daily by `capture_daily_snapshot` (invoked from the scheduler's 24h ticket-sync gate) and read today only by a narrow, flag-gated `get_risk_score_trend` capped at the most recent 90 rows. Backlog data lives on the live `Vulnerability` row (`first_detected_at`, `remediated_at`, `status`, `severity`, `sla_due_at`, `sla_breached`), and the SLA windows Phase 42's aging buckets should mirror are Phase 36's tier-keyed engine (`sla_tier_service.py`, critical=7d/high=30d/moderate=90d) — **not** the older severity-keyed `sla_service.py` engine, which the scheduler no longer treats as the live writer of `sla_due_at`/`sla_breached`.

The most consequential, non-obvious finding: **`RISK_MODEL_VERSION` has never changed from `"v1"` anywhere in this codebase.** Every `daily_snapshots.metrics["risk_model_version_snapshot"]` row in real data — dev, test, or (presumably) production — carries the identical value. Success Criterion 3 ("a v4.0 model version change never produces a false cliff") is therefore currently **unverifiable against real data**; the plan must include a way to construct a synthetic multi-version fixture (a pattern the codebase already has, just never applied to this specific field — see Common Pitfalls #1 and Code Examples #5).

On the frontend, recharts 2.12.0 is already installed and the existing `TrendChart` primitive (`components/ui/trend-chart.tsx`) is a **stacked bar chart** of severity counts, not a line chart — it cannot be reused for the risk-exposure trend line itself, only its patterns (CSS-variable fills, `RangeToggle`, sr-only data table) and its exported `SEVERITY_FILLS` constant (directly reusable for the aging chart, per the UI-SPEC). The two genuinely new chart primitives (`RiskTrendChart`, `BacklogAgingChart`) are both achievable with stock recharts APIs — confirmed via web search: `Line` naturally gaps at `null` values (default `connectNulls={false}`), and `ReferenceLine` supports a `label` and can be rendered N times for N boundaries.

**Primary recommendation:** Add a new top-level `backend/app/analytics/` module (`router.py` + `service.py` + `schemas.py`), structurally mirroring Phase 41's `backend/app/coverage/` module exactly (same RBAC pattern, same Pydantic `ConfigDict(from_attributes=True)` schema convention, same `main.py` registration idiom). Compose ONE `GET /api/v1/analytics/...` endpoint from 3+ small, decomposed, plain-async service functions (no FastAPI `Depends` inside them) so Phase 43 can call them directly — this single-endpoint shape is also what the UI-SPEC's repeated "single compute pass (D-13)" language for shared loading/error state requires. Extend `get_vuln_trends` and `get_risk_score_trend` additively (new optional params, backward-compatible defaults) rather than forking them, matching this codebase's consistent "additive, byte-identical when omitted" idiom (seen in `RiskRing`'s 3 new optional props, `compute_sla_state`'s `excepted_seconds: int = 0`, RISK-10's unconditional dual-write).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trend/aging/burndown aggregation (SQL, tier logic, exclusion predicate) | API / Backend | Database | All existing precedent (`get_vuln_trends`, `get_mttr_trend`, `sla_tier_service.py`) lives in service-layer Python composing SQLAlchemy queries — this phase's new logic follows suit. |
| Risk-model version-boundary detection | API / Backend | — | Detecting where `risk_model_version_snapshot` changes is a data-shape question, resolved once server-side and shipped to the client as an already-annotated series + boundary list — never re-derived client-side from raw dates. |
| Version-boundary visual rendering (segment break + reference marker) | Browser / Client | — | Purely a recharts rendering concern once the backend hands over pre-segmented data + boundary markers. |
| Group-scoped retroactive trend derivation (intersect per-asset dicts with current membership) | API / Backend | Database (`AssetGroupMember` join) | Requires a tenant-scoped membership fetch (`groups_service.py::list_members`) + JSONB dict intersection — must happen server-side to avoid shipping every tenant asset's historical score to the browser. |
| SLA-tier aging bucketing | API / Backend | — | Reuses `sla_tier_service.py`'s tier-day constants; a pure computation, no new persistence. |
| Exclusion-predicate filtering (SUPPRESSED/FALSE_POSITIVE/active exception) | API / Backend | Database (`EXISTS` subquery) | `active_exception_subquery` is a correlated SQL subquery — must be applied inside the query, not post-filtered in Python. |
| Scope + window selection (dropdown, range toggle, custom date fields) | Browser / Client | — | URL-state-driven controls (`useUrlState`), no server involvement beyond receiving the resulting query params. |
| Chart rendering (segmented line, stacked SLA-tier bars) | Browser / Client | — | recharts composition; data already fully shaped by the backend. |
| Daily snapshot persistence (`capture_daily_snapshot`, scheduler cadence) | Database | API / Backend (scheduler) | **Not touched by this phase** — Phase 42 is read-only against this existing capture pipeline. |
| New "Analytics" nav entry | Browser / Client | — | Static `nav-items.ts` array entry, no data dependency. |
| Cross-phase service reuse (Phase 43 PDF/report) | API / Backend | — | D-16 requires the analytics service functions be callable directly (no HTTP round-trip) — a plain-Python-function contract, same tier as the HTTP route that also calls them. |

## Standard Stack

No new external dependency is required for this phase — every library below is already installed and pinned in the repo's lockfiles. This section documents the **existing** stack the phase must build on, verified against the actual lockfiles/config, not assumed from training data.

### Core (already installed — verified against package.json / pyproject.toml)
| Library | Version | Purpose | Why Standard (in this repo) |
|---------|---------|---------|--------------|
| recharts | ^2.12.0 [VERIFIED: frontend/package.json:30] | Chart rendering (existing `TrendChart`; new `RiskTrendChart` line chart, `BacklogAgingChart` stacked bars) | Every dashboard chart in the app already uses recharts; UI-SPEC mandates hand-rolled recharts compositions, not a new charting lib. |
| @tanstack/react-query | ^5.100.10 [VERIFIED: frontend/package.json:23] | Data fetching/caching for the new analytics hook(s) | Sole data-fetching layer in the app (`use-trends.ts`, `use-coverage-summary.ts`, etc.) |
| @radix-ui/react-dropdown-menu | ^2.1.16 [VERIFIED: frontend/package.json:18] | Scope dropdown (reused verbatim per UI-SPEC) | Already wrapping in `components/ui/dropdown-menu.tsx`; zero new registry installs this phase. |
| lucide-react | ^0.383.0 [VERIFIED: frontend/package.json:25] | `LineChart` icon for the new nav entry | Existing icon set; `nav-items.ts` already imports from it. |
| FastAPI | >=0.115,<1.0 [VERIFIED: backend/pyproject.toml:7] | New `/api/v1/analytics` router | Every backend route in the app. |
| SQLAlchemy (asyncio) | >=2.0 [VERIFIED: backend/pyproject.toml:11] | All new aggregation queries | Async ORM used throughout; `trends.py` is the direct precedent for the query shapes this phase needs. |
| Pydantic | >=2.9 [VERIFIED: backend/pyproject.toml:9] | New `analytics/schemas.py` response models | v2 `ConfigDict(from_attributes=True)` convention, confirmed in `coverage/schemas.py`. |

### Supporting (existing app code, not registry packages)
| Module | Purpose | When to Use |
|---------|---------|-------------|
| `app.vulnerabilities.trends` (`DailySnapshot`, `get_vuln_trends`, `get_mttr_trend`, `get_risk_score_trend`, `RISK_MODEL_VERSION` re-export) | The historical substrate — TREND-01/02/03's primary data source | Import from, extend additively; do not fork. |
| `app.vulnerabilities.sla_tier_service` (`get_tier_policy`, `tier_for_score`, `severity_to_tier`, `resolve_state_for_vuln`, `DEFAULT_TIER_POLICY`) | Phase 36's live tier-keyed SLA engine — the "Phase 36 SLA config" D-08 refers to | Reuse for SLA-aligned aging bucket boundaries. |
| `app.exceptions.service.active_exception_subquery` | Phase 39's exclusion predicate | Apply verbatim (`~active_exception_subquery(tenant_id, now)`) to every open-backlog query per D-10. |
| `app.assets.groups_service.list_members` | Tenant-scoped, 404-safe group membership fetch | Reuse for scope validation + member asset_id fetch (D-05); do not write a raw query. |
| `app.coverage.{router,service,schemas}` | Phase 41's brand-new top-level module — the structural precedent this phase should mirror | Copy the shape: `router.py` (thin, RBAC + response_model), `service.py` (plain async functions), `schemas.py` (Pydantic v2). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending `trends.py` in place | A brand-new `app/analytics/` module | CONTEXT.md's own D-01 explicitly says "mirroring Phase 41's Coverage precedent" (a brand-new module), and the actual Phase 41 code confirms that shape (`coverage/` sits beside `assets/`, not inside it). Extending `trends.py` in place would also make Phase 43's "no HTTP round-trip" reuse (D-16) less clean than importing a dedicated `analytics.service` module. Recommendation: new module that **imports from** `trends.py`, does not inline into it. |
| Multiple `/analytics/*` endpoints (one per chart) | ONE combined `/analytics/overview`-style endpoint | The UI-SPEC's repeated "single compute pass (D-13)" language for shared loading/error state across all 3 charts is a strong signal for one endpoint returning one payload; multiple endpoints would need client-side coordination of 3 independent loading/error states the UI-SPEC does not describe. |
| A new date-picker npm package for the custom range | Native `<input type="date">` | A native-date-input precedent already exists in this codebase (`exception-grant-dialog.tsx:317-323`, Phase 39) with zero new dependency — matches UI-SPEC's explicit "no new date-picker dependency" instruction. |

**Installation:** None required — zero new packages this phase.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ Browser (/dashboard/analytics)                                       │
│                                                                        │
│  Scope dropdown ──┐                                                   │
│  Window control ──┼──> useUrlState(s) ──> useAnalytics(scope, window)│
│  Custom From/To ──┘         (URL is source of truth, deep-linkable)  │
│                                     │                                 │
│                                     ▼  ONE GET request                │
└─────────────────────────────────────┼─────────────────────────────────┘
                                      │  /api/v1/analytics/... ?scope=&window=
                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FastAPI router (require_viewer, tenant-bounded)                      │
│   app/analytics/router.py                                             │
│                                     │                                 │
│                                     ▼                                 │
│   app/analytics/service.py  (plain async functions — Phase 43 reuse) │
│     ├─ get_scoped_trend_series(db, tenant_id, scope, window)          │
│     │     ├─ scope=tenant: read DailySnapshot.metrics[               │
│     │     │     "avg_risk_exposure_score"] directly                  │
│     │     └─ scope=group: list_members() [assets/groups_service.py]  │
│     │           → intersect asset_ids against every snapshot's       │
│     │             metrics["asset_risk_exposure_scores"] dict → avg   │
│     │     ├─ detect risk_model_version_snapshot changes → boundaries │
│     │     └─ segment the series at each boundary (null breakpoints)  │
│     ├─ get_aging_distribution(db, tenant_id, asset_ids|None)         │
│     │     ├─ live Vulnerability query, status OPEN/IN_PROGRESS       │
│     │     ├─ ~active_exception_subquery(...) (Phase 39 predicate)    │
│     │     ├─ bucket by sla_breached + age-since-sla_due_at           │
│     │     │   using sla_tier_service tier windows                    │
│     │     └─ group by severity within each bucket                    │
│     └─ get_burndown_rate(db, tenant_id, window, asset_ids|None)      │
│           ├─ reuses/extends get_vuln_trends's new-vs-resolved feed    │
│           └─ net velocity + projected days-to-zero                   │
│                                     │                                 │
│                                     ▼                                 │
│              Postgres: daily_snapshots (JSONB) + vulnerabilities      │
│              (existing tables, no migration this phase)              │
└─────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │  same service.py functions,
                                      │  called directly (no HTTP)
                              Phase 43 PDF/report generator (D-16)
```

### Recommended Project Structure
```
backend/app/analytics/            # NEW — mirrors backend/app/coverage/
├── __init__.py
├── router.py                     # GET /api/v1/analytics/... (require_viewer)
├── service.py                    # plain async functions; imports from
│                                  #   app.vulnerabilities.trends,
│                                  #   app.vulnerabilities.sla_tier_service,
│                                  #   app.exceptions.service,
│                                  #   app.assets.groups_service
└── schemas.py                    # Pydantic v2, ConfigDict(from_attributes=True)

frontend/src/
├── app/(authed)/dashboard/analytics/
│   ├── page.tsx                  # ErrorBoundary > Suspense > AnalyticsPageInner
│   └── page.test.tsx
├── components/analytics/         # NEW — mirrors components/coverage/
│   ├── risk-trend-chart.tsx      # new: segmented Line + ReferenceLine markers
│   ├── backlog-aging-chart.tsx   # new: stacked BarChart, SEVERITY_FILLS reused
│   ├── burndown-tile.tsx
│   ├── scope-window-controls.tsx
│   ├── analytics-page-skeleton.tsx
│   └── microcopy.ts               # mirrors dashboard/microcopy.ts, coverage/microcopy.ts
└── lib/queries/
    ├── use-analytics.ts           # NEW hook, single combined query
    └── keys.ts                    # extend with an `analytics` namespace
```

### Pattern 1: New top-level module mirrors Phase 41's Coverage exactly
**What:** `router.py` (thin, RBAC-gated, `response_model=`) + `service.py` (plain async functions, no FastAPI-specific code) + `schemas.py` (Pydantic v2), registered in `main.py` with its own prefix/tag.
**When to use:** Any new top-level analyst workflow surface — this phase, per D-01, is explicitly one.
**Example:**
```python
# Source: backend/app/coverage/router.py (verified in this session)
router = APIRouter()

@router.get("/summary", response_model=CoverageSummaryResponse)
async def get_coverage_summary_endpoint(
    db: DBSession,
    user: Annotated[CurrentUser, Depends(require_viewer)],
) -> CoverageSummaryResponse:
    return await _get_coverage_summary(db, user.tenant_id)

# backend/app/main.py:323 (verified)
app.include_router(coverage_router, prefix="/api/v1/coverage", tags=["Coverage"])
```
Phase 42's `main.py` addition follows identically: `app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])`.

### Pattern 2: Service functions are plain, HTTP-agnostic (Phase 43 reuse contract)
**What:** Every reusable service function takes `db: AsyncSession` + plain params, never `Request`/`Depends`.
**When to use:** D-16 requires Phase 43's PDF/report generator to call the same functions with no HTTP round-trip.
**Example:**
```python
# Source: backend/app/vulnerabilities/trends.py:38 (verified) — the exact shape to match
async def get_vuln_trends(db: AsyncSession, tenant_id: uuid.UUID, days: int = 30) -> dict:
    ...
```
New functions (`get_scoped_trend_series`, `get_aging_distribution`, `get_burndown_rate`) should follow this signature style exactly — callable from `analytics/router.py` today and from `reports/*.py` in Phase 43 without modification.

### Pattern 3: Group scoping — retroactive intersection against current membership (D-05/D-06)
**What:** For a group-scoped trend, do NOT add a new per-group snapshot table. Intersect each historical snapshot's per-asset dict against the group's *current* members.
**When to use:** TREND-01's team/asset-group series.
**Example:**
```python
# Sketch, composed from verified primitives:
# app/assets/groups_service.py:123 list_members(db, tenant_id, group_id) -> list[Asset] | None
# app/vulnerabilities/trends.py DailySnapshot.metrics["asset_risk_exposure_scores"]: dict[str, int]

members = await list_members(db, tenant_id, group_id)   # tenant-scoped; None => 404 (cross-tenant IDOR guard)
if members is None:
    raise HTTPException(status_code=404, detail="Asset group not found")
member_ids = {str(a.id) for a in members}

rows = await db.execute(
    select(DailySnapshot.snapshot_date, DailySnapshot.metrics)
    .where(DailySnapshot.tenant_id == tenant_id, DailySnapshot.snapshot_date.between(start, end))
    .order_by(DailySnapshot.snapshot_date)
)
series = []
for snap_date, metrics in rows.all():
    per_asset = metrics.get("asset_risk_exposure_scores", {})
    scoped_values = [v for k, v in per_asset.items() if k in member_ids]
    avg = round(sum(scoped_values) / len(scoped_values), 1) if scoped_values else None
    series.append({"date": snap_date.isoformat(), "avg_risk_exposure_score": avg,
                    "risk_model_version": metrics.get("risk_model_version_snapshot")})
```
Note: `avg` is `None` (not `0`) for a day where the group had zero scored assets — this must render as a gap, not a false zero, distinct from the D-11 version-boundary gap.

### Pattern 4: Segmented line + boundary marker (D-11) — verified recharts capability
**What:** recharts `Line` does not interpolate across a `null` value by default (`connectNulls` default is `false`); `ReferenceLine` supports a `label` and can repeat per boundary.
**When to use:** TREND-03's "never a false cliff" requirement.
**Example (pivot-per-version-segment — the more robust of two viable approaches, see Common Pitfalls #4 for the simpler alternative and its tradeoff):**
```typescript
// Source: recharts docs + community patterns (WebSearch-verified this session,
// not yet present in this codebase — new pattern for RiskTrendChart)
// Transform: one dataKey per detected version, null outside that version's date range.
type PivotedPoint = { date: string } & Record<string, number | null>;

function pivotByVersion(series: { date: string; score: number | null; version: string | null }[]): {
  data: PivotedPoint[];
  versions: string[];
} {
  const versions = Array.from(new Set(series.map(p => p.version).filter((v): v is string => v !== null)));
  const data = series.map(p => {
    const row: PivotedPoint = { date: p.date };
    for (const v of versions) row[`score_${v}`] = p.version === v ? p.score : null;
    return row;
  });
  return { data, versions };
}

// Render: one <Line> per version (same violet stroke, connectNulls left false/default)
{versions.map(v => (
  <Line key={v} type="monotone" dataKey={`score_${v}`} stroke="var(--color-violet)"
        connectNulls={false} dot={{ r: 3 }} isAnimationActive={false} />
))}
// Plus one <ReferenceLine> per detected boundary date (a real date already present
// in the series — the first date of the NEW version — so it aligns with the
// categorical x-axis domain):
{boundaries.map(b => (
  <ReferenceLine key={b.date} x={b.date} stroke="var(--color-border-strong)"
                 strokeDasharray="4 4"
                 label={{ value: `${b.oldVersion} → ${b.newVersion}`, position: 'top' }} />
))}
```

### Pattern 5: SLA-tier aging buckets reuse Phase 36's tier engine, not the legacy severity engine
**What:** `sla_tier_service.py` (critical=7d/high=30d/moderate=90d, keyed off `risk_exposure_score` tier or `severity_to_tier` fallback) is the LIVE writer of `Vulnerability.sla_due_at`/`sla_breached` today (confirmed: `run_sla_tier_pass` runs every scheduler tick; the scheduler's own comment says it "now owns `sla_due_at` + the `sla_breached` derived mirror").
**When to use:** D-08's "reuse Phase 36 SLA config" instruction.
**Example:**
```python
# Source: backend/app/vulnerabilities/sla_tier_service.py:49 (verified)
DEFAULT_TIER_POLICY: dict[str, int] = {"critical": 7, "high": 30, "moderate": 90}
# tier_for_score(score) / severity_to_tier(severity) / get_tier_policy(tenant)
# already resolve, per finding, which tier + day-count applies (D-01/D-03/D-12
# fallback chain) — reuse these functions rather than re-deriving a tier lookup.
```
Do **not** reach for `app/vulnerabilities/sla_service.py::DEFAULT_SLA_DAYS` (`CRITICAL:7, HIGH:30, MEDIUM:90, LOW:180, INFO:365`) — that module is the legacy, severity-keyed engine and is no longer the live writer of the columns the aging chart would read (see Common Pitfalls #2).

### Anti-Patterns to Avoid
- **Re-deriving SLA tier windows inline:** `sla_tier_service.py` already has `get_tier_policy`/`tier_for_score`/`severity_to_tier` — a new hardcoded `{7, 30, 90}` dict in the analytics service would silently drift from a tenant's actual configured policy (`Tenant.sla_config["tier_policy"]` overrides).
- **Re-deriving the exclusion predicate:** every prior v5.0 phase (39, 40) explicitly reuses `active_exception_subquery` verbatim; a hand-rolled `status NOT IN (...)` check would miss the active-exception half of D-10's predicate.
- **Gating the D-04 empty state on a score value:** `avg_risk_exposure_score` legitimately can be `0` for a healthy tenant (see `capture_daily_snapshot`'s `round(float(avg_risk_exposure), 1) if avg_risk_exposure else 0`) — gate the empty state on the **count of snapshot rows** in the window, never on whether the score itself is falsy.
- **Trusting `func.avg()`/`func.sum()` results as JSON-serializable without casting:** Postgres `avg`/`sum` over integer/numeric columns return `Decimal` via SQLAlchemy; every existing snapshot/trend function in this codebase explicitly does `round(float(x), N)` before putting a value in a response dict (see `capture_daily_snapshot`, `get_mttr_trend`). Any new aggregate this phase introduces (e.g., burndown's average net-per-week) must do the same or it will re-introduce the Decimal-serialized-as-string quirk in a brand-new response shape.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Is this finding excluded from active backlog?" | A new `status NOT IN (...)` + manual exception join | `active_exception_subquery(tenant_id, now)` (`exceptions/service.py:50`) | Already handles 3 scope branches (finding/asset/asset-group) with correct expiry-strictness (`expires_at > now`); a hand-rolled version will under- or over-exclude. |
| "What SLA tier/day-count applies to this finding?" | A new severity→days lookup | `sla_tier_service.tier_for_score` / `severity_to_tier` / `get_tier_policy` | Already resolves the risk-exposure-score-tier-with-severity-fallback chain and honors tenant SLA-config overrides; a new lookup would ignore tenant customization. |
| "Which assets are in this group, tenant-safe?" | A raw `AssetGroupMember` join in the new service | `groups_service.list_members(db, tenant_id, group_id)` | Already tenant-scopes and returns `None` for a cross-tenant `group_id` (404-safe, matches the IDOR-prevention pattern used everywhere else in this codebase — e.g. `coverage/router.py::_get_asset_or_404`). |
| "Segmented/multi-color line chart" | Custom SVG/canvas line renderer | recharts `Line` (default `connectNulls=false`) + `ReferenceLine` | Stock recharts, already the app's only charting library, does exactly this with no new code beyond a data pivot (see Code Examples §4). |
| "Round-trip a DB Decimal safely to JSON" | A bespoke serializer | `round(float(x), N)` before constructing the response dict | The exact idiom every existing trend/snapshot function in this codebase already uses. |

**Key insight:** Every non-obvious piece of business logic this phase needs (exclusion semantics, SLA tier windows, tenant-safe group membership) already has a canonical, tested implementation elsewhere in the v5.0 codebase, written in the last 3 phases (39, 40, 36) specifically so later phases would not re-derive them. The phase's actual net-new code is thin: date-range/window plumbing, JSONB dict intersection, version-boundary detection, and two chart components.

## Common Pitfalls

### Pitfall 1: TREND-03's success criterion is untestable against any real historical data today
**What goes wrong:** A plan that says "verify no false cliff on a real model version change" will find zero real examples — `RISK_MODEL_VERSION = "v1"` (`risk_exposure_service.py:92`) has never been bumped; every `risk_model_version_snapshot` value ever written is `"v1"` [VERIFIED: grepped every occurrence of `RISK_MODEL_VERSION` and `risk_model_version_snapshot` in the repo, plus every existing `DailySnapshot(...)` test fixture in `test_risk_boundary_guard.py` and `test_risk_trend_cutover.py` — none sets a second version string].
**Why it happens:** Phase 33/34 shipped exactly one model version; nothing since has changed it.
**How to avoid:** The plan must include a task to construct a synthetic multi-version `DailySnapshot` fixture for tests (the codebase already has a proven PATTERN for hand-constructing `DailySnapshot` rows with custom `metrics` dicts — see `test_risk_boundary_guard.py:108-114` — just never with a varying `risk_model_version_snapshot`). Do not accept "verified against live version history" as a completion signal; it must be "verified against a synthetic fixture."
**Warning signs:** A verification task that reads "confirm the chart doesn't cliff at a real version boundary" without first seeding one.

### Pitfall 2: Two SLA engines exist; only one is live
**What goes wrong:** Reaching for `app/vulnerabilities/sla_service.py::DEFAULT_SLA_DAYS`/`get_sla_days` (severity-keyed: CRITICAL=7/HIGH=30/MEDIUM=90/LOW=180/INFO=365) because it superficially looks like "the SLA config," when the scheduler's live writer of `Vulnerability.sla_due_at`/`sla_breached` is actually `sla_tier_service.py::run_sla_tier_pass` (risk-tier-keyed: critical=7/high=30/moderate=90, off `risk_exposure_score`).
**Why it happens:** The legacy module's name (`sla_service.py`) sounds more generic/canonical than the newer `sla_tier_service.py`; the day-count numbers even coincidentally match for 3 of 5 tiers, making a wrong substitution easy to miss in a quick read.
**How to avoid:** [VERIFIED: `backend/app/connectors/scheduler.py:317-321` comment: "run_sla_tier_pass now owns sla_due_at + the sla_breached derived mirror... Replaces the flat severity-keyed due-date-backfill... from sla_service.py"] — always resolve aging-bucket boundaries through `sla_tier_service.py`'s functions/constants, not `sla_service.py`'s.
**Warning signs:** A bucket threshold hardcoded as `{CRITICAL: 7, HIGH: 30, MEDIUM: 90, LOW: 180, INFO: 365}` (5 severities) instead of a 3-tier critical/high/moderate scheme, or a threshold that doesn't respect `Tenant.sla_config["tier_policy"]` overrides.

### Pitfall 3: `useUrlState`'s enum-clamp shape doesn't fit a free-form custom date range
**What goes wrong:** `useUrlState<T>(key, allowed: readonly T[], defaultValue)` (`hooks/use-url-state.ts:11`) requires a **fixed allow-list** to clamp against (a deliberate XSS/reflected-param defense — see the hook's own WR-04 comment). `from`/`to` custom dates are not a finite enum, so they cannot be passed through this hook unmodified.
**Why it happens:** The existing `Range` control (7d/30d/90d) is exactly the shape this hook was built for; the phase's new "1y + custom" requirement (D-03) is the first time this idiom needs to carry a non-enum value.
**How to avoid:** Extend the enum-clamped hook for the *preset* selector (`['7d','30d','90d','1y','custom']`), and handle `from`/`to` as separate URL params with their OWN validation (a regex/`Date.parse` format check + client-side `To > From` guard — already precedented in `exception-grant-dialog.tsx`'s `expiryFieldError` pattern), not by trying to shoehorn arbitrary dates through the allow-list hook.
**Warning signs:** A `useUrlState<string>('from', [...], '')` call with an empty or wildcard allow-list (defeats the hook's entire safety purpose).

### Pitfall 4: A single-dataKey line with one inserted null row is a *simpler* but less-tested way to satisfy D-11 than the multi-segment pivot
**What goes wrong:** Two viable recharts implementations exist for "no interpolation across the boundary": (a) pivot into one dataKey per version-segment (Code Examples §4, more code, generalizes cleanly to N boundaries, doesn't touch the x-axis category domain), or (b) keep a single `score` dataKey and insert one synthetic `{date: boundaryDate, score: null}` row between the last old-version point and first new-version point (less code, but adds an extra x-axis category tick that isn't a real snapshot date, and its exact visual gap width/interaction with tooltips is unverified in this codebase).
**Why it happens:** Both are legitimate recharts patterns; the CONTEXT.md/UI-SPEC do not prescribe which.
**How to avoid:** Prefer (a) — it doesn't perturb the x-axis domain and each segment naturally starts/stops at real data. Treat (b) as a fallback only if (a) proves harder to wire into the existing `ChartDataTable`-style sr-only table pattern than expected.
**Warning signs:** An extra x-axis tick appearing at a date with no real snapshot, or a tooltip that fires on a fabricated null point.

### Pitfall 5: Group-scoping D-02 says applies to "every chart" — but aging/burndown have no group filter today
**What goes wrong:** `get_vuln_trends(db, tenant_id, days)` (`trends.py:38`) and any live aging query have no `asset_ids` parameter at all today. D-02 explicitly states changing scope "re-scopes every chart on the page (trend line, aging distribution, burndown)" — so a plan that only group-scopes the trend line (D-05/D-06's explicit focus) and leaves aging/burndown tenant-wide would violate D-02.
**Why it happens:** D-05/D-06/D-07's decision text is entirely about the historical trend line; D-08/D-09's text doesn't mention group-scoping at all, making it easy to read them as tenant-only.
**How to avoid:** Add an optional `asset_ids: list[uuid.UUID] | None = None` filter to the aging and burndown queries (default `None` = tenant-wide, preserving any existing call site), applied as `Vulnerability.asset_id.in_(asset_ids)` when scope=group. This is simpler than the trend line's retroactive-intersection logic because aging/burndown are already live-computed — "current membership" is the only membership that could ever apply, no D-06-style retroactive caveat needed.
**Warning signs:** A plan task that only threads `scope`/`group_id` through the trend-series function and not through the aging/burndown functions.

### Pitfall 6: `func.avg`/`func.sum` over the burndown window can reintroduce the Decimal-string quirk in a brand-new response shape
**What goes wrong:** [Project memory, re-confirmed this session via `Number(v.cvss)`/`Number(r.cvss_v3_score)` call sites in `ticket-drill-content.tsx`, `hero.tsx`, `drill-content.tsx`, `use-top-triage.ts`] — raw SQLAlchemy `Numeric`/`Decimal`-typed aggregate results serialize as JSON strings via FastAPI/Pydantic, not JSON numbers, unless explicitly cast. Values already inside `DailySnapshot.metrics` JSONB (e.g. `avg_risk_exposure_score`) are safe — `capture_daily_snapshot` already does `round(float(x), 1)` before writing them, so they round-trip as native JSON numbers. The risk is specifically in **new** aggregate queries this phase writes directly against `Vulnerability` (e.g., an average net-change-per-week for the burndown tile) if they don't apply the same `float()`+`round()` cast before constructing the response.
**Why it happens:** It's easy to copy `func.avg(...)` from an existing query (e.g. `capture_daily_snapshot`'s own `avg_risk` computation) without also copying the immediately-following float-cast line.
**How to avoid:** Every new aggregate value entering a Pydantic response model must pass through `round(float(x), N) if x is not None else None` before assignment — mirror `get_mttr_trend`'s `round(float(r.avg_days), 1) if r.avg_days else None` exactly.
**Warning signs:** A frontend burndown tile that needs a `Number(...)` coercion wrapper the way `ticket-drill-content.tsx` needs one for `cvss` — if the new endpoint is built correctly, no new `Number()` coercion should be necessary on the frontend.

## Code Examples

### 1. The full existing snapshot shape (what TREND-01/02/03 read from, verbatim)
```python
# Source: backend/app/vulnerabilities/trends.py:367-384 (verified, capture_daily_snapshot)
metrics = {
    "total_vulns": total,
    "open_vulns": open_vulns,
    "critical_open": critical_open,
    "high_open": high_open,
    "remediated": remediated,
    "sla_breached": sla_breached,
    "avg_risk_score": round(float(avg_risk), 1) if avg_risk else 0,
    "total_assets": total_assets,
    "open_tickets": open_tickets,
    "compliance_pct": sla.get("compliance_pct", 100),
    "kev_count": kev_count,
    "avg_risk_exposure_score": round(float(avg_risk_exposure), 1) if avg_risk_exposure else 0,
    "asset_risk_scores": asset_risk_scores,                       # {str(asset_id): int}
    "asset_risk_exposure_scores": asset_risk_exposure_scores,     # {str(asset_id): int}
    "risk_model_version_snapshot": RISK_MODEL_VERSION,            # currently always "v1"
}
```

### 2. The existing function this phase's tenant-scope trend must supersede (raise the LIMIT, drop the flag-gate)
```python
# Source: backend/app/vulnerabilities/trends.py:166-215 (verified) — DO NOT call this
# function as-is for the new Analytics page; its LIMIT(90) and flag-gating both
# contradict D-12/D-13. Shown here because a new function must replace both:
rows = (
    await db.execute(
        select(DailySnapshot.snapshot_date, DailySnapshot.metrics)
        .where(DailySnapshot.tenant_id == tenant_id)
        .order_by(DailySnapshot.snapshot_date.desc())
        .limit(90)   # <- D-13: must become a date-range filter for 1y/custom windows
    )
).all()
metric_key = "avg_risk_exposure_score" if cutover_enabled else "avg_risk_score"  # <- D-12: always avg_risk_exposure_score
```
For a **custom date range**, replace `.order_by(...desc()).limit(90)` with `.where(DailySnapshot.snapshot_date.between(start, end)).order_by(DailySnapshot.snapshot_date.asc())` (no `LIMIT`/no `reversed()` needed) — the "most recent N" shape only fits the preset buttons, not an arbitrary historical window.

### 3. Version-boundary detection (new logic — no existing precedent to copy, first-of-its-kind this phase)
```python
# Sketch — detects boundaries by comparing each snapshot's version-tag to the previous one.
def detect_version_boundaries(rows: list[tuple[date, str | None]]) -> list[dict]:
    """rows: [(snapshot_date, risk_model_version_snapshot), ...] ascending by date."""
    boundaries = []
    prev_version: str | None = None
    for snap_date, version in rows:
        if prev_version is not None and version != prev_version:
            boundaries.append({"date": snap_date.isoformat(), "old_version": prev_version, "new_version": version})
        prev_version = version
    return boundaries
```
Since real data never varies `risk_model_version_snapshot`, `boundaries` will be `[]` for every real tenant today — this function's behavior on multi-version input can only be proven with a synthetic fixture (Pitfall 1).

### 4. Segmented line + reference markers
See Architecture Patterns, Pattern 4 (full code).

### 5. Synthetic multi-version fixture pattern (extend, don't invent)
```python
# Source: backend/tests/test_risk_boundary_guard.py:132-140 (verified) — the existing
# hand-construction pattern for a DailySnapshot row with a custom metrics dict.
# Phase 42's own tests should follow this shape but additionally vary
# risk_model_version_snapshot (which no existing test does):
db_session.add(
    DailySnapshot(
        tenant_id=tenant_a,
        snapshot_date=some_date,
        metrics={
            "avg_risk_exposure_score": 24,
            "risk_model_version_snapshot": "v2",   # <- the never-before-tested axis
        },
        created_at=datetime.now(UTC),
    )
)
```

### 6. Native date input precedent (for the D-03 custom range picker — no new dependency)
```tsx
// Source: frontend/src/components/exceptions/exception-grant-dialog.tsx:61-62,317-323 (verified)
const FIELD_CLASS =
  'w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text placeholder-text-faint focus:border-violet focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
// ...
<input
  id="exception-expires"
  type="date"
  min={minDate}
  max={maxDate}
  value={expiresAt}
  onChange={(e) => setExpiresAt(e.target.value)}
  className={FIELD_CLASS}
/>
```
Note: `components/ui/input.tsx`'s shared `InputProps.type` union is `'text' | 'email' | 'password' | 'url' | 'search' | 'tel'` — it does **not** currently include `'date'`. The UI-SPEC's ".field-input token set" phrase does not correspond to a literal CSS class anywhere in the codebase [VERIFIED: `grep -rn "field-input"` across `frontend/src` returns zero matches] — it is describing this same visual treatment conceptually. Either extend `InputProps.type` additively to include `'date'`, or hand-roll the native `<input type="date">` styled with an equivalent class string, following the exact precedent above.

### 7. Pydantic v2 schema convention for the new `analytics/schemas.py`
```python
# Source: backend/app/coverage/schemas.py:22-33 (verified) — the pattern to follow
from pydantic import BaseModel, ConfigDict

class AnalyticsTrendPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date: str
    avg_risk_exposure_score: float | None   # None = gap (D-06 zero-scored-members case)
    risk_model_version: str | None
```

## State of the Art

| Old Approach (this codebase) | New Approach (this phase) | When Changed | Impact |
|--------------------------------|------------------------------|---------------|--------|
| Dashboard `TrendSection`'s risk series (`get_risk_score_trend`) branches on `Tenant.cutover_risk_exposure_scoring` and caps at 90 rows | Analytics page's series always reads `avg_risk_exposure_score`, decoupled from the flag, unbounded by the 90-row cap (date-range-filtered instead) | This phase (D-12/D-13) | The two pages will intentionally show *different* series for a tenant that hasn't cut over yet — documented as a deliberate divergence, not a bug, in both `42-CONTEXT.md` and this research. |
| `TrendChart` (existing) = stacked severity **bar** chart | `RiskTrendChart` (new) = segmented **line** chart with reference markers | This phase | First line-chart primitive in the app; first use of `ReferenceLine`/`connectNulls` semantics anywhere in this codebase. |
| SLA aging has no dedicated visualization | `BacklogAgingChart` reuses `SEVERITY_FILLS` from the bar-chart precedent, bucketed by SLA tier instead of by day | This phase | First stacked-bar-by-derived-bucket (rather than by-date) chart in the app. |

**Deprecated/outdated:** Nothing in the stack itself is deprecated; the only "old approach" being superseded is the flag-gated/90-row-capped read path inside `get_risk_score_trend`, and only for this NEW page — the dashboard's own call to that function is explicitly left untouched (D-15).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A brand-new `backend/app/analytics/` top-level module (mirroring `coverage/`) is the right structural home, rather than adding functions directly inside `backend/app/vulnerabilities/trends.py` | Architecture Patterns, Standard Stack | Low — this is strongly evidenced (D-01's own "mirroring Phase 41's Coverage precedent" text + the actual Phase 41 file layout), but the CONTEXT.md canonical_refs describe the phase as extending/sitting "beside trends.py" without naming an exact module path, so this is the research's synthesis, not a locked decision. If wrong, the plan would instead add functions to `trends.py` itself and a lighter router addition — same data logic, different file organization. |
| A2 | ONE combined `/api/v1/analytics/...` endpoint (not 2-3 separate ones) is the intended shape | Architecture Patterns, Standard Stack | Medium — inferred from the UI-SPEC's repeated "single compute pass (D-13)" language for shared loading/error state, not stated as a locked decision (D-15 explicitly leaves "endpoint(s)" and exact shape as discretion). If wrong, the frontend would need 3 independent query hooks + 3 independent loading/error branches instead of 1, and the UI-SPEC's shared-skeleton language would need reinterpretation. |
| A3 | Aging and burndown queries need a NEW optional `asset_ids` scoping parameter (extending `get_vuln_trends` and a new aging query) to satisfy D-02's "every chart" re-scoping | Common Pitfalls #5 | Medium — D-02's text explicitly names all 3 charts, but D-08/D-09's own text never mentions group-scoping, so it's possible the original intent was tenant-only aging/burndown with only the trend line group-scoped (in which case D-02's "every chart" wording would be imprecise). Flagged as an Open Question below — recommend confirming with the user/planner rather than silently picking one reading. |
| A4 | The multi-dataKey-per-version-segment pivot (recharts Pattern 4) is preferable to a single-dataKey-with-inserted-null-row approach for D-11 | Architecture Patterns Pattern 4, Common Pitfalls #4 | Low — both are standard, documented recharts patterns; this is an implementation-style recommendation, not a functional-correctness claim. Either satisfies D-11's "no interpolation" requirement. |
| A5 | "Recently breached" vs. "long overdue" (the 2nd/3rd SLA-tier aging buckets) should split on a percentage of the finding's own tier window (mirroring `sla_tier_service.py`'s existing `approaching_pct`-of-`tier_days` philosophy) rather than a fixed day count | Architecture Patterns Pattern 5 | Low — CONTEXT.md explicitly leaves the exact boundary as Claude's discretion; this is offered as a consistent-with-existing-code recommendation, not a verified requirement. |

**If this table is empty:** N/A — see rows above. All backend data-model and existing-code claims in this document are `[VERIFIED]` by direct file reads or `[CITED]` from CONTEXT.md/UI-SPEC.md; the assumptions above are specifically the synthesis/recommendation layer where this research went beyond verbatim-verified fact to propose an implementation shape.

## Open Questions

1. **Does D-02's "every chart" re-scoping literally require group-scoping the aging and burndown queries, or only the trend line?**
   - What we know: D-02 (TREND-01 section) explicitly lists "trend line, aging distribution, burndown" as all re-scoped by the single dropdown. D-08/D-09 (TREND-02 section)'s own decision text never mentions group-scoping and reads as tenant-wide-only when read in isolation.
   - What's unclear: Whether this is an intentional requirement carried by D-02 that D-08/D-09 simply didn't restate, or whether D-02's "every chart" was written before D-08/D-09 were finalized and is slightly over-broad.
   - Recommendation: Treat D-02 as authoritative (group-scope all three) per Common Pitfalls #5 — it is the more literal reading and the added `asset_ids: list[uuid.UUID] | None = None` parameter is a small, additive, low-risk change either way. Flag for a quick confirm during planning if the planner wants to descope it.

2. **Should the aging chart trust the nightly-computed `Vulnerability.sla_due_at`/`sla_breached` columns, or recompute SLA state live via `resolve_state_for_vuln` at read time?**
   - What we know: `sla_due_at`/`sla_breached` are refreshed once per scheduler tick (effectively daily, alongside the snapshot capture) by `run_sla_tier_pass`, which already applies the Phase 39 exception-lapse-seconds adjustment. `resolve_state_for_vuln` (the underlying per-finding function) could be called again live for perfect freshness, but that means re-running the same `lapsed_exception_seconds` computation per open finding on every Analytics page load — a heavier read than reading the already-materialized columns.
   - What's unclear: Whether "live compute on-read" (D-13) is meant to apply to the SLA-state derivation itself, or only to the aggregation/bucketing built on top of already-fresh columns (matching how `get_sla_metrics`/`get_vuln_trends` already read `sla_due_at`/`sla_breached` directly rather than recomputing).
   - Recommendation: Read the stored `sla_due_at`/`sla_breached` columns directly (consistent with every existing SLA-reading function in this codebase — none of them re-invoke `resolve_state_for_vuln`); D-13's "live compute" is about the aggregation being uncached, not about re-deriving already-persisted per-row state.

3. **Exact SLA-tier aging bucket day-thresholds and the % of backlog overdue tile** — explicitly Claude's discretion per CONTEXT.md; no further research needed, just a planning-time decision following `copy-voice.md` and Pattern 5's percentage-of-tier-window recommendation above.

4. **Exact minimum-history threshold for the D-04 empty state** — explicitly Claude's discretion per CONTEXT.md. Recommend gating on snapshot ROW COUNT in the window (not on a specific day-count target), per Anti-Patterns above.

## Environment Availability

All dependencies this phase touches are already running and verified in this session — no external service, package, or infrastructure gap.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | `daily_snapshots`/`vulnerabilities` queries | ✓ [VERIFIED: `docker compose ps`] | postgres:16-alpine, container healthy | — |
| Redis | Session state (unrelated to this phase's reads, already running) | ✓ [VERIFIED: `docker compose ps`] | redis:7-alpine, container healthy | — |
| Backend container | FastAPI app | ✓ [VERIFIED: `docker compose ps`] | healthy, 3 days up | — |
| Frontend container | Next.js app | ✓ [VERIFIED: `docker compose ps`] | up, 3 days | — |
| Node.js / npm | Frontend build/test | ✓ [VERIFIED] | v26.5.0 / 12.0.1 | — |
| uv (Python package manager) | Backend dev workflow | ✓ [VERIFIED] | 0.12.0 | — |
| recharts | Chart rendering | ✓ [VERIFIED: package.json] | ^2.12.0, already installed | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — zero new dependencies this phase.

## Validation Architecture

*(`.planning/config.json` has no `workflow.nyquist_validation` key — treated as enabled per policy.)*

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.3+ / pytest-asyncio (`asyncio_mode = "auto"`) [VERIFIED: `backend/pyproject.toml:7,30-31,74-75`] |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Frontend framework | vitest ^4.1.6 + vitest-axe [VERIFIED: `frontend/package.json:10,73-74`] |
| Frontend config | `npm test` → `vitest` |
| Quick run command (backend, per new test file — project memory: run per-file, not whole `tests/` dir) | `cd backend && ENCRYPTION_KEY=... JWT_SECRET_KEY=... uv run pytest tests/test_analytics.py -x` |
| Quick run command (frontend) | `cd frontend && npx vitest run src/app/\(authed\)/dashboard/analytics/page.test.tsx` |
| Full suite command | backend: `uv run pytest tests/ -x` (per-file env vars still required); frontend: `npm test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TREND-01 | Tenant-scope trend series reads `avg_risk_exposure_score` unbounded by the 90-row cap, decoupled from cutover flag | unit | `pytest tests/test_analytics.py::test_tenant_trend_ignores_cutover_flag -x` | ❌ Wave 0 |
| TREND-01 | Group-scope trend intersects current membership against historical per-asset dicts (D-05/D-06) | unit | `pytest tests/test_analytics.py::test_group_trend_uses_current_membership_retroactively -x` | ❌ Wave 0 |
| TREND-02 | Aging distribution excludes SUPPRESSED/FALSE_POSITIVE/active-exception findings | unit | `pytest tests/test_analytics.py::test_aging_honors_exclusion_predicate -x` | ❌ Wave 0 |
| TREND-02 | Aging buckets align to Phase 36 tier windows (critical/high/moderate), not the legacy severity engine | unit | `pytest tests/test_analytics.py::test_aging_buckets_use_tier_policy -x` | ❌ Wave 0 |
| TREND-02 | Burndown produces net velocity + projected days-to-zero, or "growing" branch when net-positive | unit | `pytest tests/test_analytics.py::test_burndown_projection_branches -x` | ❌ Wave 0 |
| TREND-03 | A synthetic version-boundary fixture (2 distinct `risk_model_version_snapshot` values) is detected and segments the series | unit | `pytest tests/test_analytics.py::test_version_boundary_detected_and_segmented -x` | ❌ Wave 0 (needs the new synthetic-fixture pattern, Pitfall 1) |
| TREND-03 | A tenant with only `"v1"` ever (today's real-world case) produces zero boundaries, one continuous segment | unit | `pytest tests/test_analytics.py::test_no_boundary_when_single_version -x` | ❌ Wave 0 |
| TREND-01/02/03 (frontend) | Analytics page renders all 5 UI-Considerations state branches (empty/loading/error/populated/partial) per `42-UI-SPEC.md` | component | `vitest run src/app/(authed)/dashboard/analytics/page.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** targeted `pytest tests/test_analytics.py::<test_name> -x` / `vitest run <file>`
- **Per wave merge:** full `tests/test_analytics.py` + `page.test.tsx` file
- **Phase gate:** full backend + frontend suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_analytics.py` — new file, covers TREND-01/02/03 backend service functions; reuses the existing `db_session`/`tenant_a` fixtures already established in `test_risk_boundary_guard.py`/`test_risk_trend_cutover.py` — no new shared-fixture infrastructure needed.
- [ ] `frontend/src/app/(authed)/dashboard/analytics/page.test.tsx` — new file, mirrors `dashboard/coverage/page.test.tsx`'s state-branch-coverage shape.
- [ ] A synthetic multi-`risk_model_version_snapshot` fixture helper (Pitfall 1) — no existing test constructs one; needed before TREND-03's boundary-rendering behavior can be verified at all.
- [ ] Framework install: none — pytest/vitest both already configured and used by 40+ existing test files.

## Security Domain

*(`security_enforcement` absent from `.planning/config.json` — treated as enabled per policy.)*

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (unchanged) | Existing session auth; this phase adds no auth surface. |
| V3 Session Management | No (unchanged) | Existing Redis-backed session; untouched. |
| V4 Access Control | **Yes** | `require_viewer` RBAC dependency on every new GET route [VERIFIED pattern: `coverage/router.py`, `vulnerabilities/router.py:190`]; tenant-scoping on every query (`tenant_id ==` in every WHERE clause); group-scope IDOR guard via `groups_service.list_members` returning `None` for a cross-tenant `group_id` → 404 (never a fetch-then-403), mirroring `coverage/router.py::_get_asset_or_404`'s explicit T-41-02 precedent. |
| V5 Input Validation | **Yes** | `scope`/`window` query params validated against a fixed allow-list server-side (mirror `days: int = Query(30, ge=7, le=365)`); custom `from`/`to` dates validated as real dates + `to > from` both client- and server-side; a maximum custom-range span should be enforced server-side (mirroring the existing `le=365` cap) to bound query cost — an unbounded custom range (e.g. 50 years) over `daily_snapshots` is cheap (one JSONB table, tenant-scoped, at most one row/day) but should still be capped defensively rather than left unbounded. |
| V6 Cryptography | No (unchanged) | No new secrets, keys, or encrypted fields. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR via `group_id` scope param (reading another tenant's `AssetGroup`) | Information Disclosure / Elevation of Privilege | Tenant-scoped fetch that 404s on mismatch (`groups_service.list_members`), never a fetch-then-authorize-in-Python pattern. |
| Reflected value via URL-controlled `scope`/`window` params rendering into the page | Tampering | `useUrlState`'s existing allow-list clamp (already defends the app's other range controls); extend, don't bypass, for the new preset enum. Free-text `from`/`to` params must be validated as ISO date strings before use, never interpolated into any query string or rendered unescaped. |
| Unbounded custom date range causing an expensive scan | Denial of Service (minor — data volume here is small) | Server-side cap on the custom range span, mirroring the existing `Query(..., le=365)` idiom on the legacy `/trends` endpoint. |
| Cross-tenant data bleed via a missing `tenant_id` filter in a new aggregation query | Information Disclosure | Every new query must filter `DailySnapshot.tenant_id == tenant_id` / `Vulnerability.tenant_id == tenant_id`, matching the V4-access-control discipline already enforced everywhere else in this codebase (explicit test comments throughout the v4.0/v5.0 test suite call this out as a required check, e.g. `risk_exposure_service.py`'s own docstring: "Every query filters tenant_id... a bulk-fetch across tenants would leak cross-tenant... rows"). |

## Sources

### Primary (HIGH confidence — direct file reads this session)
- `backend/app/vulnerabilities/trends.py` — `DailySnapshot` model, `get_vuln_trends`, `get_mttr_trend`, `get_risk_score_trend`, `get_all_trends`, `capture_daily_snapshot`, `capture_all_snapshots`
- `backend/app/vulnerabilities/risk_exposure_service.py` — `RISK_MODEL_VERSION = "v1"`, full scoring formula (context, not directly consumed by Phase 42)
- `backend/app/vulnerabilities/risk_backfill_service.py` — confirms `RISK_MODEL_VERSION` is the sole version-drift detection point
- `backend/app/vulnerabilities/models.py` — `Vulnerability`, `VulnStatus`, `Severity` enums; `first_detected_at`/`remediated_at`/`sla_due_at`/`sla_breached`/`risk_exposure_score`/`risk_model_version` columns
- `backend/app/vulnerabilities/sla_tier_service.py` — `DEFAULT_TIER_POLICY`, `tier_for_score`, `severity_to_tier`, `get_tier_policy`, `compute_sla_state`, `resolve_state_for_vuln`
- `backend/app/vulnerabilities/sla_service.py` — legacy `DEFAULT_SLA_DAYS`/`get_sla_days`/`get_sla_metrics` (confirmed superseded as live SLA-column writer)
- `backend/app/vulnerabilities/router.py` — `GET /trends` (require_viewer, days 7-365), `/sla/backfill`, `/sla/recalculate`
- `backend/app/connectors/scheduler.py` — confirmed `run_sla_tier_pass` is the live `sla_due_at`/`sla_breached` writer; confirmed `capture_all_snapshots` daily cadence (gated on the 24h ticket-sync timer)
- `backend/app/assets/models.py` — `Asset`, `AssetGroup`, `AssetGroupMember`, `AssetGroupExposureOverride`
- `backend/app/assets/groups_service.py` / `groups_router.py` — `list_members` (tenant-scoped, 404-safe)
- `backend/app/assets/risk_score.py` — `RISK_SCORE_TIER_CRITICAL=80/HIGH=50/MEDIUM=20`
- `backend/app/exceptions/service.py` — `active_exception_subquery`
- `backend/app/coverage/{router,service,schemas}.py` — the structural precedent for the new module
- `backend/app/main.py` — router registration idiom
- `backend/app/tenants/models.py` — `cutover_risk_exposure_scoring`
- `backend/tests/test_risk_boundary_guard.py`, `test_risk_trend_cutover.py` — existing `DailySnapshot` fixture patterns; confirmed no existing test varies `risk_model_version_snapshot`
- `frontend/src/components/dashboard/trend-section.tsx`, `components/ui/trend-chart.tsx`, `trend-chart-skeleton.tsx` — existing chart primitives (bar chart, `SEVERITY_FILLS`, `RangeToggle`)
- `frontend/src/lib/queries/use-trends.ts`, `keys.ts`, `use-asset-groups.ts` — query-hook and cache-key conventions
- `frontend/src/components/campaigns/campaign-burndown-card.tsx` — burndown-visual precedent
- `frontend/src/components/shell/nav-items.ts` — nav entry structure, Coverage precedent
- `frontend/src/hooks/use-url-state.ts` — enum-clamp URL state hook
- `frontend/src/components/states/{index.ts,empty-state.tsx,partial-failure-banner.tsx}` — state-primitive contracts
- `frontend/src/components/ui/input.tsx`, `frontend/src/components/exceptions/exception-grant-dialog.tsx` — native date-input precedent
- `frontend/src/app/(authed)/dashboard/coverage/page.tsx` — page-composition pattern
- `frontend/package.json`, `backend/pyproject.toml` — verified installed versions
- `.planning/phases/39-exception-risk-acceptance-workflow/39-CONTEXT.md`, `.planning/phases/40-proactive-alerting-digests/40-CONTEXT.md`, `.planning/phases/41-coverage-blind-spot-detection/41-CONTEXT.md` — cross-phase precedent decisions
- `.planning/phases/42-risk-trend-analytics-burndown/42-CONTEXT.md`, `42-UI-SPEC.md` — locked decisions for this phase
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — requirement text, phase dependency map
- `docker compose ps`, `node --version`, `npm --version`, `uv --version` — live environment probe, this session

### Secondary (MEDIUM confidence — WebSearch, verified against recharts' own docs/GitHub)
- [ReferenceLine API](https://recharts.github.io/en-US/api/ReferenceLine/) — label/position/styling options
- [LineChart with ReferenceLine example](https://recharts.github.io/en-US/examples/LineChartWithReferenceLines/) — multiple reference lines on one chart
- [Chart break (leave gap) when data is null · Issue #702 · recharts/recharts](https://github.com/recharts/recharts/issues/702) — confirms default gap-at-null behavior
- [Exploring Recharts: multiple ReferenceLine segments — Gaurav Gupta, Medium](https://gaurav5430.medium.com/exploring-recharts-multiple-referenceline-segments-1856b5b07111)

### Tertiary (LOW confidence)
- None — every claim in this document is either a direct file-read/tool-verified fact or explicitly logged in the Assumptions Log above.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; every version number read directly from lockfiles/config, not training-data recall.
- Architecture (backend data model, existing endpoints, RBAC/tenant-scoping patterns): HIGH — every claim traced to an exact file+line read this session.
- Architecture (new module shape, single-endpoint recommendation, group-scoping-of-aging/burndown): MEDIUM — strongly evidenced synthesis, explicitly logged in Assumptions Log rather than presented as locked fact.
- Pitfalls: HIGH for the version-boundary-untestability and two-SLA-engines findings (both directly verified by grep/read); MEDIUM for the recharts implementation-shape tradeoff (verified via docs/search, not yet exercised in this specific codebase).
- Security: HIGH — this phase adds no new authn/crypto surface; the RBAC/tenant-scoping/IDOR patterns it must follow are all directly copied from verified existing code.

**Research date:** 2026-08-21
**Valid until:** 2026-09-20 (30 days — stable internal codebase; re-verify sooner only if Phase 43 or another concurrent phase touches `trends.py`, `sla_tier_service.py`, or `RISK_MODEL_VERSION` before this phase executes)
