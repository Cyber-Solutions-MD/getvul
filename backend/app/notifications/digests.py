"""ALERT-02 -- scheduled per-owner (email) and per-team (shared channel)
digests, assembled from Phase 36's SLA state (`resolve_state_for_vuln`) and
Phase 39's exception expiry (`ExceptionRecord.expires_at`), gated by a NEW
wall-clock send-hour check, rendered as escaped HTML, empty-suppressed, and
dispatched on the existing in-process scheduler (D-11..D-15, D-20/D-21).

Entry point (called from `scheduler.py::_scheduler_loop`, own isolated
try/except block, every tick -- the wall-clock gate below is what actually
decides whether a given tenant is due, not an elapsed-hours-since-last-send
counter like `reports.py`'s scheduled-report due-check):

    run_digests(db) -> int  # count of digests actually sent this tick

Design notes:
  - D-12/Pitfall 4: `_send_hour_due` is a pure wall-clock gate ("past the
    tenant's configured send_hour in Tenant.timezone AND not yet sent this
    calendar period") backed by the DURABLE `Tenant.alerting_last_digest_
    sent_at` column (migration 051) -- never an in-memory dict, which would
    re-fire on every process restart.
  - D-13: sections are assembled in a fixed order -- due, breaching,
    newly-critical, expiring-exceptions -- each independently queried and
    D-20-excluded (`status NOT IN (SUPPRESSED, FALSE_POSITIVE)` +
    `~active_exception_subquery`). The UI-SPEC's email copy re-orders the
    RENDERED headers for urgency (breaching leads); the underlying dict key
    order documented by D-13 is unchanged -- see `_SECTION_ORDER` in the
    render step for the reader-facing reorder.
  - D-14: a recipient (owner OR team) whose sections are ALL empty gets
    nothing -- no "all clear" digest, ever.
  - D-08/D-09: owner digests are per-person (grouped by `get_directory_user`
    resolution across their owned assets) and deliver via email; team
    digests are per-`AssetGroup` and deliver via the shared
    Slack/Teams channel configured under `routing.digest_team`
    (`_build_channel_config` + `dispatch_channel`, the exact Phase 36
    seam D-07/D-09/D-19 reuses).
  - D-15/T-40-09: every finding-derived string (CVE id, hostname) is
    `html.escape`-d before landing in the HTML body -- scanner-origin text
    is untrusted and rendered inside a real email client.
"""

from __future__ import annotations

import html
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.directory import get_directory_user
from app.assets.models import Asset, AssetGroup, AssetGroupMember
from app.email import send_email
from app.exceptions.models import ExceptionRecord
from app.exceptions.service import active_exception_subquery, lapsed_exception_seconds
from app.notifications.alerting_config import merged_alerting_config
from app.notifications.escalation_channels import dispatch_channel
from app.tenants.models import Tenant
from app.vulnerabilities.models import Vulnerability
from app.vulnerabilities.sla_tier_service import (
    _build_channel_config,
    get_tier_policy,
    resolve_state_for_vuln,
    tier_for_score,
)

logger = structlog.get_logger()

# D-15: illustrative top-N cap per section, plus an "and N more" overflow
# line with a dashboard deep-link -- keeps the email scannable/bounded.
TOP_N_PER_SECTION = 10

# D-15 backstop (Gmail web + Apple Mail verified, see SUMMARY): a hostname
# longer than this truncates with an ellipsis rather than breaking the
# table layout.
HOSTNAME_TRUNCATE_LEN = 40

# "Expiring soon" horizon for the expiring-exceptions section -- not pinned
# by any D-ID; chosen as a reasonable "act before it lapses" window,
# independent of the tier-day SLA windows above.
EXPIRING_EXCEPTION_HORIZON_DAYS = 7

# D-13 canonical section order (assembly). The rendered EMAIL headers use a
# different, urgency-led order (_SECTION_ORDER below) per the UI-SPEC.
_ASSEMBLY_SECTION_KEYS = ("due", "breaching", "newly_critical", "expiring_exceptions")

