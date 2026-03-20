"""014 - Add syslog_config to tenants.

Revision ID: 014_add_syslog_config
Revises: 013_add_audit_log
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014_add_syslog_config"
down_revision = "013_add_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("syslog_config", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("tenants", "syslog_config")
