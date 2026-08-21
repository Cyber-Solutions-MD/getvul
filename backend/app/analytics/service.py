"""Analytics business logic (Phase 42 Plan 01 -- TREND-01/03 tracer slice):
the tenant-scoped risk-exposure trend series, version-boundary detection,
and the `/overview` orchestrator. Plain async, HTTP-agnostic (D-16, no
FastAPI `Depends` anywhere in this module) -- Phase 43's report generator
calls these functions directly, no HTTP round-trip.

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
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vulnerabilities.trends import DailySnapshot


async def get_scoped_trend_series(
    db: AsyncSession, tenant_id: uuid.UUID, *, start: date, end: date
) -> list[dict[str, Any]]:
    """T-42-01 (tenant isolation): `DailySnapshot.tenant_id == tenant_id` is
    inline in this query's `.where(...)` -- never a post-fetch filter.
    Ascending by `snapshot_date` (one row per day, no timestamp ties) and
    bounded by `[start, end]` -- never the legacy 90-row LIMIT (D-13).
    ALWAYS reads `avg_risk_exposure_score` (D-12) -- never branches on the
    tenant's consumer-cutover flag.
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

    return [
        {
            "date": r.snapshot_date.isoformat(),
            "avg_risk_exposure_score": r.metrics.get("avg_risk_exposure_score"),
            "risk_model_version": r.metrics.get("risk_model_version_snapshot"),
        }
        for r in rows
    ]


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


async def get_analytics_overview(db: AsyncSession, tenant_id: uuid.UUID, *, days: int = 30) -> dict[str, Any]:
    """GET /api/v1/analytics/overview orchestrator (D-15). Structured so
    Plans 02/03 add "aging"/"burndown" keys and scope/group params onto
    this same return shape without reshaping it (D-16)."""
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days)

    trend = await get_scoped_trend_series(db, tenant_id, start=start, end=end)
    boundaries = detect_version_boundaries(trend)

    return {"trend": trend, "boundaries": boundaries}
