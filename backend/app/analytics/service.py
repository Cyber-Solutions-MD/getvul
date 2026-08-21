"""Analytics business logic (Phase 42 Plan 01 -- TREND-01/03 tracer slice;
Plan 02 adds TREND-02 aging/burndown): the tenant-scoped risk-exposure
trend series, version-boundary detection, backlog aging distribution,
burndown rate, and the `/overview` orchestrator. Plain async,
HTTP-agnostic (D-16, no FastAPI `Depends` anywhere in this module) --
Phase 43's report generator calls these functions directly, no HTTP
round-trip.

Deliberately supersedes `app/vulnerabilities/trends.py::get_risk_score_trend`
for the NEW Analytics page only -- the existing `GET /trends` endpoint and
that function are untouched (D-15). `get_risk_score_trend` LIMITs to the
most recent 90 rows and branches its primary series on the tenant's
consumer-cutover flag; this module does neither:

  - D-12: ALWAYS keys on `avg_risk_exposure_score`, never branches on the
    cutover flag. Phase 34 RISK-10 dual-writes that metric unconditionally,
    so the data exists for every tenant regardless of the flag.
  - D-13: bounds the series by a real [start, end] date range instead of a
    row-count LIMIT, so 1y/custom windows (Plan 03) are representable
    without a shape change to this function.

Plan 02 (TREND-02) additions -- `get_aging_distribution` / `get_burndown_rate`
-- reuse two Phase 36/39 primitives verbatim rather than re-deriving them
(42-RESEARCH.md "Don't Hand-Roll"):

  - D-10: `~active_exception_subquery(tenant_id, now)` (Phase 39) excludes
    actively-excepted findings from every open-backlog query below, via the
    shared `_open_backlog_conditions` helper.
  - D-08: `sla_tier_service.get_tier_policy`/`tier_for_score`/
    `severity_to_tier` (Phase 36) resolve each finding's tier window --
    NEVER the legacy severity-keyed SLA module's day-count constants
    (42-RESEARCH.md Pitfall 2). The stored `sla_due_at`/`sla_breached`
    columns are read directly, never recomputed live via
    `resolve_state_for_vuln` (42-RESEARCH.md Open Question 2, RESOLVED).

Plan 03 (TREND-01 group scope + D-03 custom range + TREND-03 multi-boundary)
additions:

  - D-05/D-06/D-07: `get_scoped_trend_series` gains an optional `member_ids`
    param -- when provided (group scope), each historical day's average is
    recomputed RETROACTIVELY by intersecting that day's
    `asset_risk_exposure_scores` dict against the group's CURRENT
    membership, never a stored/point-in-time value. A day with zero scored
    current members yields `None` (a gap), never `0` (D-06).
  - T-42-08 (IDOR): `_resolve_group_scope` reuses
    `app.assets.groups_service.list_members`'s tenant-scoped,
    None-on-cross-tenant-miss lookup -- mirrors that module's own
    "return None/False on a miss, let the caller 404" convention rather
    than raising an HTTP-specific exception from this plain-async,
    HTTP-agnostic module (D-16); the router converts `None` to a 404.
  - Pitfall 5/D-02: `get_analytics_overview` threads the SAME group-derived
    `asset_ids` into `get_aging_distribution`/`get_burndown_rate` (both
    already accept it, wired in Plan 02) so scope re-scopes EVERY chart,
    not only the trend line.
  - `MAX_ANALYTICS_WINDOW_DAYS` bounds a custom `[start, end]` range
    server-side (T-42-09 DoS guard), mirroring the existing `/trends`
    `le=365` idiom on the days-count precedent.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.groups_service import get_group, list_members
from app.exceptions.service import active_exception_subquery
from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.sla_tier_service import get_tier_policy, severity_to_tier, tier_for_score
from app.vulnerabilities.trends import DailySnapshot, get_vuln_trends

# D-08: the aging chart's severity axis has exactly 4 slots
# (critical/high/medium/low) -- mirrors `trends.py::get_vuln_trends`'s own
# `sev_by_day` dict and the frontend's `SEVERITY_FILLS`, neither of which
# carries a 5th INFO slot. An INFO-severity finding (rare in the OPEN
# backlog) folds into `low`, the same "everything below HIGH groups
# together" spirit as `severity_to_tier`'s MEDIUM/LOW/INFO -> "moderate"
# mapping.
_SEVERITY_BUCKET_KEYS: dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFO": "low",
}

# D-09/UI-SPEC E4: cap an absurd multi-thousand-day projection at a fixed
# ceiling -- the frontend renders "500+ d to clear" rather than an exact
# (and misleadingly precise) huge number. Claude's discretion per
# 42-CONTEXT.md; 500d (~1.4y) is far past any window this page offers.
MAX_PROJECTION_DAYS = 500

# T-42-09 (DoS guard): a defensive server-side cap on a custom [start, end]
# range's span (D-03/Plan 03), mirroring the existing `/trends` `le=365`
# idiom on the days-count precedent -- ~1096d (~3y) covers any legitimate
# historical-comparison use case while bounding the daily_snapshots scan.
MAX_ANALYTICS_WINDOW_DAYS = 1096


async def get_scoped_trend_series(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    start: date,
    end: date,
    member_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """T-42-01 (tenant isolation): `DailySnapshot.tenant_id == tenant_id` is
    inline in this query's `.where(...)` -- never a post-fetch filter.
    Ascending by `snapshot_date` (one row per day, no timestamp ties) and
    bounded by `[start, end]` -- never the legacy 90-row LIMIT (D-13).

    Tenant scope (`member_ids=None`, the default -- byte-identical to
    before Plan 03): ALWAYS reads `avg_risk_exposure_score` (D-12) -- never
    branches on the tenant's consumer-cutover flag.

    Group scope (`member_ids` provided -- Plan 03, D-05/D-06/D-07): each
    row's average is recomputed RETROACTIVELY by intersecting that day's
    `asset_risk_exposure_scores` dict against the group's CURRENT member
    set, then averaging -- exactly D-06's "current membership applied
    retroactively" semantic, never a stored/point-in-time value. A day
    where none of the group's current members have a score in that day's
    dict yields `avg_risk_exposure_score = None` -- a real gap (D-06),
    NEVER `0`, even though `0` is a legitimate score elsewhere on this page
    (42-RESEARCH.md Anti-Patterns: never gate/collapse on a falsy score).
    """
    rows = (
        await db.execute(
            select(DailySnapshot.snapshot_date, DailySnapshot.metrics)
            .where(
                DailySnapshot.tenant_id == tenant_id,
                DailySnapshot.snapshot_date.between(start, end),
            )
            .order_by(DailySnapshot.snapshot_date.asc())
        )
    ).all()

    series: list[dict[str, Any]] = []
    for r in rows:
        if member_ids is None:
            avg_score = r.metrics.get("avg_risk_exposure_score")
        else:
            per_asset_scores: dict[str, Any] = r.metrics.get("asset_risk_exposure_scores", {})
            scoped_values = [v for k, v in per_asset_scores.items() if k in member_ids]
            avg_score = round(sum(scoped_values) / len(scoped_values), 1) if scoped_values else None
        series.append(
            {
                "date": r.snapshot_date.isoformat(),
                "avg_risk_exposure_score": avg_score,
                "risk_model_version": r.metrics.get("risk_model_version_snapshot"),
            }
        )
    return series


def detect_version_boundaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TREND-03/D-11: walk the (already-ascending-by-date) trend series and
    emit one boundary dict every time `risk_model_version` differs from the
    previous row's. The chart segments (never interpolates) across each
    returned date.

    No existing codebase precedent for this logic (42-RESEARCH.md Pitfall 1
    / PATTERNS.md "Novel Logic") -- `RISK_MODEL_VERSION` has never been
    bumped past "v1" in any real data, so every real tenant's series today
    yields `[]` (one continuous segment). Only provable via the synthetic
    multi-version fixture in `test_analytics.py`.
    """
    boundaries: list[dict[str, Any]] = []
    prev_version: str | None = None
    for row in rows:
        version = row.get("risk_model_version")
        if prev_version is not None and version != prev_version:
            boundaries.append(
                {
                    "date": row["date"],
                    "old_version": prev_version,
                    "new_version": version,
                }
            )
        prev_version = version
    return boundaries


