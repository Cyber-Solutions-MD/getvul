"""018 - Add smtp_config JSONB column to tenants.

Revision ID: 018_smtp_config
Revises: 017_scheduled_reports
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "018_smtp_config"
down_revision = "017_scheduled_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("smtp_config", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "smtp_config")
