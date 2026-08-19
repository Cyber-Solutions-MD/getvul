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

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.risk_score import (
    RISK_SCORE_TIER_CRITICAL,
    RISK_SCORE_TIER_HIGH,
    RISK_SCORE_TIER_MEDIUM,
)
from app.audit import AuditLog
from app.encryption import decrypt_value
from app.notifications.service import create_notification
from app.tenants.models import Tenant
from app.vulnerabilities.models import SlaEscalationEvent, Vulnerability

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
    excepted_seconds: int = 0,
) -> tuple[datetime, str]:
    """D-02: the tier+elapsed-% state formula. The approaching window scales
    per-tier automatically (80% of a 7d window vs 80% of a 90d window) since
    it's computed as a % of `tier_days`, not a fixed lead time.

    Phase 39 / D-16: `excepted_seconds` (default 0, fully backward
    compatible) is the total time this finding spent under a now-LAPSED
    exception (D-04 natural expiry OR D-17 early revocation) --
    interval-merged (Pitfall 4) and computed by
    `exceptions/service.py::lapsed_exception_seconds`. Shifting the
    effective start forward is the ENTIRE subtraction mechanism: the
    on_track/approaching/breached thresholds themselves are unchanged
    (still `tier_days`/`approaching_pct`), only where the clock starts
    counting from moves.
    """
    effective_start = first_detected_at + timedelta(seconds=excepted_seconds)
    sla_due_at = effective_start + timedelta(days=tier_days)
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


# ── Escalation firing (Phase 36 Plan 03 / SLA-03, D-05/D-06/D-07/D-08) ──────
#
# detect_and_escalate is called immediately after run_sla_tier_pass in the
# SAME scheduler-tick isolation block (scheduler.py) -- it re-resolves each
# OPEN/IN_PROGRESS finding's live sla_state via the SAME resolve_state_for_
# vuln Plan 01 already ships, and for every approaching/breached transition
# at or above the tenant's configured tier floor, fires that transition's
# routed channels EXACTLY ONCE -- gated by a DB check-before-insert
# (_escalation_already_fired) backstopped by the uq_escalation_once
# UniqueConstraint (Plan 02) so the once-only guarantee holds even under a
# hypothetical concurrent double-tick (D-07). Every fire is audited
# (sla.escalation_fire) and a breach's channel fan-out is twinned by exactly
# one in-app notification (category="sla_escalation", D-08) -- reconciled
# against the legacy alerts.py::_check_sla_breaches, which this plan retires
# to a no-op so a breach never double-fires two unrelated in-app signals.

# D-06/Pitfall 5: ordered tier rank so a NULL-score severity-fallback tier
# (severity_to_tier) gates against tier_floor identically to a scored
# finding's tier (tier_for_score) -- both resolve to the same 3-value
# vocabulary before this comparison ever runs.
_TIER_RANK: dict[str, int] = {"moderate": 1, "high": 2, "critical": 3}

# D-07: the escalation-event row's `from_state` records the natural
# predecessor of `to_state` in the on_track -> approaching -> breached
# progression -- informational context for the auditable history; NOT part
# of the once-only gate's identity key (that's tenant+vulnerability+
# to_state+channel only, see uq_escalation_once).
_PREDECESSOR_STATE: dict[str, str] = {"approaching": "on_track", "breached": "approaching"}


def _tier_meets_floor(tier: str | None, tier_floor: str | None) -> bool:
    """D-06: does `tier` meet or exceed the tenant's configured tier floor?

    Default floor is "moderate" (the lowest tracked tier) when the tenant
    hasn't configured one -- escalation is ON by default for every tracked
    tier until a tenant deliberately dials it down.
    """
    if tier is None:
        return False
    floor = tier_floor or "moderate"
    return _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(floor, 0)


async def _escalation_already_fired(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    vuln_id: uuid.UUID,
    to_state: str,
    channel: str,
) -> bool:
    """D-07 check-before-insert -- mirrors `alerts.py::_notification_exists`
    but with NO time window: "ever fired for this exact transition+channel",
    not a lookback."""
    result = await db.execute(
        select(func.count(SlaEscalationEvent.id)).where(
            SlaEscalationEvent.tenant_id == tenant_id,
            SlaEscalationEvent.vulnerability_id == vuln_id,
            SlaEscalationEvent.to_state == to_state,
            SlaEscalationEvent.channel == channel,
        )
    )
    return result.scalar_one() > 0