def _open_backlog_conditions(
    tenant_id: uuid.UUID,
    now: datetime,
    asset_ids: list[uuid.UUID] | None,
) -> list[ColumnElement[bool]]:
    """D-10: the Phase 39/40 "what's genuinely open" predicate, applied
    verbatim (never re-derived, 42-RESEARCH.md "Don't Hand-Roll") to every
    open-backlog query in this module. `status.in_(["OPEN", "IN_PROGRESS"])`
    already excludes SUPPRESSED/FALSE_POSITIVE; `~active_exception_subquery`
    additionally excludes findings under an active exception (EXC-02).
    `asset_ids` is the Pitfall-5 group-scoping filter -- default `None` =
    tenant-wide (wired now, consumed by Plan 03).
    """
    conditions: list[ColumnElement[bool]] = [
        Vulnerability.tenant_id == tenant_id,
        Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        ~active_exception_subquery(tenant_id, now),
    ]
    if asset_ids is not None:
        conditions.append(Vulnerability.asset_id.in_(asset_ids))
    return conditions


async def get_aging_distribution(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    asset_ids: list[uuid.UUID] | None = None,
    now: datetime,
) -> dict[str, Any]:
    """TREND-02/D-08: current open findings bucketed into 3 SLA-tier-aligned
    buckets (`within_sla` / `recently_breached` / `long_overdue`), stacked
    by severity. Computed LIVE from the current open backlog (D-08 -- a
    point-in-time snapshot, not a trended-over-time series).

    Bucketing reads the STORED `sla_due_at`/`sla_breached` columns directly
    (written once per scheduler tick by `sla_tier_service.run_sla_tier_pass`)
    rather than recomputing per-row via `resolve_state_for_vuln`
    (42-RESEARCH.md Open Question 2, RESOLVED -- D-13's "live compute"
    governs the AGGREGATION being uncached, not per-row SLA-state
    re-derivation; every existing SLA-reading function in this codebase
    follows the same convention).

    Boundary discipline (documented per the plan's "make it deterministic"
    instruction): `sla_breached` mirrors `compute_sla_state`'s own
    `now >= sla_due_at` semantics (inclusive on the breached side) -- a
    finding exactly AT its due date is already "breached", landing in
    `recently_breached`, never double-counted into `within_sla` and never
    dropped. Within the breached findings, `recently_breached` vs.
    `long_overdue` splits on whether the finding has been overdue for MORE
    than one additional tier-window (`now - sla_due_at <= tier_days`) --
    the same "percentage of the finding's own tier window" philosophy
    `sla_tier_service`'s `approaching_pct` already uses (42-RESEARCH.md
    Pattern 5 / Assumption A5), just at a 100% multiplier: a critical
    finding breached 1-7 days is "recently", breached >7 days is "long
    overdue"; a moderate finding gets a proportionately wider 90-day
    "recently" window. Deterministic and severity/tier-relative, never an
    arbitrary absolute day count.

    `pct_overdue` (recently_breached + long_overdue over total open) is
    returned as `0`, never `None`, when the backlog is empty (UI-SPEC E3:
    "0% of open backlog is overdue" renders explicitly).
    """
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    policy = get_tier_policy(tenant)
    tier_days_map: dict[str, int] = policy["tier_days"]

    conditions = _open_backlog_conditions(tenant_id, now, asset_ids)
    rows = (
        await db.execute(
            select(
                Vulnerability.severity,
                Vulnerability.risk_exposure_score,
                Vulnerability.sla_due_at,
                Vulnerability.sla_breached,
            ).where(*conditions)
        )
    ).all()

    buckets: dict[str, dict[str, int]] = {
        "within_sla": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "recently_breached": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "long_overdue": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    }

    total_open = len(rows)
    overdue_open = 0

    for r in rows:
        sev_key = _SEVERITY_BUCKET_KEYS.get(r.severity, "low")

        if not r.sla_breached or r.sla_due_at is None:
            bucket = "within_sla"
        else:
            # D-12/D-03 tier resolution (mirrors resolve_state_for_vuln's
            # own scored-then-severity-fallback order). A `not_tracked`
            # (None) tier can only reach here via a stale not-yet-resynced
            # row -- defensively fall back to severity_to_tier rather than
            # KeyError on tier_days_map[None].
            tier = tier_for_score(r.risk_exposure_score) if r.risk_exposure_score is not None else None
            if tier is None:
                tier = severity_to_tier(r.severity)
            tier_days = tier_days_map.get(tier, tier_days_map["moderate"])
            overdue_for = now - r.sla_due_at
            bucket = "recently_breached" if overdue_for <= timedelta(days=tier_days) else "long_overdue"
            overdue_open += 1

        buckets[bucket][sev_key] += 1

    pct_overdue = round(100 * overdue_open / total_open) if total_open else 0

    return {"buckets": buckets, "pct_overdue": pct_overdue}


