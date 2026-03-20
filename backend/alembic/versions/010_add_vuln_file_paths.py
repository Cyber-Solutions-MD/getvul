"""010 - Add file_paths to vulnerabilities.

Revision ID: 010_add_file_paths
Revises: 009_link_rules_filters
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010_add_file_paths"
down_revision = "009_link_rules_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vulnerabilities", sa.Column("file_paths", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("vulnerabilities", "file_paths")