def _build_channel_config(sla_config: dict[str, Any], channel: str, tenant: Tenant) -> dict[str, Any]:
    """Assembles the per-call `config` dict `dispatch_channel` expects,
    decrypting the Fernet-at-rest secret server-side (D-14, Plan 05).
    Email's config lives across TWO different Tenant columns
    (`sla_config.channels.email.to` + the separate `Tenant.smtp_config`) --
    36-02-SUMMARY's documented merge contract."""
    channels = sla_config.get("channels") or {}
    chan = channels.get(channel) or {}
    if channel in ("slack", "teams"):
        url = chan.get("url")
        return {"url": decrypt_value(url) if url else None}
    if channel == "pagerduty":
        routing_key = chan.get("routing_key")
        return {"routing_key": decrypt_value(routing_key) if routing_key else None}
    if channel == "email":
        return {"to": chan.get("to") or [], "smtp_config": tenant.smtp_config or {}}
    return {}


async def _audit_escalation_fire(
    db: AsyncSession,
    tenant: Tenant,
    vuln: Vulnerability,
    *,
    from_state: str,
    to_state: str,
    channel: str,
    tier: str | None,
    delivery_status: str,
    error_message: str | None,
) -> None:
    """D-07: every escalation fire is audited. Constructs `AuditLog`
    directly rather than calling the shared `app.audit.audit()` helper with
    `user=None` -- that helper's None-user branch writes
    `tenant_id=uuid.UUID(int=0)` (a nil tenant), which would mis-bucket this
    genuinely tenant-scoped row and break the "every audit row tenant_id-
    scoped" convention. Mirrors this codebase's existing scheduler-
    originated-audit precedent for the identical problem:
    `app/ai/audit.py::audit_log_ai_call` / `encryption.py::rotate_
    credentials`, both of which write `AuditLog` directly with a real
    tenant_id + a `"system:scheduler"`/`"system:cli"` `user_email`.
    """
    log = AuditLog(
        tenant_id=tenant.id,
        user_id=None,
        user_email="system:scheduler",
        action="sla.escalation_fire",
        resource_type="vulnerability",
        resource_id=str(vuln.id),
        details={
            "channel": channel,
            "from_state": from_state,
            "to_state": to_state,
            "tier": tier,
            "delivery_status": delivery_status,
            "error_message": error_message,
        },
        ip_address=None,
        created_at=datetime.now(UTC),
    )
    db.add(log)


