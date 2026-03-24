"""022 - Add notifications table for in-app and email alerts.

Revision ID: 022_add_notifications
Revises: 021_daily_snapshots
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "022_add_notifications"
down_revision = "021_daily_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(200), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Composite indexes for common query patterns
    op.create_index("ix_notifications_tenant_user_read", "notifications", ["tenant_id", "user_id", "is_read"])
    op.create_index("ix_notifications_tenant_category", "notifications", ["tenant_id", "category"])
    op.create_index("ix_notifications_tenant_created", "notifications", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_tenant_created", table_name="notifications")
    op.drop_index("ix_notifications_tenant_category", table_name="notifications")
    op.drop_index("ix_notifications_tenant_user_read", table_name="notifications")
    op.drop_table("notifications")
