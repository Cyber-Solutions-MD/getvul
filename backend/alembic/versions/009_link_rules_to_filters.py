"""009 - Add saved_filter_id to ticket_rules.

Revision ID: 009_link_rules_filters
Revises: 008_add_saved_filters
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "009_link_rules_filters"
down_revision = "008_add_saved_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_rules", sa.Column("saved_filter_id", postgresql.UUID(as_uuid=True)))


def downgrade() -> None:
    op.drop_column("ticket_rules", "saved_filter_id")
