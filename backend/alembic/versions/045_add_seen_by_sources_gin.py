"""Add GIN index on assets.seen_by_sources (Phase 35 Plan 03 — SRC-08/T-35-09).

`seen_by_sources` (JSONB list of scanner/enrichment source strings) has
never had an index, despite `.contains([s])` being the query shape used by
both the assets list filter (`assets/router.py::list_assets`) and the
ticket rule engine (`ticketing/rule_engine.py::find_matching_assets`).
Phase 35 increases the frequency of `.contains()` filtering on this column
(OR-default across N selected scanners, plus the AND toggle and the
enrichment_source facet), so it needs to be index-scannable.

Mirrors `034_add_correlation_sources.py`'s GIN index shape
(`ix_vulnerability_correlations_sources`) — same `postgresql_using="gin"`
convention, purely additive, no row work, symmetric downgrade.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"045_add_seen_by_sources_gin" is 27 chars — safe.
"""

from alembic import op

revision = "045_add_seen_by_sources_gin"
down_revision = "044_add_risk_backfill_job"


def upgrade() -> None:
    op.create_index(
        "ix_assets_seen_by_sources",
        "assets",
        ["seen_by_sources"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_assets_seen_by_sources", table_name="assets")
