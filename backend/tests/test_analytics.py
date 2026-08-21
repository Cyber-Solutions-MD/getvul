"""Phase 42 Plan 01 (TREND-01/03 tracer slice) -- analytics module tests.
Plan 02 (TREND-02) appends the aging-distribution + burndown-rate tests.

Proves, in this order (mirrors test_risk_boundary_guard.py's own ordering
discipline -- prove the flag-decoupling and range-bounding first, then the
never-before-exercised version-boundary axis, then tenant isolation):

  1. get_scoped_trend_series ALWAYS reads avg_risk_exposure_score,
     regardless of Tenant.cutover_risk_exposure_scoring (D-12) -- the
     opposite of get_risk_score_trend's existing flag-branch.
  2. get_scoped_trend_series is bounded by a real date range, not the
     legacy 90-row LIMIT (D-13).
  3. detect_version_boundaries returns [] for a single-version series
     (today's real-world case for every tenant -- RISK_MODEL_VERSION has
     never been bumped past "v1").
  4. detect_version_boundaries DOES detect a boundary on a SYNTHETIC
     multi-version fixture (the never-before-varied risk_model_version_
     snapshot axis -- 42-RESEARCH.md Pitfall 1 -- there is no real data to
     test this against).
  5. get_analytics_overview is tenant-scoped -- tenant_b's data never
     leaks into tenant_a's overview (T-42-01).

Plan 02 additions (TREND-02) prove, in the plan's own <behavior> order:

  6. get_aging_distribution honors the Phase 39/40 exclusion predicate
     (SUPPRESSED/FALSE_POSITIVE/active-exception all absent from every
     bucket).
  7. Aging buckets resolve via sla_tier_service's tier policy (incl. a
     tenant sla_config override), never a hardcoded/legacy constant.
  8. The within_sla/recently_breached boundary is deterministic at the
     exact SLA-due-date edge (no double-count, no drop).
  9. Zero open findings render all 3 buckets at 0, not an error.
  10. get_burndown_rate's shrinking/growing/no_change branches, plus the
      E4 overflow cap on an extremely slow shrink rate.
  11. Every new numeric field is a plain JSON-safe int/float, never a
      Decimal.

Plan 03 additions (TREND-01 group scope + D-03 custom range + TREND-03
multi-boundary) prove, in the plan's own <behavior> order:

  12. get_scoped_trend_series's group branch averages EXACTLY the group's
      CURRENT members' per-day scores, retroactively (D-05/D-06) --
      excluding a non-member's historical score even though it is present
      in the same day's dict.
  13. A day where none of the group's current members have a score yields
      avg_risk_exposure_score = None, never 0 (D-06).
  14. A cross-tenant group_id 404s via the router's list_members-derived
      None path (T-42-08 IDOR) -- never a fetch-then-403.
  15. asset_ids threads into get_aging_distribution + get_burndown_rate
      too -- group scope narrows EVERY chart (D-02), not just the trend.
  16. detect_version_boundaries on a 3-version synthetic fixture emits
      exactly 2 boundaries (every in-window boundary, not just first/last
      -- UI-SPEC E2).
  17. A custom range beyond MAX_ANALYTICS_WINDOW_DAYS, or with to<from,
      422s server-side (T-42-09 DoS guard) -- never silently clamped.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.analytics.service import (
    MAX_ANALYTICS_WINDOW_DAYS,
    MAX_PROJECTION_DAYS,
    detect_version_boundaries,
    get_aging_distribution,
    get_analytics_overview,
    get_burndown_rate,
    get_scoped_trend_series,
)
from app.assets.models import Asset, AssetGroup, AssetGroupMember
from app.exceptions.models import ExceptionRecord
from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.risk_exposure_service import RISK_MODEL_VERSION
from app.vulnerabilities.trends import DailySnapshot


def _seed_vuln(
    tenant_id: uuid.UUID,
    *,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    risk_exposure_score: int | None = None,
    first_detected_at: datetime | None = None,
    remediated_at: datetime | None = None,
    sla_due_at: datetime | None = None,
    sla_breached: bool = False,
    asset_id: uuid.UUID | None = None,
) -> Vulnerability:
    """Bare Vulnerability row for the aging/burndown tests below -- mirrors
    `test_exceptions_sla.py::_seed_vuln` / `test_sla_tier_service.py::_vuln`,
    extended with the `sla_due_at`/`sla_breached` direct-set params these
    tests need (bypassing the scheduler's `run_sla_tier_pass` entirely, per
    42-RESEARCH.md Open Question 2 -- aging reads the STORED columns).
    Plan 03 additionally accepts `asset_id` (a real FK to `assets.id`,
    `ondelete="SET NULL"`) so `test_asset_ids_threads_into_aging_and_burndown`
    can pin a finding to a specific group member/non-member asset."""
    now = datetime.now(UTC)
    return Vulnerability(
        tenant_id=tenant_id,
        cve_id=f"CVE-AGE-{uuid.uuid4().hex[:8]}",
        severity=severity,
        source="MOCK",
        source_vuln_id=str(uuid.uuid4()),
        status=status,
        risk_exposure_score=risk_exposure_score,
        first_detected_at=first_detected_at or now,
        last_seen_at=now,
        remediated_at=remediated_at,
        sla_due_at=sla_due_at,
        sla_breached=sla_breached,
        asset_id=asset_id,
    )


async def _set_cutover_flag(db_session, tenant_id, enabled: bool) -> None:
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    tenant.cutover_risk_exposure_scoring = enabled
    await db_session.commit()


@pytest.mark.asyncio
async def test_tenant_trend_ignores_cutover_flag(db_session, tenant_a):
    """D-12: get_scoped_trend_series always reads avg_risk_exposure_score --
    identical result whether the tenant's cutover flag is True or False."""
    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day1,
            metrics={"avg_risk_exposure_score": 21.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day2,
            # Old-model key present too -- proves the new series never reads it.
            metrics={
                "avg_risk_score": 999.0,
                "avg_risk_exposure_score": 23.0,
                "risk_model_version_snapshot": RISK_MODEL_VERSION,
            },
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await _set_cutover_flag(db_session, tenant_a, False)
    off_rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)

    await _set_cutover_flag(db_session, tenant_a, True)
    on_rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)

    assert off_rows == on_rows, "series must be identical regardless of the cutover flag"
    # Ascending by date.
    assert [r["date"] for r in off_rows] == [day1.isoformat(), day2.isoformat()]
    assert off_rows[0]["avg_risk_exposure_score"] == 21.0
    assert off_rows[1]["avg_risk_exposure_score"] == 23.0
    # Never the old-model key/value (999.0 must not leak through).
    assert all(r["avg_risk_exposure_score"] != 999.0 for r in off_rows)