# UI-SPEC "Digest email copy" -- section order & headers, reordered for
# urgency (breaching leads) vs. D-13's due-first listing order.
_SECTION_ORDER = ("breaching", "due", "newly_critical", "expiring_exceptions")
_SECTION_LABELS: dict[str, str] = {
    "breaching": "Breaching SLA",
    "due": "Due soon",
    "newly_critical": "Newly critical",
    "expiring_exceptions": "Exceptions expiring soon",
}

_DASHBOARD_URL = "/dashboard/vulnerabilities"


# ---------------------------------------------------------------------------
# D-12/Pitfall 4: wall-clock send-hour gate
# ---------------------------------------------------------------------------


def _tenant_zone(tenant: Tenant) -> ZoneInfo:
    try:
        return ZoneInfo(tenant.timezone or "UTC")
    except ZoneInfoNotFoundError:
        # Defensive -- an invalid/unknown tz string must never crash the
        # scheduler tick; fall back to UTC rather than raising.
        logger.warning("digest_invalid_tenant_timezone", tenant_id=str(tenant.id), timezone=tenant.timezone)
        return ZoneInfo("UTC")


def _period_key(local_dt: datetime, cadence: str) -> tuple[int, int]:
    """D-11: daily -> (year, day-of-year); weekly -> ISO (year, week) --
    two calendar periods compare equal iff they are the SAME period, so a
    tick within the same day/week as the last send is a no-op regardless of
    how many times the gate is checked."""
    if cadence == "weekly":
        iso = local_dt.isocalendar()
        return (iso[0], iso[1])
    return (local_dt.year, local_dt.timetuple().tm_yday)


def _send_hour_due(tenant: Tenant, *, now: datetime) -> bool:
    """D-12: due when `local_now.hour >= send_hour` AND
    `alerting_last_digest_sent_at` (durable, Pitfall 4) is not within the
    current period (calendar day for daily / ISO week for weekly).

    Deliberately NOT `reports.py`'s scheduled-report due-check's
    elapsed-hours-since-last-send shape -- that gate drifts with process
    restarts and isn't tied to a business hour; this one always checks
    against a real wall-clock hour in the tenant's own timezone.
    """
    config = merged_alerting_config(tenant)
    send_hour = config.get("send_hour", 8)
    cadence = config.get("cadence", "daily")
    tz = _tenant_zone(tenant)
    local_now = now.astimezone(tz)

    if local_now.hour < send_hour:
        return False

    last_sent = tenant.alerting_last_digest_sent_at
    if last_sent is None:
        return True

    local_last = last_sent.astimezone(tz)
    return _period_key(local_now, cadence) != _period_key(local_last, cadence)


# ---------------------------------------------------------------------------
# D-13/D-20: section assembly
# ---------------------------------------------------------------------------


def _digest_window_hours(config: dict[str, Any]) -> int:
    """The newly-critical section's lookback window mirrors the digest's
    own cadence period (a daily digest surfaces the last 24h of newly
    CRITICAL findings; a weekly digest surfaces the last 7 days) -- this is
    a digest WINDOW, not the 2h fire-once dedup `_check_new_critical_vulns`
    uses for its own, unrelated, real-time in-app alert."""
    return 24 * 7 if config.get("cadence") == "weekly" else 24


def _finding_row(vuln: Vulnerability, asset: Asset | None, *, sla_due_at: datetime | None = None) -> dict[str, Any]:
    return {
        "vulnerability_id": vuln.id,
        "cve_id": vuln.cve_id,
        "hostname": asset.hostname if asset else None,
        "severity": vuln.severity,
        "risk_exposure_score": vuln.risk_exposure_score,
        "sla_due_at": sla_due_at,
        "expires_at": None,
    }


def _sort_by_risk(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("risk_exposure_score") or 0, reverse=True)


