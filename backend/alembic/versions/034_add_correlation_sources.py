"""Replace hardcoded 4-source FK columns on vulnerability_correlations with a
generalized sources ARRAY(String) + GIN index, plus a source_vuln_ids JSONB
linkage map covering all 6 VulnSource values (Phase 30, CORR-01/02/03).

Mirrors 025_add_asset_tags.py's ARRAY(String)+GIN pattern (D-01). Backfills
both new columns from the 4 legacy FK columns as a same-migration UPDATE —
this is a BASELINE only, not the final data-recovery step: rows correlated
via sources never captured by the 4-column map (any QUALYS/RAPID7-only
correlation) backfill to sources=[] because those links were never held in
the old FK columns to backfill FROM (D-06 step 2). The actual data recovery
-- re-running run_correlations() per tenant so those rows get their true
source set -- is a SEPARATE, idempotent, re-runnable step
(backend/scripts/recorrelate_all_tenants.py), deliberately NOT run inside
this migration transaction (D-07: not a blocking Alembic data migration
over a large table). Run that script once, manually, immediately after
this migration, BEFORE verifying SC#2's zero-loss requirement -- verifying
in between produces a false "data loss" signal (see 30-RESEARCH.md Pitfall 5).

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32)
(empirically confirmed once already -- see 031_rename_audit_tenant_idx.py's
docstring for the StringDataRightTruncationError it hit).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "034_add_correlation_sources"
down_revision = "033_add_ai_batch_job"


def upgrade() -> None:
    op.add_column("vulnerability_correlations", sa.Column("sources", ARRAY(sa.String()), nullable=True))
    op.create_index(
        "ix_vulnerability_correlations_sources",
        "vulnerability_correlations",
        ["sources"],
        postgresql_using="gin",
    )
    op.add_column("vulnerability_correlations", sa.Column("source_vuln_ids", postgresql.JSONB, nullable=True))

    # Baseline backfill (D-06 step 2). Canonical VulnSource declaration order:
    # CROWDSTRIKE, NESSUS, DEFENDER, WIZ (the only 4 sources the old columns held).
    # VERIFIED via direct execution: ARRAY_REMOVE(..., NULL) on an all-NULL CASE
    # list correctly produces '{}' (empty array), never NULL.
    op.execute(
        """
        UPDATE vulnerability_correlations
        SET sources = ARRAY_REMOVE(ARRAY[
            CASE WHEN crowdstrike_vuln_id IS NOT NULL THEN 'CROWDSTRIKE' END,
            CASE WHEN nessus_vuln_id     IS NOT NULL THEN 'NESSUS'      END,
            CASE WHEN defender_vuln_id   IS NOT NULL THEN 'DEFENDER'    END,
            CASE WHEN wiz_vuln_id        IS NOT NULL THEN 'WIZ'         END
        ], NULL)
        """
    )
    op.execute(
        """
        UPDATE vulnerability_correlations
        SET source_vuln_ids = jsonb_strip_nulls(jsonb_build_object(
            'CROWDSTRIKE', crowdstrike_vuln_id,
            'NESSUS', nessus_vuln_id,
            'DEFENDER', defender_vuln_id,
            'WIZ', wiz_vuln_id
        ))
        """
    )

    # Dropping these auto-drops their inline FK constraints -- verified directly,
    # no explicit DROP CONSTRAINT or CASCADE needed (Postgres core behavior).
    op.drop_column("vulnerability_correlations", "crowdstrike_vuln_id")
    op.drop_column("vulnerability_correlations", "nessus_vuln_id")
    op.drop_column("vulnerability_correlations", "defender_vuln_id")
    op.drop_column("vulnerability_correlations", "wiz_vuln_id")


def downgrade() -> None:
    # Schema-symmetric but lossy: any QUALYS/RAPID7 (or a future 7th source)
    # linkage that exists only in sources/source_vuln_ids has no column to
    # return to and is NOT recovered by this downgrade (D-01: one-way).
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "crowdstrike_vuln_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "nessus_vuln_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "defender_vuln_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "vulnerability_correlations",
        sa.Column(
            "wiz_vuln_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerabilities.id", ondelete="SET NULL"),
        ),
    )
    op.drop_column("vulnerability_correlations", "source_vuln_ids")
    op.drop_index("ix_vulnerability_correlations_sources", table_name="vulnerability_correlations")
    op.drop_column("vulnerability_correlations", "sources")
