"""020 - Add SLA tracking fields.

Revision ID: 020_sla_tracking
Revises: 019_asset_ignored
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "020_sla_tracking"
down_revision = "019_asset_ignored"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SLA fields on vulnerabilities
    op.add_column("vulnerabilities", sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vulnerabilities", sa.Column("sla_breached", sa.Boolean(), server_default="false", nullable=False))

    # SLA config on tenant
    op.add_column("tenants", sa.Column("sla_config", postgresql.JSONB, nullable=True))

    # Index for SLA queries
    op.create_index(
        "ix_vuln_sla_due_at",
        "vulnerabilities",
        ["sla_due_at"],
        postgresql_where=sa.text("status IN ('OPEN', 'IN_PROGRESS')"),
    )


def downgrade() -> None:
    op.drop_index("ix_vuln_sla_due_at", table_name="vulnerabilities")
    op.drop_column("tenants", "sla_config")
    op.drop_column("vulnerabilities", "sla_breached")
    op.drop_column("vulnerabilities", "sla_due_at")
