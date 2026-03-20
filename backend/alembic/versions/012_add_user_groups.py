"""012 - Add groups support to users.

Revision ID: 012_add_user_groups
Revises: 011_add_password_auth
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012_add_user_groups"
down_revision = "011_add_password_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User groups (JSONB array of group names/IDs)
    op.add_column("users", sa.Column("groups", postgresql.JSONB, server_default="[]"))
    op.add_column("users", sa.Column("department", sa.String(200)))
    op.add_column("users", sa.Column("job_title", sa.String(200)))
    op.add_column("users", sa.Column("idp_source", sa.String(30)))  # google, azure, humaans, local


def downgrade() -> None:
    op.drop_column("users", "idp_source")
    op.drop_column("users", "job_title")
    op.drop_column("users", "department")
    op.drop_column("users", "groups")