async def detect_and_escalate(db: AsyncSession, tenant: Tenant) -> dict[str, Any]:
    """Scheduler-tick entrypoint (SLA-03, D-05/D-06/D-07/D-08) -- called
    immediately after `run_sla_tier_pass` in the same isolated tick block
    (scheduler.py). For every OPEN/IN_PROGRESS finding whose live sla_state
    is `approaching` or `breached` AND whose tier meets the tenant's
    configured floor, fires every channel routed to that transition type
    EXACTLY ONCE (check-before-insert + the uq_escalation_once
    UniqueConstraint backstop), audits every fire, and -- for a breach that
    newly fired at least one channel this pass -- emits exactly one in-app
    `category="sla_escalation"` notification twin (D-08).

    Pattern 1 isolation: a single channel's decrypt/dispatch failure (or a
    concurrent-double-tick's uq_escalation_once collision) is caught at the
    per-channel level and never propagates -- one bad channel/tenant/vuln
    cannot stall this pass for any other channel/tenant/vuln in the same
    tick. Own-flush/no-own-commit -- matches `run_sla_tier_pass`'s isolation
    contract; the CALLER (scheduler.py) commits once per tick.
    """
    from app.notifications.escalation_channels import dispatch_channel

    now = datetime.now(UTC)
    policy = get_tier_policy(tenant)
    sla_config = tenant.sla_config or {}
    tier_floor = sla_config.get("tier_floor")
    routing = sla_config.get("routing") or {}

    result = await db.execute(
        select(Vulnerability, Asset)
        .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
        .where(
            Vulnerability.tenant_id == tenant.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
    )
    rows = result.all()

    fired = 0
    notified = 0
    for vuln, asset in rows:
        _due_at, to_state = resolve_state_for_vuln(vuln, policy, now)
        if to_state not in ("approaching", "breached"):
            continue

        score = vuln.risk_exposure_score
        tier = tier_for_score(score) if score is not None else severity_to_tier(vuln.severity)
        if not _tier_meets_floor(tier, tier_floor):
            continue

        channels = routing.get(to_state) or []
        hostname = asset.hostname if asset else None
        any_new_fire = False

        for channel in channels:
            try:
                if await _escalation_already_fired(db, tenant.id, vuln.id, to_state, channel):
                    continue

                from_state = _PREDECESSOR_STATE.get(to_state, "on_track")
                event = SlaEscalationEvent(
                    tenant_id=tenant.id,
                    vulnerability_id=vuln.id,
                    from_state=from_state,
                    to_state=to_state,
                    channel=channel,
                    fired_at=now,
                    delivery_status="pending",
                )
                try:
                    async with db.begin_nested():
                        db.add(event)
                        await db.flush()
                except IntegrityError:
                    # W4 hardening: another pass already reserved this exact
                    # (finding, to_state, channel) -- skip the POST entirely,
                    # the UniqueConstraint guards the outbound send itself.
                    continue

                try:
                    config = _build_channel_config(sla_config, channel, tenant)
                    outcome = await dispatch_channel(
                        channel,
                        config,
                        {
                            "vuln_id": str(vuln.id),
                            "cve_id": vuln.cve_id,
                            "hostname": hostname,
                            "tier": tier,
                            "tier_days": policy["tier_days"].get(tier) if tier else None,
                            "to_state": to_state,
                        },
                    )
                except Exception as e:  # decrypt/dispatch failure -- never blocks the reservation
                    outcome = {"ok": False, "error": str(e)}

                delivery_status = "sent" if outcome.get("ok") else "failed"
                error_message = None if outcome.get("ok") else outcome.get("error")

                try:
                    # Own savepoint: if the status-update+audit write itself
                    # fails (e.g. a transient DB error), roll back ONLY this
                    # bookkeeping -- the reservation from the savepoint above
                    # is already merged into the outer transaction, so the
                    # once-only guarantee holds regardless, and this failure
                    # cannot abort the outer transaction for other channels/
                    # vulns/tenants in the same tick (Pattern 1 / T-36-fire-
                    # isolation).
                    async with db.begin_nested():
                        event.delivery_status = delivery_status
                        event.error_message = error_message
                        await _audit_escalation_fire(
                            db,
                            tenant,
                            vuln,
                            from_state=from_state,
                            to_state=to_state,
                            channel=channel,
                            tier=tier,
                            delivery_status=delivery_status,
                            error_message=error_message,
                        )
                        await db.flush()
                except Exception as e:
                    logger.error(
                        "sla_escalation_bookkeeping_error",
                        tenant_id=str(tenant.id),
                        vuln_id=str(vuln.id),
                        channel=channel,
                        to_state=to_state,
                        error=str(e),
                    )

                fired += 1
                any_new_fire = True
            except Exception as e:
                logger.error(
                    "sla_escalation_channel_error",
                    tenant_id=str(tenant.id),
                    vuln_id=str(vuln.id),
                    channel=channel,
                    to_state=to_state,
                    error=str(e),
                )
                continue

        if to_state == "breached" and any_new_fire:
            try:
                resource_id = vuln.cve_id or str(vuln.id)
                # Own savepoint (same Pattern-1 reasoning as the per-channel
                # bookkeeping above): create_notification() does its own
                # db.add()+flush() -- isolate it so a notification-write
                # failure cannot abort the outer tick transaction.
                async with db.begin_nested():
                    await create_notification(
                        db,
                        tenant_id=tenant.id,
                        title=f"SLA Breach: {resource_id}",
                        message=(
                            f"{resource_id} on {hostname or 'an unassigned host'} — "
                            f"breached the {tier or 'unscored'} tier SLA"
                        ),
                        severity="critical",
                        category="sla_escalation",
                        resource_type="vulnerability",
                        resource_id=resource_id,
                        details={"tier": tier, "to_state": to_state, "channels_notified": channels},
                    )
                notified += 1
            except Exception as e:
                logger.error(
                    "sla_escalation_notify_error",
                    tenant_id=str(tenant.id),
                    vuln_id=str(vuln.id),
                    error=str(e),
                )

    logger.info(
        "sla_escalation_pass_completed",
        tenant_id=str(tenant.id),
        fired=fired,
        notified=notified,
    )
    return {"tenant_id": str(tenant.id), "fired": fired, "notified": notified}
