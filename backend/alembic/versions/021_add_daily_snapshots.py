"""021 - Add daily_snapshots table for trend analytics.

Revision ID: 021_daily_snapshots
Revises: 020_sla_tracking
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "021_daily_snapshots"
down_revision = "020_sla_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metrics", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "snapshot_date", name="uq_snapshot_tenant_date"),
    )
    op.create_index("ix_snapshot_tenant_date", "daily_snapshots", ["tenant_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_index("ix_snapshot_tenant_date", table_name="daily_snapshots")
    op.drop_table("daily_snapshots")
