"""Escalation channel senders (Phase 36 Plan 02, SLA-03 delivery plumbing).

Builds per-channel payloads and sends them via raw `httpx.AsyncClient` POSTs
(Slack incoming webhook, Microsoft Teams Workflows webhook, PagerDuty Events
API v2) or the existing SMTP path (`app.email.send_email`, the email
channel) -- no vendor SDKs (D-04). This module is delivery plumbing ONLY:
the transition-detection + once-only firing logic that calls
`dispatch_channel()` (and writes/audits a `SlaEscalationEvent` row) lands in
Plan 03.

D-13 (PagerDuty manual-resolution limitation): every PagerDuty event this
module sends carries `event_action` `"trigger"` -- nothing else, this
phase. This module never automatically closes a PagerDuty incident: when a
finding un-breaches or is remediated, a human must resolve the incident
manually inside PagerDuty until a future phase adds that automation. Do
not wire up an auto-closing call without revisiting D-13.

Pitfall 10 (SSRF): every outbound webhook POST to a tenant-admin-controlled
URL (Slack/Teams) is validated via `_validate_webhook_url` -- https-only,
rejecting private/loopback/link-local/reserved/multicast IP literals and
well-known cloud metadata hosts -- before httpx is ever invoked.
`httpx.AsyncClient(follow_redirects=False)` additionally prevents a
redirect-based bypass of that pre-POST check. PagerDuty's target is a fixed
constant (never tenant-controlled) but is still passed through the same
guard for defense in depth.

Pattern 1 (scheduler-tick isolation): every sender -- and `dispatch_channel`
itself -- wraps its own httpx/SMTP call in a try/except so a channel
failure (timeout, DNS failure, non-2xx, TLS error, unknown channel name,
etc.) is caught HERE and returned as `{"ok": False, "error": ...}` --
never raised. Plan 03's firing loop records this on the escalation-event
row (`delivery_status="failed"`) and must be able to keep processing every
other tenant/finding/channel in the same scheduler tick regardless of what
any single channel does.
"""

from __future__ import annotations

import asyncio
import ipaddress
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.email import send_email

logger = structlog.get_logger(__name__)

REQUEST_TIMEOUT = 10.0
RATE_LIMIT_MAX_RETRIES = 3  # mirrors okta_sync.py's 429-retry shape, adapted from GET to a JSON POST

PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

_TIER_TO_PAGERDUTY_SEVERITY: dict[str, str] = {"critical": "critical", "high": "error", "moderate": "warning"}

# DNS names that resolve to a cloud metadata endpoint -- a literal-IP check
# alone does not catch these (Pitfall 10).
_BLOCKED_METADATA_HOSTS = {"metadata.google.internal", "metadata.goog", "localhost"}


# ---------------------------------------------------------------------------
# SSRF guard (Pitfall 10)
# ---------------------------------------------------------------------------


def _validate_webhook_url(url: str | None) -> bool:
    """https-only + private/loopback/link-local/metadata SSRF guard.

    Returns True only if `url` is safe to POST to. Does not perform DNS
    resolution (no network call inside a pure validator, and httpx's own
    connect would need to re-check regardless) -- it rejects well-known
    metadata hostnames by literal string match and any literal IP-address
    host that is private/loopback/link-local/reserved/multicast/unspecified.
    `httpx.AsyncClient(follow_redirects=False)` is the complementary guard
    against a redirect-based bypass at request time.
    """
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_METADATA_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # a normal DNS hostname, not a literal IP -- allowed
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


# ---------------------------------------------------------------------------
# Payload builders (pure -- no I/O)
# ---------------------------------------------------------------------------


def _build_summary_text(context: dict[str, Any]) -> str:
    to_state = context.get("to_state") or "breached"
    verb = "breach" if to_state == "breached" else "approaching"
    cve = context.get("cve_id") or context.get("vuln_id") or "unknown finding"
    host = context.get("hostname") or "unknown host"
    tier = context.get("tier") or "unscored"
    tier_days = context.get("tier_days")
    days_part = f", {tier_days}d" if tier_days is not None else ""
    return f"SLA {verb}: {cve} on {host} ({tier} tier{days_part})"


