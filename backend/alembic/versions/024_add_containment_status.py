"""Add containment_status to assets."""

import sqlalchemy as sa

from alembic import op

revision = "024_add_containment_status"
down_revision = "023_add_branding"


def upgrade() -> None:
    op.add_column("assets", sa.Column("containment_status", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "containment_status")
