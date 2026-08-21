# Phase 42: Risk Trend Analytics & Burndown - Context

**Gathered:** 2026-08-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A tenant can see whether its risk posture is actually improving **over time** — and how fast its backlog is **burning down** — instead of only a today snapshot. Three deliverables (TREND-01..03):

1. **TREND-01 — trend lines:** tenant / team / asset-group risk-exposure trend lines over a selectable time window.
2. **TREND-02 — aging & burndown:** open findings by age × severity (a distribution) plus a backlog burndown rate (a velocity).
3. **TREND-03 — version-boundary aware:** trends annotate risk-model version boundaries and never blend across them — a v4.0 model-version change must never render as a false cliff or false improvement.

This is a **how-to-implement** boundary — no new capabilities beyond TREND-01..03. The phase is **mostly read-side analytics over data GetVul already captures**: the v4.0 Phase 34 `daily_snapshots` table (per-day tenant metrics + per-asset score dicts + `risk_model_version_snapshot`) plus live queries over `Vulnerability` timestamps, surfaced on a new Analytics page. It is **not** new ingestion, a new scoring model, or a new capture pipeline.

**Explicitly NOT this phase:**
- Executive/board **PDF export**, role-scoped dashboards, and framework-control **compliance mapping** — that is Phase 43 (RPT-01..03), which *consumes* this phase's data.
- **MTTR-by-tier** as a first-class deliverable — MTTR trend already exists (`get_mttr_trend`) and Phase 36/43 own the tier breakdown; do not expand it here (a plain MTTR line may appear as supporting context only, not a new build-out).
- Re-deriving the v4.0 risk-exposure model, the EPSS/KEV feeds, or the daily-snapshot capture job (consume, never re-derive).
- A **membership-history / point-in-time-group audit** table (D-05 uses current membership retroactively).
- **Materialized/pre-aggregated** trend rollups (D-11 computes live on-read; materialize later only if a large tenant proves a need).
- **Per-group access control** — none exists today; any tenant user can scope to any group (D-10).

</domain>

<decisions>
## Implementation Decisions

