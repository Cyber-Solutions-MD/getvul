"""Risk-tier-keyed SLA engine (Phase 36 / SLA-01, SLA-02 — LEAD TRACER).

Replaces the flat severity-keyed SLA (`sla_service.py`) as the PRIMARY
source of due dates + live state for OPEN/IN_PROGRESS findings. Per D-01,
policy is keyed off the v4.0 `Vulnerability.risk_exposure_score` tier bands
(`RISK_SCORE_TIER_CRITICAL/HIGH/MEDIUM` from `assets/risk_score.py`),
independent of the `cutover_risk_exposure_scoring` flag — this engine reads
the raw shadow-computed score directly, regardless of which score is
PRIMARY for sort/display elsewhere.

`sla_service.py`'s severity-keyed engine is KEPT, unmodified — its
`DEFAULT_SLA_DAYS`/`get_sla_days` are NOT reused here. Per D-03/D-12, this
module defines its OWN small, explicit severity->tier fallback map
(`severity_to_tier`) for findings with a NULL `risk_exposure_score`; the two
"severity SLA" concepts (the old per-severity day counts vs. this fallback's
tier mapping) are deliberately different values.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.risk_score import (
    RISK_SCORE_TIER_CRITICAL,
    RISK_SCORE_TIER_HIGH,
    RISK_SCORE_TIER_MEDIUM,
)
from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# D-01: default tier-keyed SLA policy (days per tier) — critical 7d / high
# 30d / moderate 90d, per the roadmap's SLA-01 default. A tenant may
# override any subset via Tenant.sla_config["tier_policy"] (get_tier_policy
# below does the custom-or-default merge, mirroring sla_service.get_sla_days).
DEFAULT_TIER_POLICY: dict[str, int] = {"critical": 7, "high": 30, "moderate": 90}

# D-02: default % of the tier window elapsed before a finding is
# "approaching" its due date. Illustrative per CONTEXT.md — tenant-
# configurable via Tenant.sla_config["approaching_pct"].
DEFAULT_APPROACHING_PCT = 0.8


def tier_for_score(score: int | None) -> str | None:
    """D-12: risk-tier for a v4.0 `risk_exposure_score`.

    Returns None below RISK_SCORE_TIER_MEDIUM (20) — such findings are
    always on_track, carry no due date, and never escalate (the policy
    stays at exactly three tiers; no 4th "low" tier is added). None is also
    the return for a NULL score itself — callers needing the D-03 severity
    fallback must branch on `score is None` BEFORE calling this and use
    `severity_to_tier` instead (see `resolve_state_for_vuln`).
    """
    if score is None:
        return None
    if score >= RISK_SCORE_TIER_CRITICAL:
        return "critical"
    if score >= RISK_SCORE_TIER_HIGH:
        return "high"
    if score >= RISK_SCORE_TIER_MEDIUM:
        return "moderate"
    return None


def severity_to_tier(severity: str) -> str:
    """D-03/D-12 fallback map for a NULL `risk_exposure_score`.

    CRITICAL->critical, HIGH->high, MEDIUM/LOW/INFO->moderate — an explicit,
    tested lookup (not a re-derivation of the score tier boundaries).
    """
    if severity == "CRITICAL":
        return "critical"
    if severity == "HIGH":
        return "high"
    return "moderate"


def get_tier_policy(tenant: Tenant | None) -> dict[str, Any]:
    """Custom-or-default merge over `Tenant.sla_config` (mirrors
    `sla_service.get_sla_days`'s per-key fallback shape).

    Returns {"tier_days": {"critical": int, "high": int, "moderate": int},
    "approaching_pct": float}.
    """
    tier_days = dict(DEFAULT_TIER_POLICY)
    approaching_pct = DEFAULT_APPROACHING_PCT
    if tenant and tenant.sla_config:
        custom_tier_days = tenant.sla_config.get("tier_policy")
        if custom_tier_days:
            tier_days = {
                "critical": custom_tier_days.get("critical", DEFAULT_TIER_POLICY["critical"]),
                "high": custom_tier_days.get("high", DEFAULT_TIER_POLICY["high"]),
                "moderate": custom_tier_days.get("moderate", DEFAULT_TIER_POLICY["moderate"]),
            }
        approaching_pct = tenant.sla_config.get("approaching_pct", DEFAULT_APPROACHING_PCT)
    return {"tier_days": tier_days, "approaching_pct": approaching_pct}


def compute_sla_state(
    *,
    first_detected_at: datetime,
    tier_days: int,
    approaching_pct: float,
    now: datetime,
) -> tuple[datetime, str]:
    """D-02: the tier+elapsed-% state formula. The approaching window scales
    per-tier automatically (80% of a 7d window vs 80% of a 90d window) since
    it's computed as a % of `tier_days`, not a fixed lead time.
    """
    sla_due_at = first_detected_at + timedelta(days=tier_days)
    approaching_at = sla_due_at - timedelta(days=tier_days * (1 - approaching_pct))
    if now >= sla_due_at:
        return sla_due_at, "breached"
    if now >= approaching_at:
        return sla_due_at, "approaching"
    return sla_due_at, "on_track"


def resolve_state_for_vuln(
    vuln: Vulnerability,
    policy: dict[str, Any],
    now: datetime,
) -> tuple[datetime | None, str]:
    """Per-finding SLA resolution (D-01/D-03/D-12):
    (a) `tier_for_score` on `risk_exposure_score` when the finding is scored,
    (b) `severity_to_tier` fallback when `risk_exposure_score` is NULL (D-03),
    (c) (None, "not_tracked") when a SCORED finding's tier is None
        (score < RISK_SCORE_TIER_MEDIUM, D-12) — severity is irrelevant
        once a finding is scored.
    """
    score = vuln.risk_exposure_score
    tier: str | None
    if score is None:
        tier = severity_to_tier(vuln.severity)
    else:
        tier = tier_for_score(score)
        if tier is None:
            return None, "not_tracked"

    tier_days = policy["tier_days"][tier]
    approaching_pct = policy["approaching_pct"]
    return compute_sla_state(
        first_detected_at=vuln.first_detected_at,
        tier_days=tier_days,
        approaching_pct=approaching_pct,
        now=now,
    )


async def run_sla_tier_pass(db: AsyncSession, tenant: Tenant) -> dict[str, Any]:
    """Scheduler-tick entrypoint (D-01/D-02/D-08) — replaces the old
    `backfill_sla_due_dates` + `check_sla_breaches` calls in scheduler.py.

    For every OPEN/IN_PROGRESS finding belonging to `tenant`: resolves the
    tier-based `sla_due_at` (via `resolve_state_for_vuln` + the tenant's
    policy) and writes it, plus the `sla_breached` DERIVED MIRROR (D-08) so
    already-shipped consumers (ticket SlaPill, metrics, dashboard) keep
    working unmodified. After flushing, resyncs every affected ticket
    group's materialized SLA (Pitfall 2 — ticket `sla_due_at` is a MIN
    aggregate over linked vulns and goes stale otherwise).

    Own-session/own-try-except/own-commit isolation (Pattern 1) is the
    CALLER's responsibility (scheduler.py's existing shape) — this function
    only flushes, it does not commit.
    """
    now = datetime.now(UTC)
    policy = get_tier_policy(tenant)

    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.tenant_id == tenant.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    vulns = result.scalars().all()

    updated = 0
    for vuln in vulns:
        due_at, state = resolve_state_for_vuln(vuln, policy, now)
        breached = state == "breached"
        if vuln.sla_due_at != due_at or vuln.sla_breached != breached:
            vuln.sla_due_at = due_at
            vuln.sla_breached = breached
            updated += 1

    # Pitfall 2: flush so the new sla_due_at values are visible to the
    # ticket-group MIN aggregate inside recompute_ticket_sla below.
    await db.flush()

    from sqlalchemy import distinct
    from sqlalchemy import select as _select

    from app.ticketing.models import Ticket
    from app.ticketing.service import recompute_ticket_sla

    ticket_urls = (
        (await db.execute(_select(distinct(Ticket.external_ticket_url)).where(Ticket.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    for ticket_url in ticket_urls:
        await recompute_ticket_sla(db, ticket_url, tenant.id)

    logger.info(
        "sla_tier_pass_completed",
        tenant_id=str(tenant.id),
        updated=updated,
        ticket_groups=len(ticket_urls),
    )

    return {"tenant_id": str(tenant.id), "updated": updated}