async def _assemble_sections(
    db: AsyncSession,
    tenant: Tenant,
    asset_ids: set[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """D-13: assembles the four ordered sections -- due, breaching,
    newly-critical, expiring-exceptions -- each independently tenant-scoped
    and D-20-excluded. `asset_ids`, when provided, additionally scopes
    every section to a single recipient's (owner or team) assets; `None`
    means tenant-wide (used by e.g. a future "send test digest" preview).
    Every returned list is FULL (uncapped, risk-sorted) -- the top-N cap +
    "and N more" overflow line is a RENDER-time concern (`_render_digest_
    html`), not an assembly-time one.
    """
    now = now or datetime.now(UTC)
    config = merged_alerting_config(tenant)
    policy = get_tier_policy(tenant)

    asset_scope = [Vulnerability.asset_id.in_(asset_ids)] if asset_ids is not None else []

    # ── due (approaching) + breaching (breached) ──────────────────────────
    rows = (
        await db.execute(
            select(Vulnerability, Asset)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant.id,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.status.notin_(["SUPPRESSED", "FALSE_POSITIVE"]),
                ~active_exception_subquery(tenant.id, now),
                *asset_scope,
            )
        )
    ).all()

    keys = {(v.cve_id, v.asset_id) for v, _asset in rows if v.cve_id and v.asset_id}
    lapsed_by_key = await lapsed_exception_seconds(db, tenant.id, keys, now) if keys else {}

    due_items: list[dict[str, Any]] = []
    breaching_items: list[dict[str, Any]] = []
    for vuln, asset in rows:
        excepted_seconds = 0
        if vuln.cve_id and vuln.asset_id:
            excepted_seconds = lapsed_by_key.get((vuln.cve_id, vuln.asset_id), 0)
        due_at, state = resolve_state_for_vuln(vuln, policy, now, excepted_seconds=excepted_seconds)
        if state == "approaching":
            due_items.append(_finding_row(vuln, asset, sla_due_at=due_at))
        elif state == "breached":
            breaching_items.append(_finding_row(vuln, asset, sla_due_at=due_at))

    # ── newly-critical ─────────────────────────────────────────────────────
    window_hours = _digest_window_hours(config)
    cutoff = now - timedelta(hours=window_hours)
    nc_rows = (
        await db.execute(
            select(Vulnerability, Asset)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant.id,
                Vulnerability.severity == "CRITICAL",
                Vulnerability.first_detected_at >= cutoff,
                Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
                Vulnerability.status.notin_(["SUPPRESSED", "FALSE_POSITIVE"]),
                ~active_exception_subquery(tenant.id, now),
                *asset_scope,
            )
        )
    ).all()
    newly_critical_items = [_finding_row(vuln, asset) for vuln, asset in nc_rows]

    # ── expiring-exceptions ────────────────────────────────────────────────
    horizon_cutoff = now + timedelta(days=EXPIRING_EXCEPTION_HORIZON_DAYS)
    exc_filters = [
        ExceptionRecord.tenant_id == tenant.id,
        ExceptionRecord.revoked_at.is_(None),
        ExceptionRecord.expires_at > now,
        ExceptionRecord.expires_at <= horizon_cutoff,
    ]
    if asset_ids is not None:
        group_ids_subq = select(AssetGroupMember.group_id).where(AssetGroupMember.asset_id.in_(asset_ids))
        exc_filters.append(
            or_(
                ExceptionRecord.asset_id.in_(asset_ids),
                ExceptionRecord.asset_group_id.in_(group_ids_subq),
            )
        )
    exc_rows = (await db.execute(select(ExceptionRecord).where(*exc_filters))).scalars().all()

    asset_id_lookup = {r.asset_id for r in exc_rows if r.asset_id}
    assets_by_id: dict[uuid.UUID, Asset] = {}
    if asset_id_lookup:
        asset_rows = (await db.execute(select(Asset).where(Asset.id.in_(asset_id_lookup)))).scalars().all()
        assets_by_id = {a.id: a for a in asset_rows}

    expiring_items: list[dict[str, Any]] = [
        {
            "vulnerability_id": record.vulnerability_id,
            "cve_id": record.cve_id,
            "hostname": assets_by_id[record.asset_id].hostname if record.asset_id in assets_by_id else None,
            "severity": None,
            "risk_exposure_score": None,
            "sla_due_at": None,
            "expires_at": record.expires_at,
        }
        for record in exc_rows
    ]
    expiring_items.sort(key=lambda item: item["expires_at"] or now)

    return {
        "due": _sort_by_risk(due_items),
        "breaching": _sort_by_risk(breaching_items),
        "newly_critical": _sort_by_risk(newly_critical_items),
        "expiring_exceptions": expiring_items,
    }


