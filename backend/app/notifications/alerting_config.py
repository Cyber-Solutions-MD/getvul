"""Canonical schema + defaults for `Tenant.alerting_config` (Phase 40 --
ALERT-01..03: proactive KEV/EPSS alerting + owner/team digests).

This module is the SINGLE source of truth for the `alerting_config` JSONB
key set. Every downstream plan imports `DEFAULT_ALERTING_CONFIG` (or reads
effective settings via `merged_alerting_config`) rather than re-deriving the
key set -- this is the "one agreed config-key contract" the phase objective
calls for, so the four consuming plans (detection = Plan 02, digests = Plan
03, PATCH /settings save = Plan 04, the settings pane = Plan 05) can never
drift into inventing their own subset of keys (the "scavenger hunt"
anti-pattern the phase plan explicitly guards against).

Alerting/digests reuse Phase 36's channel credential store
(`Tenant.sla_config["channels"]` -- Fernet-encrypted Slack/Teams/PagerDuty
webhook secrets + SMTP) per D-19: one place configures the webhooks,
alerting/digests only reference those already-configured channel *names*
with their own independent on/off + routing. `alerting_config` therefore
holds ONLY routing/enablement/thresholds and must NEVER contain a raw or
encrypted secret (see this plan's threat_model T-40-02 + the plan's
`prohibitions`).
"""

from __future__ import annotations

from typing import Any

# Channel names referenced by `routing` below are the same keys used by
# `Tenant.sla_config["channels"]` (Phase 36 D-04): "slack", "teams",
# "pagerduty", "email". A routing list may reference a channel name that the
# tenant has not actually configured/enabled yet in sla_config -- the send
# path (Plan 02/03) is responsible for treating an unconfigured channel as a
# no-op, not this module.
DEFAULT_ALERTING_CONFIG: dict[str, Any] = {
    # ALERT-01 detection gates (D-05/D-06).
    "kev_enabled": True,  # CISA KEV is an authoritative, low-noise signal -- on by default.
    "epss_threshold": 0.5,  # D-05 tenant-specific EPSS qualifying threshold (0.0-1.0).
    # ALERT-02 digest cadence (D-11/D-12).
    "cadence": "daily",
    "send_hour": 8,  # Target hour in Tenant.timezone; scheduler fires past this hour, once per period.
    # ALERT-02 digest recipient scope (D-08) -- admin can enable either or both independently.
    "per_owner_digests": True,
    "per_team_digests": True,
    # Per-alert-type channel routing (D-07/D-09/D-19). Values are lists of
    # channel names from sla_config["channels"]; an empty list means no
    # channel push for that alert type (in-app/email delivery, where
    # applicable, is independent of this map). NO secrets live here -- only
    # references to already-configured channels.
    "routing": {
        "new_kev_epss": ["slack"],  # ALERT-01 real-time push (D-07).
        "digest_owner": ["email"],  # ALERT-02 per-owner digest channel (D-09).
        "digest_team": ["slack"],  # ALERT-02 per-team digest channel (D-09).
    },
}


def merged_alerting_config(tenant: Any) -> dict[str, Any]:
    """Return `DEFAULT_ALERTING_CONFIG` overlaid with `tenant.alerting_config`.

    A shallow merge at the top level, plus a nested merge for `routing` so a
    tenant can override a single alert type's channel list without
    resubmitting the entire routing map. `tenant.alerting_config` is `None`
    until the tenant has ever saved alerting settings (Plan 04).

    Downstream code (detection, digests, the settings pane's GET) should
    read effective alerting settings through this function -- never through
    `tenant.alerting_config` directly -- so default-filling for keys the
    tenant has never touched lives in exactly one place, matching this
    plan's "one agreed config-key contract" objective.
    """
    overrides = getattr(tenant, "alerting_config", None) or {}
    merged: dict[str, Any] = {**DEFAULT_ALERTING_CONFIG, **overrides}
    merged["routing"] = {
        **DEFAULT_ALERTING_CONFIG["routing"],
        **(overrides.get("routing") or {}),
    }
    return merged
