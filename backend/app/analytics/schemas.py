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


class AnalyticsOverviewResponse(BaseModel):
    """GET /api/v1/analytics/overview (TREND-01/03 tracer slice). Plans
    02/03 add "aging"/"burndown" keys and scope/group params onto this same
    shape without reshaping it (D-16 reusable-service-layer contract)."""

    model_config = ConfigDict(from_attributes=True)

    trend: list[AnalyticsTrendPointResponse]
    boundaries: list[VersionBoundaryResponse]