def _sections_empty(sections: dict[str, list[dict[str, Any]]]) -> bool:
    return not any(sections.get(key) for key in _ASSEMBLY_SECTION_KEYS)


# ---------------------------------------------------------------------------
# D-15/T-40-09: HTML rendering (every finding-derived string is escaped)
# ---------------------------------------------------------------------------


def _truncate_hostname(hostname: str | None) -> str:
    if not hostname:
        return "Unknown host"
    if len(hostname) > HOSTNAME_TRUNCATE_LEN:
        return hostname[: HOSTNAME_TRUNCATE_LEN - 1] + "…"
    return hostname


def _render_section_rows(items: list[dict[str, Any]]) -> str:
    capped = items[:TOP_N_PER_SECTION]
    overflow = len(items) - len(capped)
    rows_html = ""
    for item in capped:
        cve = html.escape(item.get("cve_id") or "Unknown CVE")
        hostname = html.escape(_truncate_hostname(item.get("hostname")))
        badge = ""
        if item.get("sla_due_at"):
            badge = html.escape(item["sla_due_at"].strftime("%Y-%m-%d"))
        elif item.get("expires_at"):
            badge = html.escape(item["expires_at"].strftime("%Y-%m-%d"))
        badge_html = f" &mdash; {badge}" if badge else ""
        rows_html += (
            '<tr><td style="padding:4px 0;font-size:13px;color:#1A1430;">'
            f"&#9650; {cve} on {hostname}{badge_html}</td></tr>"
        )
    if overflow > 0:
        rows_html += (
            '<tr><td style="padding:4px 0;font-size:13px;">'
            f'<a href="{html.escape(_DASHBOARD_URL)}" style="color:#5B4CDB;">and {overflow} more &rarr;</a>'
            "</td></tr>"
        )
    return rows_html


def _render_digest_html(
    sections: dict[str, list[dict[str, Any]]],
    *,
    recipient_label: str | None = None,
    dashboard_url: str = _DASHBOARD_URL,
) -> str:
    """D-15: light-background HTML (email clients frequently force light
    backgrounds regardless of the tenant's app theme), top-N per section +
    an "and N more" overflow line + a dashboard deep-link. Every
    finding-derived string is `html.escape`-d before interpolation
    (T-40-09 -- CVE ids/hostnames are scanner-origin, untrusted text)."""
    total = sum(len(sections.get(key) or []) for key in _ASSEMBLY_SECTION_KEYS)

    body_parts: list[str] = []
    for key in _SECTION_ORDER:
        items = sections.get(key) or []
        if not items:
            continue
        label = html.escape(_SECTION_LABELS[key])
        body_parts.append(
            '<table role="presentation" style="width:100%;margin-top:32px;" cellpadding="0" cellspacing="0">'
            f'<tr><td style="font-size:14px;font-weight:600;color:#1A1430;padding-bottom:8px;">{label}</td></tr>'
            f"{_render_section_rows(items)}"
            "</table>"
        )
    sections_html = "".join(body_parts) or '<p style="color:#1A1430;font-size:13px;">Nothing to report.</p>'

    greeting = html.escape(recipient_label) if recipient_label else "there"
    return (
        '<html><body style="background:#FFFFFF;color:#1A1430;font-family:Inter,Arial,sans-serif;">'
        f'<p style="font-size:13px;color:#1A1430;">Hi {greeting},</p>'
        f'<p style="font-size:13px;color:#1A1430;">{total} findings need attention.</p>'
        f"{sections_html}"
        f'<p style="font-size:12px;color:#6B6488;margin-top:32px;">'
        f'<a href="{html.escape(dashboard_url)}" style="color:#5B4CDB;">View in GetVul &rarr;</a></p>'
        "</body></html>"
    )


def _digest_subject(config: dict[str, Any], total: int) -> str:
    prefix = "Your weekly GetVul digest" if config.get("cadence") == "weekly" else "Your GetVul digest"
    return f"{prefix} — {total} findings need attention"