def _build_slack_payload(context: dict[str, Any]) -> dict[str, Any]:
    """Slack incoming webhook (36-RESEARCH.md:486-498) -- a top-level "text"
    fallback is required by Slack's own contract; "blocks" is the richer
    mrkdwn rendering."""
    to_state = context.get("to_state") or "breached"
    label = "SLA breach" if to_state == "breached" else "SLA approaching"
    cve = context.get("cve_id") or context.get("vuln_id") or "unknown finding"
    host = context.get("hostname") or "unknown host"
    tier = context.get("tier") or "unscored"
    block_text = f"*{label}* — `{cve}` on `{host}`\ntier: *{tier}*"
    return {
        "text": _build_summary_text(context),
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": block_text}}],
    }


def _build_teams_payload(context: dict[str, Any]) -> dict[str, Any]:
    """Microsoft Teams Workflows webhook (D-15 / Pitfall 7). The
    `webhook.office.com` Workflows URL still accepts this simple
    `{"text": ...}` form (36-RESEARCH.md:500-518) -- this must NEVER be the
    retired classic connector's MessageCard envelope
    (`"@type": "MessageCard"`, `"themeColor"`, etc.)."""
    return {"text": _build_summary_text(context)}


def _pagerduty_severity(tier: str | None) -> str:
    if tier is None:
        return "warning"
    return _TIER_TO_PAGERDUTY_SEVERITY.get(tier, "warning")


def _build_pagerduty_payload(context: dict[str, Any], routing_key: str) -> dict[str, Any]:
    """PagerDuty Events API v2 trigger event (36-RESEARCH.md:521-541). Per
    D-13, `event_action` is ALWAYS "trigger" -- this function has no branch
    that can produce "resolve" or "acknowledge"."""
    to_state = context.get("to_state") or "breached"
    vuln_id = context.get("vuln_id")
    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": f"getvul:{vuln_id}:{to_state}",
        "payload": {
            "summary": _build_summary_text(context),
            "source": "getvul",
            "severity": _pagerduty_severity(context.get("tier")),
            "timestamp": datetime.now(UTC).isoformat(),
            "custom_details": {
                "cve_id": context.get("cve_id"),
                "tier": context.get("tier"),
                "asset": context.get("hostname"),
            },
        },
        "client": "GetVul",
    }


# ---------------------------------------------------------------------------
# Outbound POST (shared by the three webhook-based channels)
# ---------------------------------------------------------------------------


async def _post_json_with_retry(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> httpx.Response:
    """POST with 429 retry -- mirrors okta_sync.py's `_request_with_retry`
    shape (backend/app/connectors/okta_sync.py:69-93), adapted from a
    paginated GET to a one-shot JSON POST."""
    response: httpx.Response | None = None
    for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 1):
        response = await client.post(url, json=payload)
        if response.status_code != 429:
            return response
        wait = 2**attempt
        logger.warning("escalation_channel_rate_limited", attempt=attempt, wait_seconds=wait, url=url)
        await asyncio.sleep(wait)
    assert response is not None  # the loop above always executes >= 1 time
    return response


