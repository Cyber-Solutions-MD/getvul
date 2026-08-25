"""Ticket rule engine — evaluates rules against assets and creates tickets automatically.

Rule conditions (all optional, combined with AND):
  device_category: list[str]    — ["WORKSTATION", "SERVER"]
  min_risk_score: int           — minimum asset risk score
  severity: list[str]           — require vulns of these severities ["CRITICAL", "HIGH"]
  exploit_available: bool       — require exploitable vulns
  cisa_kev: bool                — require CISA KEV vulns
  min_critical_vulns: int       — minimum number of critical vulns
  min_high_vulns: int           — minimum number of high vulns
  scanner: list[str]            — asset seen by these scanners

Rule action:
  provider: str                 — "ASANA" (or future: "JIRA", "GITHUB")
  project_key: str              — Asana project GID (empty = default)
  auto_assign: bool             — assign to host's Humaans user
  due_days: int | null          — custom due days (null = SLA defaults)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.constants import SCANNER_SOURCES
from app.assets.models import Asset
from app.exceptions.service import active_exception_subquery
from app.ticketing.dispatch import build_ticketing_client
from app.ticketing.models import Ticket, TicketRule
from app.ticketing.providers import TicketProvider
from app.ticketing.schemas import HostTicketCreateRequest
from app.ticketing.service import create_host_ticket, create_remediation_ticket
from app.vulnerabilities.models import Vulnerability

logger = structlog.get_logger()

# Which config key a rule's action.project_key override lands on, per provider
# (D-09: mirrors router.py's per-request project override so a rule can still
# target a non-default Asana project / Jira project without dispatch.py
# needing to know about rules at all). GitHub has no per-request project
# concept — its routing (owner/repo) is fixed on the connector.
_PROVIDER_PROJECT_FIELD = {
    TicketProvider.ASANA: "project_gid",
    TicketProvider.JIRA: "project_key",
}


async def find_matching_assets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    conditions: dict,
) -> list[Asset]:
    """Find assets matching the rule conditions."""
    query = select(Asset).where(Asset.tenant_id == tenant_id, Asset.is_ignored.is_(False))

    # Device category filter
    categories = conditions.get("device_category")
    if categories and isinstance(categories, list):
        query = query.where(Asset.device_category.in_(categories))

    # Minimum risk score
    min_risk = conditions.get("min_risk_score")
    if min_risk is not None and min_risk > 0:
        query = query.where(Asset.risk_score >= min_risk)

    # Scanner filter (from "scanner" or "source" conditions).
    #
    # SRC-03 bug fix: this used to be a chained `.where(...)` loop (one call
    # per condition scanner), the IDENTICAL AND-bug as assets/router.py's
    # pre-fix scanner filter — SQLAlchemy ANDs successive `.where()` calls,
    # so a rule listing 2+ scanners silently required "seen by ALL" instead
    # of "seen by ANY" (CONTEXT.md "Real bug to fix"). Now OR-default via
    # `or_(*contains)`, clamped to SCANNER_SOURCES (shared with the assets
    # router) so an enrichment source can't masquerade as a scanner
    # condition. No AND toggle here — the rule schema has no such axis
    # today; OR-default is the correct fix (interfaces block note).
    scanners = conditions.get("scanner") or conditions.get("source")
    if scanners and isinstance(scanners, list):
        scanners = [s for s in (x.strip().upper() for x in scanners) if s in SCANNER_SOURCES]
        if scanners:
            query = query.where(or_(*[Asset.seen_by_sources.contains([s]) for s in scanners]))

    assets = (await db.execute(query)).scalars().all()

    # Now filter by vulnerability conditions (need per-asset vuln counts)
    severity_filter = conditions.get("severity")
    exploit_required = conditions.get("exploit_available")
    kev_required = conditions.get("cisa_kev")
    min_critical = conditions.get("min_critical_vulns", 0) or 0
    min_high = conditions.get("min_high_vulns", 0) or 0

    if not severity_filter and not exploit_required and not kev_required and not min_critical and not min_high:
        return assets

    matched = []
    for asset in assets:
        # Count ALL open vulns for this asset (unfiltered for exploit/kev checks)
        counts_q = select(
            func.count().label("total"),
            func.count().filter(Vulnerability.severity == "CRITICAL").label("critical"),
            func.count().filter(Vulnerability.severity == "HIGH").label("high"),
            func.count().filter(Vulnerability.exploit_available.is_(True)).label("exploitable"),
            func.count().filter(Vulnerability.cisa_kev.is_(True)).label("kev"),
        ).where(
            Vulnerability.asset_id == asset.id,
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            # EXC-02/D-15 (Phase 39 Consumer 10, Tier 2 #8 governance-critical):
            # an actively-excepted finding must not make an asset match a
            # rule -- otherwise a scheduler tick would auto-open a ticket for
            # a governed accept-risk decision.
            ~active_exception_subquery(tenant_id, datetime.now(UTC)),
        )

        vc = (await db.execute(counts_q)).one()

        if vc.total == 0:
            continue

        # Severity filter: require at least 1 vuln of the specified severities
        if severity_filter:
            has_severity = False
            for sev in severity_filter:
                if sev == "CRITICAL" and vc.critical > 0:
                    has_severity = True
                if sev == "HIGH" and vc.high > 0:
                    has_severity = True
                if sev == "MEDIUM" and (vc.total - vc.critical - vc.high) > 0:
                    has_severity = True
            if not has_severity:
                continue

        if exploit_required and vc.exploitable == 0:
            continue
        if kev_required and vc.kev == 0:
            continue
        if min_critical and vc.critical < min_critical:
            continue
        if min_high and vc.high < min_high:
            continue

        matched.append(asset)

    return matched


async def run_rule(
    db: AsyncSession,
    rule: TicketRule,
    credentials: dict[str, Any],
    config: dict[str, Any],
) -> dict:
    """Evaluate a single rule and create tickets for matching assets (D-09).

    `credentials`/`config` are the ALREADY-DECRYPTED connector credentials +
    raw connector config for whichever provider this rule's own
    `action.provider` resolves to (the caller looks that connector up per
    rule — see run_all_due_rules/router.run_rule_now) — not always Asana.
    """
    conditions = rule.conditions or {}
    action = rule.action or {}

    # Find matching assets
    assets = await find_matching_assets(db, rule.tenant_id, conditions)

    if not assets:
        return {"matched": 0, "created": 0, "skipped": 0}

    provider = action.get("provider", "ASANA")
    provider_enum = TicketProvider(provider)

    rule_project_key = action.get("project_key")
    effective_config = dict(config)
    project_field = _PROVIDER_PROJECT_FIELD.get(provider_enum)
    if rule_project_key and project_field:
        effective_config[project_field] = rule_project_key

    client = build_ticketing_client(provider_enum, credentials, effective_config)

    # project_key stored on Ticket rows is metadata only (D-07: routing itself
    # is baked into `client` via effective_config above).
    project_key = rule_project_key or (effective_config.get(project_field, "") if project_field else "")
    auto_assign = action.get("auto_assign", True)
    due_days = action.get("due_days")
    ticket_mode = action.get("ticket_mode", "per_host")
    max_tickets_per_day = action.get("max_tickets", 10)

    # Daily ticket budget: count distinct tickets created today for this tenant + provider
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_created = (
        await db.execute(
            select(func.count(func.distinct(Ticket.external_ticket_id))).where(
                Ticket.tenant_id == rule.tenant_id,
                Ticket.provider == provider,
                Ticket.ticket_created_at >= today_start,
            )
        )
    ).scalar_one()

    remaining_budget = max(0, max_tickets_per_day - today_created)
    if remaining_budget == 0:
        logger.info("rule_daily_limit_reached", rule=rule.name, max=max_tickets_per_day, today=today_created)
        return {"matched": len(assets), "created": 0, "skipped": 0, "daily_limit_reached": True}

    created = 0
    skipped = 0

    assignee_email = action.get("assignee_email")

    if ticket_mode == "per_remediation":
        # Create one ticket per remediation across matching assets
        # Apply the same severity/source/exploit filters to remediations
        asset_ids = [a.id for a in assets]
        rem_q = select(
            Vulnerability.remediation_id,
            func.count(func.distinct(Vulnerability.asset_id)).label("host_count"),
        ).where(
            Vulnerability.tenant_id == rule.tenant_id,
            Vulnerability.asset_id.in_(asset_ids),
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
            Vulnerability.remediation_id.isnot(None),
            Vulnerability.remediation_id != "",
            # EXC-02/D-15 (Phase 39 Consumer 10 sibling): same governance
            # exclusion as find_matching_assets' counts_q, applied to the
            # per_remediation ticket-mode's own asset/remediation matcher.
            ~active_exception_subquery(rule.tenant_id, datetime.now(UTC)),
        )
        # Apply severity filter to remediations too
        severity_filter = conditions.get("severity")
        if severity_filter:
            rem_q = rem_q.where(Vulnerability.severity.in_(severity_filter))
        # Apply source filter
        source_filter = conditions.get("source")
        if source_filter:
            rem_q = rem_q.where(Vulnerability.source.in_(source_filter))
        # Apply exploit filter
        if conditions.get("exploit_available"):
            rem_q = rem_q.where(Vulnerability.exploit_available.is_(True))
        if conditions.get("cisa_kev"):
            rem_q = rem_q.where(Vulnerability.cisa_kev.is_(True))

        rem_q = rem_q.group_by(Vulnerability.remediation_id).order_by(
            func.count(func.distinct(Vulnerability.asset_id)).desc()
        )
        rem_rows = (await db.execute(rem_q)).all()

        for row in rem_rows:
            if created >= remaining_budget:
                break
            result = await create_remediation_ticket(
                db=db,
                tenant_id=rule.tenant_id,
                user_id=None,
                remediation_id=row.remediation_id,
                provider=provider,
                project_key=project_key,
                client=client,
                due_days=due_days,
                assignee_email=assignee_email,
                severity_filter=conditions.get("severity"),
                source_filter=conditions.get("source"),
                exploit_filter=bool(conditions.get("exploit_available")),
                kev_filter=bool(conditions.get("cisa_kev")),
            )
            if "error" not in result:
                created += 1
            else:
                skipped += 1

    else:
        # per_host: one ticket per matching host (existing behavior)
        for asset in assets:
            if created >= remaining_budget:
                break
            existing = await db.execute(
                select(Ticket)
                .join(Vulnerability, Ticket.vulnerability_id == Vulnerability.id)
                .where(
                    Ticket.tenant_id == rule.tenant_id,
                    Ticket.provider == provider,
                    Ticket.resolved_at.is_(None),
                    Vulnerability.asset_id == asset.id,
                )
                .limit(1)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            assignee = None
            if auto_assign:
                h = asset.mdm_details or {}
                assignee = h.get("humaans_email")

            request = HostTicketCreateRequest(
                asset_id=asset.id,
                provider=provider,
                project_key=project_key,
                assignee=assignee,
                due_days=due_days,
            )

            result = await create_host_ticket(
                db=db,
                tenant_id=rule.tenant_id,
                user_id=None,
                request=request,
                client=client,
            )

            if "error" not in result:
                created += 1
            else:
                logger.warning("rule_ticket_failed", rule=rule.name, asset=asset.hostname, error=result["error"])
                skipped += 1

    return {"matched": len(assets), "created": created, "skipped": skipped}


def _has_min_credentials(provider: str, creds: dict[str, Any], config: dict[str, Any]) -> bool:
    """Minimal sanity check before dispatching — mirrors the pre-existing
    Asana `if not token: continue` / `if not workspace_gid: continue` guards,
    generalized per provider (D-09)."""
    if provider == TicketProvider.ASANA:
        return bool(creds.get("access_token")) and bool(config.get("workspace_gid"))
    if provider == TicketProvider.JIRA:
        return bool(creds.get("email")) and bool(creds.get("api_token")) and bool(creds.get("url"))
    if provider == TicketProvider.GITHUB:
        return bool(creds.get("token")) and bool(config.get("owner")) and bool(config.get("repo"))
    return False


async def run_all_due_rules(db: AsyncSession) -> dict:
    """Check all enabled rules and run those that are due. Called by the scheduler.

    D-09: the connector lookup used to be hardcoded to the Asana connector
    type only — a rule with `action.provider="JIRA"` either no-op'd (no
    Asana connector to find) or,
    worse, silently ran against the tenant's Asana connector regardless of
    what the rule asked for. Now the lookup is keyed on the UNION of
    providers actually referenced by the tenant's due rules (default ASANA
    for back-compat), one enabled ConnectorConfig per provider, and each rule
    dispatches through ITS OWN provider's client. A rule whose provider has no
    configured connector is skipped (logged), not silently redirected to a
    different provider.
    """
    from app.connectors.service import get_decrypted_credentials
    from app.ticketing.models import ConnectorConfig

    now = datetime.now(UTC)

    # Get all enabled rules
    rules = (await db.execute(select(TicketRule).where(TicketRule.is_enabled.is_(True)))).scalars().all()

    if not rules:
        return {"rules_checked": 0}

    total_created = 0
    rules_run = 0

    # Group rules by tenant
    tenant_rules: dict[uuid.UUID, list[TicketRule]] = {}
    for rule in rules:
        # Check if rule is due
        if rule.last_run_at:
            elapsed = (now - rule.last_run_at).total_seconds() / 60
            if elapsed < rule.schedule_minutes:
                continue
        tenant_rules.setdefault(rule.tenant_id, []).append(rule)

    for tenant_id, t_rules in tenant_rules.items():
        # Union of providers referenced by this tenant's due rules (default ASANA)
        providers_needed = {(rule.action or {}).get("provider", "ASANA") for rule in t_rules}

        connectors_by_provider: dict[str, tuple[dict[str, Any], dict[str, Any]] | None] = {}
        for provider in providers_needed:
            connector = (
                await db.execute(
                    select(ConnectorConfig).where(
                        ConnectorConfig.tenant_id == tenant_id,
                        ConnectorConfig.connector_type == provider,
                        ConnectorConfig.is_enabled.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if not connector:
                connectors_by_provider[provider] = None
                continue

            creds = get_decrypted_credentials(connector)
            config = connector.config or {}
            if not _has_min_credentials(provider, creds, config):
                connectors_by_provider[provider] = None
                continue

            connectors_by_provider[provider] = (creds, config)

        for rule in t_rules:
            provider = (rule.action or {}).get("provider", "ASANA")
            resolved = connectors_by_provider.get(provider)
            if resolved is None:
                logger.warning("rule_provider_not_configured", rule=rule.name, provider=provider)
                continue
            creds, config = resolved

            try:
                result = await run_rule(db, rule, creds, config)
                rule.last_run_at = now
                rule.last_run_status = "SUCCESS"
                rule.last_run_tickets_created = result["created"]
                total_created += result["created"]
                rules_run += 1

                logger.info(
                    "ticket_rule_run",
                    rule=rule.name,
                    provider=provider,
                    matched=result["matched"],
                    created=result["created"],
                    skipped=result["skipped"],
                )
            except Exception as e:
                rule.last_run_at = now
                rule.last_run_status = "FAILED"
                logger.error("ticket_rule_error", rule=rule.name, provider=provider, error=str(e))

    await db.commit()
    return {"rules_checked": len(rules), "rules_run": rules_run, "tickets_created": total_created}
