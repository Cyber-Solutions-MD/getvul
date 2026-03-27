"""Add branding JSONB to tenants."""

revision = "023_add_branding"
down_revision = "022_add_notifications"

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op


def upgrade() -> None:
    op.add_column("tenants", sa.Column("branding", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "branding")
