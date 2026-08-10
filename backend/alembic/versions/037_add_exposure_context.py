"""Add asset exposure-context columns (business_criticality, data_sensitivity,
internet_facing) plus their *_source discriminators.

Phase 32 Plan 01 (LEAD TRACER) — EXPO-01/02/03. Mirrors the risk_score /
device_category materialized-column precedent (models.py) rather than a
native Postgres ENUM (no native enum type exists anywhere in this codebase).
Every column carries a `server_default` (not just a Python-side `default`)
so existing rows backfill without a data migration, matching
`is_ignored`'s `server_default="false"` shape (models.py). No index —
these are scalar String/Boolean columns, not arrays (contrast with the GIN
index on `tags`, 025_add_asset_tags.py).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
"037_add_exposure_context" is 25 chars — safe.
"""

import sqlalchemy as sa

from alembic import op

revision = "037_add_exposure_context"
down_revision = "036_add_enrichment_ref_tables"


def upgrade() -> None:
    op.add_column("assets", sa.Column("business_criticality", sa.String(20), server_default="MEDIUM", nullable=False))
    op.add_column(
        "assets", sa.Column("business_criticality_source", sa.String(20), server_default="AUTO", nullable=False)
    )
    op.add_column("assets", sa.Column("data_sensitivity", sa.String(20), server_default="INTERNAL", nullable=False))
    op.add_column("assets", sa.Column("data_sensitivity_source", sa.String(20), server_default="AUTO", nullable=False))
    op.add_column("assets", sa.Column("internet_facing", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assets", sa.Column("internet_facing_source", sa.String(20), server_default="AUTO", nullable=False))


def downgrade() -> None:
    op.drop_column("assets", "internet_facing_source")
    op.drop_column("assets", "internet_facing")
    op.drop_column("assets", "data_sensitivity_source")
    op.drop_column("assets", "data_sensitivity")
    op.drop_column("assets", "business_criticality_source")
    op.drop_column("assets", "business_criticality")
