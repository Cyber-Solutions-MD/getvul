"""Add EPSS percentile + native priority + source_signals columns to vulnerabilities.

Phase 31 Plan 01 (ENRICH-01/02/03/04, D-03/D-05). `epss_score` already exists
(models.py:56, Numeric(5,4)) -- this migration adds its missing percentile
sibling plus a generic native_priority_score/native_priority_rating pair
(D-05: raw vendor value, no cross-scale normalization -- that's Phase 33) and
a source_signals JSONB (D-07/D-08: sparse allowlist, mirrors Asset.mdm_details
at assets/models.py:67).

Plain btree indexes on native_priority_score/epss_score support future sort
(RISK-02 intent, Claude's Discretion) -- no index on source_signals, mirroring
034_add_correlation_sources.py's un-indexed source_vuln_ids JSONB precedent
(queried via containment only when actually needed, not preemptively).

epss_percentile is deliberately Numeric(5,4) -- matching the existing
epss_score column's precision -- even though the live FIRST.org feed
publishes 5 decimals (31-RESEARCH.md External Feeds section). Accepting a
<=0.00005 rounding on write keeps both EPSS columns symmetric; widening
epss_score itself is out of this migration's additive scope.

Revision id kept <= 32 chars: alembic_version.version_num is varchar(32)
(empirically confirmed once already -- see 031_rename_audit_tenant_idx.py's
docstring for the StringDataRightTruncationError it hit).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "035_add_enrichment_columns"
down_revision = "034_add_correlation_sources"


def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("epss_percentile", sa.Numeric(5, 4), nullable=True))
    op.add_column("vulnerabilities", sa.Column("native_priority_score", sa.Numeric(7, 2), nullable=True))
    op.add_column("vulnerabilities", sa.Column("native_priority_rating", sa.String(50), nullable=True))
    op.add_column("vulnerabilities", sa.Column("source_signals", postgresql.JSONB, nullable=True))

    op.create_index("ix_vulnerabilities_native_priority_score", "vulnerabilities", ["native_priority_score"])
    op.create_index("ix_vulnerabilities_epss_score", "vulnerabilities", ["epss_score"])


def downgrade() -> None:
    op.drop_index("ix_vulnerabilities_epss_score", table_name="vulnerabilities")
    op.drop_index("ix_vulnerabilities_native_priority_score", table_name="vulnerabilities")

    op.drop_column("vulnerabilities", "source_signals")
    op.drop_column("vulnerabilities", "native_priority_rating")
    op.drop_column("vulnerabilities", "native_priority_score")
    op.drop_column("vulnerabilities", "epss_percentile")
