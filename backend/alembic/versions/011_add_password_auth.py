"""011 - Add password authentication and SSO enforcement.

Adds password_hash and allow_password_login to users.
Adds sso_enforced to tenants.

Revision ID: 011_add_password_auth
Revises: 010_add_file_paths
"""

import sqlalchemy as sa

from alembic import op

revision = "011_add_password_auth"
down_revision = "010_add_file_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users: password auth fields
    op.add_column("users", sa.Column("password_hash", sa.String(255)))
    op.add_column("users", sa.Column("allow_password_login", sa.Boolean(), server_default="true"))

    # Tenants: SSO enforcement
    op.add_column("tenants", sa.Column("sso_enforced", sa.Boolean(), server_default="false"))


def downgrade() -> None:
    op.drop_column("tenants", "sso_enforced")
    op.drop_column("users", "allow_password_login")
    op.drop_column("users", "password_hash")