async def get_burndown_rate(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    days: int,
    asset_ids: list[uuid.UUID] | None = None,
) -> dict[str, Any]:
    """TREND-02/D-09: net backlog velocity (avg resolved - new per day,
    expressed per week) plus a projected days-to-clear, composed from
    `get_vuln_trends`'s existing new-vs-resolved daily feed (never a
    separate raw query -- 42-RESEARCH.md Architecture Patterns Pattern 2).

    `net_per_week` is always a non-negative MAGNITUDE; direction lives in
    `status` (`shrinking` | `growing` | `no_change`) so the frontend never
    branches on sign, only on `status` (UI-SPEC's 3 locked copy branches,
    including the E4 net-zero "no change" branch distinct from both
    directional ones).

    `days_to_clear` is populated ONLY for `status == "shrinking"`, capped
    at `MAX_PROJECTION_DAYS` (D-09/UI-SPEC E4 overflow -- `capped=True`
    signals the frontend to render "500+ d to clear" instead of an exact
    absurd number). All division happens HERE, server-side -- the frontend
    burndown tile receives only these already-computed plain values.
    """
    trends = await get_vuln_trends(db, tenant_id, days=days, asset_ids=asset_ids)
    timeline = trends["timeline"]

    if timeline:
        # Plan-literal formula: round(float(avg(resolved - new) * 7), 1).
        # Positive => resolving faster than arriving => shrinking.
        raw_net_per_week = round(float(sum(day["resolved"] - day["new"] for day in timeline) / len(timeline) * 7), 1)
    else:
        raw_net_per_week = 0.0

    if raw_net_per_week > 0:
        status = "shrinking"
    elif raw_net_per_week < 0:
        status = "growing"
    else:
        status = "no_change"

    now = datetime.now(UTC)
    conditions = _open_backlog_conditions(tenant_id, now, asset_ids)
    open_backlog = (await db.execute(select(func.count(Vulnerability.id)).where(*conditions))).scalar_one()

    days_to_clear: int | None = None
    capped = False
    if status == "shrinking":
        if open_backlog == 0:
            days_to_clear = 0
        else:
            uncapped_days = open_backlog * 7 / raw_net_per_week
            if uncapped_days > MAX_PROJECTION_DAYS:
                days_to_clear = MAX_PROJECTION_DAYS
                capped = True
            else:
                days_to_clear = round(uncapped_days)

    return {
        "status": status,
        "net_per_week": abs(raw_net_per_week),
        "open_backlog": open_backlog,
        "days_to_clear": days_to_clear,
        "capped": capped,
    }


