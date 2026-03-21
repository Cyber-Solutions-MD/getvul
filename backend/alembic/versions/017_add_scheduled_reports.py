"""017 - Add scheduled_reports table.

Revision ID: 017_scheduled_reports
Revises: 016_add_password_policy
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017_scheduled_reports"
down_revision = "016_add_password_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true"),
        sa.Column("schedule", sa.String(20), nullable=False),  # daily, weekly, monthly
        sa.Column("format", sa.String(10), server_default="pdf"),  # pdf, csv, txt
        sa.Column("recipients", postgresql.JSONB, nullable=False),  # ["email@example.com"]
        sa.Column("sections", postgresql.JSONB, server_default='["vulns","assets","risk","top_hosts","top_remediations","tickets"]'),
        sa.Column("filters", postgresql.JSONB, server_default='{}'),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_send_status", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("scheduled_reports")
