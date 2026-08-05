"""Add global epss_scores + cisa_kev reference tables.

Phase 31 Plan 01 (ENRICH-01/02/05, D-11). D-11 SIGNED-OFF EXCEPTION: unlike
every other table in this codebase (which composes Base + UUIDPrimaryKeyMixin
+ TimestampMixin with a tenant_id column/FK -- see app/db/base.py), these two
tables are DELIBERATELY global with NO tenant_id and NO surrogate UUID id
column. `cve_id` IS the primary key directly -- these are CVE-level facts
(published EPSS scores, the CISA KEV catalog), not tenant-owned data, and
every tenant's findings read the SAME row for a given CVE
(sync.py::_lookup_enrichment).

Refreshed wholesale (TRUNCATE + bulk insert) by the daily scheduler job
landed in a later plan (ENRICH-05) -- this migration only creates the empty
shape; Plan 01 populates rows only via test fixtures.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32).
VERIFIED this session: the more descriptive "036_add_enrichment_reference_tables"
is 35 chars -- OVER the limit and would reproduce the exact
StringDataRightTruncationError 031_rename_audit_tenant_idx.py already hit
once. "036_add_enrichment_ref_tables" (29 chars) is the safe shortened form.
"""

import sqlalchemy as sa

from alembic import op

revision = "036_add_enrichment_ref_tables"
down_revision = "035_add_enrichment_columns"


def upgrade() -> None:
    op.create_table(
        "epss_scores",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("epss_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("percentile", sa.Numeric(6, 5), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("score_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "cisa_kev",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("date_added", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vendor_project", sa.String(50), nullable=True),
        sa.Column("product", sa.String(200), nullable=True),
        sa.Column("vulnerability_name", sa.String(200), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("known_ransomware_campaign_use", sa.String(10), nullable=True),
        sa.Column("catalog_version", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("cisa_kev")
    op.drop_table("epss_scores")
