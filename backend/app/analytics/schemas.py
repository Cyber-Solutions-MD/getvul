"""Pydantic schemas for the Analytics API (Phase 42 Plan 01 -- TREND-01/03
tracer slice): the tenant-scoped risk-exposure trend series + detected
version-boundary list. Mirrors `app/coverage/schemas.py`'s response-model
conventions -- Pydantic v2, `ConfigDict(from_attributes=True)` on every
model (Plans 02/03 extend additively -- aging/burndown/scope -- without
reshaping, per D-16).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AnalyticsTrendPointResponse(BaseModel):
    """One day's tenant risk-exposure reading (D-07: the stored AVERAGE
    across the scope's assets, read directly from
    `DailySnapshot.metrics["avg_risk_exposure_score"]`).

    `avg_risk_exposure_score` is nullable -- None means a real gap (reserved
    for Plan 03's zero-scored-group-members case, D-06). The tenant series
    this plan reads never emits None in practice (`capture_daily_snapshot`
    always writes a float, defaulting to 0 -- see trends.py), but the type
    stays nullable now so Plan 03's group-scoped series doesn't need a
    contract change.
    """

    model_config = ConfigDict(from_attributes=True)

    date: str
    avg_risk_exposure_score: float | None
    risk_model_version: str | None


class VersionBoundaryResponse(BaseModel):
    """A detected `risk_model_version_snapshot` change (D-11) -- the trend
    line must segment (never interpolate) across this date and render a
    neutral labeled marker, never colored as accent/severity/success."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    old_version: str
    new_version: str


class AgingBucketResponse(BaseModel):
    """One SLA-tier-aligned aging bucket (D-08), stacked by severity. The
    three buckets are always present, in the fixed order `within_sla` ->
    `recently_breached` -> `long_overdue` -- even at zero (a "nothing
    overdue" tenant renders 3 zero-height buckets, never an empty chart,
    per 42-UI-SPEC.md E3's zero-one-many resolution).

    Only 4 severities are tracked here (critical/high/medium/low) --
    mirrors `trends.py::get_vuln_trends`'s own `sev_by_day` dict and the
    frontend's `SEVERITY_FILLS`, neither of which carries a 5th INFO slot;
    an INFO-severity finding folds into `low` (see
    `service.py::_SEVERITY_BUCKET_KEYS`).
    """

    model_config = ConfigDict(from_attributes=True)

    bucket: str
    critical: int
    high: int
    medium: int
    low: int


class BurndownResponse(BaseModel):
    """Net backlog velocity + a projected clear-date (D-09). `net_per_week`
    is always a non-negative MAGNITUDE -- direction lives entirely in
    `status` (`shrinking` | `growing` | `no_change`) so the frontend never
    needs an `abs()`/sign check, only a copy-branch switch on `status`.

    `days_to_clear` is populated only when `status == "shrinking"`; it is
    `None` for `growing`/`no_change` (UI-SPEC: "no clear date at this
    rate"). When the raw projection would exceed `MAX_PROJECTION_DAYS`,
    `days_to_clear` is CAPPED at that value and `capped=True` (UI-SPEC E4:
    "500+ d to clear" rather than an absurd multi-thousand-day number) --
    the frontend never computes the cap itself.
    """

    model_config = ConfigDict(from_attributes=True)

    status: str
    net_per_week: float
    open_backlog: int
    days_to_clear: int | None
    capped: bool


class AnalyticsOverviewResponse(BaseModel):
    """GET /api/v1/analytics/overview (TREND-01/03 tracer slice; TREND-02
    aging/burndown added Plan 02). Plan 03 adds scope/group params onto
    this same shape without reshaping it (D-16 reusable-service-layer
    contract)."""

    model_config = ConfigDict(from_attributes=True)

    trend: list[AnalyticsTrendPointResponse]
    boundaries: list[VersionBoundaryResponse]
    aging: list[AgingBucketResponse]
    aging_pct_overdue: int
    burndown: BurndownResponse