async def _post_json(url: str, payload: dict[str, Any], *, channel: str) -> dict[str, Any]:
    """Shared outbound POST for the webhook-based channels. Every failure
    mode (timeout, DNS error, non-2xx, TLS error, or any other exception)
    is caught HERE and returned as `{"ok": False, "error": ...}` -- this
    function must never raise (Pattern 1)."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            response = await _post_json_with_retry(client, url, payload)
        if 200 <= response.status_code < 300:
            return {"ok": True}
        return {"ok": False, "error": f"{channel} webhook returned HTTP {response.status_code}"}
    except Exception as e:
        logger.error("escalation_channel_post_failed", channel=channel, url=url, error=str(e))
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Channel senders
# ---------------------------------------------------------------------------


async def send_slack(config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """Slack incoming webhook channel (D-04)."""
    url = (config or {}).get("url")
    if not url or not _validate_webhook_url(url):
        return {"ok": False, "error": "Invalid or unsafe Slack webhook URL"}
    return await _post_json(url, _build_slack_payload(context), channel="slack")


async def send_teams(config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """Microsoft Teams Workflows webhook channel (D-04/D-15)."""
    url = (config or {}).get("url")
    if not url or not _validate_webhook_url(url):
        return {"ok": False, "error": "Invalid or unsafe Teams webhook URL"}
    return await _post_json(url, _build_teams_payload(context), channel="teams")


async def send_pagerduty(config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """PagerDuty Events API v2 channel (D-04). Per D-13, sends
    `event_action="trigger"` only -- see the module docstring."""
    routing_key = (config or {}).get("routing_key")
    if not routing_key:
        return {"ok": False, "error": "PagerDuty routing key is not configured"}
    if not _validate_webhook_url(PAGERDUTY_EVENTS_URL):
        # Defensive only -- PAGERDUTY_EVENTS_URL is a fixed https constant,
        # never tenant-controlled, so this branch is unreachable in practice.
        return {"ok": False, "error": "PagerDuty Events API URL failed the SSRF guard"}
    payload = _build_pagerduty_payload(context, routing_key)
    return await _post_json(PAGERDUTY_EVENTS_URL, payload, channel="pagerduty")


def send_email_channel(config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """Email escalation channel -- delegates to `app.email.send_email`
    verbatim (D-04: no new email integration). `config` is expected to
    carry `{"to": [...], "smtp_config": {...}}`: the tenant's SMTP settings
    live on a different `Tenant` column (`smtp_config`) than the
    per-channel `sla_config.channels.email` block (just `{"to", "enabled"}`,
    see `tenants/router.py`'s `SlaEmailChannel`), so Plan 03's firing loop
    is expected to merge the two before calling
    `dispatch_channel("email", ...)`."""
    cfg = config or {}
    to = cfg.get("to") or []
    smtp_config = cfg.get("smtp_config") or {}
    if not to:
        return {"ok": False, "error": "No email recipients configured"}
    subject = f"GetVul SLA {context.get('to_state', 'alert')}: {context.get('cve_id') or context.get('vuln_id') or ''}"
    body = _build_summary_text(context)
    try:
        return send_email(smtp_config=smtp_config, to=to, subject=subject, body=body)
    except Exception as e:
        # send_email() already wraps its own body in try/except and never
        # raises -- this is belt-and-suspenders so send_email_channel's own
        # contract (never raise, Pattern 1) holds even if that changes.
        logger.error("escalation_channel_post_failed", channel="email", error=str(e))
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


async def dispatch_channel(channel: str, config: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """Route an escalation fire to the right channel sender (D-04). Every
    branch -- including an unrecognized channel name -- returns
    `{"ok": bool, "error": str | None}`; this function itself never raises
    (Pattern 1), so Plan 03's per-tenant/per-finding firing loop can keep
    processing every other channel/tenant in the same tick regardless of
    what any single channel does.

    Sender names are looked up as bare module-global references (not a
    dict built once at import time) so monkeypatching e.g. `send_slack` at
    the module level is honored on the next call, mirroring this
    codebase's existing dispatcher-monkeypatch convention
    (test_scheduler_enrichment_refresh.py).
    """
    try:
        if channel == "slack":
            return await send_slack(config, context)
        if channel == "teams":
            return await send_teams(config, context)
        if channel == "pagerduty":
            return await send_pagerduty(config, context)
        if channel == "email":
            return send_email_channel(config, context)
        return {"ok": False, "error": f"Unknown escalation channel: {channel}"}
    except Exception as e:
        logger.error("escalation_dispatch_failed", channel=channel, error=str(e))
        return {"ok": False, "error": str(e)}
