"""019 - Add is_ignored and ignored_at to assets.

Revision ID: 019_asset_ignored
Revises: 018_smtp_config
"""

import sqlalchemy as sa

from alembic import op

revision = "019_asset_ignored"
down_revision = "018_smtp_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("is_ignored", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assets", sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assets", sa.Column("ignored_reason", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "ignored_reason")
    op.drop_column("assets", "ignored_at")
    op.drop_column("assets", "is_ignored")
