"""Correlation engine — links same CVE across multiple scanner sources."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.vulnerabilities.models import Vulnerability, VulnerabilityCorrelation

logger = structlog.get_logger()

# Source column mapping on VulnerabilityCorrelation
SOURCE_COLUMN_MAP = {
    "CROWDSTRIKE": "crowdstrike_vuln_id",
    "NESSUS": "nessus_vuln_id",
    "DEFENDER": "defender_vuln_id",
    "WIZ": "wiz_vuln_id",
}


async def run_correlations(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """
    Rebuild correlation records for a tenant.

    Finds all (cve_id, asset_id) pairs that have vulnerabilities from
    multiple sources and upserts VulnerabilityCorrelation records.

    Returns stats dict with counts.
    """
    # Step 1: Find all (cve_id, asset_id) groups with their per-source vuln IDs.
    # We pick the most recent vuln per (cve, asset, source) to link.
    groups = await _find_correlated_groups(db, tenant_id)

    created = 0

    for key, source_vulns in groups.items():
        cve_id, asset_id = key
        sources_count = len(source_vulns)

        if sources_count >= 3:
            confidence = "HIGH"
        elif sources_count == 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Build the source vuln ID columns
        values = {
            "tenant_id": tenant_id,
            "cve_id": cve_id,
            "asset_id": asset_id,
            "sources_count": sources_count,
            "confidence": confidence,
            "crowdstrike_vuln_id": source_vulns.get("CROWDSTRIKE"),
            "nessus_vuln_id": source_vulns.get("NESSUS"),
            "defender_vuln_id": source_vulns.get("DEFENDER"),
            "wiz_vuln_id": source_vulns.get("WIZ"),
        }

        # Upsert on (tenant_id, cve_id, asset_id)
        stmt = pg_insert(VulnerabilityCorrelation).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_correlation",
            set_={
                "sources_count": stmt.excluded.sources_count,
                "confidence": stmt.excluded.confidence,
                "crowdstrike_vuln_id": stmt.excluded.crowdstrike_vuln_id,
                "nessus_vuln_id": stmt.excluded.nessus_vuln_id,
                "defender_vuln_id": stmt.excluded.defender_vuln_id,
                "wiz_vuln_id": stmt.excluded.wiz_vuln_id,
            },
        )
        result = await db.execute(stmt)
        # rowcount from ON CONFLICT DO UPDATE is always 1 for upsert;
        # we track created vs updated via xmax trick not available here,
        # so just count total.
        if result.rowcount:
            created += 1

    # Step 2: Remove stale correlations where sources dropped below 2
    # (e.g., a vuln was remediated from one source)
    stale_deleted = await _prune_stale_correlations(db, tenant_id, groups)

    logger.info(
        "correlation_complete",
        tenant_id=str(tenant_id),
        correlated=created,
        stale_removed=stale_deleted,
    )

    return {
        "correlated": created,
        "stale_removed": stale_deleted,
    }


async def _find_correlated_groups(
    db: AsyncSession, tenant_id: uuid.UUID
) -> dict[tuple[str, uuid.UUID], dict[str, uuid.UUID]]:
    """
    Find (cve_id, asset_id) groups that have open vulns from 2+ sources.

    Returns a dict mapping (cve_id, asset_id) -> {source: vuln_id}.
    """
    # Query: for each (cve_id, asset_id, source), pick the vuln id
    # Only consider vulns that have a CVE and an asset
    query = (
        select(
            Vulnerability.cve_id,
            Vulnerability.asset_id,
            Vulnerability.source,
            Vulnerability.id,
        )
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.cve_id.isnot(None),
            Vulnerability.asset_id.isnot(None),
            Vulnerability.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .order_by(Vulnerability.last_seen_at.desc())
    )

    rows = (await db.execute(query)).all()

    # Group by (cve_id, asset_id) -> {source: vuln_id}
    # Use first seen per source (already ordered by last_seen desc)
    groups: dict[tuple[str, uuid.UUID], dict[str, uuid.UUID]] = {}
    for cve_id, asset_id, source, vuln_id in rows:
        key = (cve_id, asset_id)
        if key not in groups:
            groups[key] = {}
        # Only keep the first (most recent) vuln per source
        if source not in groups[key]:
            groups[key][source] = vuln_id

    # Filter to only groups with 2+ sources
    return {k: v for k, v in groups.items() if len(v) >= 2}


async def _prune_stale_correlations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    active_groups: dict[tuple[str, uuid.UUID], dict[str, uuid.UUID]],
) -> int:
    """Remove correlations that no longer have 2+ active sources."""
    # Get all existing correlations for this tenant
    existing = (
        await db.execute(
            select(VulnerabilityCorrelation.id, VulnerabilityCorrelation.cve_id, VulnerabilityCorrelation.asset_id)
            .where(VulnerabilityCorrelation.tenant_id == tenant_id)
        )
    ).all()

    stale_ids = []
    for corr_id, cve_id, asset_id in existing:
        if (cve_id, asset_id) not in active_groups:
            stale_ids.append(corr_id)

    if stale_ids:
        await db.execute(
            delete(VulnerabilityCorrelation).where(VulnerabilityCorrelation.id.in_(stale_ids))
        )

    return len(stale_ids)


async def get_correlation_for_vuln(
    db: AsyncSession, tenant_id: uuid.UUID, cve_id: str, asset_id: uuid.UUID
) -> dict | None:
    """Get correlation details for a specific CVE + asset pair."""
    result = await db.execute(
        select(VulnerabilityCorrelation).where(
            VulnerabilityCorrelation.tenant_id == tenant_id,
            VulnerabilityCorrelation.cve_id == cve_id,
            VulnerabilityCorrelation.asset_id == asset_id,
        )
    )
    corr = result.scalar_one_or_none()
    if corr is None:
        return None

    sources = []
    if corr.crowdstrike_vuln_id:
        sources.append("CROWDSTRIKE")
    if corr.nessus_vuln_id:
        sources.append("NESSUS")
    if corr.defender_vuln_id:
        sources.append("DEFENDER")
    if corr.wiz_vuln_id:
        sources.append("WIZ")

    return {
        "id": corr.id,
        "cve_id": corr.cve_id,
        "asset_id": corr.asset_id,
        "sources": sources,
        "sources_count": corr.sources_count,
        "confidence": corr.confidence,
        "crowdstrike_vuln_id": corr.crowdstrike_vuln_id,
        "nessus_vuln_id": corr.nessus_vuln_id,
        "defender_vuln_id": corr.defender_vuln_id,
        "wiz_vuln_id": corr.wiz_vuln_id,
    }