async def _resolve_group_scope(
    db: AsyncSession, tenant_id: uuid.UUID, group_id: uuid.UUID
) -> tuple[set[str], list[uuid.UUID], str] | None:
    """D-05/D-06 group-scope resolution for `get_analytics_overview`.

    T-42-08 IDOR guard: `list_members` (Phase 32,
    `app.assets.groups_service`) is ALREADY the tenant-scoped,
    None-on-miss lookup this module's guard needs (42-RESEARCH.md "Don't
    Hand-Roll" / mirrors `coverage/router.py::_get_asset_or_404`'s "tenant
    filter inline in the WHERE clause, never fetch-then-403" shape) --
    `None` here means the group_id does not exist OR belongs to a
    different tenant. Mirrors `groups_service.py`'s OWN "return None/False
    on a miss, let the caller decide" convention (its module docstring)
    rather than raising an HTTP-specific exception from this plain-async,
    HTTP-agnostic module (D-16) -- `get_analytics_overview` below
    propagates the `None`, and the router converts THAT to a 404, exactly
    like every other tenant-scoped lookup in this codebase.
    """
    members = await list_members(db, tenant_id, group_id)
    if members is None:
        return None
    group = await get_group(db, tenant_id, group_id)
    group_name = group.name if group is not None else ""
    member_ids = {str(a.id) for a in members}
    asset_ids = [a.id for a in members]
    return member_ids, asset_ids, group_name


