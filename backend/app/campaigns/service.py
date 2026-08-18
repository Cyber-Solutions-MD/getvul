"""Campaign business logic: race-safe get-or-create (D-11) + compute-on-read
progress aggregation (D-07/D-18) + per-owner bulk ticket carve-up (CAMP-02)
for Phase 38 (CAMP-01/CAMP-02/CAMP-04).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.campaigns.models import Campaign
from app.ticketing.dispatch import TicketingClient
from app.ticketing.models import Ticket
from app.ticketing.service import SEVERITY_SLA_DAYS, _extract_ref, _provider_create_kwargs, recompute_ticket_sla
from app.vulnerabilities.models import RemediationEvent, Vulnerability

# D-05: byte-identical severity ranking to ticketing/service.py's inline
# `sev_rank` dict inside create_remediation_ticket -- never re-derive.
_SEV_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}

# D-18 / 38-RESEARCH.md Pitfall 2: campaign membership/progress counts ONLY
# these three actionable statuses. NEVER reuse remediation_service.py's
# _base_open_vulns() here -- it excludes REMEDIATED entirely, which would
# make "% remediated" permanently read 0. SUPPRESSED/FALSE_POSITIVE are
# deliberately excluded from the denominator (D-18), matching the
# remediation-grouped entry-point view's own default semantics.
_CAMPAIGN_MEMBER_STATUSES = ("OPEN", "IN_PROGRESS", "REMEDIATED")


async def get_or_create_campaign(
    db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str, user_id: uuid.UUID
) -> tuple[Campaign, bool]:
    """D-11 race-safe get-or-create.

    SELECTs the existing ACTIVE campaign first (the common-case fast path --
    D-11's "opens the existing campaign" UX), then INSERTs inside a nested
    transaction, catching the partial-unique-index `IntegrityError` as the
    concurrent-request backstop -- mirrors `sla_tier_service.py:406-428`'s
    proven `begin_nested()` + `IntegrityError` shape for the identical
    "insert unless a matching unique-constrained row already exists"
    problem.

    Returns `(campaign, is_new)` -- `is_new=False` means D-11 opened an
    existing active campaign: no row was created, and per CAMP-04's "only
    when a NEW campaign is created" contract the caller must NOT write a
    second `campaign.create` audit row in that case.
    """
    existing = (
        await db.execute(
            select(Campaign).where(
                Campaign.tenant_id == tenant_id,
                Campaign.remediation_id == remediation_id,
                Campaign.closed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    campaign = Campaign(tenant_id=tenant_id, remediation_id=remediation_id, created_by_user_id=user_id)
    db.add(campaign)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Another request won the race between our SELECT and INSERT -- the
        # partial unique index rejected our insert. Re-SELECT the row that
        # won; it is guaranteed to exist now.
        existing = (
            await db.execute(
                select(Campaign).where(
                    Campaign.tenant_id == tenant_id,
                    Campaign.remediation_id == remediation_id,
                    Campaign.closed_at.is_(None),
                )
            )
        ).scalar_one()
        return existing, False
    return campaign, True


async def get_campaign_progress(db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str) -> dict[str, int]:
    """Compute-on-read progress (D-07): total/open/in_progress/done/
    pct_remediated, aggregated fresh from a live `vulnerabilities` join --
    no persisted snapshot, ever, so this always reflects true current
    exposure (D-03 live membership).

    Pitfall 5: explicit zero-guard so a zero-member remediation_id (every
    member suppressed, or a race against ingestion right after launch)
    returns `pct_remediated=0` instead of raising `ZeroDivisionError`.
    """
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Vulnerability.status == "REMEDIATED").label("done"),
                func.count().filter(Vulnerability.status == "IN_PROGRESS").label("in_progress"),
            ).where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.remediation_id == remediation_id,
                Vulnerability.status.in_(_CAMPAIGN_MEMBER_STATUSES),
            )
        )
    ).one()
    total, done, in_progress = row.total, row.done, row.in_progress
    return {
        "total": total,
        "open": total - done - in_progress,
        "in_progress": in_progress,
        "done": done,
        "pct_remediated": round(done / total * 100) if total else 0,
    }


async def get_campaign_mttr(db: AsyncSession, tenant_id: uuid.UUID, remediation_id: str) -> float | None:
    """D-12: campaign MTTR = average of member `RemediationEvent.duration_
    seconds`, joined through `Vulnerability.remediation_id` (the same
    grouping key as `get_campaign_progress`). Deliberately NOT filtered by
    `_CAMPAIGN_MEMBER_STATUSES` -- a `RemediationEvent` row is durable
    history (Phase 36 D-09) and survives a later reopen-on-recurrence
    (D-04), so this always reflects every remediation this group has ever
    completed, not just currently-REMEDIATED members.

    Returns `None` (never `0`, never a raised error) when no member has
    ever been remediated -- Pitfall 5's zero-guard sibling for MTTR.

    Pitfall 7: Postgres `AVG()` over an `Integer` column returns a
    `Decimal`, which does not round-trip cleanly through Pydantic/JSON as a
    plain float -- explicit `float(...)` coercion mirrors
    `get_mttr_by_tier`'s identical fix (`vulnerabilities/service.py`).
    """
    avg_seconds = (
        await db.execute(
            select(func.avg(RemediationEvent.duration_seconds))
            .join(Vulnerability, RemediationEvent.vulnerability_id == Vulnerability.id)
            .where(
                RemediationEvent.tenant_id == tenant_id,
                Vulnerability.remediation_id == remediation_id,
            )
        )
    ).scalar_one()
    return float(avg_seconds) if avg_seconds is not None else None


async def list_campaigns(db: AsyncSession, tenant_id: uuid.UUID) -> list[Campaign]:
    """All campaigns for a tenant, deterministically ordered (backstop:
    `created_at DESC, id` tiebreak so equal-timestamp campaigns never
    reorder between reads)."""
    result = await db.execute(
        select(Campaign).where(Campaign.tenant_id == tenant_id).order_by(Campaign.created_at.desc(), Campaign.id)
    )
    return list(result.scalars().all())


def _build_owner_ticket_description(members: list[tuple[Vulnerability, str | None]]) -> str:
    """Plain-text ticket body for one owner's bucket of campaign members --
    mirrors `ticketing/service.py::create_remediation_ticket`'s per-host
    block layout (lines 633-646), scoped to just this owner's hosts instead
    of the whole remediation group.
    """
    hosts: dict[str, list[Vulnerability]] = {}
    for vuln, hostname in members:
        hosts.setdefault(hostname or "unknown", []).append(vuln)

    lines: list[str] = []
    for hostname, vulns in hosts.items():
        lines.append(f"━━━ {hostname} ━━━")
        for v in vulns:
            cve = v.cve_id or "N/A"
            paths = ""
            if v.file_paths and isinstance(v.file_paths, list):
                paths = f" | Path: {', '.join(v.file_paths[:3])}"
            exploit = " ⚡EXPLOIT" if v.exploit_available else ""
            kev = " 🛡KEV" if v.cisa_kev else ""
            lines.append(f"  [{v.severity}] {cve}{exploit}{kev}{paths}")
        lines.append("")
    return "\n".join(lines)


async def bulk_create_campaign_tickets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    campaign: Campaign,
    provider: str,
    project_key: str,
    client: TicketingClient,
    due_days: int | None = None,
) -> dict[str, int | list[str | None]]:
    """CAMP-02: re-carve of `create_remediation_ticket()`'s single-ticket
    group shape (`ticketing/service.py:548-706`) into ONE ticket PER OWNER,
    each covering only that owner's live campaign members. Every run is
    audited by the caller (D-10); already-ticketed findings are adopted, not
    duplicated (D-06); an owner-less finding lands in the None/unassigned
    bucket instead of being dropped (D-08); campaign tickets share the bare
    `campaign.remediation_id` as `created_by_rule` (D-20 / Pitfall 1) so a
    later `per_remediation` automation rule's own group-level dedup check
    sees them and does not double-ticket.

    Returns `{created_tickets, tickets_linked, adopted, owners, failed_owners}`.
    """
    # 1. Live members. NARROWER than the progress-aggregation filter
    # (_CAMPAIGN_MEMBER_STATUSES includes REMEDIATED) -- a member already
    # REMEDIATED needs no new ticket, matching every existing ticket-creation
    # primitive's OPEN/IN_PROGRESS convention.
    rows = (
        await db.execute(
            select(Vulnerability, Asset.hostname, Asset.mdm_details)
            .outerjoin(Asset, Vulnerability.asset_id == Asset.id)
            .where(
                Vulnerability.tenant_id == tenant_id,
                Vulnerability.remediation_id == campaign.remediation_id,
                Vulnerability.status.in_(("OPEN", "IN_PROGRESS")),
            )
            .order_by(Asset.hostname)
        )
    ).all()

    # 2. D-06 adopt: exclude vuln_ids already linked to ANY unresolved
    # Ticket row, per-vulnerability -- NOT the group-level created_by_rule
    # check `create_remediation_ticket` uses (that check is what Pitfall 1
    # warns is too coarse for a per-owner carve-up).
    vuln_ids = [v.id for v, _hostname, _mdm in rows]
    already_ticketed: set[uuid.UUID] = set()
    if vuln_ids:
        already_ticketed = set(
            (
                await db.execute(
                    select(Ticket.vulnerability_id).where(
                        Ticket.tenant_id == tenant_id,
                        Ticket.vulnerability_id.in_(vuln_ids),
                        Ticket.resolved_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
    unticketed = [(v, hostname, mdm) for v, hostname, mdm in rows if v.id not in already_ticketed]
    adopted_count = len(vuln_ids) - len(unticketed)

    # 3. Carve by owner_email (D-05 verbatim derivation, byte-identical to
    # ticketing/service.py:614's `(mdm or {}).get("humaans_email")`; D-08
    # the None bucket is the unassigned default-project ticket -- never
    # silently dropped).
    owner_groups: dict[str | None, list[tuple[Vulnerability, str | None]]] = {}
    for vuln, hostname, mdm in unticketed:
        owner_email = (mdm or {}).get("humaans_email") or None
        owner_groups.setdefault(owner_email, []).append((vuln, hostname))

    tickets_linked = 0
    failed_owners: list[str | None] = []
    now = datetime.now(UTC)
    for owner_email, members in owner_groups.items():
        notes = _build_owner_ticket_description(members)
        max_sev = max((m[0].severity for m in members), key=lambda s: _SEV_RANK.get(s, 0))
        if due_days:
            due_on = (now + timedelta(days=due_days)).strftime("%Y-%m-%d")
        else:
            due_on = (now + timedelta(days=SEVERITY_SLA_DAYS.get(max_sev, 30))).strftime("%Y-%m-%d")
        task_name = f"[{max_sev}] {campaign.remediation_id[:60]} — {owner_email or 'Unassigned'} ({len(members)} hosts)"

        url = await client.create(task_name, notes, **_provider_create_kwargs(provider, owner_email, due_on))
        if url is None:
            failed_owners.append(owner_email)
            continue

        ref = _extract_ref(url)
        for vuln, _hostname in members:
            db.add(
                Ticket(
                    tenant_id=tenant_id,
                    vulnerability_id=vuln.id,
                    provider=provider,
                    external_ticket_id=f"{ref}:{vuln.id}",
                    external_ticket_url=url,
                    external_status="open",
                    project_key=project_key,
                    assignee=owner_email,
                    created_by_user_id=user_id,
                    # D-20 / Pitfall 1: bare remediation_id (NEVER a
                    # "campaign:{id}"-prefixed string) so
                    # create_remediation_ticket's own pre-existing
                    # group-level dedup check (Ticket.created_by_rule ==
                    # remediation_id) sees these rows if a per_remediation
                    # automation rule later fires on this remediation_id.
                    created_by_rule=campaign.remediation_id,
                    detected_at=vuln.first_detected_at,
                    ticket_created_at=now,
                )
            )
            vuln.status = "IN_PROGRESS"
            tickets_linked += 1
        await db.flush()
        await recompute_ticket_sla(db, url, tenant_id)

    return {
        "created_tickets": len(owner_groups) - len(failed_owners),
        "tickets_linked": tickets_linked,
        "adopted": adopted_count,
        "owners": len(owner_groups),
        "failed_owners": failed_owners,
    }
