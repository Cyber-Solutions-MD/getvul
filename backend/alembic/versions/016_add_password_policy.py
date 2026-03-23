"""016 - Add password_policy to tenants.

Revision ID: 016_add_password_policy
Revises: 015_add_timezone
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "016_add_password_policy"
down_revision = "015_add_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("password_policy", postgresql.JSONB,
        server_default='{"min_length": 8, "require_uppercase": false, "require_lowercase": false, "require_digit": false, "require_symbol": false, "history_count": 0}'))
    op.add_column("users", sa.Column("password_history", postgresql.JSONB, server_default="[]"))


def downgrade() -> None:
    op.drop_column("users", "password_history")
    op.drop_column("tenants", "password_policy")