async def get_analytics_overview(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    days: int = 30,
    start: date | None = None,
    end: date | None = None,
    scope: str = "all",
    group_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """GET /api/v1/analytics/overview orchestrator (D-15). Plan 02 added
    the "aging"/"aging_pct_overdue"/"burndown" keys additively --
    "trend"/"boundaries" unchanged. Plan 03 adds `scope`/`group_id` (D-02
    group scoping) and `start`/`end` (D-03 custom range) params, plus the
    additive `scope`/`group_name` response keys the frontend's mandatory
    group-scope caption reads (D-06) -- still no reshape of the existing
    keys (D-16).

    `start`/`end` (a validated custom range, router-supplied) take
    precedence over `days` (a preset window) when both are given -- the
    router only ever supplies one pair, never both (see router.py).

    Returns `None` when `scope="group"` and `group_id` does not
    exist/belong to this tenant (T-42-08 -- mirrors `_resolve_group_scope`'s
    own None-on-miss convention); the router converts that to a 404, never
    a fetch-then-403.
    """
    member_ids: set[str] | None = None
    asset_ids: list[uuid.UUID] | None = None
    group_name: str | None = None

    if scope == "group":
        if group_id is None:
            return None
        resolved = await _resolve_group_scope(db, tenant_id, group_id)
        if resolved is None:
            return None
        member_ids, asset_ids, group_name = resolved

    if start is not None and end is not None:
        range_start, range_end = start, end
    else:
        range_end = datetime.now(UTC).date()
        range_start = range_end - timedelta(days=days)

    trend = await get_scoped_trend_series(db, tenant_id, start=range_start, end=range_end, member_ids=member_ids)
    boundaries = detect_version_boundaries(trend)

    now = datetime.now(UTC)
    aging = await get_aging_distribution(db, tenant_id, asset_ids=asset_ids, now=now)
    # Pitfall 5/D-02: aging + burndown re-scope to the SAME group-derived
    # asset_ids -- "every chart" re-scopes as one mental model, not just
    # the trend line. Burndown's window is span-derived (at least 1 day,
    # defensively) rather than reusing `days` verbatim, so a custom range
    # narrower/wider than a preset still yields a sane velocity window.
    span_days = max((range_end - range_start).days, 1)
    burndown = await get_burndown_rate(db, tenant_id, days=span_days, asset_ids=asset_ids)

    aging_buckets = [{"bucket": bucket_id, **counts} for bucket_id, counts in aging["buckets"].items()]

    return {
        "trend": trend,
        "boundaries": boundaries,
        "aging": aging_buckets,
        "aging_pct_overdue": aging["pct_overdue"],
        "burndown": burndown,
        "scope": scope,
        "group_name": group_name,
    }