### TREND-01 — View placement, scope & window
- **D-01:** **New dedicated top-level "Analytics" nav page** (sidebar entry, mirroring Phase 41's Coverage precedent), NOT an expansion of the existing dashboard `TrendSection`. The dashboard `TrendSection` stays as-is (a compact at-a-glance strip); the Analytics page is the deep view with room for trend lines + aging + burndown on one focused screen. Matches ROADMAP "UI hint: yes" and the distinct-analyst-workflow pattern.
- **D-02:** **Single scope dropdown as the primary selector** — "All (tenant)" by default plus each `AssetGroup`. Changing it re-scopes **every** chart on the page (trend line, aging distribution, burndown) to one mental model. Chosen over overlaid multi-series lines (busier; aging/burndown still need a single scope anyway).
- **D-03:** **Selectable window = 7d / 30d / 90d / 1y preset buttons PLUS a custom start/end date-range picker.** Default 30d. The rendered series is naturally bounded by however much snapshot history exists. Reuses the existing `Range` control idiom (`trend-section.tsx` uses `useUrlState` over `['7d','30d','90d']`), extended with 1y + a custom range. — **Reversibility:** reversible — range set is a frontend control + a query param.
- **D-04:** **Guided empty state below a minimum-history threshold.** When a scope (young tenant, or a just-created group) has fewer than a small threshold of snapshot data points, render a canonical `EmptyState` ("Trends appear after a few days of history — check back soon") instead of a misleading 1–2-point line. Mirrors Phase 41 D-11's honesty rule. Exact threshold + copy is planner discretion (follow `copy-voice.md`).

### TREND-01 — Team/asset-group series derivation
- **D-05:** **Group trend lines derived retroactively, on-read, from the per-asset score dicts already stored in each snapshot.** Each `DailySnapshot.metrics` already carries `asset_risk_scores` and `asset_risk_exposure_scores` (asset_id → score). A group series is computed by intersecting those historical dicts with the group's **current** `AssetGroupMember` set — so group trends work immediately over ALL existing history, with **no schema change and no forward-only wait**. Chosen over adding new per-group snapshot rows (no history until it accrues; adds write-path + migration for data the per-asset dicts already contain). The per-asset dicts were captured (Phase 34 RISK-10) for exactly this.
- **D-06:** **Group history uses CURRENT membership applied retroactively across the whole window** (recompute each past point over exactly today's members), not point-in-time membership. Answers "how has *this team's current footprint* trended." No membership-history table exists and building one is out of scope. Caption the semantic on the chart so it's not misread. Point-in-time membership rejected (needs a new audit/history capture + migration heavier than this phase warrants).
- **D-07:** **The plotted aggregate is the AVERAGE risk-exposure score across the scope's assets** — exactly what the tenant snapshot's `avg_risk_exposure_score` already stores. Gives consistent tenant↔group semantics and comparability across differently-sized groups. Sum/total-exposure rejected (big groups dwarf small ones; not what the snapshot stores). Not toggleable this phase.

### TREND-02 — Backlog aging & burndown
- **D-08:** **"Open findings by age × severity" = a point-in-time stacked aging chart** — current open findings bucketed by age (since `first_detected_at`) and stacked/colored by severity, computed live from current open vulns. Answers "how much of my backlog is old AND critical *right now*." Chosen over trending each age band over time (needs age-at-each-past-date the snapshots don't store; the point-in-time distribution already conveys aging). Age buckets are **SLA-tier aligned** — mirror the existing per-severity SLA windows (within-SLA / recently-breached / long-overdue) so aging reads directly against the tenant's own remediation commitments (reuse Phase 36 SLA config), rather than arbitrary absolute day counts. Note: SLA-aligned buckets are severity-relative by construction.
- **D-09:** **Burndown rate = net flow + a projected days-to-zero.** From the daily new-vs-resolved series (already computed by `get_vuln_trends` from `first_detected_at` / `remediated_at`), show the net burndown velocity (avg resolved − new per period) and a projected "days to clear the backlog at current rate" (or an explicit "backlog growing" when net-positive). Chosen over a bare open-count slope (which doesn't separate inflow from remediation velocity or project a horizon).
- **D-10 (exclusions):** **Aging + burndown honor the Phase 39/40 exclusion predicate** — open-backlog counts exclude `status IN (SUPPRESSED, FALSE_POSITIVE)` and findings under an active exception (EXC-02), reusing the Phase 39 predicate **verbatim** (do not re-derive). Same "what's genuinely open" definition Phase 40 digests use, so burndown reflects the tenant's real obligations. Counting all-open rejected (diverges from the rest of v5.0; makes burndown look worse than reality).

### TREND-03 — Version-boundary awareness & which score
- **D-11 (boundary rendering):** **Segment the line at each version-change date (no interpolation across the boundary) AND drop a labeled vertical reference marker** (e.g. "risk model v4.1 → v4.2"). A boundary is detectable as the date `DailySnapshot.metrics["risk_model_version_snapshot"]` changes value. This makes a model change visibly NOT a real risk cliff/improvement — directly satisfying SC3. Marker-only-on-a-continuous-line rejected (the eye still reads the cross-boundary jump as a real trend, weakening "never produces a false cliff").
- **D-12 (which score):** **Always plot the versioned risk-exposure score (`avg_risk_exposure_score` / the RISK-01..10 model), decoupled from the tenant's `cutover_risk_exposure_scoring` flag.** Version-boundary awareness (TREND-03) only makes sense for the *versioned* model; the legacy `risk_score` piecewise curve has no meaningful `risk_model_version` boundaries. Because Phase 34 RISK-10 **dual-writes** the exposure metrics unconditionally, the data exists for every tenant regardless of the consumer-cutover flag. This intentionally **diverges** from the existing dashboard `/trends` behavior (which honors the flag, `get_risk_score_trend`) — the new Analytics page is the versioned-model view. — **Reversibility:** reversible — a metric-key selection in the new analytics service; no data or contract change.

### Compute, RBAC & backend shape
- **D-13 (compute):** **Live compute on-read**, tenant-bounded, matching Phase 41 D-10 and the existing `/trends`. Series/aging/burndown are computed per request from `daily_snapshots` + live vuln queries. Raise the current 90-row snapshot `LIMIT` (in `get_risk_score_trend`) to cover the 1y/custom windows. Research confirms cost; materialize only if a large tenant demonstrates a real need. Cache/materialize-now rejected as premature infra. — **Reversibility:** reversible — pure read-side service; can be cached/materialized later without contract change.
- **D-14 (RBAC):** **Viewer+ (any authenticated tenant user), any group.** Match the existing `/trends` endpoint (`require_viewer`); read-only analytics over data the user can already see elsewhere. No per-group access control (none exists today). Analyst+ gating rejected (diverges from the viewer-readable `/trends` precedent).
- **D-15 (endpoints):** **New `/analytics` endpoint(s)** taking scope + range/date params, leaving the existing `GET /trends` untouched for the dashboard `TrendSection`. Keeps the dense new-page payload from bloating the dashboard's compact call. Extending `/trends` rejected (couples the lightweight dashboard call to the heavier analytics payload).
- **D-16 (Phase 43 hand-off):** **Shape the compute as a reusable service layer** — service functions (like `trends.py`'s `get_*` functions) that BOTH the new HTTP route AND Phase 43's PDF/report generator can call directly, with no HTTP round-trip for reporting. Phase 43 (RPT-01) explicitly depends on this trend+burndown data; a small discipline now saves a Phase-43 extraction later. Endpoint-only rejected (Phase 43 would have to extract the logic anyway).

### Claude's Discretion
- Exact minimum-history threshold + empty-state copy (D-04) — follow `copy-voice.md`.
- Exact SLA-tier bucket boundaries/labels for the aging chart (D-08) and whether a headline "% of backlog overdue" tile accompanies it.
- Exact burndown metric presentation — number, sparkline, or "days-to-zero" tile (D-09).
- Whether a plain MTTR line appears as supporting context on the page (reusing `get_mttr_trend`) — allowed but not required; not a new build-out.
- Exact `/analytics` route naming, param shape, and response schema (D-15); how the reusable service functions are decomposed (D-16).
- Whether the tenant "All" series reads the snapshot's stored `avg_risk_exposure_score` directly vs. re-aggregating the per-asset dict (both should agree; direct read is cheaper).
- Chart library reuse — the existing `TrendChart` primitive (recharts, dynamic-imported) vs. an extension for segmented lines + annotations (D-11 may need a reference-line/segment capability recharts supports).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 42: Risk Trend Analytics & Burndown" — goal, 3 success criteria, dependencies.
- `.planning/REQUIREMENTS.md` — TREND-01, TREND-02, TREND-03 (lines ~70–72; dependency map ~118–120: all three depend on the v4.0 Phase 34 recompute/score-history, already shipped).

### The historical data source (the whole phase reads from here)
- `backend/app/vulnerabilities/trends.py` — **the core asset.** `DailySnapshot` model (`daily_snapshots` table: `tenant_id`, `snapshot_date`, `metrics` JSONB), `capture_daily_snapshot` (writes per-day metrics incl. `avg_risk_score`, `avg_risk_exposure_score`, `open_vulns`, `critical_open`, `high_open`, `remediated`, `sla_breached`, per-asset `asset_risk_scores` / `asset_risk_exposure_scores` dicts, and `risk_model_version_snapshot`), and the existing read functions `get_vuln_trends` (live new/resolved/net by day + severity), `get_mttr_trend`, `get_risk_score_trend` (flag-gated primary series — the behavior D-12 intentionally diverges from), `get_all_trends`.
- `backend/app/vulnerabilities/router.py` §L187 — existing `GET /trends` (`require_viewer`, `days` 7–365) consumed by the dashboard; the RBAC/param precedent for the new `/analytics` endpoints (D-14/D-15).
- `backend/app/connectors/scheduler.py` — where `capture_all_snapshots` is invoked daily (confirm cadence; the phase must not touch the capture job).

### Risk model version & score fields (TREND-03)
- `backend/app/vulnerabilities/risk_exposure_service.py` — `RISK_MODEL_VERSION` constant stamped into each snapshot (`risk_model_version_snapshot`); the value D-11 detects boundaries on.
- `backend/app/assets/models.py` §L71 — `Asset.risk_model_version`, `Asset.risk_score` (legacy), `Asset.risk_exposure_score` (versioned); `AssetGroup` (§L141) + `AssetGroupMember` (§L155) join table for D-05/D-06 group scoping.
- `backend/app/tenants/models.py` — `Tenant.cutover_risk_exposure_scoring` flag (the consumer-cutover flag D-12 decouples the Analytics page from).

### Backlog aging, burndown & exclusions (TREND-02)
- `backend/app/vulnerabilities/models.py` — `first_detected_at`, `remediated_at`, `status`, `severity`, `sla_breached`, `sla_due_at` (aging/burndown source columns).
- Phase 36 SLA config + `backend/app/vulnerabilities/sla_tier_service.py` / `sla_service.py::get_sla_metrics` — the per-severity SLA windows the aging buckets align to (D-08).
- `.planning/phases/39-exception-risk-acceptance-workflow/39-CONTEXT.md` — the exception exclusion predicate (`status IN (SUPPRESSED, FALSE_POSITIVE) OR active exception`) reused verbatim (D-10).
- `.planning/phases/40-proactive-alerting-digests/40-CONTEXT.md` §D-20 — precedent for applying that exclusion predicate to a derived backlog view.

### Precedent (mirror these patterns)
- `.planning/phases/41-coverage-blind-spot-detection/41-CONTEXT.md` — new top-level nav page (D-03 there), live-compute-on-read (D-10 there), guided honest empty state (D-11 there) — all mirrored by D-01/D-13/D-04 here.

### Frontend
- `frontend/src/components/dashboard/trend-section.tsx` — existing trend section (range control via `useUrlState`, `PartialFailureBanner` on error, dynamic-imported `TrendChart`); the closest analog + the `Range` idiom D-03 extends.
- `frontend/src/components/ui/trend-chart.tsx` + `trend-chart-skeleton.tsx` — the recharts `TrendChart` primitive (may need a segmented-line/reference-line extension for D-11).
- `frontend/src/lib/queries/use-trends.ts` + `frontend/src/lib/queries/keys.ts` — TanStack query hook + key namespace pattern for the new analytics queries.
- `frontend/src/components/campaigns/campaign-burndown-card.tsx` + `RiskRing` — existing burndown-visual precedent (Phase 38 CAMP-03) to reference for D-09 presentation.
- `.claude/skills/sketch-findings-getvul/` — sunset design system; `references/state-patterns.md` (mandatory empty state, D-04), `references/visual-language.md` (severity colors for aging, SLA visual language), `references/page-layouts.md` (new-page layout), `references/copy-voice.md`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`daily_snapshots` + `capture_daily_snapshot`** (`trends.py`): the entire historical substrate. Per-day tenant metrics AND per-asset score dicts AND `risk_model_version_snapshot` already captured — TREND-01/03 read this; no new capture work.
- **`get_vuln_trends` / `get_mttr_trend`** (`trends.py`): live new/resolved/net-by-day + severity + weekly MTTR — directly feed the burndown-rate compute (D-09) and any supporting MTTR line.
- **`AssetGroup` / `AssetGroupMember`** (`assets/models.py`): the current-membership set D-05/D-06 intersect the per-asset snapshot dicts against for group scoping.
- **`GET /trends` + `require_viewer`** (`router.py`): the RBAC + `days`-param precedent the new `/analytics` endpoints follow (D-14/D-15).
- **Phase 39 exclusion predicate** + **Phase 36 SLA windows**: reused verbatim for backlog exclusions (D-10) and SLA-aligned aging buckets (D-08).
- **Frontend**: `TrendChart` primitive, `TrendSection` range idiom, `use-trends` hook, `campaign-burndown-card`/`RiskRing`, canonical `EmptyState`/`PartialFailureBanner` state primitives compose the entire Analytics page.

### Established Patterns
- **Live read-side compute over tenant-bounded data** (Phase 41 D-10, existing list/facet/trend endpoints) — D-13.
- **New top-level nav page for a distinct analyst workflow** (Phase 41 Coverage) — D-01.
- **Reusable service functions callable by both HTTP route and other services** (`trends.py` `get_*`) — D-16, for Phase 43 reuse.
- **`avg_risk_exposure_score` dual-write unconditional** (Phase 34 RISK-10) — the reason D-12 can plot the versioned score for every tenant regardless of cutover flag.

### Integration Points
- New "Analytics" sidebar nav entry + top-level page/route (D-01).
- New `/analytics` read endpoint(s): scoped trend series + point-in-time aging + burndown, `require_viewer`, scope + range/date params (D-13/D-14/D-15).
- New reusable analytics **service layer** (extends/sits beside `trends.py`) computing scoped series (tenant + per-group), aging distribution, burndown rate, and version-boundary segmentation — callable by Phase 43 (D-16).
- Raise the 90-row snapshot `LIMIT` in the read path to honor 1y/custom windows (D-13).

</code_context>

<specifics>
## Specific Ideas

- The value is answering "is my risk posture *actually* improving, and how fast is the backlog clearing" — a trajectory, not a snapshot. The version-boundary rule (D-11/D-12) exists so a model upgrade never masquerades as real progress or regression.
- "Team/asset-group" trends work retroactively on day one because the per-asset score dicts were already banked in every historical snapshot (D-05) — no waiting for new capture.
- Aging is deliberately framed against the tenant's own SLA commitments (D-08), not arbitrary day counts, so "old" means "overdue relative to what we promised for that severity."
- The Analytics page is intentionally the *versioned-model* view (D-12), distinct from the flag-gated dashboard `/trends` — this is a deliberate divergence, not an inconsistency to reconcile.

</specifics>

<deferred>
## Deferred Ideas

- **Materialized/pre-aggregated trend rollups** — D-13 computes on-read; materialize only if a very large tenant demonstrates a real performance need.
- **Point-in-time group membership (membership-history table)** — D-06 uses current membership retroactively; a true historical-membership view needs a new audit/capture pipeline. Future phase if demanded.
- **Sum/total-exposure trend aggregate** and a per-chart avg↔total toggle — D-07 ships average only.
- **Per-group access control (RBAC)** — D-14 allows any tenant user to scope any group; a group-scoped permission model is a broader RBAC effort, not this phase.
- **Aging bands trended over time** (each age band as its own historical line) — D-08 ships the point-in-time distribution; trending the bands needs age-at-each-past-date the snapshots don't store.
- **MTTR-by-tier breakdown, exec/board PDF, role-scoped dashboards, framework-control compliance mapping** — Phase 43 (RPT-01..03), which consumes this phase's data.

</deferred>

---

*Phase: 42-risk-trend-analytics-burndown*
*Context gathered: 2026-08-21*
