"""015 - Add timezone to tenants.

Revision ID: 015_add_timezone
Revises: 014_add_syslog_config
"""

from alembic import op
import sqlalchemy as sa

revision = "015_add_timezone"
down_revision = "014_add_syslog_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("timezone", sa.String(50), server_default="UTC"))


def downgrade() -> None:
    op.drop_column("tenants", "timezone")