def _digest_plain_text(sections: dict[str, list[dict[str, Any]]]) -> str:
    lines: list[str] = []
    for key in _SECTION_ORDER:
        items = sections.get(key) or []
        if not items:
            continue
        lines.append(f"{_SECTION_LABELS[key]} ({len(items)}):")
        capped = items[:TOP_N_PER_SECTION]
        for item in capped:
            lines.append(f"  - {item.get('cve_id') or 'Unknown CVE'} on {item.get('hostname') or 'Unknown host'}")
        overflow = len(items) - len(capped)
        if overflow > 0:
            lines.append(f"  ...and {overflow} more")
    return "\n".join(lines) or "Nothing to report."


# ---------------------------------------------------------------------------
# D-08/D-09: per-owner (email) / per-team (channel) dispatch
# ---------------------------------------------------------------------------


async def _dispatch_owner_digests(db: AsyncSession, tenant: Tenant, config: dict[str, Any], now: datetime) -> int:
    """D-08/D-09: groups every tenant asset by resolved owner (same
    `get_directory_user` precedence ALERT-01 uses), assembles that owner's
    scoped sections, and emails an HTML digest -- suppressed (D-14) when
    every section is empty for that owner."""
    smtp_config = tenant.smtp_config or {}
    if not smtp_config.get("enabled") or not smtp_config.get("host"):
        # Matches reports.py:219's existing "silently skip if SMTP isn't
        # configured/enabled" convention -- not an error, just nothing to do.
        return 0

    assets = (await db.execute(select(Asset).where(Asset.tenant_id == tenant.id))).scalars().all()
    owners_map: dict[str, set[uuid.UUID]] = {}
    for asset in assets:
        directory_user = await get_directory_user(db, tenant.id, asset)
        if directory_user and directory_user.get("email"):
            owners_map.setdefault(directory_user["email"], set()).add(asset.id)

    sent = 0
    for owner_email, asset_ids in owners_map.items():
        sections = await _assemble_sections(db, tenant, asset_ids=asset_ids, now=now)
        if _sections_empty(sections):
            continue
        total = sum(len(sections[key]) for key in _ASSEMBLY_SECTION_KEYS)
        result = send_email(
            smtp_config=smtp_config,
            to=[owner_email],
            subject=_digest_subject(config, total),
            body=_digest_plain_text(sections),
            html_body=_render_digest_html(sections, recipient_label=owner_email),
        )
        if result.get("ok"):
            sent += 1
        else:
            logger.warning(
                "digest_owner_email_failed",
                tenant_id=str(tenant.id),
                owner_email=owner_email,
                error=result.get("error"),
            )
    return sent


def _team_digest_channel_context(
    group_name: str, sections: dict[str, list[dict[str, Any]]], total: int
) -> dict[str, Any]:
    """The shared `dispatch_channel` payload builders (`escalation_channels.
    py::_build_slack_payload`/`_build_teams_payload`) are single-finding
    SLA-shaped (context keys `cve_id`/`hostname`/`tier`/`to_state`) -- there
    is no digest-shaped builder (40-RESEARCH.md Assumptions Log A3,
    explicit planner's-discretion item; `escalation_channels.py` is out of
    this plan's `files_modified`, so it is not extended here). This
    function reuses the existing shape as a "most-urgent-item" heads-up
    notification for the team channel -- the full itemized multi-section
    content is what the per-owner HTML email carries; the channel push is a
    pointer, not a duplicate of the email."""
    for key, to_state in (
        ("breaching", "breached"),
        ("due", "approaching"),
        ("newly_critical", "approaching"),
        ("expiring_exceptions", "approaching"),
    ):
        items = sections.get(key) or []
        if not items:
            continue
        top = items[0]
        hostname = top.get("hostname") or group_name
        if total > 1:
            hostname = f"{hostname} (+{total - 1} more)"
        score = top.get("risk_exposure_score")
        tier = tier_for_score(score) if score is not None else None
        return {
            "cve_id": top.get("cve_id") or f"{group_name} digest",
            "hostname": hostname,
            "tier": tier,
            "to_state": to_state,
        }
    return {"cve_id": f"{group_name} digest", "hostname": group_name, "tier": None, "to_state": "approaching"}