@pytest.mark.asyncio
async def test_tenant_trend_respects_date_range(db_session, tenant_a):
    """D-13: only in-window rows are returned -- no reliance on a 90-row
    LIMIT. A snapshot far outside the requested window must not appear even
    though it would easily fit inside a 90-row cap."""
    in_window = (datetime.now(UTC) - timedelta(days=5)).date()
    out_of_window = (datetime.now(UTC) - timedelta(days=200)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=in_window,
            metrics={"avg_risk_exposure_score": 10.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=out_of_window,
            metrics={"avg_risk_exposure_score": 999.0, "risk_model_version_snapshot": RISK_MODEL_VERSION},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    start = (datetime.now(UTC) - timedelta(days=30)).date()
    end = datetime.now(UTC).date()
    rows = await get_scoped_trend_series(db_session, tenant_a, start=start, end=end)

    dates = [r["date"] for r in rows]
    assert in_window.isoformat() in dates
    assert out_of_window.isoformat() not in dates
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_no_boundary_when_single_version(db_session, tenant_a):
    """A single-version series (every real tenant today) yields zero
    boundaries and stays one continuous segment."""
    base = datetime.now(UTC) - timedelta(days=3)
    for i in range(3):
        db_session.add(
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=(base + timedelta(days=i)).date(),
                metrics={"avg_risk_exposure_score": float(10 + i), "risk_model_version_snapshot": "v1"},
                created_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    start = (base).date()
    end = datetime.now(UTC).date()
    rows = await get_scoped_trend_series(db_session, tenant_a, start=start, end=end)
    boundaries = detect_version_boundaries(rows)

    assert boundaries == []


@pytest.mark.asyncio
async def test_version_boundary_detected_and_segmented(db_session, tenant_a):
    """SYNTHETIC fixture (42-RESEARCH.md Pitfall 1 -- no real tenant has
    ever varied risk_model_version_snapshot): seeding "v1" then "v2" must
    emit exactly one boundary dict {date, old_version, new_version}."""
    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day1,
            metrics={"avg_risk_exposure_score": 20.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day2,
            metrics={"avg_risk_exposure_score": 22.0, "risk_model_version_snapshot": "v2"},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day2)
    boundaries = detect_version_boundaries(rows)

    assert boundaries == [{"date": day2.isoformat(), "old_version": "v1", "new_version": "v2"}]


@pytest.mark.asyncio
async def test_overview_is_tenant_scoped(db_session, tenant_a, tenant_b):
    """T-42-01: get_analytics_overview(db, tenant_a) never returns
    tenant_b's data, even when both tenants have a snapshot on the exact
    same date."""
    today = datetime.now(UTC).date()

    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=today,
            metrics={"avg_risk_exposure_score": 24.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_b,
            snapshot_date=today,
            metrics={"avg_risk_exposure_score": 99.0, "risk_model_version_snapshot": "v1"},
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    overview = await get_analytics_overview(db_session, tenant_a, days=30)

    assert overview["trend"], "tenant_a must see its own snapshot"
    assert all(r["avg_risk_exposure_score"] != 99.0 for r in overview["trend"]), (
        "tenant_b's score must never leak into tenant_a's overview"
    )
    assert overview["trend"][-1]["avg_risk_exposure_score"] == 24.0
    # Plan 02 (TREND-02): the overview additively carries aging/burndown --
    # both present, both shaped, without touching the trend assertions above.
    assert {b["bucket"] for b in overview["aging"]} == {"within_sla", "recently_breached", "long_overdue"}
    assert isinstance(overview["aging_pct_overdue"], int)
    assert overview["burndown"]["status"] in ("shrinking", "growing", "no_change")


# ── TREND-02 (Plan 02): get_aging_distribution ─────────────────────────────


@pytest.mark.asyncio
async def test_aging_honors_exclusion_predicate(db_session, tenant_a, admin_user, analyst_user):
    """D-10: SUPPRESSED, FALSE_POSITIVE, and an actively-excepted OPEN
    finding must all be absent from every bucket -- only the genuinely
    open, non-excepted finding is counted."""
    now = datetime.now(UTC)
    vuln_open = _seed_vuln(tenant_a, severity="HIGH", status="OPEN")
    vuln_suppressed = _seed_vuln(tenant_a, severity="HIGH", status="SUPPRESSED")
    vuln_false_positive = _seed_vuln(tenant_a, severity="HIGH", status="FALSE_POSITIVE")
    vuln_excepted = _seed_vuln(tenant_a, severity="CRITICAL", status="OPEN")
    db_session.add_all([vuln_open, vuln_suppressed, vuln_false_positive, vuln_excepted])
    await db_session.flush()

    exception = ExceptionRecord(
        tenant_id=tenant_a,
        type="ACCEPTED_RISK",
        scope_type="FINDING",
        cve_id=vuln_excepted.cve_id,
        vulnerability_id=vuln_excepted.id,
        justification="Accepted for aging exclusion test",
        approver_user_id=admin_user.id,
        granted_by_user_id=analyst_user.id,
        expires_at=now + timedelta(days=30),
    )
    db_session.add(exception)
    await db_session.commit()

    result = await get_aging_distribution(db_session, tenant_a, now=now)

    total_counted = sum(sum(bucket.values()) for bucket in result["buckets"].values())
    assert total_counted == 1, "only vuln_open may be counted -- suppressed/false_positive/excepted are excluded"
    assert result["buckets"]["within_sla"]["high"] == 1


@pytest.mark.asyncio
async def test_aging_buckets_use_tier_policy(db_session, tenant_a):
    """D-08: bucketing must follow the RESOLVED tier policy (incl. a
    tenant sla_config override), never a hardcoded/legacy severity-keyed
    constant. Seeds one breached finding per tier (critical/high/moderate)
    -- the critical finding's classification flips from recently_breached
    (default 7d window) to long_overdue once the tenant overrides
    critical -> 3d, proving the override is actually read."""
    now = datetime.now(UTC)
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == tenant_a))).scalar_one()
    tenant.sla_config = {"tier_policy": {"critical": 3}}
    await db_session.commit()

    # Critical (severity fallback tier, no score): breached 5d ago. Default
    # critical window is 7d (5 <= 7 -> recently_breached); the tenant's
    # override (3d) makes 5 > 3 -> long_overdue instead.
    critical_due = now - timedelta(days=5)
    vuln_critical = _seed_vuln(
        tenant_a,
        severity="CRITICAL",
        first_detected_at=critical_due - timedelta(days=3),
        sla_due_at=critical_due,
        sla_breached=True,
    )
    # High (severity fallback tier): breached 10d ago, default 30d window
    # (untouched by the override) -> 10 <= 30 -> recently_breached.
    high_due = now - timedelta(days=10)
    vuln_high = _seed_vuln(
        tenant_a,
        severity="HIGH",
        first_detected_at=high_due - timedelta(days=20),
        sla_due_at=high_due,
        sla_breached=True,
    )
    # Moderate (MEDIUM severity fallback tier): breached 95d ago, default
    # 90d window -> 95 > 90 -> long_overdue.
    moderate_due = now - timedelta(days=95)
    vuln_moderate = _seed_vuln(
        tenant_a,
        severity="MEDIUM",
        first_detected_at=moderate_due - timedelta(days=5),
        sla_due_at=moderate_due,
        sla_breached=True,
    )
    db_session.add_all([vuln_critical, vuln_high, vuln_moderate])
    await db_session.commit()

    result = await get_aging_distribution(db_session, tenant_a, now=now)
    buckets = result["buckets"]

    assert buckets["long_overdue"]["critical"] == 1, (
        "critical must respect the tenant's 3d override, not the 7d default"
    )
    assert buckets["recently_breached"]["critical"] == 0
    assert buckets["recently_breached"]["high"] == 1
    assert buckets["long_overdue"]["medium"] == 1


@pytest.mark.asyncio
async def test_aging_bucket_edge_deterministic(db_session, tenant_a):
    """Backstop must_have: a finding whose age exactly equals its SLA
    tier-window boundary lands in exactly one bucket, deterministically,
    with one-day-either-side siblings in the adjacent bucket -- documents
    the inclusive `now >= sla_due_at` boundary (mirrors compute_sla_state's
    own semantics): the due-date instant itself is already breached."""
    now = datetime.now(UTC)
    tier_days = 7  # default critical tier

    before = _seed_vuln(
        tenant_a,
        severity="CRITICAL",
        first_detected_at=now - timedelta(days=tier_days - 1),
        sla_due_at=now + timedelta(days=1),
        sla_breached=False,
    )
    at_boundary = _seed_vuln(
        tenant_a,
        severity="CRITICAL",
        first_detected_at=now - timedelta(days=tier_days),
        sla_due_at=now,
        sla_breached=True,
    )
    after = _seed_vuln(
        tenant_a,
        severity="CRITICAL",
        first_detected_at=now - timedelta(days=tier_days + 1),
        sla_due_at=now - timedelta(days=1),
        sla_breached=True,
    )
    db_session.add_all([before, at_boundary, after])
    await db_session.commit()

    result = await get_aging_distribution(db_session, tenant_a, now=now)
    buckets = result["buckets"]

    assert buckets["within_sla"]["critical"] == 1, "one day before the boundary is not yet breached"
    assert buckets["recently_breached"]["critical"] == 2, "the boundary instant itself + one day after are breached"
    assert buckets["long_overdue"]["critical"] == 0

    total = sum(sum(b.values()) for b in buckets.values())
    assert total == 3, "no double-count, no drop across the 3 seeded findings"


@pytest.mark.asyncio
async def test_aging_zero_open_renders_three_zero_buckets(db_session, tenant_a):
    """UI-SPEC E3: zero open findings in scope is a valid 'nothing
    overdue' state -- all 3 buckets present at 0, never an error, and
    pct_overdue is 0 (never None)."""
    now = datetime.now(UTC)
    result = await get_aging_distribution(db_session, tenant_a, now=now)

    assert set(result["buckets"].keys()) == {"within_sla", "recently_breached", "long_overdue"}
    for bucket in result["buckets"].values():
        assert bucket == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assert result["pct_overdue"] == 0


# ── TREND-02 (Plan 02): get_burndown_rate ──────────────────────────────────


@pytest.mark.asyncio
async def test_burndown_projection_branches(db_session):
    """D-09: shrinking (resolved > new -> positive days-to-clear), growing
    (new > resolved -> no clear date), no-change (net == 0 -> a third,
    distinct branch per UI-SPEC E4) -- plus the E4 overflow cap when a
    backlog is shrinking too slowly to clear within MAX_PROJECTION_DAYS.
    Each branch uses its own throwaway tenant_id (Vulnerability.tenant_id
    carries no FK constraint) so the 4 scenarios can't cross-contaminate
    each other's new/resolved/open-backlog counts."""
    now = datetime.now(UTC)
    outside_window = now - timedelta(days=100)  # never counted as "new" in a 30d window

    # -- Shrinking: 8 resolved vs 1 new inside the window.
    shrinking_tenant = uuid.uuid4()
    new_v = _seed_vuln(shrinking_tenant, status="OPEN", first_detected_at=now - timedelta(days=1))
    resolved_vulns = []
    for _ in range(8):
        v = _seed_vuln(
            shrinking_tenant,
            status="REMEDIATED",
            first_detected_at=outside_window,
            remediated_at=now - timedelta(days=1),
        )
        resolved_vulns.append(v)
    db_session.add_all([new_v, *resolved_vulns])
    await db_session.commit()

    shrinking = await get_burndown_rate(db_session, shrinking_tenant, days=30)
    assert shrinking["status"] == "shrinking"
    assert shrinking["net_per_week"] > 0
    assert shrinking["days_to_clear"] is not None
    assert shrinking["capped"] is False

    # -- Growing: 8 new vs 1 resolved inside the window.
    growing_tenant = uuid.uuid4()
    new_vulns = [_seed_vuln(growing_tenant, status="OPEN", first_detected_at=now - timedelta(days=1)) for _ in range(8)]
    resolved_v = _seed_vuln(
        growing_tenant,
        status="REMEDIATED",
        first_detected_at=outside_window,
        remediated_at=now - timedelta(days=1),
    )
    db_session.add_all([*new_vulns, resolved_v])
    await db_session.commit()

    growing = await get_burndown_rate(db_session, growing_tenant, days=30)
    assert growing["status"] == "growing"
    assert growing["net_per_week"] > 0
    assert growing["days_to_clear"] is None
    assert growing["capped"] is False

    # -- No change: nothing new, nothing resolved in the window at all.
    no_change_tenant = uuid.uuid4()
    no_change = await get_burndown_rate(db_session, no_change_tenant, days=30)
    assert no_change["status"] == "no_change"
    assert no_change["net_per_week"] == 0
    assert no_change["days_to_clear"] is None
    assert no_change["capped"] is False

    # -- Overflow cap: 2 resolved vs 1 new (a glacial shrink rate) against
    # a sizeable open backlog projects well past MAX_PROJECTION_DAYS.
    capped_tenant = uuid.uuid4()
    slow_new = _seed_vuln(capped_tenant, status="OPEN", first_detected_at=now - timedelta(days=1))
    slow_resolved = [
        _seed_vuln(
            capped_tenant,
            status="REMEDIATED",
            first_detected_at=outside_window,
            remediated_at=now - timedelta(days=1),
        )
        for _ in range(2)
    ]
    filler_backlog = [_seed_vuln(capped_tenant, status="OPEN", first_detected_at=outside_window) for _ in range(20)]
    db_session.add_all([slow_new, *slow_resolved, *filler_backlog])
    await db_session.commit()

    capped = await get_burndown_rate(db_session, capped_tenant, days=30)
    assert capped["status"] == "shrinking"
    assert capped["capped"] is True
    assert capped["days_to_clear"] == MAX_PROJECTION_DAYS


@pytest.mark.asyncio
async def test_burndown_and_aging_numeric_types(db_session, tenant_a):
    """42-RESEARCH.md Pitfall 6: every numeric field these new aggregates
    produce must be a plain JSON-safe int/float, never a SQLAlchemy
    Decimal (which serializes as a JSON string, not a number, at the
    Pydantic/FastAPI response boundary)."""
    now = datetime.now(UTC)
    vuln = _seed_vuln(
        tenant_a,
        severity="HIGH",
        status="OPEN",
        first_detected_at=now - timedelta(days=40),
        sla_due_at=now - timedelta(days=10),
        sla_breached=True,
    )
    db_session.add(vuln)
    await db_session.commit()

    aging = await get_aging_distribution(db_session, tenant_a, now=now)
    assert isinstance(aging["pct_overdue"], int)
    assert not isinstance(aging["pct_overdue"], Decimal)
    for bucket in aging["buckets"].values():
        for count in bucket.values():
            assert isinstance(count, int)
            assert not isinstance(count, Decimal)

    burndown = await get_burndown_rate(db_session, tenant_a, days=30)
    assert isinstance(burndown["net_per_week"], float)
    assert not isinstance(burndown["net_per_week"], Decimal)
    assert isinstance(burndown["open_backlog"], int)
    assert not isinstance(burndown["open_backlog"], Decimal)
    assert burndown["days_to_clear"] is None or isinstance(burndown["days_to_clear"], int)


# ── TREND-01 (Plan 03): group scoping + custom range + multi-boundary ─────


@pytest.mark.asyncio
async def test_group_trend_uses_current_membership_retroactively(db_session, tenant_a):
    """D-05/D-06: a group trend point is the AVERAGE of exactly the
    group's CURRENT members' scores on that historical day -- a
    non-member's score, present in the SAME day's per-asset dict, must
    never be folded into the average, even though it existed on that
    date. The tenant-wide `avg_risk_exposure_score` key (999.0) is also
    present on both days and must never leak into the group series
    either -- proves the group branch reads the per-asset dict, not the
    tenant-wide key."""
    await db_session.commit()  # AssetGroup has a real FK to tenants (test_asset_groups.py precedent)

    asset_member_1 = Asset(tenant_id=tenant_a, hostname="member-1.local")
    asset_member_2 = Asset(tenant_id=tenant_a, hostname="member-2.local")
    asset_non_member = Asset(tenant_id=tenant_a, hostname="non-member.local")
    db_session.add_all([asset_member_1, asset_member_2, asset_non_member])
    await db_session.flush()

    group = AssetGroup(tenant_id=tenant_a, name="Prod Web Tier")
    db_session.add(group)
    await db_session.flush()
    db_session.add_all(
        [
            AssetGroupMember(group_id=group.id, asset_id=asset_member_1.id),
            AssetGroupMember(group_id=group.id, asset_id=asset_member_2.id),
        ]
    )
    await db_session.commit()

    day1 = (datetime.now(UTC) - timedelta(days=2)).date()
    day2 = (datetime.now(UTC) - timedelta(days=1)).date()
    db_session.add_all(
        [
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=day1,
                metrics={
                    "avg_risk_exposure_score": 999.0,  # tenant-wide value -- must NOT leak into the group series
                    "risk_model_version_snapshot": "v1",
                    "asset_risk_exposure_scores": {
                        str(asset_member_1.id): 10,
                        str(asset_member_2.id): 20,
                        str(asset_non_member.id): 990,
                    },
                },
                created_at=datetime.now(UTC),
            ),
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=day2,
                metrics={
                    "avg_risk_exposure_score": 999.0,
                    "risk_model_version_snapshot": "v1",
                    "asset_risk_exposure_scores": {
                        str(asset_member_1.id): 30,
                        str(asset_member_2.id): 50,
                        # asset_non_member has no score at all on day2 -- still excluded, not required.
                    },
                },
                created_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.commit()

    overview = await get_analytics_overview(db_session, tenant_a, days=30, scope="group", group_id=group.id)
    assert overview is not None
    by_date = {r["date"]: r["avg_risk_exposure_score"] for r in overview["trend"]}
    assert by_date[day1.isoformat()] == 15.0  # avg(10, 20) -- excludes the non-member's 990
    assert by_date[day2.isoformat()] == 40.0  # avg(30, 50)
    assert overview["scope"] == "group"
    assert overview["group_name"] == "Prod Web Tier"


@pytest.mark.asyncio
async def test_group_trend_none_for_zero_scored_day(db_session, tenant_a):
    """D-06: a day where NONE of the group's current members have a score
    in that day's per-asset dict yields avg_risk_exposure_score = None (a
    rendered gap) -- never 0, even though 0 is a legitimate score value
    elsewhere on this page."""
    await db_session.commit()

    asset_member = Asset(tenant_id=tenant_a, hostname="member.local")
    other_asset = Asset(tenant_id=tenant_a, hostname="other.local")
    db_session.add_all([asset_member, other_asset])
    await db_session.flush()

    group = AssetGroup(tenant_id=tenant_a, name="Empty-Scored Group")
    db_session.add(group)
    await db_session.flush()
    db_session.add(AssetGroupMember(group_id=group.id, asset_id=asset_member.id))
    await db_session.commit()

    day = (datetime.now(UTC) - timedelta(days=1)).date()
    db_session.add(
        DailySnapshot(
            tenant_id=tenant_a,
            snapshot_date=day,
            metrics={
                "avg_risk_exposure_score": 0,
                "risk_model_version_snapshot": "v1",
                # Only the OTHER (non-member) asset has a score this day --
                # the group's own member has none.
                "asset_risk_exposure_scores": {str(other_asset.id): 5},
            },
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    overview = await get_analytics_overview(db_session, tenant_a, days=30, scope="group", group_id=group.id)
    assert overview is not None
    point = next(r for r in overview["trend"] if r["date"] == day.isoformat())
    assert point["avg_risk_exposure_score"] is None


@pytest.mark.asyncio
async def test_cross_tenant_group_id_404(client_factory, db_session, tenant_a, tenant_b, admin_user):
    """T-42-08 IDOR: a group_id belonging to tenant_b, requested by a
    tenant_a user, 404s via list_members' tenant-scoped None-on-miss path
    -- never a fetch-then-403, and no group data leaks into the
    response."""
    await db_session.commit()  # AssetGroup has a real FK to tenants

    tenant_b_group = AssetGroup(tenant_id=tenant_b, name="Tenant B Prod")
    db_session.add(tenant_b_group)
    await db_session.commit()

    client = client_factory(admin_user)
    r = await client.get(f"/api/v1/analytics/overview?scope=group&group_id={tenant_b_group.id}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Asset group not found"


@pytest.mark.asyncio
async def test_asset_ids_threads_into_aging_and_burndown(db_session, tenant_a):
    """D-02/Pitfall 5: group scope re-scopes EVERY chart, not only the
    trend line -- aging + burndown narrow to the group's member
    asset_ids; scope=all still sees the non-member's finding too."""
    await db_session.commit()

    asset_member = Asset(tenant_id=tenant_a, hostname="scoped-member.local")
    asset_non_member = Asset(tenant_id=tenant_a, hostname="scoped-non-member.local")
    db_session.add_all([asset_member, asset_non_member])
    await db_session.flush()

    group = AssetGroup(tenant_id=tenant_a, name="Scoped Group")
    db_session.add(group)
    await db_session.flush()
    db_session.add(AssetGroupMember(group_id=group.id, asset_id=asset_member.id))
    await db_session.commit()

    vuln_member = _seed_vuln(tenant_a, severity="HIGH", status="OPEN", asset_id=asset_member.id)
    vuln_non_member = _seed_vuln(tenant_a, severity="CRITICAL", status="OPEN", asset_id=asset_non_member.id)
    db_session.add_all([vuln_member, vuln_non_member])
    await db_session.commit()

    tenant_wide = await get_analytics_overview(db_session, tenant_a, days=30)
    group_scoped = await get_analytics_overview(db_session, tenant_a, days=30, scope="group", group_id=group.id)
    assert tenant_wide is not None
    assert group_scoped is not None

    def _total_aging(buckets: list[dict]) -> int:
        return sum(v for bucket in buckets for k, v in bucket.items() if k != "bucket")

    assert _total_aging(tenant_wide["aging"]) == 2
    assert _total_aging(group_scoped["aging"]) == 1
    assert tenant_wide["burndown"]["open_backlog"] == 2
    assert group_scoped["burndown"]["open_backlog"] == 1


@pytest.mark.asyncio
async def test_multiple_version_boundaries_each_marked(db_session, tenant_a):
    """UI-SPEC E2: a window spanning 3 distinct risk_model_version_snapshot
    values emits 2 boundaries (v1->v2 AND v2->v3) -- every in-window
    boundary gets its own marker, not just the first/last."""
    day1 = (datetime.now(UTC) - timedelta(days=3)).date()
    day2 = (datetime.now(UTC) - timedelta(days=2)).date()
    day3 = (datetime.now(UTC) - timedelta(days=1)).date()

    db_session.add_all(
        [
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=day1,
                metrics={"avg_risk_exposure_score": 10.0, "risk_model_version_snapshot": "v1"},
                created_at=datetime.now(UTC),
            ),
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=day2,
                metrics={"avg_risk_exposure_score": 20.0, "risk_model_version_snapshot": "v2"},
                created_at=datetime.now(UTC),
            ),
            DailySnapshot(
                tenant_id=tenant_a,
                snapshot_date=day3,
                metrics={"avg_risk_exposure_score": 30.0, "risk_model_version_snapshot": "v3"},
                created_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.commit()

    rows = await get_scoped_trend_series(db_session, tenant_a, start=day1, end=day3)
    boundaries = detect_version_boundaries(rows)

    assert boundaries == [
        {"date": day2.isoformat(), "old_version": "v1", "new_version": "v2"},
        {"date": day3.isoformat(), "old_version": "v2", "new_version": "v3"},
    ]


@pytest.mark.asyncio
async def test_custom_range_span_capped(client_factory, db_session, tenant_a, admin_user):
    """T-42-09 DoS guard: a custom range beyond MAX_ANALYTICS_WINDOW_DAYS
    422s server-side; a to<from range 422s too -- never silently clamped,
    never accepted."""
    await db_session.commit()

    client = client_factory(admin_user)

    too_wide_from = (datetime.now(UTC) - timedelta(days=MAX_ANALYTICS_WINDOW_DAYS + 30)).date().isoformat()
    today = datetime.now(UTC).date().isoformat()
    r = await client.get(f"/api/v1/analytics/overview?scope=all&from={too_wide_from}&to={today}")
    assert r.status_code == 422

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    r2 = await client.get(f"/api/v1/analytics/overview?scope=all&from={today}&to={yesterday}")
    assert r2.status_code == 422
