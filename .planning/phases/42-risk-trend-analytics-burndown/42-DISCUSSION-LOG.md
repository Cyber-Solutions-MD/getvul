# Phase 42: Risk Trend Analytics & Burndown - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-21
**Phase:** 42-risk-trend-analytics-burndown
**Areas discussed:** View placement & layout, Team/asset-group series, Aging & burndown, Version-boundary & score, RBAC / who can view, Compute strategy & scale, Endpoint shape, Phase 43 hand-off

---

## View placement & layout

| Option | Description | Selected |
|--------|-------------|----------|
| New 'Analytics' nav page | Dedicated top-level sidebar page (Phase 41 Coverage precedent); dashboard TrendSection stays | ✓ |
| Expand dashboard TrendSection | Grow existing dashboard trend area in place, no new nav | |
| Analytics page + dashboard teaser | New page + a teaser tile on the dashboard | |

**User's choice:** New 'Analytics' nav page

| Option | Description | Selected |
|--------|-------------|----------|
| Scope dropdown (All / group) | Single selector, All (tenant) default + each AssetGroup, re-scopes every chart | ✓ |
| Overlaid multi-series lines | Tenant + team lines on same chart with legend toggle | |
| You decide | Planner picks | |

**User's choice:** Scope dropdown (All / group)

| Option | Description | Selected |
|--------|-------------|----------|
| 7d / 30d / 90d / 1y | Extend existing preset set with 1y | |
| Add custom date range | Presets PLUS a custom start/end date picker | ✓ |
| You decide | Planner picks | |

**User's choice:** Add custom date range (i.e. 7d/30d/90d/1y presets + custom range)

| Option | Description | Selected |
|--------|-------------|----------|
| Guided empty state | Canonical EmptyState below a minimum data-point threshold (Phase 41 D-11) | ✓ |
| Plot whatever exists | Always render even 1-2 points | |
| You decide | Planner picks threshold/copy | |

**User's choice:** Guided empty state

---

## Team/asset-group series

| Option | Description | Selected |
|--------|-------------|----------|
| Retroactive from per-asset dicts | Intersect each snapshot's stored per-asset score dict with current group membership; works over all history, no schema change | ✓ |
| New per-group snapshot rows | Forward-only per-group capture (new rows/table) | |
| You decide | Planner picks | |

**User's choice:** Retroactive from per-asset dicts

| Option | Description | Selected |
|--------|-------------|----------|
| Current membership, retroactively applied | Today's membership applied across the whole window; no membership-history table | ✓ |
| Point-in-time membership | Reflect who was in the group on each historical date (needs new capture) | |
| You decide | Planner picks | |

**User's choice:** Current membership, retroactively applied

| Option | Description | Selected |
|--------|-------------|----------|
| Average (match tenant snapshot) | Mean asset risk-exposure score across scope; matches avg_risk_exposure_score | ✓ |
| Sum (total exposure) | Total summed exposure across scope | |
| Both, toggleable | avg + total toggle | |

**User's choice:** Average (match tenant snapshot)

---

## Aging & burndown

| Option | Description | Selected |
|--------|-------------|----------|
| Point-in-time stacked aging chart | Current open findings bucketed by age, stacked by severity, live | ✓ |
| Aging bands trended over time | Each age band as its own historical line (needs age-at-past-date) | |
| You decide | Planner picks | |

**User's choice:** Point-in-time stacked aging chart

| Option | Description | Selected |
|--------|-------------|----------|
| SLA-tier aligned | Buckets mirror per-severity SLA windows (reuse Phase 36) | ✓ |
| Fixed day buckets | 0-30 / 31-60 / 61-90 / 90+ absolute | |
| You decide | Planner picks | |

**User's choice:** SLA-tier aligned

| Option | Description | Selected |
|--------|-------------|----------|
| Net flow + projected days-to-zero | Net velocity (resolved − new) + projected days to clear / "backlog growing" | ✓ |
| Open-count slope only | Just plot open_vulns over time | |
| You decide | Planner picks | |

**User's choice:** Net flow + projected days-to-zero

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — exclude, reuse Phase 39 predicate | Exclude SUPPRESSED/FALSE_POSITIVE + active exceptions, verbatim | ✓ |
| No — count all open | Count every OPEN/IN_PROGRESS regardless | |
| You decide | Planner picks | |

**User's choice:** Yes — exclude, reuse Phase 39 predicate

---

## Version-boundary & score

| Option | Description | Selected |
|--------|-------------|----------|
| Segment + labeled marker | Break line at version-change date (no interpolation) + labeled vertical marker | ✓ |
| Marker only (continuous line) | One continuous line with a boundary annotation | |
| You decide | Planner picks | |

**User's choice:** Segment + labeled marker

| Option | Description | Selected |
|--------|-------------|----------|
| Versioned exposure score, flag-independent | Always plot avg_risk_exposure_score, decoupled from cutover flag | ✓ |
| Honor the cutover flag | Mirror /trends (legacy when flag OFF) | |
| You decide | Planner picks | |

**User's choice:** Versioned exposure score, flag-independent

---

## RBAC / who can view

| Option | Description | Selected |
|--------|-------------|----------|
| Viewer+ (any tenant user), any group | Match /trends require_viewer; no per-group access control | ✓ |
| Analyst+ gated | Restrict to analyst and above | |
| You decide | Planner picks | |

**User's choice:** Viewer+ (any tenant user), any group

---

## Compute strategy & scale

| Option | Description | Selected |
|--------|-------------|----------|
| Live compute on-read (Phase 41 precedent) | Per-request from snapshots + live queries; raise snapshot LIMIT for 1y | ✓ |
| Cache / materialize now | Pre-aggregate group series up front | |
| You decide | Planner picks | |

**User's choice:** Live compute on-read

---

## Endpoint shape

| Option | Description | Selected |
|--------|-------------|----------|
| New /analytics endpoints | New scoped endpoints; leave GET /trends untouched | ✓ |
| Extend existing /trends | Add scope+range params, grow payload | |
| You decide | Planner picks | |

**User's choice:** New /analytics endpoints

---

## Phase 43 hand-off

| Option | Description | Selected |
|--------|-------------|----------|
| Reusable service layer | Service functions callable by both HTTP route and Phase 43 report generator | ✓ |
| Endpoint-only for now | Just the HTTP endpoint; Phase 43 refactors later | |
| You decide | Planner picks | |

**User's choice:** Reusable service layer

---

## Claude's Discretion

- Minimum-history threshold + empty-state copy (D-04).
- Exact SLA-tier aging bucket boundaries/labels + optional "% overdue" tile (D-08).
- Exact burndown presentation — number/sparkline/days-to-zero tile (D-09).
- Whether a plain supporting MTTR line appears (allowed, not required).
- `/analytics` route naming, params, response schema (D-15); service decomposition (D-16).
- Whether tenant "All" reads stored avg_risk_exposure_score vs re-aggregating the per-asset dict.
- Chart-library reuse vs. segmented-line/reference-line extension for D-11.

## Deferred Ideas

- Materialized/pre-aggregated trend rollups.
- Point-in-time group membership (membership-history table).
- Sum/total-exposure aggregate + avg↔total toggle.
- Per-group access control (RBAC).
- Aging bands trended over time.
- MTTR-by-tier, exec/board PDF, role-scoped dashboards, framework-control compliance mapping (Phase 43).