async def _dispatch_team_digests(db: AsyncSession, tenant: Tenant, config: dict[str, Any], now: datetime) -> int:
    """D-08/D-09: iterates only `AssetGroup`s that currently HAVE members
    (A4 -- avoids empty-post churn), assembles that group's scoped
    sections, and pushes to every channel configured under
    `routing.digest_team` via the shared Phase-36 dispatch seam
    (`_build_channel_config` + `dispatch_channel`, fail-isolated -- a
    channel failure never blocks another channel/group/tenant in the same
    tick). Suppressed (D-14) when every section is empty for that group."""
    routing = config.get("routing") or {}
    channels = routing.get("digest_team") or []
    if not channels:
        return 0

    groups = (await db.execute(select(AssetGroup).where(AssetGroup.tenant_id == tenant.id))).scalars().all()
    sla_config = tenant.sla_config or {}

    sent = 0
    for group in groups:
        member_ids = set(
            (await db.execute(select(AssetGroupMember.asset_id).where(AssetGroupMember.group_id == group.id)))
            .scalars()
            .all()
        )
        if not member_ids:
            continue

        sections = await _assemble_sections(db, tenant, asset_ids=member_ids, now=now)
        if _sections_empty(sections):
            continue
        total = sum(len(sections[key]) for key in _ASSEMBLY_SECTION_KEYS)
        context = _team_digest_channel_context(group.name, sections, total)

        any_ok = False
        for channel in channels:
            try:
                channel_config = _build_channel_config(sla_config, channel, tenant)
                outcome = await dispatch_channel(channel, channel_config, context)
            except Exception as e:  # decrypt/dispatch failure -- never blocks another channel/group
                outcome = {"ok": False, "error": str(e)}
            if outcome.get("ok"):
                any_ok = True
            else:
                logger.warning(
                    "digest_team_channel_failed",
                    tenant_id=str(tenant.id),
                    group=group.name,
                    channel=channel,
                    error=outcome.get("error"),
                )
        if any_ok:
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# Scheduler-tick entrypoint
# ---------------------------------------------------------------------------


async def run_digests(db: AsyncSession, *, tenant_id: uuid.UUID | None = None, now: datetime | None = None) -> int:
    """D-11..D-15: for each active tenant (or a single `tenant_id`, for
    tests / a future "send test digest" action), skip if the tenant has
    neither digest scope enabled, skip if the wall-clock send-hour gate
    (`_send_hour_due`) isn't due yet, otherwise dispatch per-owner (email)
    and per-team (channel) digests and stamp `alerting_last_digest_sent_at`
    (Pitfall 4 -- the durable marker, written REGARDLESS of whether any
    individual recipient's digest ended up empty-suppressed, so the gate
    correctly reads "already processed this period" on the next tick).

    Own-commit (mirrors `run_alert_checks`'s top-level-entrypoint contract,
    NOT the own-flush/no-own-commit contract of the per-tenant helpers it
    calls) -- the scheduler's isolated try/except block awaits this
    directly, with no separate `db.commit()` at the call site.
    """
    now = now or datetime.now(UTC)

    tenants: Sequence[Tenant]
    if tenant_id is not None:
        tenants = [(await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()]
    else:
        tenants = (await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))).scalars().all()

    total_sent = 0
    for tenant in tenants:
        config = merged_alerting_config(tenant)
        if not config.get("per_owner_digests") and not config.get("per_team_digests"):
            continue
        if not _send_hour_due(tenant, now=now):
            continue

        tenant_sent = 0
        if config.get("per_owner_digests"):
            tenant_sent += await _dispatch_owner_digests(db, tenant, config, now)
        if config.get("per_team_digests"):
            tenant_sent += await _dispatch_team_digests(db, tenant, config, now)

        # Pitfall 4: stamp the durable marker for this period whether or
        # not anything was actually sent -- an all-empty period is still a
        # "processed" period; without this, an empty-but-due tenant would
        # re-run the full assembly on every tick until content appears.
        tenant.alerting_last_digest_sent_at = now
        await db.flush()
        total_sent += tenant_sent

    await db.commit()
    return total_sent
